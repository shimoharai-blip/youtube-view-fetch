import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

RAW_CSV = "view_history_hourly_raw.csv"
PROCESSED_CSV = "view_history_hourly_processed.csv"
REPORT_MD = "analysis_report.md"

# 4版のラベル
VERSION_MAP = {
    "T24rF_x0TmQ": "ABM",
    "xJQ6KrmdpD0": "EL6",
    "pRy8kStWlAw": "ShiyunBaau",
    "SnZvS3f5IrA": "KOMAINU"
}

# =========================
# CSV読み込み（raw）
# =========================
def load_csv():
    df = pd.read_csv(RAW_CSV)

    # ★ timestamp を完全統一（過去データも救済）
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    df = df.sort_values(["videoId", "timestamp"])
    return df

# =========================
# メトリクス計算（完全統合）
# =========================
def calc_metrics(df):
    gb = df.groupby("videoId")

    # 時速
    df["view_per_hour"] = gb["views"].diff().fillna(0)

    # rolling
    df["roll24"] = gb["view_per_hour"].transform(lambda x: x.rolling(24).mean())
    df["roll7"]  = gb["view_per_hour"].transform(lambda x: x.rolling(7).mean())
    df["rolling_base"] = df["roll24"].fillna(df["roll7"])

    # スパイク強度
    df["spike_strength"] = df["view_per_hour"] / df["rolling_base"].replace(0, np.nan)
    df["spike_strength"] = df["spike_strength"].fillna(0)

    # 版名付与
    df["version"] = df["videoId"].map(VERSION_MAP)

    return df

# =========================
# processed CSV 追記
# =========================
def save_processed(df):
    latest_rows = df.groupby("videoId").tail(1)

    if not latest_rows.empty:
        if pd.io.common.file_exists(PROCESSED_CSV):
            df_existing = pd.read_csv(PROCESSED_CSV)

            # ★ 過去の timestamp を datetime に統一
            df_existing["timestamp"] = pd.to_datetime(df_existing["timestamp"], errors="coerce")
            latest_rows["timestamp"] = pd.to_datetime(latest_rows["timestamp"], errors="coerce")

            # ★ 結合
            df_all = pd.concat([df_existing, latest_rows], ignore_index=True)

            # ★ 重複除去（videoId + timestamp）
            df_all = df_all.drop_duplicates(subset=["videoId", "timestamp"], keep="last")

            df_all.to_csv(PROCESSED_CSV, index=False)
        else:
            latest_rows.to_csv(PROCESSED_CSV, index=False)

# =========================
# 波及モデル（lag / strength）
# =========================
def detect_propagation(processed_df):
    report = []
    report.append("\n# 4版 波及モデル\n")

    spikes = processed_df[processed_df["spike_strength"] > 3]
    if len(spikes) == 0:
        report.append("スパイクなし → 波及なし\n")
        return report

    # 波及元（最強スパイク）
    source = spikes.sort_values("spike_strength", ascending=False).iloc[0]

    source_vid = source["videoId"]
    source_title = source["title"]
    source_time = pd.to_datetime(source["timestamp"])
    source_strength = source["spike_strength"]

    report.append(f"## 波及元: {source_title} ({source_vid})\n")
    report.append(f"- 強度: {source_strength:.2f}x\n")
    report.append(f"- 発生時刻: {source_time}\n")

    # 波及先
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
# レポート生成（ランキング＋波及モデル）
# =========================
def generate_report(df):
    md = []
    md.append("# 📊 自動分析レポート")
    md.append(f"生成時刻: **{datetime.now()}**\n")

    # ランキング
    gb = df.groupby("videoId")
    ranking = gb.agg(
        total_growth=("views", lambda x: x.iloc[-1] - x.iloc[0]),
        avg_hourly=("view_per_hour", "mean"),
        max_spike=("spike_strength", "max")
    ).sort_values("avg_hourly", ascending=False)

    md.append("## 🏆 成長速度ランキング\n")
    md.append(ranking.to_markdown())
    md.append("\n")

    # 波及モデル
    processed_df = pd.read_csv(PROCESSED_CSV)
    propagation = detect_propagation(processed_df)
    md.extend(propagation)

    # グラフ
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
