import os
import csv
import yt_dlp
import time

# Configuration
DOWNLOAD_PATH = "downloaded_videos"
URL_FILE = "video_urls.csv"
STATUS_FILE = "upload_status.txt"

def download_video(url, output_path):
    """
    Download a YouTube Shorts video using yt-dlp.
    Returns the path to the downloaded video or None if the download fails.
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

def maintain_five_videos():
    """
    Ensure there are always 5 videos in DOWNLOAD_PATH by downloading from URL_FILE as needed.
    """
    # Ensure directories and files exist
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
    if not os.path.exists(URL_FILE):
        with open(URL_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url"])
    if not os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "w") as f:
            f.write("")

    # Count current videos
    current_videos = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
    videos_needed = 5 - len(current_videos)

    if videos_needed > 0:
        with open(URL_FILE, "r", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if len(rows) <= 1:  # Only header, no URLs
            with open(STATUS_FILE, "a") as f:
                f.write(f"No URLs available to download at {time.ctime()}\n")
            return

        urls = [row[0] for row in rows[1:] if row]
        to_download = urls[:videos_needed]  # Take only what's needed
        successful_downloads = []

        for url in to_download:
            video_path = download_video(url, DOWNLOAD_PATH)
            if video_path:
                successful_downloads.append(url)

        # Update URL_FILE, removing only successful downloads
        remaining_urls = [url for url in urls if url not in successful_downloads]
        with open(URL_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url"])
            for url in remaining_urls:
                writer.writerow([url])