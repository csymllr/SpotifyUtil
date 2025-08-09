# Spotify Genre Playlister

This project automatically organizes your Spotify tracks or playlists into genre-based playlists using artist genre data from Spotify and MusicBrainz.

## Features
- Assigns genres to tracks using all artists, related artists, and MusicBrainz tags
- Creates or updates genre playlists in your Spotify account
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
   python spotify_genre_playlister.py --liked
   ```
   Or for a playlist:
   ```sh
   python spotify_genre_playlister.py --playlist <playlist_id_or_url>
   ```

## Flags
- `--use-all-artists` Use all track artists for genre assignment
- `--infer-related` Infer genres from related artists
- `--use-musicbrainz` Use MusicBrainz tags as fallback
- `--mb-delay` Delay between MusicBrainz requests

## Output
- Genre playlists created/updated in your Spotify account
- CSV report of genre assignments

## License
MIT
