import os
import csv
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
import pandas as pd

API_KEY = os.getenv("YOUTUBE_API_KEY")
CSV_FILE = "view_history_hourly.csv"

# ★収集したい動画ID（4版）
VIDEO_IDS = [
    "T24rF_x0TmQ",   # 本家
    "xJQ6KrmdpD0",   # EL6
    "pRy8kStWlAw",   # ばぁう
    "SnZvS3f5IrA",   # KOMAINU
]

# ============================
# JST タイムスタンプ
# ============================
def get_timestamp_jst():
    JST = timezone(timedelta(hours=9))
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")

# ============================
# YouTube API → 再生数取得
# ============================
def fetch_views():
    youtube = build("youtube", "v3", developerKey=API_KEY)
    now = get_timestamp_jst()
    rows = []

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
# 4版：海外流入スパイク検出
# ============================
def detect_spikes(csv_file):
    df = pd.read_csv(csv_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print("\n=== 海外流入スパイク検出（4版） ===")

    for vid in df["videoId"].unique():
        d = df[df["videoId"] == vid].sort_values("timestamp").copy()

        if len(d) < 25:
            print(f"{vid}: データ不足（判定不可）")
            continue

        d["diff"] = d["views"].diff()

        last3 = d["diff"].tail(3).mean()
        last24 = d["diff"].tail(24).mean()

        hour = d["timestamp"].iloc[-1].hour
        night_or_morning = (hour <= 8) or (hour >= 23)

        spike = (last3 > last24 * 1.4) and night_or_morning
        title = d["title"].iloc[-1]

        if spike:
            print(f"★ {title}（{vid}）: 海外流入スパイク検出")
        else:
            print(f"  {title}（{vid}）: スパイクなし")

        print(f"    直近3時間平均: {last3:.0f}, 直近24時間平均: {last24:.0f}")

# ============================
# 4版：海外流入強度スコア（0〜100）
# ============================
def calc_intensity(csv_file):
    df = pd.read_csv(csv_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print("\n=== 海外流入強度（Intensity）計算 ===")

    for vid in df["videoId"].unique():
        d = df[df["videoId"] == vid].sort_values("timestamp").copy()

        if len(d) < 2:
            print(f"{vid}: データ不足")
            continue

        d["diff"] = d["views"].diff()
        last_speed = d["diff"].iloc[-1]

        domestic = 800  # 国内基準
        intensity = max(0, min(100, (last_speed - domestic) / 3000 * 100))

        title = d["title"].iloc[-1]

        print(f"{title}（{vid}）")
        print(f"  最新時速: {last_speed:.0f}/h")
        print(f"  海外流入強度: {intensity:.1f} / 100")

# ============================
# メイン処理（完全統合版）
# ============================
def main():
    fetch_views()
    detect_spikes(CSV_FILE)
    calc_intensity(CSV_FILE)

if __name__ == "__main__":
    main()
