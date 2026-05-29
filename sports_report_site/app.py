import os
import requests
from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UC_VGGub9Va3XpVs4s-Ld2Zw")


def get_latest_videos(max_results=6):
    if not YOUTUBE_API_KEY:
        print("No YouTube API key found.")
        return []

    uploads_playlist_id = YOUTUBE_CHANNEL_ID.replace("UC", "UU", 1)

    url = "https://www.googleapis.com/youtube/v3/playlistItems"

    params = {
        "key": YOUTUBE_API_KEY,
        "playlistId": uploads_playlist_id,
        "part": "snippet",
        "maxResults": max_results,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    print(data)

    videos = []

    for item in data.get("items", []):
        snippet = item["snippet"]
        video_id = snippet["resourceId"]["videoId"]

        videos.append({
            "title": snippet["title"],
            "thumbnail": snippet["thumbnails"]["high"]["url"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    return videos


@app.route("/")
def home():
    videos = get_latest_videos()

    print(videos)

    return render_template("index.html", videos=videos)


if __name__ == "__main__":
    app.run(debug=True)