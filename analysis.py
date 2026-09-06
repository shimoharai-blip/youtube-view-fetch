import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

def parse_ts(x):
    if pd.isna(x):
        return pd.NaT

    x = str(x).strip()

    formats = [
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(x, fmt)
        except ValueError:
            continue

    return pd.NaT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_CSV = os.path.join(BASE_DIR, "view_history_hourly_raw.csv")
PROCESSED_CSV = os.path.join(BASE_DIR, "view_history_hourly_processed.csv")
REPORT_MD = os.path.join(BASE_DIR, "analysis_report.md")

VERSION_MAP = {
    "T24rF_x0TmQ": "ABM",
    "xJQ6KrmdpD0": "EL6",
    "pRy8kStWlAw": "ShiyunBaau",
    "SnZvS3f5IrA": "KOMAINU"
}

# =========================
# CSV読み込み（raw）
# =========================
import time

def load_csv():
    print("=== DEBUG: RAW_CSV path ===")
    print("RAW_CSV =", RAW_CSV)

    print("=== DEBUG: RAW_CSV absolute path ===")
    print("abs =", os.path.abspath(RAW_CSV))

    print("=== DEBUG: RAW_CSV exists? ===")
    print("exists =", os.path.exists(RAW_CSV))

    if os.path.exists(RAW_CSV):
        print("=== DEBUG: RAW_CSV file stats ===")
        st = os.stat(RAW_CSV)
        print("size =", st.st_size, "bytes")
        print("mtime =", time.ctime(st.st_mtime))

    df = pd.read_csv(RAW_CSV)
    df["timestamp"] = df["timestamp"].apply(parse_ts)

    # ★ 過去の壊れた行（timestamp 空欄）を完全除去
    df = df.dropna(subset=["timestamp"])

    # ★ 丸め処理（秒を切り捨てて分単位に統一）
    df["timestamp"] = df["timestamp"].dt.floor("min")

    print("=== RAW CSV 読み込み直後の timestamp 最新20行 ===")
    print(df.sort_values("timestamp").tail(20)[["timestamp", "videoId", "views"]])

    df = df.sort_values(["videoId", "timestamp"])
    return df

# =========================
# メトリクス計算（完全統合）
# =========================
def calc_metrics(df):
    gb = df.groupby("videoId")

    # =========================
    # 1. 実時間差（時間）
    # =========================
    df["time_diff_hours"] = gb["timestamp"].diff().dt.total_seconds() / 3600

    # =========================
    # 2. views 差分
    # =========================
    df["views_diff"] = gb["views"].diff()

    # =========================
    # 3. view_per_hour（views_diff ÷ 実時間差）
    # =========================
    df["view_per_hour"] = df.apply(
        lambda row: row["views_diff"] / row["time_diff_hours"]
        if row["time_diff_hours"] and row["time_diff_hours"] > 0 else 0,
        axis=1
    )

    # =========================
    # 4. 過去24時間平均（時間ベース rolling）
    # =========================
    df["roll24"] = gb.apply(
        lambda g: g.set_index("timestamp")["view_per_hour"].rolling("24h").mean()
    ).reset_index(level=0, drop=True)

    # =========================
    # 5. 過去7時間平均（時間ベース rolling）
    # =========================
    df["roll7"] = gb.apply(
        lambda g: g.set_index("timestamp")["view_per_hour"].rolling("7h").mean()
    ).reset_index(level=0, drop=True)

    # =========================
    # 6. rolling_base（24H優先 → fallback 7H）
    # =========================
    df["rolling_base"] = df["roll24"].fillna(df["roll7"])

    # =========================
    # 7. spike_strength（本物のスパイク強度）
    # =========================
    df["spike_strength"] = df["view_per_hour"] / df["rolling_base"].replace(0, np.nan)
    df["spike_strength"] = df["spike_strength"].fillna(0)

    # =========================
    # 8. version
    # =========================
    df["version"] = df["videoId"].map(VERSION_MAP)

    return df

# =========================
# processed CSV 追記
# =========================
def save_processed(df):
    df = df.dropna(subset=["timestamp", "videoId", "views"])

    latest_rows = df.groupby("videoId").tail(1)
    print("=== latest_rows ===")
    print(latest_rows[["timestamp", "videoId", "views"]])
    
    if not latest_rows.empty:
        if pd.io.common.file_exists(PROCESSED_CSV):
            df_existing = pd.read_csv(PROCESSED_CSV)

            df_existing["timestamp"] = pd.to_datetime(df_existing["timestamp"], errors="coerce")
            df_existing = df_existing.dropna(subset=["timestamp", "videoId", "views"])

            latest_rows["timestamp"] = latest_rows["timestamp"].apply(parse_ts)

            # ★ 丸め処理（raw と processed の timestamp を完全一致させる）
            df_existing["timestamp"] = df_existing["timestamp"].dt.floor("min")
            latest_rows["timestamp"] = latest_rows["timestamp"].dt.floor("min")

            df_all = pd.concat([df_existing, latest_rows], ignore_index=True)

            df_all = df_all.drop_duplicates(subset=["videoId", "timestamp"], keep="last")

            df_all.to_csv(PROCESSED_CSV, index=False)
        else:
            latest_rows.to_csv(PROCESSED_CSV, index=False)

# =========================
# 波及モデル
# =========================
def detect_propagation(processed_df):
    report = []
    report.append("\n# 4版 波及モデル\n")

    spikes = processed_df[processed_df["spike_strength"] > 3]
    if len(spikes) == 0:
        report.append("スパイクなし → 波及なし\n")
        return report

    source = spikes.sort_values("spike_strength", ascending=False).iloc[0]

    source_vid = source["videoId"]
    source_title = source["title"]
    source_time = pd.to_datetime(source["timestamp"])
    source_strength = source["spike_strength"]

    report.append(f"## 波及元: {source_title} ({source_vid})\n")
    report.append(f"- 強度: {source_strength:.2f}x\n")
    report.append(f"- 発生時刻: {source_time}\n")

    for _, row in spikes.iterrows():
        if row["videoId"] == source_vid:
            continue

        target_time = pd.to_datetime(row["timestamp"])
        lag = (target_time - source_time).total_seconds() / 3600
        strength = row["spike_strength"] / source_strength * 100

        report.append(f"\n### {source_title} → {row['title']}")
        report.append(f"- lag: {lag:.1f}h")
        report.append(f"- strength: {strength:.1f}%")

    return report

# =========================
# グラフ生成
# =========================
def generate_graphs(df):
    for vid, title in df[["videoId", "title"]].drop_duplicates().values:
        sub = df[df["videoId"] == vid]
        x = sub["timestamp"].values
        y = sub["view_per_hour"].values

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x, y, color="blue", linewidth=1.2)

        spikes = sub[sub["spike_strength"] > 3]
        if len(spikes) > 0:
            ax.scatter(spikes["timestamp"], spikes["view_per_hour"], color="red", s=30)

        ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Views per hour")
        fig.tight_layout()

        fig.savefig(f"graph_{vid}.png", dpi=120)
        plt.close(fig)

