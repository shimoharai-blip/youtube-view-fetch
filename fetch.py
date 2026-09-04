import os
import csv
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

API_KEY = os.getenv("YOUTUBE_API_KEY")
CSV_FILE = "view_history_hourly.csv"

# ★ここに収集したい動画IDを入れる（自由に追加OK）
VIDEO_IDS = [
    "T24rF_x0TmQ",
    "xJQ6KrmdpD0",
    "pRy8kStWlAw",
    "SnZvS3f5IrA",
]

def main():
    youtube = build("youtube", "v3", developerKey=API_KEY)

    # ★ JST（日本時間）に固定
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    rows = []

    # 50件ずつバッチ処理
    for i in range(0, len(VIDEO_IDS), 50):
        batch = VIDEO_IDS[i:i+50]
        v = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(batch)
        ).execute()

        for item in v["items"]:
            title = item["snippet"]["title"]
            views = item["statistics"].get("viewCount", 0)
            rows.append([now, item["id"], title, views])

    new_file = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "videoId", "title", "views"])
        w.writerows(rows)

    print(f"{now} 完了（GitHub Actions）")

if __name__ == "__main__":
    main()
