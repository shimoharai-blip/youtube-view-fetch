import os
import csv
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

API_KEY = os.getenv("YOUTUBE_API_KEY")
CSV_FILE = "view_history_hourly_raw.csv"   # ★生データ専用CSVに変更

# ★収集したい動画ID（4版）
VIDEO_IDS = [
    "T24rF_x0TmQ",   # ABM 本家
    "xJQ6KrmdpD0",   # EL6
    "pRy8kStWlAw",   # しゆん×ばぁう
    "SnZvS3f5IrA",   # KOMAINU
]

# ============================
# JST タイムスタンプ
# ============================
def get_timestamp_jst():
    JST = timezone(timedelta(hours=9))
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

# ============================
# YouTube API → 再生数取得（生データ専用）
# ============================
def fetch_views():
    youtube = build("youtube", "v3", developerKey=API_KEY)
    now = get_timestamp_jst()
    rows = []

    # API 呼び出し（50件バッチ処理はそのまま）
    for i in range(0, len(VIDEO_IDS), 50):
        batch = VIDEO_IDS[i:i+50]
        v = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(batch)
        ).execute()

        for item in v["items"]:
            title = item["snippet"]["title"]
            views = int(item["statistics"].get("viewCount", 0))
            rows.append([now, item["id"], title, views])

    # ★ CSV ヘッダー安全化（空ファイルでも必ず書く）
    new_file = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "videoId", "title", "views"])
        w.writerows(rows)

    print(f"{now} 完了（GitHub Actions）")
    return rows

# ============================
# メイン処理（fetch専用）
# ============================
def main():
    fetch_views()

if __name__ == "__main__":
    main()
