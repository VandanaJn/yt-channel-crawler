import os
import requests
import whisper
import yt_dlp
from dotenv import load_dotenv
import json
import re
import unicodedata
from pathlib import Path
# === CONFIG ===

NUM_VIDEOS = os.getenv("NUM_VIDEOS")
OUTPUT_FILE = os.getenv("OUTPUT_FILE")
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE")
AUDIO_QUALITY = os.getenv("AUDIO_QUALITY")
API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID") 
JASON_PATH = os.getenv("JASON_PATH")
AUDIO_FOLDER=os.getenv("AUDIO_FOLDER")

def get_filename(title):
    # Normalize Unicode
    title = unicodedata.normalize("NFKD", title)
    # Remove HTML entities
    title = title.replace("&quot;", "").replace("&#39;", "").replace("&amp;", "and")
    # Replace punctuation and spaces with underscores
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s\-]+", "_", title)
    # Lowercase and trim
    return title.lower().strip("_")

def update_video_metadata_json():
    print("📺 Fetching latest video metadata...")
    # Load existing JSON
    if os.path.exists(JASON_PATH):
        with open(JASON_PATH, "r", encoding="utf-8") as f:
            existing_log = json.load(f)
            existing_ids = {entry["video_id"] for entry in existing_log}
    else:
        existing_log = []
        existing_ids = set()

    # Step 1: Get latest video IDs
    search_url = 'https://www.googleapis.com/youtube/v3/search'
    search_params = {
        'key': API_KEY,
        'channelId': CHANNEL_ID,
        'part': 'snippet',
        'order': 'date',
        'maxResults': NUM_VIDEOS,
        'type': 'video'
    }
    search_response = requests.get(search_url, params=search_params)
    items = search_response.json().get("items", [])
    video_ids = [item['id']['videoId'] for item in items]

    # Step 2: Get full metadata
    videos_url = "https://www.googleapis.com/youtube/v3/videos"
    videos_params = {
        "key": API_KEY,
        "id": ",".join(video_ids),
        "part": "snippet"
    }
    videos_response = requests.get(videos_url, params=videos_params)

    updated_log = existing_log.copy()
    for item in videos_response.json().get("items", []):
        video_id = item['id']
        title = item["snippet"]["title"]
        description = clean_description(item["snippet"]["description"])
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Update or append
        existing_entry = next((e for e in updated_log if e["video_id"] == video_id), None)
        if existing_entry:
            existing_entry.update({"title": title, "url": url, "description": description})
            print(f"🔄 Updated: {title}")
        else:
            updated_log.append({
                "video_id": video_id,
                "title": title,
                "url": url,
                "description": description
            })
            print(f"➕ Added: {title}")

    with open(JASON_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_log, f, indent=2)
    print("📦 Metadata JSON updated.")
    
def download_audio(video_url, output_path):
    print(f"🔻 Downloading audio from {video_url}")

    Path(AUDIO_FOLDER).mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(Path(AUDIO_FOLDER) / output_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': AUDIO_QUALITY,
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    print("✅ Audio downloaded.")
    
def download_mp3s_from_json():
    print("🎧 Checking audio downloads...")
    if not os.path.exists(JASON_PATH):
        print("⚠️ No JSON found.")
        return

    with open(JASON_PATH, "r", encoding="utf-8") as f:
        queue = json.load(f)

    updated = False
    for entry in queue:
        title = entry["title"]
        url = entry["url"]
        video_id = entry["video_id"]
        filename_without_extension = get_filename(title) 
        filename = get_filename(title) +".mp3"
        audio_path = str(Path(AUDIO_FOLDER) / filename)

        if "filename" in entry and os.path.exists(audio_path):
            print(f"⏩ Already downloaded: {filename}")
            continue

        download_audio(url, filename_without_extension)
        entry["filename"] = filename
        updated = True

    if updated:
        with open(JASON_PATH, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
        print("📦 JSON updated with filenames.")
        
def transcribe_and_append():
    print("🧠 Starting transcription...")
    if not os.path.exists(JASON_PATH):
        print("⚠️ No JSON found.")
        return

    with open(JASON_PATH, "r", encoding="utf-8") as f:
        queue = json.load(f)

    # Collect existing URLs from Markdown
    existing_urls = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("http"):
                    existing_urls.add(line.strip())

    model = whisper.load_model(MODEL_SIZE)

    for entry in queue:
        url = entry["url"]
        title = entry["title"]
        description = entry.get("description", "").strip()
        filename = entry.get("filename")
        audio_path = str(Path(AUDIO_FOLDER) / filename) if filename else None

        if url in existing_urls:
            print(f"⏩ Already transcribed: {title}")
            continue
        if not audio_path or not os.path.exists(audio_path):
            print(f"⚠️ Missing audio: {title}")
            continue

        print(f"🧘‍♀️ Transcribing: {title}")
        transcript = model.transcribe(audio_path)["text"]

        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(f"{title} ({url})\n")
            f.write(f"summary: {description}\n")
            f.write(f"transcript: {transcript}\n\n")

    print("🌸 Transcripts appended.")
    
def clean_description(text):
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"\[\d{1,2}:\d{2}(?::\d{2})?\]", "", text)
    return re.sub(r"\s+", " ", text).replace("Subtitles by the Amara.org community", "").strip()

def generate_transcripts_to_json():
    print("🧠 Starting transcript generation...")

    if not os.path.exists(JASON_PATH):
        print("⚠️ No JSON file found.")
        return

    with open(JASON_PATH, "r", encoding="utf-8") as f:
        queue = json.load(f)

    model = whisper.load_model(MODEL_SIZE)

    for entry in queue:
        filename = entry.get("filename")
        transcript = entry.get("transcript")

        if transcript:
            print(f"⏩ Already transcribed: {entry['title']}")
            continue

        if not filename:
            print(f"⚠️ Missing filename for: {entry['title']}")
            continue

        audio_path = str(Path(AUDIO_FOLDER) / filename)
        if not os.path.exists(audio_path):
            print(f"⚠️ Audio file not found: {audio_path}")
            continue

        print(f"🎙️ Transcribing: {entry['title']}")
        result = model.transcribe(audio_path)
        entry["transcript"] = result["text"].strip()

        with open(JASON_PATH, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
        print(f"📥 Updated JSON after: {entry['title']}")

        


if __name__=="__main__":
    update_video_metadata_json()
    download_mp3s_from_json()
    generate_transcripts_to_json()