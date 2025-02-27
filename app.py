import csv
import os
import time
from flask import Flask, request, render_template_string, redirect, url_for
from threading import Thread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import datetime
import pytz
from video_downloader import maintain_five_videos

# Configuration
app = Flask(__name__)
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
DOWNLOAD_PATH = "downloaded_videos"
STATUS_FILE = "upload_status.txt"
SECRET_KEY = "mysecret123"
ist = pytz.timezone('Asia/Kolkata')
upload_queue = []  # Queue for videos to be uploaded

# Authentication Function
def authenticate_youtube():
    """
    Authenticate with the YouTube API using OAuth 2.0.
    Returns a YouTube API client instance.
    """
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(port=8080)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)

# Upload Function
def upload_video(youtube, video_path, url):
    """
    Upload a video to YouTube with predefined title and tags.
    Returns True if successful, False otherwise.
    """
    try:
        request_body = {
            "snippet": {
                "title": "Dive into world of AI Cat",
                "description": "Automated upload of copyright-free Short video",
                "tags": ["#aicat", "#animals", "#catvideos", "#catlovers", "#tiger", "#animalvideos"],
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

# Scheduling Helper
def get_next_event(now):
    """
    Determine the next upload time based on current IST time (6 AM, 5 PM, 7 PM).
    Returns a tuple (next_event_time, action).
    """
    today = now.date()
    upload_times = [
        datetime.time(6, 0),   # 6 AM
        datetime.time(17, 0),  # 5 PM
        datetime.time(19, 0)   # 7 PM
    ]
    for t in upload_times:
        event_dt = ist.localize(datetime.datetime.combine(today, t))
        if now < event_dt:
            return event_dt, 'upload'
    # If all uploads today have passed, schedule for tomorrow's 6 AM
    tomorrow = today + datetime.timedelta(days=1)
    next_upload = ist.localize(datetime.datetime.combine(tomorrow, datetime.time(6, 0)))
    return next_upload, 'upload'

# Main Processing Function
def process_videos():
    """
    Maintain 5 downloaded videos and upload them at 6 AM, 5 PM, 7 PM IST.
    """
    youtube = authenticate_youtube()
    # Initial check to ensure 5 videos are downloaded
    maintain_five_videos()

    while True:
        now = datetime.datetime.now(ist)
        next_event_time, action = get_next_event(now)
        sleep_seconds = (next_event_time - now).total_seconds()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        if action == 'upload':
            current_videos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
            if current_videos:
                video_file = current_videos[0]  # Take the first video
                video_path = os.path.join(DOWNLOAD_PATH, video_file)
                # Using a placeholder URL since we don't track original URLs per file
                success = upload_video(youtube, video_path, f"video_{video_file}")
                if success:
                    os.remove(video_path)
                    maintain_five_videos()  # Download a new video to replace the uploaded one

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
            with open("video_urls.csv", "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([url])
            return redirect(url_for("add_url", key=key))

    video_urls = []
    with open("video_urls.csv", "r", newline="") as f:
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

# Main Execution
if __name__ == "__main__":
    Thread(target=process_videos, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=True)