# Spotify Utility Suite

A comprehensive, optimized toolkit for analyzing and managing your Spotify music collection with intelligent genre classification, concert setlists, artist management, and bulk music discovery.

## ✨ Key Features
- **🎯 Smart Genre Classification**: 6 core buckets (Rock, Country, Hip-Hop, Classical, Musical, Electronic) with 500+ genre mappings
- **⚡ Batch Processing**: Up to 50x faster with optimized Spotify API calls
- **🎸 Concert Setlist Processing**: Create playlists from real concert setlists with validation
- **👨‍🎤 Artist Management**: Bulk add/remove entire discographies based on preferences
- **📊 Advanced Analytics**: Detailed CSV exports with weighted genre scoring
- **🧠 Intelligent Fallbacks**: Artist aliases, name detection, MusicBrainz integration
- **📈 Weighted Scoring**: Primary artists get more influence than featured artists

## 🔧 Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Spotify API Configuration
Create environment variables or a `.env` file:
```env
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8080
```

**Important**: Add `http://127.0.0.1:8080` to your Spotify app's redirect URIs in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

### 3. Required Spotify App Scopes
Your Spotify app needs these permissions:
- `user-library-read` - Read liked songs
- `user-library-modify` - Add/remove liked songs  
- `playlist-read-private` - Read your playlists
- `playlist-modify-private` - Create/modify private playlists
- `playlist-modify-public` - Create/modify public playlists

## 📖 Command Reference

### 🎵 Genre Playlist Creation
Automatically organize your music into 6 core genre buckets with intelligent classification.

```bash
# Process liked songs into genre playlists (optimized batch processing)
python spotify_genre_playlister.py --liked

# Process existing playlist into genre playlists  
python spotify_genre_playlister.py --playlist <playlist_id_or_url>

# Dry run with analysis (see genre distribution without creating playlists)
python spotify_genre_playlister.py --liked --dry-run

# Limit processing for testing
python spotify_genre_playlister.py --liked --max 100

# Advanced genre detection options
python spotify_genre_playlister.py --liked --infer-related --use-musicbrainz
python spotify_genre_playlister.py --liked --dry-run

# Clear existing genre playlists before adding
python spotify_genre_playlister.py --liked --clear

# Create public playlists instead of private
python spotify_genre_playlister.py --liked --public

# Custom playlist name prefix
python spotify_genre_playlister.py --liked --prefix "My Music – "

# Clear existing playlists and rebuild
python spotify_genre_playlister.py --liked --clear

# Create public playlists instead of private
python spotify_genre_playlister.py --liked --public
```

**🎯 Optimized 6-Genre System:**
- **Rock**: All rock subgenres, punk, emo, metal, alternative, indie rock
- **Country**: Country, folk, americana, singer-songwriter
- **Hip-Hop**: All rap and hip-hop subgenres
- **Classical**: Classical, orchestral, opera, instrumental
- **Musical**: Soundtracks, Broadway, film scores
- **Electronic**: EDM, house, techno, synthwave, electronic

### 🎤 Concert Setlist Processing
Convert real concert setlists into validated Spotify playlists.

```bash
# Create playlist from setlist file (with validation)
python spotify_genre_playlister.py --setlist-file concert.txt --concert-playlist "Amazing Concert 2025"

# Validate setlist first without creating playlist (recommended)
python spotify_genre_playlister.py --setlist-file concert.txt --validate-only

# Process only first 20 songs for highlights
python spotify_genre_playlister.py --setlist-file concert.txt --concert-playlist "Concert Highlights" --max 20
```

**Setlist File Format** (`concert.txt`):
```
# Green Day Concert - August 2025
Green Day: Basket Case
Green Day: When I Come Around  
The Offspring: Come Out and Play
Bad Religion: Generator
# Encore
Green Day: Good Riddance (Time of Your Life)
```

### 📊 Data Export & Analysis
Export detailed analytics with weighted genre scoring and batch processing.

```bash
# Export artist summary with genres, song counts, and favorites column (FAST!)
python spotify_genre_playlister.py --liked --export-artist-summary

# Export detailed analysis grouped by artist/album
python spotify_genre_playlister.py --liked --export-analysis

# Export complete artist/album availability matrix
python spotify_genre_playlister.py --liked --export-artists

# Custom CSV output filenames
python spotify_genre_playlister.py --liked --export-artist-summary --csv my_artists.csv
python spotify_genre_playlister.py --liked --export-analysis --csv detailed_analysis.csv
```

### 🎯 Artist Management
Intelligent bulk management of your music collection.

```bash
# Process artist actions from CSV (bulk add/remove entire discographies)
python spotify_genre_playlister.py --process-artist-actions artist_summary.csv

# Add specific albums from text file
python spotify_genre_playlister.py --add-albums albums.txt

# Add all albums from favorite artists
python spotify_genre_playlister.py --favorite-artists favorites.txt
```

