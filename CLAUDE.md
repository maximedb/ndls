# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a podcast transcription automation system that downloads daily episodes from an RSS feed, transcribes them using the Gladia API, and generates HTML pages with the transcriptions. The system includes archiving capabilities and timezone-aware scheduling.

## Key Architecture

The system operates around a single Python script (`daily_transcription.py`) that orchestrates the entire workflow:

1. **RSS Feed Processing**: Fetches and parses RSS feed to extract MP3 URLs
2. **Audio Handling**: Downloads MP3 files or uses direct URL transcription via Gladia API
3. **Transcription Processing**: Handles API polling and saves both JSON and HTML outputs
4. **Web Interface**: Generates styled HTML pages with utterance timestamps and speaker identification
5. **Archiving**: Maintains historical transcriptions with automatic archive linking

## Directory Structure

- `audio_files/` - Downloaded MP3 files (named by date: YYYY-MM-DD.mp3)
- `transcriptions/` - Raw JSON transcription results from Gladia API
- `archive/` - Historical HTML transcription pages
- `index.html` - Current/latest transcription page (auto-generated)

## Running the System

### Prerequisites
- Python 3.x with required packages: `requests`, `pytz`
- Environment variable: `GLADIA_API_KEY` must be set

### Main Command
```bash
python3 daily_transcription.py
```

The script includes timezone logic (Brussels time) and will exit if run before 7 AM local time.

## Key Features

- **Timezone Awareness**: Only runs after 7 AM Brussels time
- **Dual Transcription Methods**: Direct URL transcription preferred, with fallback to download+upload
- **Speaker Diarization**: Identifies different speakers in transcriptions
- **Automatic HTML Generation**: Creates styled web pages with timestamps and confidence scores
- **Archive Management**: Maintains up to 10 most recent transcriptions linked from main page
- **Error Handling**: Comprehensive error handling with fallback methods

## Configuration

Key configuration variables in `daily_transcription.py`:
- `RSS_URL`: Podcast RSS feed URL
- `OUTPUT_DIR`: Audio files directory
- `TRANSCRIPTIONS_DIR`: JSON transcriptions directory  
- `ARCHIVE_DIR`: Historical HTML pages directory
- `HTML_OUTPUT`: Main HTML file path

## Data Flow

1. Check Brussels timezone (exit if before 7 AM)
2. Parse RSS feed for latest episode MP3 URL
3. Attempt direct URL transcription via Gladia API
4. If direct fails, download MP3 and upload to Gladia
5. Poll Gladia API for transcription completion
6. Save JSON results to `transcriptions/`
7. Generate HTML page with utterances, timestamps, and metadata
8. Update `index.html` and create archived copy
9. Link recent archives in generated HTML