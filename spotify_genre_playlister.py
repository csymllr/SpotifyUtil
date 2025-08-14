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
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

import requests
from dotenv import load_dotenv

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Suppress spotipy's HTTP error logging for cleaner output
logging.getLogger('spotipy').setLevel(logging.WARNING)

load_dotenv()

# Artist weighting for primary vs featured
ARTIST_WEIGHTS = {"primary": 1.0, "featured": 0.5}

# Source confidence weights
WEIGHTS_SOURCE = {
    "spotify_artist": 1.0,        # direct artist genres
    "alias": 0.9,
    "spotify_related": 0.6,
    "musicbrainz": 0.5,
    "name_signal": 0.8
}

# Cache TTL (14 days)
CACHE_TTL = 60 * 60 * 24 * 14

# Artist aliases for common "unknown" cases
ALIAS_GENRES = {
    "Macklemore": ["hip-hop", "rap"],
    "Macklemore & Ryan Lewis": ["hip-hop", "rap"],
    "The Piano Guys": ["classical", "pop"],
    "Hans Zimmer": ["soundtrack"],
    "Ramin Djawadi": ["soundtrack"],
    "Lorne Balfe": ["soundtrack"],
    "Andrea Bocelli": ["classical", "opera"],
    "Yiruma": ["classical"],
    "Imagine Dragons": ["alternative rock", "pop"],
    "Sia": ["electronic", "pop"],
    "Blackbear": ["hip-hop", "pop"],
    "Lewis Capaldi": ["pop"],
    "Huey Lewis & The News": ["rock", "pop"],
    "OK Go": ["alternative rock", "pop"],
    "Snow Patrol": ["alternative rock", "rock"],
}

# Canonical genre to bucket mapping for scored bucketing
CANON_TO_BUCKET = {
    # rock family (including all rock subgenres, punk, emo, metal, alternative, indie rock)
    "rock": "rock", "classic rock": "rock", "hard rock": "rock", "soft rock": "rock", "arena rock": "rock",
    "alternative rock": "rock", "alt rock": "rock", "alt-rock": "rock", "modern rock": "rock",
    "indie rock": "rock", "indie-rock": "rock", "garage rock": "rock", "psychedelic rock": "rock",
    "progressive rock": "rock", "prog rock": "rock", "art rock": "rock", "glam rock": "rock",
    "punk": "rock", "pop punk": "rock", "pop-punk": "rock", "skate punk": "rock", "hardcore punk": "rock",
    "post-punk": "rock", "punk rock": "rock", "street punk": "rock",
    "emo": "rock", "emo-pop": "rock", "screamo": "rock", "post-hardcore": "rock",
    "metal": "rock", "heavy metal": "rock", "metalcore": "rock", "deathcore": "rock", "death metal": "rock",
    "black metal": "rock", "thrash metal": "rock", "prog metal": "rock", "nu metal": "rock",
    "power metal": "rock", "speed metal": "rock", "doom metal": "rock", "sludge metal": "rock",
    "grunge": "rock", "post-grunge": "rock", "noise rock": "rock", "shoegaze": "rock",
    "ska punk": "rock", "folk punk": "rock", "celtic punk": "rock",
    
    # country family (all country subgenres, americana, folk)
    "country": "country", "classic country": "country", "modern country": "country", "country pop": "country",
    "alt-country": "country", "alternative country": "country", "americana": "country", "outlaw country": "country",
    "texas country": "country", "red dirt": "country", "bluegrass": "country", "honky tonk": "country",
    "country rock": "country", "southern rock": "country", "folk": "country", "indie folk": "country",
    "singer-songwriter": "country", "roots rock": "country", "cowboy": "country", "nashville sound": "country",
    
    # hip-hop family (all rap and hip-hop subgenres)
    "hip-hop": "hip-hop", "hip hop": "hip-hop", "rap": "hip-hop", "gangsta rap": "hip-hop",
    "east coast hip hop": "hip-hop", "west coast hip hop": "hip-hop", "southern hip hop": "hip-hop",
    "trap": "hip-hop", "mumble rap": "hip-hop", "conscious hip hop": "hip-hop", "alternative hip hop": "hip-hop",
    "old school hip hop": "hip-hop", "boom bap": "hip-hop", "g-funk": "hip-hop", "crunk": "hip-hop",
    "emo rap": "hip-hop", "cloud rap": "hip-hop", "drill": "hip-hop", "uk drill": "hip-hop",
    
    # classical family (classical, orchestral, opera, piano, instrumental)
    "classical": "classical", "neoclassical": "classical", "contemporary classical": "classical",
    "orchestral": "classical", "symphony": "classical", "chamber music": "classical", "opera": "classical",
    "classical piano": "classical", "piano": "classical", "solo piano": "classical", "instrumental": "classical",
    "baroque": "classical", "romantic era": "classical", "modern classical": "classical",
    "film score": "classical", "cinematic": "classical", "ambient classical": "classical",
    
    # musical family (soundtracks, broadway, show tunes, film scores)
    "soundtrack": "musical", "score": "musical", "ost": "musical", "original soundtrack": "musical",
    "musicals": "musical", "broadway": "musical", "show tunes": "musical", "theatre": "musical",
    "film soundtrack": "musical", "movie soundtrack": "musical", "tv soundtrack": "musical",
    "video game music": "musical", "anime soundtrack": "musical",
    
    # electronic family (all electronic music, EDM, dance, synth)
    "electronic": "electronic", "edm": "electronic", "dance": "electronic", "electro": "electronic",
    "house": "electronic", "deep house": "electronic", "tech house": "electronic", "progressive house": "electronic",
    "techno": "electronic", "trance": "electronic", "progressive trance": "electronic", "uplifting trance": "electronic",
    "dubstep": "electronic", "drum and bass": "electronic", "drum & bass": "electronic", "dnb": "electronic",
    "breakbeat": "electronic", "jungle": "electronic", "garage": "electronic", "uk garage": "electronic",
    "ambient": "electronic", "downtempo": "electronic", "chillout": "electronic", "trip hop": "electronic",
    "synthwave": "electronic", "synthpop": "electronic", "electropop": "electronic", "electronica": "electronic",
    "industrial": "electronic", "ebm": "electronic", "darkwave": "electronic", "new wave": "electronic",
    "disco": "electronic", "funk": "electronic", "future funk": "electronic", "vaporwave": "electronic",
    "hardstyle": "electronic", "hardcore": "electronic", "gabber": "electronic", "big beat": "electronic",
    "future bass": "electronic", "melodic bass": "electronic", "bedroom pop": "electronic", "indie-pop": "electronic",
}

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
    except Exception as e:
        # Log the error for summary but don't print immediately
        if hasattr(get_artist_genres_by_id, '_errors'):
            get_artist_genres_by_id._errors.append(f"Artist ID {artist_id}: {str(e)}")
        else:
            get_artist_genres_by_id._errors = [f"Artist ID {artist_id}: {str(e)}"]
        return []

