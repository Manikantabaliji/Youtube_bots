import os
import time
import csv
from flask import Flask, request, render_template_string, redirect, url_for
from threading import Thread
import yt_dlp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
app = Flask(__name__)
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DOWNLOAD_PATH = "downloaded_videos"
UPLOAD_INTERVAL = 10  # Upload interval in seconds (for testing)
URL_FILE = "video_urls.csv"
STATUS_FILE = "upload_status.txt"
SECRET_KEY = "mysecret123"  # Simple secret for securing routes

# Ensure necessary directories and files exist
for path in [DOWNLOAD_PATH]:
    if not os.path.exists(path):
        os.makedirs(path)
for file in [STATUS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            f.write("")
if not os.path.exists(URL_FILE):
    with open(URL_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["url"])

def authenticate_youtube():
    """
    Authenticate with YouTube API using OAuth 2.0 credentials.
    Returns a YouTube API client instance.
    """
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(port=8080)  # Use a fixed port
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)

def download_video(url, output_path):
    """
    Download a YouTube Short video using yt-dlp.
    Returns the path to the downloaded video or None if download fails.
    """
    try:
        ydl_opts = {
            "format": "best[ext=mp4]",
            "outtmpl": os.path.join(output_path, "%(id)s.%(ext)s"),
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = os.path.join(output_path, f"{info['id']}.mp4")
        with open(STATUS_FILE, "a") as f:
            f.write(f"Downloaded {url} to {video_path} at {time.ctime()}\n")
        return video_path
    except yt_dlp.utils.DownloadError as e:
        with open(STATUS_FILE, "a") as f:
            f.write(f"Error downloading {url}: {str(e)}\n")
        return None
    except Exception as e:
        with open(STATUS_FILE, "a") as f:
            f.write(f"Unexpected error downloading {url}: {str(e)}\n")
        return None

def upload_video(youtube, video_path, url):
    """
    Upload a downloaded video to YouTube using the YouTube API.
    Returns True if upload is successful, False otherwise.
    """
    try:
        request_body = {
            "snippet": {
                "title": f"Short Video - {time.strftime('%Y%m%d-%H%M%S')}",
                "description": "Automated upload of copyright-free Short video",
                "tags": ["shorts", "copyrightfree", "automated"],
                "categoryId": "22"  # People & Blogs category
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
        media = MediaFileUpload(video_path)
        upload_request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )
        response = upload_request.execute()
        with open(STATUS_FILE, "a") as f:
            f.write(f"Uploaded {url} as video ID: {response['id']} at {time.ctime()}\n")
        return True
    except Exception as e:
        with open(STATUS_FILE, "a") as f:
            f.write(f"Error uploading {url}: {str(e)}\n")
        return False

def process_videos():
    """
    Continuously process video URLs from the CSV file, download, and upload them.
    Handles retries and logs all actions.
    """
    youtube = authenticate_youtube()
    processed_videos = set()
    failed_attempts = {}

    while True:
        video_urls = []
        with open(URL_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            video_urls = [row["url"].strip() for row in reader if row["url"].strip()]

        for url in video_urls:
            if url not in processed_videos:
                with open(STATUS_FILE, "a") as f:
                    f.write(f"Processing {url} at {time.ctime()}\n")
                video_path = download_video(url, DOWNLOAD_PATH)
                if video_path:
                    success = upload_video(youtube, video_path, url)
                    if success:
                        processed_videos.add(url)
                        os.remove(video_path)
                    time.sleep(UPLOAD_INTERVAL)
                else:
                    failed_attempts[url] = failed_attempts.get(url, 0) + 1
                    if failed_attempts[url] >= 3:
                        processed_videos.add(url)
                        with open(STATUS_FILE, "a") as f:
                            f.write(f"Giving up on {url} after 3 failed attempts at {time.ctime()}\n")
                    time.sleep(60)

        if len(processed_videos) == len(video_urls) and video_urls:
            with open(STATUS_FILE, "a") as f:
                f.write(f"All videos processed. Waiting for new URLs at {time.ctime()}\n")
            time.sleep(24 * 3600)  # Wait 24 hours before resetting
            processed_videos.clear()
            failed_attempts.clear()
        else:
            time.sleep(60)

# Flask Routes
@app.route("/")
def home():
    """Redirect to the add_url page with the secret key."""
    return redirect(url_for("add_url", key=SECRET_KEY))

@app.route("/secret-add-url/<key>", methods=["GET", "POST"])
def add_url(key):
    """Handle adding URLs and displaying status. Requires secret key."""
    if key != SECRET_KEY:
        return "Unauthorized", 403

    if request.method == "POST":
        url = request.form.get("url")
        if url:
            with open(URL_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([url])
            return redirect(url_for("add_url", key=key))

    video_urls = []
    with open(URL_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        video_urls = [row["url"].strip() for row in reader if row["url"].strip()]

    with open(STATUS_FILE, "r") as f:
        status = f.readlines()[-10:]  # Show last 10 status updates

    return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>YouTube Shorts Automation</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; background-color: #f8f9fa; }
                .container { max-width: 800px; }
                .status-box { background-color: #fff; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="mb-4">YouTube Shorts Automation</h1>

                <form method="POST" class="mb-4">
                    <div class="input-group">
                        <input type="text" name="url" class="form-control" placeholder="Enter YouTube Shorts URL" required>
                        <button type="submit" class="btn btn-primary">Add URL</button>
                    </div>
                </form>

                <h3>Queued URLs</h3>
                <ul class="list-group mb-4">
                    {% if urls %}
                        {% for url in urls %}
                            <li class="list-group-item">{{ url }}</li>
                        {% endfor %}
                    {% else %}
                        <li class="list-group-item">No URLs in queue</li>
                    {% endif %}
                </ul>

                <h3>Status Updates</h3>
                <div class="status-box">
                    {% if status %}
                        {% for line in status %}
                            <p class="mb-1">{{ line }}</p>
                        {% endfor %}
                    {% else %}
                        <p>No status updates yet</p>
                    {% endif %}
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
    """, urls=video_urls, status=status)

if __name__ == "__main__":
    Thread(target=process_videos, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=True)