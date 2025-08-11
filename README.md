# Spotify Genre Playlister

This project automatically organizes your Spotify tracks or playlists into genre-based playlists using artist genre data from Spotify and MusicBrainz.

## Features
- Assigns genres to tracks using all artists, related artists, and MusicBrainz tags
- Creates or updates genre playlists in your Spotify account
- **NEW**: Creates concert playlists from actual setlists
- Exports genre assignments to CSV
- Caches artist genre lookups for speed
- Command-line flags for customization

## Requirements
- Python 3.8+
- Spotify API credentials (set in `.env` or environment variables)
- See `requirements.txt` for dependencies

## Setup
1. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
2. Set up Spotify API credentials:
   - Create a `.env` file with:
     ```
     SPOTIPY_CLIENT_ID=your_client_id
     SPOTIPY_CLIENT_SECRET=your_client_secret
     SPOTIPY_REDIRECT_URI=your_redirect_uri
     ```
3. Run the script:
   ```sh
   # For liked songs
   python spotify_genre_playlister.py --liked
   
   # For existing playlist
   python spotify_genre_playlister.py --playlist <playlist_id_or_url>
   
   # For concert playlist from setlist file
   python spotify_genre_playlister.py --setlist-file setlist.txt --concert-playlist "My Concert 2025"
   
   # Validate setlist first (recommended)
   python spotify_genre_playlister.py --setlist-file setlist.txt --validate-only
   ```

## Setlist Format
Create a text file (e.g., `setlist.txt`) with your songs:
```
# Concert Setlist
Green Day: Basket Case
Green Day: When I Come Around
The Offspring: Come Out and Play
The Offspring: Self Esteem
Bad Religion: Generator
```
- Use `Artist Name: Song Title` format (one per line)
- Lines starting with `#` are comments
- Script will search Spotify for each song and add to playlist

## Flags
- `--setlist-file` Text file with concert setlist (Artist: Song format)
- `--concert-playlist` Name for the concert playlist to create
- `--validate-only` Validate songs against Spotify without creating playlist
- `--use-all-artists` Use all track artists for genre assignment
- `--infer-related` Infer genres from related artists
- `--use-musicbrainz` Use MusicBrainz tags as fallback
- `--mb-delay` Delay between MusicBrainz requests

## Output
- Genre playlists created/updated in your Spotify account
- CSV report of genre assignments

## License
MIT