**Artist Management Workflow**:
1. **Export**: `python spotify_genre_playlister.py --liked --export-artist-summary`
2. **Edit**: Open CSV, set `favorite_artist` column to `YES`/`REMOVE`/`NO`
3. **Execute**: `python spotify_genre_playlister.py --process-artist-actions liked_songs_artist_summary.csv`

**Albums File Format** (`albums.txt`):
```
# Albums I want to add
Green Day: American Idiot
The Offspring: Smash
Bad Religion: Suffer
```

**Favorite Artists File Format** (`favorites.txt`):
```
# Add all albums from these artists
Green Day
The Offspring  
Bad Religion
```

### 🔧 Advanced Options & Optimization

```bash
# Performance & Cache Options
python spotify_genre_playlister.py --liked --cache custom_cache.json
python spotify_genre_playlister.py --liked --max 1000  # Process subset for testing

# Enhanced Genre Detection (slower but more comprehensive)
python spotify_genre_playlister.py --liked --infer-related --use-musicbrainz --mb-delay 1.5

# Playlist Customization Options
python spotify_genre_playlister.py --liked --prefix "My Genres – " --public --clear

# Custom playlist owner (for shared accounts)
python spotify_genre_playlister.py --liked --owner different_username
```

## 📁 File Formats

### Artist Summary CSV
Generated by `--export-artist-summary` - optimized for bulk management:
```csv
artist_name,genres,song_count,favorite_artist,artist_id
blink-182,"pop-punk, punk, rock",214,NO,6FBDaR13swtiWwGhX1WQsP
Breaking Benjamin,"alternative metal, post-grunge",103,YES,5BtHciL0e0zOP7prIHn3pP
Skillet,"alternative metal, christian rock",89,YES,1Uff91EOsvd99rtAupatMP
```

### Artist Albums Discovery CSV  
Generated by `--export-artists` - discover new music from your artists:
```csv
artist_name,artist_id,album_name,album_id,album_type,release_date,total_tracks,have_in_liked
blink-182,6FBDaR13swtiWwGhX1WQsP,California,6u7jPZnNJTvJk8iSMOGhJA,album,2016-07-01,16,YES
blink-182,6FBDaR13swtiWwGhX1WQsP,NINE,4xG8G2kxEbVEKbhGWxzfoj,album,2019-09-20,15,NO
```

## ⚡ Performance Features

### Optimized Batch Processing
- **50x Faster**: Batch fetch up to 50 artists per API call vs individual calls
- **Smart Caching**: 14-day TTL cache prevents redundant API requests  
- **Weighted Scoring**: Primary artists weighted 1.0x, featured artists 0.5x
- **Intelligent Fallbacks**: Artist aliases → Name detection → Related artists → MusicBrainz

### Genre Classification Intelligence  
- **500+ Genre Mappings**: Comprehensive mapping to 6 core buckets
- **Confidence Scoring**: Different weights for different genre sources
- **Multi-Source**: Spotify direct (1.0) → Aliases (0.9) → Related (0.6) → MusicBrainz (0.5)

## 🎯 Usage Examples

### Quick Start - Genre Playlists
```bash
# Analyze your music and create 6 genre playlists
python spotify_genre_playlister.py --liked

# Result: Creates "Genres – Rock", "Genres – Electronic", etc.
```

### Bulk Artist Management
```bash
# 1. Export your artists with genres and song counts  
python spotify_genre_playlister.py --liked --export-artist-summary

# 2. Edit CSV: Set favorite_artist to YES/REMOVE
# 3. Process: Add all songs from YES artists, remove REMOVE artists
python spotify_genre_playlister.py --process-artist-actions liked_songs_artist_summary.csv
```

### Concert Playlist Creation
```bash
# 1. Create setlist file with "Artist: Song" format
# 2. Validate against Spotify database
python spotify_genre_playlister.py --setlist-file concert.txt --validate-only

# 3. Create playlist with validation results
python spotify_genre_playlister.py --setlist-file concert.txt --concert-playlist "Epic Concert 2025"
```

## 🤝 Tips & Best Practices

1. **Start with Analysis**: Always use `--dry-run` first to see genre distribution
2. **Validate Setlists**: Use `--validate-only` before creating concert playlists  
3. **Test with Limits**: Use `--max 100` to test changes on small samples
4. **Cache Management**: The cache refreshes every 14 days automatically
5. **Bulk Operations**: Artist management can add/remove hundreds of tracks at once
6. **Genre Coverage**: The 6-bucket system covers 95%+ of popular music genres

---

## 🚀 Recent Optimizations

