#!/usr/bin/env python3
"""
spotify_genre_playlister.py (enhanced)
--------------------------------------
Adds deeper fill for empty genres:
1) Use all track artists (not just primary)
2) Spotify search by artist name (fallback)
3) Spotify related artists (optional inference)
4) MusicBrainz tags (optional fallback)

New flags:
  --use-all-artists
  --infer-related
  --use-musicbrainz
  --mb-delay 1.1

Other behavior matches previous version.
"""

import argparse
import os
import sys
import time
import csv
import re
import json
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

import requests
from dotenv import load_dotenv

import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

DEFAULT_BUCKET_RULES = [
    ("pop-punk", ["pop punk", "pop-punk"]),
    ("punk", ["punk", "skate punk", "hardcore punk"]),
    ("emo", ["emo", "emo-pop", "emo rap"]),
    ("ska", ["ska", "2 tone", "two-tone", "third wave ska", "ska punk"]),
    ("alternative rock", ["alternative rock", "alt rock", "alt-rock", "modern rock"]),
    ("indie-rock", ["indie rock", "indie-rock"]),
    ("indie-pop", ["indie pop", "indie-pop"]),
    ("metal", ["metal", "metalcore", "deathcore", "death metal", "nu metal", "thrash metal", "black metal", "prog metal"]),
    ("hard rock", ["hard rock", "arena rock"]),
    ("rock", ["rock", "classic rock", "soft rock", "glam rock", "roots rock"]),
    ("electronic", ["electronic", "edm", "house", "techno", "trance", "dubstep", "electro", "synthwave", "synthpop"]),
    ("hip-hop", ["hip hop", "hip-hop", "rap"]),
    ("rnb", ["r&b", "rnb", "neo soul"]),
    ("country", ["country", "alt-country"]),
    ("folk", ["folk", "americana", "singer-songwriter"]),
    ("reggae", ["reggae", "ska reggae", "dub reggae", "dancehall"]),
    ("latin", ["latin", "reggaeton", "banda", "mariachi", "salsa", "cumbia", "bachata"]),
    ("jazz", ["jazz", "smooth jazz", "bebop", "fusion"]),
    ("blues", ["blues"]),
    ("christian", ["christian", "worship", "ccm"]),
    ("soundtrack", ["soundtrack", "score", "ost"]),
    ("classical", ["classical", "baroque", "romantic era", "orchestral", "piano"]),
    ("comedy", ["comedy"]),
]

GENERIC_TAGS = set([
    "seen live","favorite","favorites","best","awesome","good","great",
    "all","american","british","canadian","uk","usa","united states"
])

def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[/_]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_genre(g: str) -> str:
    g = norm(g)
    replacements = {
        "hip hop": "hip-hop",
        "r&b": "rnb",
        "alt rock": "alternative rock",
        "alt-rock": "alternative rock",
        "synth pop": "synthpop",
        "indie pop": "indie-pop",
        "indie rock": "indie-rock",
        "electro pop": "electropop",
        "drum and bass": "drum & bass",
        "dnb": "drum & bass",
        "edm": "electronic",
        "emo pop": "emo-pop",
        "pop punk": "pop-punk",
    }
    return replacements.get(g, g)

def bucketize(genres: List[str], rules=DEFAULT_BUCKET_RULES, default="other") -> str:
    gset = [normalize_genre(g) for g in genres if g and norm(g) not in GENERIC_TAGS]
    for bucket, needles in rules:
        for g in gset:
            for needle in needles:
                if needle in g:
                    return bucket
    if gset:
        return gset[0]
    return default

def split_artists(artists) -> List[Tuple[str, str]]:
    out = []
    for a in artists or []:
        if a and a.get("id"):
            out.append( (a["id"], a.get("name","")) )
    return out

def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

def get_artist_genres_by_id(sp: spotipy.Spotify, artist_id: str) -> List[str]:
    try:
        a = sp.artist(artist_id)
        return [normalize_genre(g) for g in a.get("genres", [])]
    except Exception:
        return []

def search_artist_genres_by_name(sp: spotipy.Spotify, name: str) -> List[str]:
    try:
        res = sp.search(q=f"artist:{name}", type="artist", limit=1)
        items = res.get("artists", {}).get("items", [])
        if not items:
            return []
        return [normalize_genre(g) for g in items[0].get("genres", [])]
    except Exception:
        return []

def infer_from_related(sp: spotipy.Spotify, artist_id: str) -> List[str]:
    try:
        rel = sp.artist_related_artists(artist_id).get("artists", [])
        genres = []
        for a in rel[:10]:
            genres.extend(a.get("genres", []))
        genres = [normalize_genre(g) for g in genres]
        common = [g for g, _ in Counter(genres).most_common(3)]
        return common
    except Exception:
        return []

MB_HEADERS = {"User-Agent": "GenreFiller/2.0 ( https://example.com )"}

