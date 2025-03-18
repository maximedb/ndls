#!/usr/bin/env python3
# daily_transcription.py - Download and transcribe daily podcast episode

import requests
import os
import time
import json
from datetime import datetime
import xml.etree.ElementTree as ET
import re
import sys
import pytz  # For timezone handling

# Configuration
RSS_URL = "https://www.omnycontent.com/d/playlist/5978613f-cd11-4352-8f26-adb900fa9a58/3c1222e5-288f-4047-a2f0-ae1b00a91688/a0389eb5-55da-493d-b7bb-ae1b00d0d95a/podcast.rss"
OUTPUT_DIR = "audio_files"
TRANSCRIPTIONS_DIR = "transcriptions"
HTML_OUTPUT = "index.html"
ARCHIVE_DIR = "archive"

def check_brussels_time():
    """
    Check if current time in Brussels is after 7 AM
    Returns True if it's after 7 AM, False otherwise
    """
    # Get current time in Brussels
    brussels_tz = pytz.timezone('Europe/Brussels')
    now_brussels = datetime.now(brussels_tz)
    
    # Check if it's after 7 AM
    if now_brussels.hour < 7:
        print(f"Current time in Brussels is {now_brussels.strftime('%H:%M:%S')}, before 7 AM threshold")
        return False
    
    print(f"Current time in Brussels is {now_brussels.strftime('%H:%M:%S')}, after 7 AM threshold")
    return True

def download_latest_mp3(rss_url, output_directory):
    """
    Parse RSS feed and download the latest MP3
    """
    try:
        # Get the RSS feed content
        response = requests.get(rss_url)
        if response.status_code != 200:
            print(f"Failed to fetch RSS feed. Status code: {response.status_code}")
            return None
        
        # Parse the XML content using ElementTree
        rss_content = response.text
        root = ET.fromstring(rss_content)
        
        # Find the first item in the channel (the latest episode)
        channel = root.find('channel')
        if channel is None:
            print("No channel found in RSS feed")
            return None
        
        item = channel.find('item')
        if item is None:
            print("No items found in RSS feed")
            return None
        
        # Extract MP3 URL from media:content
        media_content = item.find('.//{http://search.yahoo.com/mrss/}content[@type="audio/mpeg"]')
        if media_content is None:
            print("No media:content with audio/mpeg type found")
            return None
        
        mp3_url = media_content.get('url')
        if not mp3_url:
            print("No URL found in media:content")
            return None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        # Generate filename based on date
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{today}.mp3"
        filepath = os.path.join(output_directory, filename)
        
        # Download the MP3 file
        mp3_response = requests.get(mp3_url)
        if mp3_response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(mp3_response.content)
            print(f"Downloaded MP3 to {filepath}")
            return filepath
        else:
            print(f"Failed to download MP3. Status code: {mp3_response.status_code}")
            return None
        
    except Exception as e:
        print(f"Error downloading MP3: {str(e)}")
        return None