# =========================
# レポート生成
# =========================
def generate_report(df):
    md = []
    md.append("# 📊 自動分析レポート")
    md.append(f"生成時刻: **{datetime.now()}**\n")

    gb = df.groupby("videoId")
    ranking = gb.agg(
        total_growth=("views", lambda x: x.iloc[-1] - x.iloc[0]),
        avg_hourly=("view_per_hour", "mean"),
        max_spike=("spike_strength", "max")
    ).sort_values("avg_hourly", ascending=False)

    md.append("## 🏆 成長速度ランキング\n")
    md.append(ranking.to_markdown())
    md.append("\n")

    processed_df = pd.read_csv(PROCESSED_CSV)
    processed_df["timestamp"] = processed_df["timestamp"].apply(parse_ts)
    processed_df["timestamp"] = processed_df["timestamp"].dt.floor("min")
    processed_df["spike_strength"] = pd.to_numeric(processed_df["spike_strength"], errors="coerce")
    processed_df = processed_df.dropna(subset=["timestamp"])

    propagation = detect_propagation(processed_df)
    md.extend(propagation)

    md.append("\n## 📈 時速グラフ（各版）\n")
    for vid, title in df[["videoId", "title"]].drop_duplicates().values:
        md.append(f"### {title}")
        md.append(f"![{title}](graph_{vid}.png)\n")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

# =========================
# メイン処理
# =========================
def main():
    df = load_csv()
    df = calc_metrics(df)
    save_processed(df)
    generate_graphs(df)
    generate_report(df)
    print("analysis.py 完了：processed CSV とレポートを更新しました")

main()