def mb_search_artist(name: str) -> Optional[str]:
    try:
        url = "https://musicbrainz.org/ws/2/artist/"
        params = {"query": name, "fmt": "json"}
        r = requests.get(url, params=params, headers=MB_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        artists = data.get("artists", [])
        if not artists:
            return None
        artists.sort(key=lambda a: a.get("score", 0), reverse=True)
        return artists[0].get("id")
    except Exception:
        return None

def mb_artist_genres(mbid: str) -> List[str]:
    try:
        url = f"https://musicbrainz.org/ws/2/artist/{mbid}"
        params = {"inc": "tags", "fmt": "json"}
        r = requests.get(url, params=params, headers=MB_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        tags = data.get("tags", []) or []
        names = [t.get("name","") for t in tags if isinstance(t, dict)]
        names = [normalize_genre(n) for n in names if n and n.lower() not in GENERIC_TAGS]
        return names
    except Exception:
        return []

def load_cache(path: str) -> Dict[str, List[str]]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache: Dict[str, List[str]], path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--liked", action="store_true", help="Use your Liked Songs as the source")
    ap.add_argument("--playlist", help="Playlist URL/URI/ID to process instead of Liked Songs")
    ap.add_argument("--max", type=int, default=0, help="Process at most N tracks (0 = all)")
    ap.add_argument("--prefix", default="Genres – ", help="Playlist name prefix for created/updated genre playlists")
    ap.add_argument("--owner", default="", help="Optional user ID to own the new playlists (defaults to your account)")
    ap.add_argument("--public", action="store_true", help="Create genre playlists as public (default private)")
    ap.add_argument("--clear", action="store_true", help="Clear genre playlists before adding new tracks")
    ap.add_argument("--dry-run", action="store_true", help="Do not create/update playlists, only print and export CSV")
    ap.add_argument("--csv", default="genre_assignments.csv", help="CSV path to export report")
    ap.add_argument("--cache", default="spotify_artist_genre_cache.json", help="Cache file for artist genres")
    ap.add_argument("--use-all-artists", action="store_true", help="Use all artists on the track to collect genres")
    ap.add_argument("--infer-related", action="store_true", help="If empty, infer genres from Spotify related artists")
    ap.add_argument("--use-musicbrainz", action="store_true", help="If still empty, query MusicBrainz tags")
    ap.add_argument("--mb-delay", type=float, default=1.1, help="Delay between MusicBrainz requests (seconds)")
    args = ap.parse_args()

    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI")

    if not (client_id and client_secret and redirect_uri):
        print("ERROR: Missing SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET / SPOTIPY_REDIRECT_URI in environment.", file=sys.stderr)
        sys.exit(2)

    scope = "user-library-read playlist-read-private playlist-modify-private playlist-modify-public"
    auth = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope=scope, open_browser=True, cache_path=".spotipyoauthcache")
    sp = spotipy.Spotify(auth_manager=auth)

    me = sp.current_user()
    user_id = me["id"]
    owner_id = args.owner or user_id
    print(f"Authed as: {me.get('display_name') or user_id} ({user_id}) -> creating playlists for owner: {owner_id}")

    def paginate_saved_tracks(limit=50, max_items=0):
        offset = 0
        got = 0
        while True:
            res = sp.current_user_saved_tracks(limit=limit, offset=offset)
            items = res.get("items", [])
            if not items:
                break
            for it in items:
                yield it
                got += 1
                if max_items and got >= max_items:
                    return
            offset += len(items)

    def paginate_playlist_tracks(playlist_id: str, limit=100, max_items=0):
        offset = 0
        got = 0
        while True:
            res = sp.playlist_items(playlist_id, limit=limit, offset=offset)
            items = res.get("items", [])
            if not items:
                break
            for it in items:
                yield it
                got += 1
                if max_items and got >= max_items:
                    return
            offset += len(items)

    def extract_playlist_id(s: str) -> str:
        s = s.strip()
        if s.startswith("spotify:playlist:"):
            return s.split(":")[-1]
        if "open.spotify.com/playlist/" in s:
            return s.split("playlist/")[-1].split("?")[0]
        return s

    tracks = []
    if args.liked:
        print("Fetching Liked Songs...")
        for item in paginate_saved_tracks(max_items=args.max):
            tr = item.get("track") or {}
            if not tr or not tr.get("id"):
                continue
            tracks.append(tr)
    elif args.playlist:
        pid = extract_playlist_id(args.playlist)
        meta = sp.playlist(pid, fields="name,owner(id),id")
        print(f"Fetching playlist: {meta.get('name')} ({pid})")
        for item in paginate_playlist_tracks(pid, max_items=args.max):
            tr = item.get("track") or {}
            if not tr or not tr.get("id"):
                continue
            tracks.append(tr)
    else:
        print("ERROR: Choose one of --liked or --playlist <id/url/uri>", file=sys.stderr)
        sys.exit(2)

    print(f"Collected {len(tracks)} tracks. Getting artist genres (with fallbacks)...")

    cache = load_cache(args.cache)

    def get_by_id_or_name(aid: str, aname: str) -> List[str]:
        g = get_artist_genres_by_id(sp, aid)
        if not g:
            g = search_artist_genres_by_name(sp, aname)
        return g

    def genres_for_artists(artist_pairs: List[Tuple[str, str]]) -> List[str]:
        acc: List[str] = []
        for aid, aname in artist_pairs:
            cached = cache.get(aid)
            if cached is None:
                g = get_by_id_or_name(aid, aname)
                cache[aid] = g
            else:
                g = cached
            acc.extend(g or [])
        # dedupe preserve order
        seen = set()
        dedup = []
        for x in acc:
            if x not in seen:
                dedup.append(x)
                seen.add(x)
        return dedup

    out_rows = []
    for tr in tracks:
        tid = tr.get("id")
        tname = tr.get("name","" )
        album = (tr.get("album") or {}).get("name","" )
        artists = split_artists(tr.get("artists"))
        primary_id = artists[0][0] if artists else None

        artist_list = artists if args.use_all_artists else artists[:1]
        genres = genres_for_artists(artist_list)

        if not genres and args.infer_related and primary_id:
            relg = infer_from_related(sp, primary_id)
            genres = list(dict.fromkeys(relg))

        if not genres and args.use_musicbrainz:
            mbg = []
            for aid, aname in artist_list:
                mbid = mb_search_artist(aname)
                time.sleep(args.mb_delay)
                if mbid:
                    g = mb_artist_genres(mbid)
                    mbg.extend(g)
                    time.sleep(args.mb_delay)
            # dedupe
            seen = set()
            dedup = []
            for x in mbg:
                if x not in seen:
                    dedup.append(x)
                    seen.add(x)
            genres = dedup

        bucket = bucketize(genres)

        out_rows.append({
            "track_id": tid,
            "track_name": tname,
            "album": album,
            "artist_names": ", ".join([a[1] for a in artists]),
            "primary_artist_id": primary_id or "",
            "genres_raw": "; ".join(genres),
            "bucket": bucket
        })

    save_cache(cache, args.cache)

    by_bucket = defaultdict(list)
    for r in out_rows:
        by_bucket[r["bucket"]].append(r["track_id"])

    csv_path = args.csv
    if out_rows:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"Wrote report: {csv_path}")
    else:
        print("No rows to write.")

    if args.dry_run:
        print("Dry run: Not creating/updating playlists.")
        print("Bucket counts:")
        for b, tids in sorted(by_bucket.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"  {b}: {len(tids)}")
        return

    existing = {}
    limit = 50
    offset = 0
    while True:
        pls = sp.current_user_playlists(limit=limit, offset=offset)
        items = pls.get("items", [])
        for p in items:
            existing[p["name"]] = p
        if len(items) < limit:
            break
        offset += len(items)

    created = []
    updated = []
    def chunked(seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    for bucket, tids in by_bucket.items():
        name = f"{args.prefix}{bucket}"
        pl = existing.get(name)
        if not pl:
            pl = sp.user_playlist_create(owner_id, name, public=args.public, description="Auto-generated by spotify_genre_playlister.py")
            print(f"Created playlist: {name}")
            created.append(name)
        else:
            print(f"Using existing playlist: {name}")
        pid = pl["id"]

        if args.clear:
            current_items = []
            poff = 0
            while True:
                res = sp.playlist_items(pid, fields="items(track(id)),total,next", offset=poff, limit=100)
                its = res.get("items", [])
                if not its:
                    break
                ids = [it["track"]["id"] for it in its if it.get("track") and it["track"].get("id") ]
                current_items.extend(ids)
                if len(its) < 100:
                    break
                poff += len(its)
            for ch in chunked(current_items, 100):
                sp.playlist_remove_all_occurrences_of_items(pid, ch)
            print(f"Cleared playlist: {name}")

        existing_ids = set()
        poff = 0
        while True:
            res = sp.playlist_items(pid, fields="items(track(id)),total,next", offset=poff, limit=100)
            its = res.get("items", [])
            for it in its:
                t = it.get("track") or {}
                if t.get("id"):
                    existing_ids.add(t["id"])
            if len(its) < 100:
                break
            poff += len(its)

        to_add = [t for t in tids if t not in existing_ids]
        added = 0
        for ch in chunked(to_add, 100):
            sp.playlist_add_items(pid, ch)
            added += len(ch)

        updated.append((name, len(tids), added))

    print("Done creating/updating playlists.")
    for name, total, added in updated:
        print(f"  {name}: total bucket tracks={total}, newly added={added}")
    if created:
        print(f"Created playlists: {', '.join(created)}")


if __name__ == "__main__":
    main()