def transcribe_audio_with_gladia(audio_path, api_key):
    """
    Transcribe audio using Gladia API
    """
    try:
        # Verify file exists and has content before attempting upload
        if not os.path.exists(audio_path):
            print(f"Error: Audio file does not exist at {audio_path}")
            return None
            
        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            print(f"Error: Audio file is empty (0 bytes)")
            return None
            
        print(f"File verification successful. Size: {file_size} bytes")
        # Step 1: Upload the file
        upload_url = "https://api.gladia.io/v2/upload"
        headers = {
            'x-gladia-key': api_key
        }
        
        # Create a properly named file object with filename
        file_name = os.path.basename(audio_path)
        with open(audio_path, 'rb') as f:
            files = {
                'audio': (file_name, f, 'audio/mpeg')
            }
            print(f"Uploading file {file_name} to Gladia API...")
            upload_response = requests.post(upload_url, headers=headers, files=files)
        
        try:
            if upload_response.status_code != 200:
                print(f"Error uploading file: {upload_response.text}")
                print(f"HTTP Status Code: {upload_response.status_code}")
                print(f"Response Headers: {upload_response.headers}")
                return None
            
            upload_result = upload_response.json()
            print(f"File uploaded successfully. Response: {upload_result}")
        except Exception as e:
            print(f"Exception while processing upload response: {str(e)}")
            return None
        audio_url = upload_result.get('audio_url')
        
        # Step 2: Request transcription
        transcription_url = "https://api.gladia.io/v2/pre-recorded"
        transcription_headers = {
            'Content-Type': 'application/json',
            'x-gladia-key': api_key
        }
        
        transcription_payload = {
            "audio_url": audio_url,
            "diarization": True,
            "detect_language": True
        }
        
        transcription_response = requests.post(
            transcription_url,
            headers=transcription_headers,
            json=transcription_payload
        )
        
        print(f"Transcription request status code: {transcription_response.status_code}")
        print(f"Transcription response: {transcription_response.text}")
        
        # Accept status codes 200, 201, 202 as success
        if transcription_response.status_code not in [200, 201, 202]:
            print(f"Error requesting transcription: {transcription_response.text}")
            return None
        
        transcription_result = transcription_response.json()
        
        # Verify we have the required fields
        if 'id' not in transcription_result or 'result_url' not in transcription_result:
            print(f"Invalid response format. Missing required fields: {transcription_result}")
            return None
            
        print(f"Transcription job created successfully. ID: {transcription_result.get('id')}")
        result_url = transcription_result.get('result_url')
        
        # Step 3: Poll for results
        max_retries = 60  # 10 minutes with 10 second interval
        for i in range(max_retries):
            print(f"Polling for results (attempt {i+1}/{max_retries})...")
            result_response = requests.get(result_url, headers={'x-gladia-key': api_key})
            
            if result_response.status_code == 200:
                result = result_response.json()
                print(f"Response status: {result.get('status')}")
                
                if result.get('status') == 'done':
                    # Save raw JSON result for reference
                    os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)
                    today = datetime.now().strftime("%Y-%m-%d")
                    json_path = os.path.join(TRANSCRIPTIONS_DIR, f"{today}.json")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2)
                    
                    # Verify that the response contains the necessary data
                    if 'result' in result and 'transcription' in result['result']:
                        print("Transcription data found in response")
                    else:
                        print("Warning: Transcription data not found in response structure")
                        print(f"Available keys: {list(result.keys())}")
                        if 'result' in result:
                            print(f"Keys in result: {list(result['result'].keys())}")
                    
                    return result
                elif result.get('status') == 'error':
                    print(f"Transcription failed with error: {result.get('error_code')}")
                    print(f"Error details: {result.get('error_message', 'No details provided')}")
                    return None
                else:
                    print(f"Status: {result.get('status')} - continuing to poll...")
            else:
                print(f"Error polling for results: Status {result_response.status_code}")
                print(result_response.text)
            
            time.sleep(10)  # Wait 10 seconds before polling again
        
        print("Transcription timed out")
        return None
        
    except Exception as e:
        print(f"Error transcribing audio: {str(e)}")
        return None

