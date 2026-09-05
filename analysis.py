import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

# =========================
# CSV読み込み（高速 & 安定）
# =========================
def load_csv():
    df = pd.read_csv("view_history_hourly.csv", parse_dates=["timestamp"])

    # 列名の統一（fetch.py に合わせる）
    df = df.rename(columns={
        "videoId": "videoId",
        "title": "title",
        "views": "views",
        "timestamp": "timestamp"
    })

    if "videoId" not in df.columns:
        raise ValueError("CSV に videoId 列がありません。fetch.py の出力を確認してください。")

    df = df.sort_values(["videoId", "timestamp"])
    return df


# =========================
# メトリクス計算（高速化）
# =========================
def calc_metrics(df):
    gb = df.groupby("videoId")

    # 時速（numpyで高速化）
    df["view_per_hour"] = gb["views"].diff().fillna(0)

    # rolling(24) + fallback rolling(7)
    df["roll24"] = gb["view_per_hour"].transform(lambda x: x.rolling(24).mean())
    df["roll7"]  = gb["view_per_hour"].transform(lambda x: x.rolling(7).mean())
    df["rolling_base"] = df["roll24"].fillna(df["roll7"])

    # スパイク強度（誤検出防止）
    df["spike_strength"] = df["view_per_hour"] / df["rolling_base"].replace(0, np.nan)
    df["spike_strength"] = df["spike_strength"].fillna(0)

    return df


# =========================
# 成長速度ランキング（精度改善）
# =========================
def generate_ranking(df):
    gb = df.groupby("videoId")

    ranking = gb.agg(
        total_growth=("views", lambda x: x.iloc[-1] - x.iloc[0]),
        avg_hourly=("view_per_hour", "mean"),
        max_spike=("spike_strength", "max")
    )

    # 正規化（スコアの偏りを防ぐ）
    ranking["norm_growth"] = ranking["total_growth"] / ranking["total_growth"].max()
    ranking["norm_hourly"] = ranking["avg_hourly"] / ranking["avg_hourly"].max()
    ranking["norm_spike"]  = ranking["max_spike"] / ranking["max_spike"].max()

    ranking["score"] = (
        ranking["norm_growth"] * 0.4 +
        ranking["norm_hourly"] * 0.4 +
        ranking["norm_spike"]  * 0.2
    )

    return ranking.sort_values("score", ascending=False)


# =========================
# スパイク検出（精度改善）
# =========================
def detect_spikes(df):
    return df[df["spike_strength"] > 3]


# =========================
# 海外流入検出（深夜・早朝・日中の伸びを比較）
# =========================
def detect_overseas_inflow(df):
    df["hour"] = df["timestamp"].dt.hour

    late = df[(df["hour"] >= 23) | (df["hour"] <= 3)]
    early = df[(df["hour"] >= 4) & (df["hour"] <= 8)]
    daytime = df[(df["hour"] >= 10) & (df["hour"] <= 17)]

    def ratio(sub):
        if len(sub) == 0:
            return 0
        return (sub["view_per_hour"].mean() /
                sub["rolling_base"].mean())

    late_ratio = ratio(late)
    early_ratio = ratio(early)
    day_ratio = ratio(daytime)

    score = (late_ratio + early_ratio + day_ratio) / 3

    return {
        "late_ratio": late_ratio,
        "early_ratio": early_ratio,
        "day_ratio": day_ratio,
        "score": score
    }


# =========================
# グラフ生成（高速化）
# =========================
def generate_graphs(df):
    for vid, title in df[["videoId", "title"]].drop_duplicates().values:
        sub = df[df["videoId"] == vid]
        x = sub["timestamp"].values
        y = sub["view_per_hour"].values

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x, y, color="blue", linewidth=1.2)

        # スパイク点を赤でマーキング
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
# レポート生成（海外流入統合）
# =========================
def generate_report(ranking, spikes, df):
    md = []

    md.append("# 📊 自動分析レポート")
    md.append(f"生成時刻: **{datetime.now()}**\n")

    # ハイライト
    top = ranking.iloc[0]
    md.append("## 🔥 今日のハイライト\n")
    md.append(f"- **最も伸びた動画**: {top.name}")
    md.append(f"- **総成長**: {int(top.total_growth):,} views")
    md.append(f"- **平均時速**: {top.avg_hourly:.1f} views/h")
    md.append(f"- **最大スパイク**: {top.max_spike:.2f}x\n")

    # ランキング
    md.append("## 🏆 成長速度ランキング\n")
    md.append(ranking.to_markdown())
    md.append("\n")

    # スパイク検出
    md.append("## ⚡ スパイク検出\n")
    if len(spikes) == 0:
        md.append("> **スパイクなし（安定しています）**\n")
    else:
        md.append("> **スパイク発生！** 以下の時間帯で急増が確認されました。\n")
        md.append(spikes[["timestamp", "title", "view_per_hour", "spike_strength"]].to_markdown())
    md.append("\n")

    # 海外流入検出
    md.append("## 🌏 海外流入の検出\n")
    overseas = detect_overseas_inflow(df)

    md.append(f"- 深夜帯の強度: **{overseas['late_ratio']:.2f}x**")
    md.append(f"- 早朝帯の強度: **{overseas['early_ratio']:.2f}x**")
    md.append(f"- 日中帯の強度: **{overseas['day_ratio']:.2f}x**")
    md.append(f"- 総合スコア: **{overseas['score']:.2f}**\n")

    if overseas["score"] >= 0.7:
        md.append("> **海外流入が強く再発しています（スパイク前兆）**\n")
    elif overseas["score"] >= 0.4:
        md.append("> **弱い海外流入が発生中（再発の前兆）**\n")
    else:
        md.append("> **海外流入は観測されていません（国内中心）**\n")

    md.append("\n")

    # グラフ
    md.append("## 📈 時速グラフ（各版）\n")
    for vid, title in df[["videoId", "title"]].drop_duplicates().values:
        md.append(f"### {title}")
        md.append(f"![{title}](graph_{vid}.png)\n")

    with open("analysis_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))


# =========================
# メイン処理
# =========================
def main():
    df = load_csv()
    df = calc_metrics(df)
    ranking = generate_ranking(df)
    spikes = detect_spikes(df)

    generate_graphs(df)
    generate_report(ranking, spikes, df)

main()
