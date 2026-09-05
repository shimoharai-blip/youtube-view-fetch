import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

# CSV読み込み
def load_csv():
    df = pd.read_csv("view_history_hourly.csv", parse_dates=["timestamp"])
    df = df.sort_values(["video_id", "timestamp"])
    return df

# 時速・rolling・スパイク計算
def calc_metrics(df):
    gb = df.groupby("video_id")

    # 時速
    df["view_per_hour"] = gb["views"].diff()

    # rolling(24) + fallback rolling(7)
    df["roll24"] = gb["view_per_hour"].transform(lambda x: x.rolling(24).mean())
    df["roll7"]  = gb["view_per_hour"].transform(lambda x: x.rolling(7).mean())
    df["rolling_base"] = df["roll24"].fillna(df["roll7"])

    # スパイク強度
    df["spike_strength"] = df["view_per_hour"] / df["rolling_base"]

    return df

# 成長速度ランキング
def generate_ranking(df):
    gb = df.groupby("video_id")

    ranking = gb.agg(
        total_growth=("views", lambda x: x.iloc[-1] - x.iloc[0]),
        avg_hourly=("view_per_hour", "mean"),
        max_spike=("spike_strength", "max")
    )

    ranking["score"] = (
        ranking["total_growth"] * 0.4 +
        ranking["avg_hourly"] * 0.4 +
        ranking["max_spike"] * 0.2
    )

    return ranking.sort_values("score", ascending=False)

# スパイク検出
def detect_spikes(df):
    return df[df["spike_strength"] > 3]

# グラフ生成（高速化済み）
def generate_graphs(df):
    for vid, title in df[["video_id", "title"]].drop_duplicates().values:
        sub = df[df["video_id"] == vid]
        x = sub["timestamp"].values
        y = sub["view_per_hour"].values

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x, y, color="blue", linewidth=1.2)
        ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Views per hour")
        fig.tight_layout()

        fig.savefig(f"graph_{vid}.png", dpi=120)
        plt.close(fig)

# レポート生成（Markdown）
def generate_report(ranking, spikes, df):
    md = []
    md.append("# 自動分析レポート")
    md.append(f"生成時刻: {datetime.now()}\n")

    md.append("## 成長速度ランキング\n")
    md.append(ranking.to_markdown())

    md.append("\n## スパイク検出\n")
    if len(spikes) == 0:
        md.append("スパイクなし")
    else:
        md.append(spikes[["timestamp", "title", "view_per_hour", "spike_strength"]].to_markdown())

    md.append("\n## 時速グラフ\n")
    for vid, title in df[["video_id", "title"]].drop_duplicates().values:
        md.append(f"### {title}")
        md.append(f"![{title}](graph_{vid}.png)\n")

    with open("analysis_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

# メイン処理
def main():
    df = load_csv()
    df = calc_metrics(df)
    ranking = generate_ranking(df)
    spikes = detect_spikes(df)

    generate_graphs(df)
    generate_report(ranking, spikes, df)

main()
