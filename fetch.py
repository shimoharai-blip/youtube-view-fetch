import os
import csv
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

API_KEY = os.getenv("YOUTUBE_API_KEY")
CSV_FILE = "view_history_hourly_raw.csv"

VIDEO_IDS = [
    "T24rF_x0TmQ",
    "xJQ6KrmdpD0",
    "pRy8kStWlAw",
    "SnZvS3f5IrA",
]

def get_timestamp_jst():
    JST = timezone(timedelta(hours=9))
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

def fetch_views():
    print("DEBUG: API_KEY =", API_KEY)

    youtube = build("youtube", "v3", developerKey=API_KEY)
    print("DEBUG: YouTube client built")

    now = get_timestamp_jst()
    print("DEBUG: Timestamp =", now)

    rows = []

    for i in range(0, len(VIDEO_IDS), 50):
        batch = VIDEO_IDS[i:i+50]
        print("DEBUG: Fetching batch:", batch)

        v = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(batch)
        ).execute()

        print("DEBUG: API response:", v)

        for item in v.get("items", []):
            title = item["snippet"]["title"]
            views = int(item["statistics"].get("viewCount", 0))
            print("DEBUG: Parsed:", item["id"], views)
            rows.append([now, item["id"], title, views])

    print("DEBUG: Rows collected:", rows)

    new_file = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            print("DEBUG: Writing header")
            w.writerow(["timestamp", "videoId", "title", "views"])
        print("DEBUG: Appending rows to CSV")
        w.writerows(rows)

    print(f"{now} 完了（GitHub Actions）")
    return rows

def main():
    fetch_views()

if __name__ == "__main__":
    main()