def search_artist_genres_by_name(sp: spotipy.Spotify, name: str, market: Optional[str] = None) -> List[str]:
    """Search for artist genres by name with improved matching"""
    try:
        artist = search_artist_best(sp, name, market)
        if not artist:
            # Log for summary
            if hasattr(search_artist_genres_by_name, '_errors'):
                search_artist_genres_by_name._errors.append(f"Artist name not found: {name}")
            else:
                search_artist_genres_by_name._errors = [f"Artist name not found: {name}"]
            return []
        return [normalize_genre(g) for g in artist.get("genres", [])]
    except Exception as e:
        if hasattr(search_artist_genres_by_name, '_errors'):
            search_artist_genres_by_name._errors.append(f"Artist name search {name}: {str(e)}")
        else:
            search_artist_genres_by_name._errors = [f"Artist name search {name}: {str(e)}"]
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
    except Exception as e:
        # Log for summary
        if hasattr(infer_from_related, '_errors'):
            infer_from_related._errors.append(f"Related artists for {artist_id}: {str(e)}")
        else:
            infer_from_related._errors = [f"Related artists for {artist_id}: {str(e)}"]
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

def load_cache(path: str) -> Dict[str, dict]:
    """Load cache with TTL structure"""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache: Dict[str, dict], path: str) -> None:
    """Save cache with TTL structure"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def cache_get(cache: Dict[str, dict], aid: str) -> Optional[List[str]]:
    """Get genres from cache if not expired"""
    ent = cache.get(aid)
    if not ent:
        return None
    
    # Handle old cache format (direct list) vs new format (dict with ts)
    if isinstance(ent, list):
        # Old format - convert to new format and assume it's expired
        cache_put(cache, aid, ent)
        return None  # Force refresh for old entries
    
    if (time.time() - ent.get("ts", 0)) > CACHE_TTL:
        return None
    return ent.get("genres", [])

def cache_put(cache: Dict[str, dict], aid: str, genres: List[str]) -> None:
    """Put genres in cache with current timestamp"""
    cache[aid] = {"genres": genres, "ts": time.time()}

def get_genres_for_artist_ids(sp: spotipy.Spotify, artist_ids: List[str]) -> Dict[str, List[str]]:
    """Batch fetch artist genres (50 at a time)"""
    out = {}
    for chunk in chunked(artist_ids, 50):
        try:
            res = sp.artists(chunk).get("artists", [])
            for a in res:
                out[a["id"]] = [normalize_genre(g) for g in a.get("genres", [])]
        except Exception as e:
            # retry once with small sleep
            time.sleep(0.5)
            try:
                res = sp.artists(chunk).get("artists", [])
                for a in res:
                    out[a["id"]] = [normalize_genre(g) for g in a.get("genres", [])]
            except Exception:
                for aid in chunk:
                    out.setdefault(aid, [])
    return out

def weighted_genres_for_track(sp: spotipy.Spotify, track: dict, cache: Dict[str, dict]) -> List[Tuple[str, float]]:
    """Get weighted genres for track artists"""
    artists = track.get("artists", []) or []
    if not artists:
        return []

    ids = [a.get("id") for a in artists if a.get("id")]
    
    # Get from cache or batch pull as needed
    missing = [aid for aid in ids if aid and cache_get(cache, aid) is None]
    if missing:
        batch_results = get_genres_for_artist_ids(sp, missing)
        for aid, genres in batch_results.items():
            cache_put(cache, aid, genres)

    scores = Counter()
    for i, a in enumerate(artists):
        aid = a.get("id")
        if not aid:
            continue
        role = "primary" if (i == 0) else "featured"
        w = ARTIST_WEIGHTS[role]
        genres = cache_get(cache, aid) or []
        for g in genres:
            scores[g] += w

    # return [(genre, score)...] sorted
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))

def genres_from_alias(artist_name: str) -> List[str]:
    """Get genres from alias table"""
    return [normalize_genre(g) for g in ALIAS_GENRES.get(artist_name, [])]

def name_signal_genres(artist_name: str) -> List[str]:
    """Get genres from name signals (fast rules)"""
    a = artist_name.lower()
    if any(tok in a for tok in ["original broadway cast", "cast company", "broadway"]):
        return ["musicals"]
    if any(tok in a for tok in ["orchestra", "symphony", "philharmonic"]) or \
       re.search(r"\b(debussy|rachmaninov|mozart|beethoven|vivaldi|bocelli|einaudi|yiruma)\b", a):
        return ["classical"]
    return []

def add_weighted(scores: Counter, genres: List[str], weight: float) -> None:
    """Add weighted genres to counter"""
    for g in genres:
        scores[normalize_genre(g)] += weight

def search_artist_best(sp: spotipy.Spotify, name: str, market: Optional[str] = None) -> Optional[dict]:
    """Search for best artist match with market preference and popularity"""
    try:
        res = sp.search(q=f'artist:"{name}"', type="artist", limit=5, market=market)
        items = res.get("artists", {}).get("items", [])
        if not items:
            return None
        items.sort(key=lambda a: a.get("popularity", 0), reverse=True)
        return items[0]
    except Exception:
        return None

def bucketize_scored(weighted_genres: List[Tuple[str, float]]) -> str:
    """Score-based bucketizer instead of first substring match"""
    bucket_scores = Counter()
    for g, s in weighted_genres:
        b = CANON_TO_BUCKET.get(g)
        if b:
            bucket_scores[b] += s
    
    if not bucket_scores:
        return "other"
    
    # deterministic tie-break with your 6 preferred buckets first
    order = ["rock", "country", "hip-hop", "classical", "musical", "electronic", "other"]
    top = sorted(bucket_scores.items(), key=lambda kv: (-kv[1], order.index(kv[0]) if kv[0] in order else 999))[0][0]
    return top

def paginate_saved_tracks(sp, limit=50, max_items=0):
    """Paginate through saved tracks"""
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

def get_artist_albums(sp, artist_id: str) -> List[dict]:
    """Get all albums for an artist"""
    try:
        albums = []
        results = sp.artist_albums(artist_id, album_type='album,single', limit=50)
        albums.extend(results['items'])
        
        while results['next']:
            results = sp.next(results)
            albums.extend(results['items'])
        
        # Remove duplicates (sometimes albums appear multiple times)
        seen = set()
        unique_albums = []
        for album in albums:
            key = (album['name'].lower(), album['release_date'][:4] if album['release_date'] else '')  # Name + year
            if key not in seen:
                seen.add(key)
                unique_albums.append(album)
        
        return unique_albums
    except Exception as e:
        if hasattr(get_artist_albums, '_errors'):
            get_artist_albums._errors.append(f"Artist albums {artist_id}: {str(e)}")
        else:
            get_artist_albums._errors = [f"Artist albums {artist_id}: {str(e)}"]
        return []

def get_album_tracks(sp, album_id: str) -> List[dict]:
    """Get all tracks from an album"""
    try:
        tracks = []
        results = sp.album_tracks(album_id, limit=50)
        tracks.extend(results['items'])
        
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
            
        return tracks
    except Exception as e:
        if hasattr(get_album_tracks, '_errors'):
            get_album_tracks._errors.append(f"Album tracks {album_id}: {str(e)}")
        else:
            get_album_tracks._errors = [f"Album tracks {album_id}: {str(e)}"]
        return []

def search_album(sp, artist: str, album: str) -> Optional[dict]:
    """Search for a specific album by artist and album name"""
    try:
        query = f'artist:"{artist}" album:"{album}"'
        results = sp.search(q=query, type='album', limit=1)
        albums = results.get('albums', {}).get('items', [])
        
        if albums:
            return albums[0]
        
        # Try broader search
        query = f'artist:{artist} album:{album}'
        results = sp.search(q=query, type='album', limit=5)
        albums = results.get('albums', {}).get('items', [])
        
        for album_result in albums:
            album_artists = [a['name'].lower() for a in album_result.get('artists', [])]
            if any(artist.lower() in aa for aa in album_artists):
                return album_result
        
        return None
        
    except Exception as e:
        print(f"ERROR: Failed to search for album '{artist}: {album}': {e}")
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--liked", action="store_true", help="Use your Liked Songs as the source")
    ap.add_argument("--playlist", help="Playlist URL/URI/ID to process instead of Liked Songs")
    ap.add_argument("--setlist-file", help="Text file with setlist for concert playlist (format: 'Artist Name: Song Title' per line)")
    ap.add_argument("--concert-playlist", help="Name for the concert playlist to create")
    ap.add_argument("--validate-only", action="store_true", help="Only validate songs against Spotify, don't create playlist")
    ap.add_argument("--max", type=int, default=0, help="Process at most N tracks (0 = all)")
    ap.add_argument("--prefix", default="Genres – ", help="Playlist name prefix for created/updated genre playlists")
    ap.add_argument("--owner", default="", help="Optional user ID to own the new playlists (defaults to your account)")
    ap.add_argument("--public", action="store_true", help="Create genre playlists as public (default private)")
    ap.add_argument("--clear", action="store_true", help="Clear genre playlists before adding new tracks")
    ap.add_argument("--dry-run", action="store_true", help="Do not create/update playlists, only print and export CSV")
    ap.add_argument("--export-analysis", action="store_true", help="Export detailed artist/album/genre analysis instead of creating playlists")
    ap.add_argument("--export-artists", action="store_true", help="Export all artists from liked songs with their albums and availability")
    ap.add_argument("--export-artist-summary", action="store_true", help="Export distinct artists with genres, song counts, and favorites flag")
    ap.add_argument("--process-artist-actions", help="Process artist actions from CSV file (YES=add all songs, REMOVE=remove from liked)")
    ap.add_argument("--add-albums", help="Text file with albums to add (format: 'Artist Name: Album Name' per line)")
    ap.add_argument("--favorite-artists", help="Text file with favorite artists to add all their albums (one artist per line)")
    ap.add_argument("--csv", default="genre_assignments.csv", help="CSV path to export report")
    ap.add_argument("--cache", default="spotify_artist_genre_cache.json", help="Cache file for artist genres")
    ap.add_argument("--use-all-artists", action="store_true", default=True, help="Use all artists on the track to collect genres (default: True)")
    ap.add_argument("--infer-related", action="store_true", help="If empty, infer genres from Spotify related artists")
    ap.add_argument("--use-musicbrainz", action="store_true", help="If still empty, query MusicBrainz tags")
    ap.add_argument("--mb-delay", type=float, default=1.1, help="Delay between MusicBrainz requests (seconds)")
    args = ap.parse_args()

    def chunked(seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    # Initialize error tracking
    get_artist_genres_by_id._errors = []
    search_artist_genres_by_name._errors = []
    infer_from_related._errors = []
    get_artist_albums._errors = []
    get_album_tracks._errors = []

    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI")

    if not (client_id and client_secret and redirect_uri):
        print("ERROR: Missing SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET / SPOTIPY_REDIRECT_URI in environment.", file=sys.stderr)
        sys.exit(2)

    scope = "user-library-read user-library-modify playlist-read-private playlist-modify-private playlist-modify-public"
    auth = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope=scope, open_browser=True, cache_path=".spotipyoauthcache")
    sp = spotipy.Spotify(auth_manager=auth)

    me = sp.current_user()
    user_id = me["id"]
    owner_id = args.owner or user_id
    print(f"Authed as: {me.get('display_name') or user_id} ({user_id}) -> creating playlists for owner: {owner_id}")

    # Handle special export modes first
    if args.export_artists:
        if not args.liked:
            print("ERROR: --export-artists requires --liked", file=sys.stderr)
            sys.exit(2)
        
        print("Fetching Liked Songs...")
        liked_tracks = []
        for item in paginate_saved_tracks(sp):
            tr = item.get("track") or {}
            if tr and tr.get("id"):
                liked_tracks.append(tr)
        
        # Get all unique artists from liked songs
        print(f"Found {len(liked_tracks)} liked tracks")
        print("Extracting unique artists...")
        
        liked_artists = {}
        liked_albums = set()
        
        for track in liked_tracks:
            album_name = (track.get("album") or {}).get("name", "")
            if album_name:
                liked_albums.add(album_name.lower())
            
            for artist in track.get("artists", []):
                artist_id = artist.get("id")
                artist_name = artist.get("name", "")
                if artist_id and artist_name:
                    if artist_id not in liked_artists:
                        liked_artists[artist_id] = artist_name
        
        print(f"Found {len(liked_artists)} unique artists")
        print("Getting albums for each artist...")
        
        artist_data = []
        for i, (artist_id, artist_name) in enumerate(liked_artists.items(), 1):
            print(f"[{i}/{len(liked_artists)}] Getting albums for: {artist_name}")
            albums = get_artist_albums(sp, artist_id)
            
            for album in albums:
                album_name = album.get('name', '')
                release_date = album.get('release_date', '')
                total_tracks = album.get('total_tracks', 0)
                album_type = album.get('album_type', '')
                
                # Check if we have this album in liked songs
                have_album = album_name.lower() in liked_albums
                
                artist_data.append({
                    'artist_name': artist_name,
                    'artist_id': artist_id,
                    'album_name': album_name,
                    'album_id': album.get('id', ''),
                    'album_type': album_type,
                    'release_date': release_date,
                    'total_tracks': total_tracks,
                    'have_in_liked': 'YES' if have_album else 'NO'
                })
            
            time.sleep(0.1)  # Be nice to API
        
        # Export to CSV
        export_path = args.csv.replace('.csv', '_artists_albums.csv')
        with open(export_path, 'w', encoding='utf-8', newline='') as f:
            if artist_data:
                fieldnames = list(artist_data[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(artist_data)
        
        print(f"Exported artist/album data: {export_path}")
        print(f"Found {len(artist_data)} total albums from {len(liked_artists)} artists")
        return
            
    elif args.export_artist_summary:
        if not args.liked:
            print("ERROR: --export-artist-summary requires --liked", file=sys.stderr)
            sys.exit(2)
        
        print("Fetching Liked Songs...")
        liked_tracks = []
        for item in paginate_saved_tracks(sp):
            tr = item.get("track") or {}
            if tr and tr.get("id"):
                liked_tracks.append(tr)
        
        print(f"Found {len(liked_tracks)} liked tracks")
        print("Analyzing artists...")
        
        artist_stats = {}
        
        for track in liked_tracks:
            for artist in track.get("artists", []):
                artist_id = artist.get("id")
                artist_name = artist.get("name", "")
                if artist_id and artist_name:
                    if artist_id not in artist_stats:
                        artist_stats[artist_id] = {
                            'artist_name': artist_name,
                            'artist_id': artist_id,
                            'song_count': 0,
                            'genres': [],
                            'favorite_artist': 'NO'  # User can edit this in CSV
                        }
                    artist_stats[artist_id]['song_count'] += 1
        
        print(f"Found {len(artist_stats)} unique artists")
        print("Getting genres for each artist (using batch processing)...")
        
        # Collect all unique artist IDs for batch processing
        all_artist_ids = list(artist_stats.keys())
        
        # Batch fetch genres
        print("Batch fetching genres from Spotify...")
        cache = load_cache(args.cache)
        batch_results = get_genres_for_artist_ids(sp, all_artist_ids)
        
        # Update cache with results
        for aid, genres in batch_results.items():
            cache_put(cache, aid, genres)
        
        # Apply genres to artist stats
        for artist_id, stats in artist_stats.items():
            genres = batch_results.get(artist_id, [])
            
            # Try alias if no Spotify genres
            if not genres:
                genres = genres_from_alias(stats['artist_name'])
            
            # Try name signals if still empty
            if not genres:
                genres = name_signal_genres(stats['artist_name'])
            
            # Use unknown if still empty
            if not genres:
                genres = ['unknown']
            
            stats['genres'] = ', '.join(genres)
        
        # Save updated cache
        save_cache(cache, args.cache)
        
        # Convert to list for CSV export
        artist_summary = list(artist_stats.values())
        
        # Sort by song count (highest first)
        artist_summary.sort(key=lambda x: x['song_count'], reverse=True)
        
        # Export to CSV
        export_path = args.csv.replace('.csv', '_artist_summary.csv')
        with open(export_path, 'w', encoding='utf-8', newline='') as f:
            if artist_summary:
                fieldnames = ['artist_name', 'genres', 'song_count', 'favorite_artist', 'artist_id']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(artist_summary)
        
        print(f"Exported artist summary: {export_path}")
        print(f"Found {len(artist_summary)} unique artists")
        print("You can edit the 'favorite_artist' column to mark your favorites (YES/NO/REMOVE)")
        return
        
    elif args.process_artist_actions:
        if not os.path.exists(args.process_artist_actions):
            print(f"ERROR: CSV file not found: {args.process_artist_actions}", file=sys.stderr)
            sys.exit(2)
        
        print(f"Processing artist actions from: {args.process_artist_actions}")
        
        # Read the CSV file
        artist_actions = []
        with open(args.process_artist_actions, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                favorite = row.get('favorite_artist', '').upper()
                if favorite in ['YES', 'REMOVE']:
                    artist_actions.append({
                        'artist_name': row.get('artist_name', ''),
                        'artist_id': row.get('artist_id', ''),
                        'action': favorite
                    })
        
        if not artist_actions:
            print("No actions to process. Make sure 'favorite_artist' column has 'YES' or 'REMOVE' values.")
            return
        
        print(f"Found {len(artist_actions)} artists to process:")
        for action in artist_actions:
            print(f"  - {action['action']}: {action['artist_name']}")
        
        # Get current liked songs for comparison
        print("\nFetching current liked songs...")
        current_liked = set()
        for item in paginate_saved_tracks(sp):
            track = item.get("track")
            if track and track.get("id"):
                current_liked.add(track["id"])
        
        print(f"Current liked songs: {len(current_liked)}")
        
        # Process each action
        for i, action in enumerate(artist_actions, 1):
            artist_name = action['artist_name']
            artist_id = action['artist_id']
            action_type = action['action']
            
            print(f"\n[{i}/{len(artist_actions)}] {action_type}: {artist_name}")
            
            if action_type == 'YES':
                # Add all songs from this artist that we don't already have
                print("  Getting all albums for artist...")
                albums = get_artist_albums(sp, artist_id)
                
                all_tracks = []
                for album in albums:
                    album_tracks = get_album_tracks(sp, album['id'])
                    all_tracks.extend(album_tracks)
                
                # Filter to tracks we don't already have
                new_tracks = []
                for track in all_tracks:
                    if track.get('id') and track['id'] not in current_liked:
                        new_tracks.append(track['id'])
                
                if new_tracks:
                    print(f"  Adding {len(new_tracks)} new tracks...")
                    # Add in batches of 50 (Spotify API limit)
                    for batch_start in range(0, len(new_tracks), 50):
                        batch = new_tracks[batch_start:batch_start + 50]
                        try:
                            sp.current_user_saved_tracks_add(batch)
                            print(f"    Added batch of {len(batch)} tracks")
                        except Exception as e:
                            print(f"    Error adding batch: {e}")
                        time.sleep(0.1)
                    
                    # Update our current_liked set
                    current_liked.update(new_tracks)
                else:
                    print("  No new tracks to add (already have all)")
                    
            elif action_type == 'REMOVE':
                # Remove all songs from this artist
                print("  Finding tracks to remove...")
                tracks_to_remove = []
                
                for item in paginate_saved_tracks(sp):
                    track = item.get("track")
                    if not track or not track.get("id"):
                        continue
                    
                    # Check if any artist on this track matches
                    for artist in track.get("artists", []):
                        if artist.get("id") == artist_id:
                            tracks_to_remove.append(track["id"])
                            break
                
                if tracks_to_remove:
                    print(f"  Removing {len(tracks_to_remove)} tracks...")
                    # Remove in batches of 50
                    for batch_start in range(0, len(tracks_to_remove), 50):
                        batch = tracks_to_remove[batch_start:batch_start + 50]
                        try:
                            sp.current_user_saved_tracks_delete(batch)
                            print(f"    Removed batch of {len(batch)} tracks")
                        except Exception as e:
                            print(f"    Error removing batch: {e}")
                        time.sleep(0.1)
                    
                    # Update our current_liked set
                    current_liked.difference_update(tracks_to_remove)
                else:
                    print("  No tracks found to remove")
            
            time.sleep(0.5)  # Be nice to API between artists
        
        print(f"\nProcessing complete! Final liked songs count: {len(current_liked)}")
        return

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

    def parse_setlist_file(file_path: str) -> List[Tuple[str, str]]:
        """Parse setlist file. Format: 'Artist Name: Song Title' per line"""
        setlist = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if ': ' in line:
                        artist, song = line.split(': ', 1)
                        setlist.append((artist.strip(), song.strip()))
                    else:
                        print(f"WARNING: Line {line_num} doesn't match format 'Artist: Song' - skipping: {line}")
        except FileNotFoundError:
            print(f"ERROR: Setlist file not found: {file_path}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"ERROR: Failed to read setlist file: {e}", file=sys.stderr)
            sys.exit(2)
        return setlist

    def parse_albums_file(file_path: str) -> List[Tuple[str, str]]:
        """Parse albums file. Format: 'Artist Name: Album Name' per line"""
        albums = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if ': ' in line:
                        artist, album = line.split(': ', 1)
                        albums.append((artist.strip(), album.strip()))
                    else:
                        print(f"WARNING: Line {line_num} doesn't match format 'Artist: Album' - skipping: {line}")
        except FileNotFoundError:
            print(f"ERROR: Albums file not found: {file_path}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"ERROR: Failed to read albums file: {e}", file=sys.stderr)
            sys.exit(2)
        return albums

    def parse_favorite_artists_file(file_path: str) -> List[str]:
        """Parse favorite artists file. Format: one artist name per line"""
        artists = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        artists.append(line)
        except FileNotFoundError:
            print(f"ERROR: Favorite artists file not found: {file_path}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"ERROR: Failed to read favorite artists file: {e}", file=sys.stderr)
            sys.exit(2)
        return artists

    def search_track(sp, artist: str, song: str) -> Tuple[Optional[dict], str]:
        """Search for a specific track by artist and song name. Returns (track, status)"""
        try:
            # Try exact search first
            query = f'artist:"{artist}" track:"{song}"'
            results = sp.search(q=query, type='track', limit=1)
            tracks = results.get('tracks', {}).get('items', [])
            
            if tracks:
                return tracks[0], "exact_match"
            
            # Try broader search without quotes
            query = f'artist:{artist} track:{song}'
            results = sp.search(q=query, type='track', limit=5)
            tracks = results.get('tracks', {}).get('items', [])
            
            # Look for best match
            for track in tracks:
                track_artists = [a['name'].lower() for a in track.get('artists', [])]
                if any(artist.lower() in ta for ta in track_artists):
                    return track, "fuzzy_match"
            
            # If no artist match, return first result as potential match
            if tracks:
                return tracks[0], "potential_match"
            
            return None, "not_found"
            
        except Exception as e:
            return None, f"error: {e}"
        """Search for a specific track by artist and song name. Returns (track, status)"""
        try:
            # Try exact search first
            query = f'artist:"{artist}" track:"{song}"'
            results = sp.search(q=query, type='track', limit=1)
            tracks = results.get('tracks', {}).get('items', [])
            
            if tracks:
                return tracks[0], "exact_match"
            
            # Try broader search without quotes
            query = f'artist:{artist} track:{song}'
            results = sp.search(q=query, type='track', limit=5)
            tracks = results.get('tracks', {}).get('items', [])
            
            # Look for best match
            for track in tracks:
                track_artists = [a['name'].lower() for a in track.get('artists', [])]
                if any(artist.lower() in ta for ta in track_artists):
                    return track, "fuzzy_match"
            
            # If no artist match, return first result as potential match
            if tracks:
                return tracks[0], "potential_match"
            
            return None, "not_found"
            
        except Exception as e:
            return None, f"error: {e}"

    tracks = []
    if args.liked:
        print("Fetching Liked Songs...")
        for item in paginate_saved_tracks(sp, max_items=args.max):
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
    elif args.setlist_file:
        if not args.validate_only and not args.concert_playlist:
            print("ERROR: --concert-playlist name required when using --setlist-file (unless using --validate-only)", file=sys.stderr)
            sys.exit(2)
        
        print(f"Reading setlist from: {args.setlist_file}")
        setlist = parse_setlist_file(args.setlist_file)
        
        print(f"Validating {len(setlist)} songs against Spotify...")
        print("=" * 80)
        
        found_tracks = []
        validation_results = []
        
        for i, (artist, song) in enumerate(setlist, 1):
            print(f"[{i:2d}/{len(setlist)}] Searching: {artist} - {song}")
            track, status = search_track(sp, artist, song)
            
            result = {
                'original_artist': artist,
                'original_song': song,
                'track': track,
                'status': status
            }
            
            if track:
                found_artist = ', '.join([a['name'] for a in track['artists']])
                found_song = track['name']
                print(f"         ✓ Found: {found_artist} - {found_song}")
                
                if status == "exact_match":
                    print(f"         ✓ EXACT MATCH")
                elif status == "fuzzy_match":
                    print(f"         ⚠ FUZZY MATCH (artist matched)")
                else:
                    print(f"         ? POTENTIAL MATCH (check manually)")
                    
                found_tracks.append(track)
            else:
                print(f"         ✗ NOT FOUND ({status})")
                
            validation_results.append(result)
            time.sleep(0.1)  # Be nice to Spotify API
        
        # Print summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        exact_matches = sum(1 for r in validation_results if r['status'] == 'exact_match')
        fuzzy_matches = sum(1 for r in validation_results if r['status'] == 'fuzzy_match')
        potential_matches = sum(1 for r in validation_results if r['status'] == 'potential_match')
        not_found = sum(1 for r in validation_results if r['status'] == 'not_found')
        
        print(f"Total songs: {len(setlist)}")
        print(f"✓ Exact matches: {exact_matches}")
        print(f"⚠ Fuzzy matches: {fuzzy_matches}")
        print(f"? Potential matches: {potential_matches}")
        print(f"✗ Not found: {not_found}")
        print(f"Success rate: {(len(found_tracks)/len(setlist)*100):.1f}%")
        
        if not_found > 0:
            print(f"\nSongs not found ({not_found}):")
            for r in validation_results:
                if r['status'] == 'not_found':
                    print(f"  - {r['original_artist']}: {r['original_song']}")
        
        if args.validate_only:
            print("\nValidation complete. Use without --validate-only to create playlist.")
            return
        
        # Continue with playlist creation if not just validating
        tracks.extend(found_tracks)
        
        if not found_tracks:
            print("No tracks found - playlist not created")
            return
            
        # Create the concert playlist
        concert_pl = sp.user_playlist_create(
            owner_id, 
            args.concert_playlist, 
            public=args.public, 
            description=f"Setlist playlist with {len(found_tracks)} songs ({(len(found_tracks)/len(setlist)*100):.1f}% match rate)"
        )
        
        # Add tracks to concert playlist
        track_ids = [t['id'] for t in found_tracks]
        for chunk in chunked(track_ids, 100):
            sp.playlist_add_items(concert_pl['id'], chunk)
        print(f"\nCreated concert playlist '{args.concert_playlist}' with {len(track_ids)} tracks")
        
        if args.dry_run:
            print("Dry run: Concert playlist created but genre processing skipped")
            return
            
    elif args.add_albums:
        print(f"Reading albums to add from: {args.add_albums}")
        albums_to_add = parse_albums_file(args.add_albums)
        
        print(f"Searching for {len(albums_to_add)} albums...")
        found_tracks = []
        
        for artist, album_name in albums_to_add:
            print(f"  Searching: {artist} - {album_name}")
            album = search_album(sp, artist, album_name)
            
            if album:
                print(f"    Found album: {album['name']} ({album['release_date'][:4]})")
                album_tracks = get_album_tracks(sp, album['id'])
                print(f"    Adding {len(album_tracks)} tracks")
                
                # Convert album tracks to full track objects for compatibility
                for track in album_tracks:
                    if track.get('id'):
                        found_tracks.append(track)
            else:
                print(f"    Album not found: {artist} - {album_name}")
            
            time.sleep(0.1)
        
        tracks.extend(found_tracks)
        print(f"Found {len(found_tracks)} tracks from albums")
        
    elif args.favorite_artists:
        print(f"Reading favorite artists from: {args.favorite_artists}")
        favorite_artists = parse_favorite_artists_file(args.favorite_artists)
        
        print(f"Getting all albums for {len(favorite_artists)} favorite artists...")
        found_tracks = []
        
        for artist_name in favorite_artists:
            print(f"  Searching for artist: {artist_name}")
            
            # Search for artist
            results = sp.search(q=f'artist:"{artist_name}"', type='artist', limit=1)
            artists = results.get('artists', {}).get('items', [])
            
            if not artists:
                print(f"    Artist not found: {artist_name}")
                continue
            
            artist_id = artists[0]['id']
            print(f"    Found artist: {artists[0]['name']}")
            
            # Get all their albums
            albums = get_artist_albums(sp, artist_id)
            print(f"    Found {len(albums)} albums")
            
            for album in albums:
                album_name = album.get('name', '')
                print(f"      Adding album: {album_name}")
                
                album_tracks = get_album_tracks(sp, album['id'])
                found_tracks.extend([t for t in album_tracks if t.get('id')])
                time.sleep(0.1)
            
            time.sleep(0.2)  # Extra delay between artists
        
        tracks.extend(found_tracks)
        print(f"Found {len(found_tracks)} tracks from favorite artists")
            
    else:
        print("ERROR: Choose one of --liked, --playlist <id/url/uri>, --setlist-file <file>, --export-artists, --add-albums <file>, or --favorite-artists <file>", file=sys.stderr)
        sys.exit(2)

    cache = load_cache(args.cache)  # now using TTL structure
    user_market = (me.get("country") or None)

    def genres_for_track(sp: spotipy.Spotify, tr: dict, cache: Dict[str, dict]) -> List[Tuple[str, float]]:
        """Get weighted genres for a track using all fallback methods"""
        scores = Counter()

        # 1) Spotify direct (weighted by primary/featured)
        w = weighted_genres_for_track(sp, tr, cache)   # [(genre, score)]
        for g, s in w:
            add_weighted(scores, [g], WEIGHTS_SOURCE["spotify_artist"] * s)

        if not scores:
            # 2) alias by name
            for a in tr.get("artists", []):
                add_weighted(scores, genres_from_alias(a.get("name", "")), WEIGHTS_SOURCE["alias"])

        if not scores:
            # 3) name signals
            for a in tr.get("artists", []):
                add_weighted(scores, name_signal_genres(a.get("name", "")), WEIGHTS_SOURCE["name_signal"])

        if not scores and args.infer_related:
            # 4) related artists (primary only)
            primary_id = tr.get("artists", [{}])[0].get("id")
            if primary_id:
                rel = infer_from_related(sp, primary_id)  # already returns top list
                add_weighted(scores, rel, WEIGHTS_SOURCE["spotify_related"])

        if not scores and args.use_musicbrainz:
            # 5) MusicBrainz tags
            for a in tr.get("artists", []):
                aname = a.get("name", "")
                if aname:
                    mbid = mb_search_artist(aname)
                    if mbid:
                        add_weighted(scores, mb_artist_genres(mbid), WEIGHTS_SOURCE["musicbrainz"])
                        time.sleep(args.mb_delay)

        # turn scores into sorted list
        weighted_list = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return weighted_list

    print(f"Collected {len(tracks)} tracks. Getting artist genres (with optimized batch processing)...")

    out_rows = []
    for tr in tracks:
        tid = tr.get("id")
        tname = tr.get("name", "")
        album = (tr.get("album") or {}).get("name", "")
        artists = split_artists(tr.get("artists"))
        primary_id = artists[0][0] if artists else None

        # Get weighted genres using new system
        weighted = genres_for_track(sp, tr, cache)
        bucket = bucketize_scored(weighted)
        genres = [g for g, _ in weighted]  # for CSV

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

    save_cache(cache, args.cache)

    by_bucket = defaultdict(list)
    for r in out_rows:
        by_bucket[r["bucket"]].append(r["track_id"])

    csv_path = args.csv
    if out_rows:
        if args.export_analysis:
            # Create detailed analysis grouped by artist/album
            analysis_data = []
            
            # Group by artist first
            by_artist = defaultdict(lambda: defaultdict(list))
            for row in out_rows:
                artist_name = row["artist_names"].split(", ")[0]  # Use primary artist
                album_name = row["album"]
                by_artist[artist_name][album_name].append(row)
            
            # Create analysis rows
            for artist_name in sorted(by_artist.keys()):
                albums = by_artist[artist_name]
                
                # Get all genres for this artist across all their songs
                all_artist_genres = set()
                total_tracks = 0
                
                for album_name in sorted(albums.keys()):
                    tracks = albums[album_name]
                    total_tracks += len(tracks)
                    
                    for track in tracks:
                        if track["genres_raw"]:
                            all_artist_genres.update(track["genres_raw"].split("; "))
                
                # Most common genre for this artist
                artist_genre_counts = Counter()
                for album_name, tracks in albums.items():
                    for track in tracks:
                        artist_genre_counts[track["bucket"]] += 1
                
                most_common_genre = artist_genre_counts.most_common(1)[0][0] if artist_genre_counts else "unknown"
                
                # Add artist summary row
                analysis_data.append({
                    "type": "ARTIST",
                    "artist": artist_name,
                    "album": f"--- {len(albums)} albums, {total_tracks} tracks ---",
                    "track_name": "",
                    "genres_raw": "; ".join(sorted(all_artist_genres)) if all_artist_genres else "",
                    "most_common_bucket": most_common_genre,
                    "bucket_distribution": ", ".join([f"{bucket}({count})" for bucket, count in artist_genre_counts.most_common()]),
                    "track_count": total_tracks
                })
                
                # Add album rows
                for album_name in sorted(albums.keys()):
                    tracks = albums[album_name]
                    
                    # Get genres for this album
                    album_genres = set()
                    album_buckets = Counter()
                    
                    for track in tracks:
                        if track["genres_raw"]:
                            album_genres.update(track["genres_raw"].split("; "))
                        album_buckets[track["bucket"]] += 1
                    
                    album_most_common = album_buckets.most_common(1)[0][0] if album_buckets else "unknown"
                    
                    analysis_data.append({
                        "type": "ALBUM",
                        "artist": "",
                        "album": album_name,
                        "track_name": f"--- {len(tracks)} tracks ---",
                        "genres_raw": "; ".join(sorted(album_genres)) if album_genres else "",
                        "most_common_bucket": album_most_common,
                        "bucket_distribution": ", ".join([f"{bucket}({count})" for bucket, count in album_buckets.most_common()]),
                        "track_count": len(tracks)
                    })
                    
                    # Add individual tracks
                    for track in sorted(tracks, key=lambda x: x["track_name"]):
                        analysis_data.append({
                            "type": "TRACK",
                            "artist": "",
                            "album": "",
                            "track_name": track["track_name"],
                            "genres_raw": track["genres_raw"],
                            "most_common_bucket": track["bucket"],
                            "bucket_distribution": track["bucket"],
                            "track_count": 1
                        })
                
                # Add separator row
                analysis_data.append({
                    "type": "---",
                    "artist": "---",
                    "album": "---", 
                    "track_name": "---",
                    "genres_raw": "---",
                    "most_common_bucket": "---",
                    "bucket_distribution": "---",
                    "track_count": "---"
                })
            
            # Write analysis CSV
            analysis_path = args.csv.replace('.csv', '_analysis.csv')
            with open(analysis_path, "w", encoding="utf-8", newline="") as f:
                fieldnames = ["type", "artist", "album", "track_name", "genres_raw", "most_common_bucket", "bucket_distribution", "track_count"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(analysis_data)
            print(f"Wrote detailed analysis: {analysis_path}")
            
        else:
            # Regular CSV export
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
                writer.writeheader()
                writer.writerows(out_rows)
            print(f"Wrote report: {csv_path}")
    else:
        print("No rows to write.")

    if args.dry_run or args.export_analysis:
        if args.export_analysis:
            print("Analysis export complete.")
        else:
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

    # Print error summary
    all_errors = []
    for func in [get_artist_genres_by_id, search_artist_genres_by_name, infer_from_related, get_artist_albums, get_album_tracks]:
        if hasattr(func, '_errors'):
            all_errors.extend(func._errors)
    
    if all_errors:
        print(f"\nAPI Issues Summary ({len(all_errors)} total):")
        
        # Group by error type
        error_counts = {}
        for error in all_errors:
            if "404" in error:
                error_type = "404 Not Found"
            elif "not found" in error.lower():
                error_type = "Artist Not Found"
            else:
                error_type = "Other API Error"
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        for error_type, count in error_counts.items():
            print(f"  {error_type}: {count}")
        
        # Show first few examples if requested
        print("  (This is normal - some artists may be removed, restricted, or podcasts)")
    else:
        print("\nNo API issues encountered!")


if __name__ == "__main__":
    main()