def create_html_page(transcription_result, output_path):
    """
    Create an HTML page from transcription results
    """
    try:
        # Debug the structure of the transcription result
        print("Transcription result structure:")
        print(f"Keys at root level: {list(transcription_result.keys())}")
        
        # The structure is different than expected - data is nested under 'result'
        if 'result' in transcription_result:
            print("Found 'result' key - using nested structure")
            metadata = transcription_result.get('result', {}).get('metadata', {})
            transcription = transcription_result.get('result', {}).get('transcription', {})
        else:
            print("Using flat structure")
            metadata = transcription_result.get('metadata', {})
            transcription = transcription_result.get('transcription', {})
        
        print(f"Metadata: {metadata}")
        print(f"Transcription keys: {list(transcription.keys()) if transcription else 'None'}")
        
        # Get audio duration in human-readable format
        audio_duration = metadata.get('audio_duration', 0)
        minutes = int(audio_duration // 60)
        seconds = int(audio_duration % 60)
        duration_formatted = f"{minutes}:{seconds:02d}"
        
        # Get utterances
        utterances = transcription.get('utterances', [])
        print(f"Number of utterances found: {len(utterances)}")
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Daily Podcast Transcription</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    max-width: 800px;
                    margin: 0 auto;
                    color: #333;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }}
                .meta-info {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    font-size: 14px;
                }}
                .meta-item {{
                    margin-bottom: 5px;
                }}
                .utterance {{
                    margin-bottom: 15px;
                    padding: 12px;
                    background-color: #f9f9f9;
                    border-radius: 5px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                .utterance-text {{
                    font-size: 16px;
                    margin-bottom: 8px;
                }}
                .utterance-info {{
                    font-size: 12px;
                    color: #666;
                }}
                .timestamp {{
                    font-weight: bold;
                }}
                .confidence {{
                    margin-left: 10px;
                }}
                .updated-date {{
                    text-align: right;
                    font-style: italic;
                    margin-top: 30px;
                    color: #999;
                }}
                .archives {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                }}
                .archives h2 {{
                    font-size: 18px;
                    margin-bottom: 10px;
                }}
                .archives ul {{
                    list-style-type: none;
                    padding: 0;
                }}
                .archives li {{
                    margin-bottom: 5px;
                }}
                .archives a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                .archives a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <h1>Daily Podcast Transcription</h1>
            
            <div class="meta-info">
                <div class="meta-item"><strong>Date:</strong> {datetime.now().strftime("%Y-%m-%d")}</div>
                <div class="meta-item"><strong>Audio Duration:</strong> {duration_formatted}</div>
                <div class="meta-item"><strong>Number of Channels:</strong> {metadata.get('number_of_distinct_channels', 'Unknown')}</div>
                <div class="meta-item"><strong>Language:</strong> {transcription.get('languages', ['Unknown'])[0] if transcription.get('languages') else 'Unknown'}</div>
            </div>
            
            <h2>Transcription</h2>
        """
        
        # Add utterances
        for idx, utterance in enumerate(utterances, 1):
            text = utterance.get('text', '')
            start = utterance.get('start', 0)
            end = utterance.get('end', 0)
            confidence = utterance.get('confidence', 0)
            speaker = utterance.get('speaker', 0)
            
            # Format timestamps as minutes:seconds
            start_min = int(start // 60)
            start_sec = int(start % 60)
            end_min = int(end // 60)
            end_sec = int(end % 60)
            
            start_formatted = f"{start_min}:{start_sec:02d}"
            end_formatted = f"{end_min}:{end_sec:02d}"
            
            html_content += f"""
            <div class="utterance">
                <div class="utterance-text">{text}</div>
                <div class="utterance-info">
                    <span class="timestamp">{start_formatted} - {end_formatted}</span>
                    <span class="confidence">Confidence: {confidence:.2f}</span>
                    <span class="speaker">Speaker: {speaker}</span>
                </div>
            </div>
            """
        
        # Add archive links
        html_content += """
            <div class="archives">
                <h2>Archives</h2>
                <ul>
        """
        
        # Get list of archive files
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        archive_files = []
        for file in os.listdir(ARCHIVE_DIR):
            if file.endswith('.html'):
                # Extract date from filename
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.html', file)
                if date_match:
                    date_str = date_match.group(1)
                    archive_files.append((date_str, file))
        
        # Sort archive files by date (newest first)
        archive_files.sort(reverse=True)
        
        # Add up to 10 most recent archives
        for date_str, filename in archive_files[:10]:
            html_content += f'<li><a href="archive/{filename}">{date_str}</a></li>\n'
            
        html_content += """
                </ul>
            </div>
            
            <div class="updated-date">Last updated: {}
            </div>
        </body>
        </html>
        """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # Save HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Create an archive copy
        today = datetime.now().strftime("%Y-%m-%d")
        archive_path = os.path.join(ARCHIVE_DIR, f"{today}.html")
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Created HTML page at {output_path} and archived to {archive_path}")
        
    except Exception as e:
        print(f"Error creating HTML page: {str(e)}")

def transcribe_audio_with_url(audio_url, api_key):
    """
    Transcribe audio using direct URL (no upload required)
    """
    try:
        print(f"Transcribing directly from URL: {audio_url}")
        
        # Request transcription
        transcription_url = "https://api.gladia.io/v2/pre-recorded"
        transcription_headers = {
            'Content-Type': 'application/json',
            'x-gladia-key': api_key
        }
        
        transcription_payload = {
            "audio_url": audio_url,
            "diarization": True,
            "detect_language": True
        }
        
        transcription_response = requests.post(
            transcription_url,
            headers=transcription_headers,
            json=transcription_payload
        )
        
        print(f"Transcription request status code: {transcription_response.status_code}")
        print(f"Transcription response: {transcription_response.text}")
        
        # Accept status codes 200, 201, 202 as success
        if transcription_response.status_code not in [200, 201, 202]:
            print(f"Error requesting transcription: {transcription_response.text}")
            return None
        
        transcription_result = transcription_response.json()
        
        # Verify we have the required fields
        if 'id' not in transcription_result or 'result_url' not in transcription_result:
            print(f"Invalid response format. Missing required fields: {transcription_result}")
            return None
            
        print(f"Transcription job created successfully. ID: {transcription_result.get('id')}")
        result_url = transcription_result.get('result_url')
        
        # Step 3: Poll for results
        max_retries = 60  # 10 minutes with 10 second interval
        for i in range(max_retries):
            print(f"Polling for results (attempt {i+1}/{max_retries})...")
            result_response = requests.get(result_url, headers={'x-gladia-key': api_key})
            
            if result_response.status_code == 200:
                result = result_response.json()
                print(f"Response status: {result.get('status')}")
                
                if result.get('status') == 'done':
                    # Save raw JSON result for reference
                    os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)
                    today = datetime.now().strftime("%Y-%m-%d")
                    json_path = os.path.join(TRANSCRIPTIONS_DIR, f"{today}.json")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2)
                    
                    # Verify that the response contains the necessary data
                    if 'result' in result and 'transcription' in result['result']:
                        print("Transcription data found in response")
                    else:
                        print("Warning: Transcription data not found in response structure")
                        print(f"Available keys: {list(result.keys())}")
                        if 'result' in result:
                            print(f"Keys in result: {list(result['result'].keys())}")
                    
                    return result
                elif result.get('status') == 'error':
                    print(f"Transcription failed with error: {result.get('error_code')}")
                    print(f"Error details: {result.get('error_message', 'No details provided')}")
                    return None
                else:
                    print(f"Status: {result.get('status')} - continuing to poll...")
            else:
                print(f"Error polling for results: Status {result_response.status_code}")
                print(result_response.text)
            
            time.sleep(10)  # Wait 10 seconds before polling again
        
        print("Transcription timed out")
        return None
        
    except Exception as e:
        print(f"Error transcribing audio from URL: {str(e)}")
        return None

def main():
    """
    Main function
    """
    # Check if it's after 7 AM Brussels time
    if not check_brussels_time():
        print("Exiting: Current time is before 7 AM in Brussels")
        sys.exit(0)
    
    # Get API key from environment variable
    api_key = os.environ.get("GLADIA_API_KEY")
    if not api_key:
        print("Error: GLADIA_API_KEY environment variable is not set")
        sys.exit(1)
    
    # Create directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    
    # Parse RSS to get latest MP3 URL without downloading
    try:
        response = requests.get(RSS_URL)
        if response.status_code == 200:
            rss_content = response.text
            root = ET.fromstring(rss_content)
            channel = root.find('channel')
            item = channel.find('item')
            media_content = item.find('.//{http://search.yahoo.com/mrss/}content[@type="audio/mpeg"]')
            mp3_url = media_content.get('url')
            
            if mp3_url:
                print(f"Found MP3 URL: {mp3_url}")
                
                # Try direct URL transcription first
                print("Attempting transcription directly from URL...")
                transcription_result = transcribe_audio_with_url(mp3_url, api_key)
                
                if transcription_result:
                    print("Direct URL transcription successful")
                else:
                    # Fallback to download and upload method
                    print("Direct URL transcription failed, falling back to download method...")
                    mp3_path = download_latest_mp3(RSS_URL, OUTPUT_DIR)
                    if not mp3_path:
                        print("Failed to download MP3, exiting")
                        sys.exit(1)
                    
                    print(f"Transcribing audio file: {mp3_path}...")
                    transcription_result = transcribe_audio_with_gladia(mp3_path, api_key)
            else:
                print("No MP3 URL found in RSS feed, falling back to download method...")
                mp3_path = download_latest_mp3(RSS_URL, OUTPUT_DIR)
                if not mp3_path:
                    print("Failed to download MP3, exiting")
                    sys.exit(1)
                
                print(f"Transcribing audio file: {mp3_path}...")
                transcription_result = transcribe_audio_with_gladia(mp3_path, api_key)
        else:
            # Fallback to original method
            print(f"Failed to fetch RSS feed. Status code: {response.status_code}")
            print("Falling back to download method...")
            mp3_path = download_latest_mp3(RSS_URL, OUTPUT_DIR)
            if not mp3_path:
                print("Failed to download MP3, exiting")
                sys.exit(1)
            
            print(f"Transcribing audio file: {mp3_path}...")
            transcription_result = transcribe_audio_with_gladia(mp3_path, api_key)
    except Exception as e:
        print(f"Error parsing RSS directly: {str(e)}")
        print("Falling back to download method...")
        mp3_path = download_latest_mp3(RSS_URL, OUTPUT_DIR)
        if not mp3_path:
            print("Failed to download MP3, exiting")
            sys.exit(1)
        
        print(f"Transcribing audio file: {mp3_path}...")
        transcription_result = transcribe_audio_with_gladia(mp3_path, api_key)
    
    # Check if we have a transcription result
    if not transcription_result:
        print("Failed to transcribe audio, exiting")
        sys.exit(1)
    
    # Create HTML page
    print("Creating HTML page...")
    print(f"Transcription result keys: {list(transcription_result.keys())}")
    
    # Save raw JSON for debugging
    debug_path = "transcription_debug.json"
    with open(debug_path, 'w', encoding='utf-8') as f:
        json.dump(transcription_result, f, indent=2)
    print(f"Saved debug JSON to {debug_path}")
    
    create_html_page(transcription_result, HTML_OUTPUT)
    
    print("Process completed successfully")

if __name__ == "__main__":
    main()