### v2.0 Performance Updates
- **Batch API Calls**: Process 50 artists per request instead of individual calls
- **Weighted Artist Priority**: Primary artists influence genre more than featured artists
- **Smart Cache**: TTL-based caching with automatic 14-day refresh
- **Enhanced Genre Mapping**: 500+ genre variations mapped to 6 core buckets
- **Artist Aliases**: Direct mappings for common artists without Spotify genres
- **Name Detection**: Automatic classification for orchestras, Broadway casts, etc.

### Intelligence Improvements
- **Multi-Source Fallbacks**: Spotify → Artist aliases → Name signals → Related artists → MusicBrainz
- **Confidence Scoring**: Different source reliability weights for better accuracy
- **Score-Based Bucketizing**: Weighted genre assignment instead of first-match
- **Comprehensive Coverage**: Rock, Country, Hip-Hop, Classical, Musical, Electronic buckets

Built with ❤️ for music lovers who want better organization and discovery tools.

### Optimized Batch Processing
- **50x Faster**: Batch fetch up to 50 artists per API call vs individual calls
- **Smart Caching**: 14-day TTL cache prevents redundant API requests  
- **Weighted Scoring**: Primary artists weighted 1.0x, featured artists 0.5x
- **Intelligent Fallbacks**: Artist aliases → Name detection → Related artists → MusicBrainz

### Genre Classification Intelligence  
- **500+ Genre Mappings**: Comprehensive mapping to 6 core buckets
- **Confidence Scoring**: Different weights for different genre sources
- **Multi-Source**: Spotify direct (1.0) → Aliases (0.9) → Related (0.6) → MusicBrainz (0.5)

## 🎯 Usage Examples

### Quick Start - Genre Playlists
```bash
# Analyze your music and create 6 genre playlists
python spotify_genre_playlister.py --liked

# Result: Creates "Genres – Rock", "Genres – Electronic", etc.
```

### Bulk Artist Management
```bash
# 1. Export your artists with genres and song counts  
python spotify_genre_playlister.py --liked --export-artist-summary

# 2. Edit CSV: Set favorite_artist to YES/REMOVE
# 3. Process: Add all songs from YES artists, remove REMOVE artists
python spotify_genre_playlister.py --process-artist-actions liked_songs_artist_summary.csv
```

### Concert Playlist Creation
```bash
# 1. Create setlist file with "Artist: Song" format
# 2. Validate against Spotify database
python spotify_genre_playlister.py --setlist-file concert.txt --validate-only

# 3. Create playlist with validation results
python spotify_genre_playlister.py --setlist-file concert.txt --concert-playlist "Epic Concert 2025"
```

## 🤝 Tips & Best Practices

1. **Start with Analysis**: Always use `--dry-run` first to see genre distribution
2. **Validate Setlists**: Use `--validate-only` before creating concert playlists  
3. **Test with Limits**: Use `--max 100` to test changes on small samples
4. **Cache Management**: The cache refreshes every 14 days automatically
5. **Bulk Operations**: Artist management can add/remove hundreds of tracks at once
6. **Genre Coverage**: The 6-bucket system covers 95%+ of popular music genres
Skillet,49bzE5vRBRIota4qeHtQM8,Victorious,6uBm8oGd1fJNWpCsaURaPZ,album,2019-08-02,12,NO
```

## Genre Classification

The tool uses smart genre bucketing rules:
- **Rock**: alternative rock, hard rock, classic rock, etc.
- **Metal**: heavy metal, death metal, metalcore, etc.  
- **Pop**: pop rock, indie pop, electropop, etc.
- **Country**: country, americana, folk, bluegrass, etc.
- **Electronic**: EDM, house, techno, dubstep, etc.
- **Hip-Hop**: rap, hip hop, trap, etc.
- **Other**: Everything else

## Example Workflows

### Complete Music Analysis
```bash
# 1. Export your artist summary
python spotify_genre_playlister.py --liked --export-artist-summary --csv my_artists.csv

# 2. Export discovery data  
python spotify_genre_playlister.py --liked --export-artists --csv discovery.csv

# 3. Create genre playlists
python spotify_genre_playlister.py --liked

# 4. Edit my_artists.csv and bulk manage artists
python spotify_genre_playlister.py --process-artist-actions my_artists.csv
```

### Concert Experience
```bash
# 1. Validate your setlist
python spotify_genre_playlister.py --setlist-file show.txt --validate-only

# 2. Create the playlist
python spotify_genre_playlister.py --setlist-file show.txt --concert-playlist "Epic Show 2025"
```

## Troubleshooting

- **Invalid redirect URI**: Add `http://127.0.0.1:8080` to your Spotify app settings
- **403 Insufficient scope**: App needs `user-library-modify` permission
- **No genres found**: Enable `--use-musicbrainz` for additional genre sources
- **Rate limiting**: Increase `--mb-delay` for MusicBrainz requests

## License
MIT
