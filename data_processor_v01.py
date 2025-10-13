from this import d
from xml.etree.ElementInclude import include
import pandas as pd
import datetime
import os
import glob
import re

def process_latest_csv():
    # 1. 最新CSVを取得
    raw_dir = os.path.join("data", "raw")
    csv_files = sorted(glob.glob(os.path.join(raw_dir, "japan-all-stock-prices_*.csv")))
    if not csv_files:
        print("❌ CSVファイルが見つかりません")
        return None

    latest_csv = csv_files[-1]
    print(f"📄 Processing CSV: {latest_csv}")

    # ファイル名から日付抽出
    match = re.search(r"japan-all-stock-prices_(\d{8})\.csv", latest_csv)
    if match:
        file_date_str = match.group(1)
    else:
        file_date_str = datetime.date.today().strftime("%Y%m%d")
        print("ファイル名取得不可のため、実行日を使用します。")

    # 2. CSV読み込み
    df = pd.read_csv(latest_csv, encoding="cp932")

    # 「株価指数」を除外
    df = df[df["業種"] != "株価指数"]

    # 数値列変換
    df["前日比（％）"] = pd.to_numeric(df["前日比（％）"], errors="coerce")
    df["売買代金（千円）"] = pd.to_numeric(df["売買代金（千円）"], errors="coerce")
    df["出来高"] = pd.to_numeric(df["出来高"], errors="coerce")
    df["時価総額（百万円）"] = pd.to_numeric(df["時価総額（百万円）"], errors="coerce").fillna(0)

    # 値上がり／値下がりを判定
    df["値上がり"] = df["前日比（％）"] > 0
    df["値下がり"] = df["前日比（％）"] < 0

    # -------------------------------
    # 📅 日付列の追加,　整形
    # -------------------------------
    if pd.api.types.is_numeric_dtype(df["日付"]):
        # 数値をYYYYMMDD形式とする
        df["日付"] = df["日付"].astype(str).str.extract(r"(\d{8})")[0]
        df["日付"] = pd.to_datetime(df["日付"], format="%Y%m%d", errors="coerce")
    else:
        df["日付"] = pd.to_datetime(df["日付"], errors="coerce")

    # 全てNaTの場合は今日の日付で補完
    if df["日付"].isna().all():
        df["日付"] = pd.to_datetime(datetime.date.today())
    # 日付のみ抽出（時刻除去）
    df["日付"] = df["日付"].dt.date
    # 表示用に "YYYY/MM/DD" 形式へ変換
    df["日付"] = df["日付"].apply(lambda x: x.strftime("%Y/%m/%d"))

    # -------------------------------
    # 🧠 時価総額レンジ分類
    # -------------------------------
    def classify_market_cap(x):
        if x < 10_000:       # 100億円未満
            return "小型"
        elif x < 100_000:    # 1000億未満
            return "中型"
        elif x < 1_000_000:  # 1兆未満
            return "大型"
        else:
            return "超大型"

    df["時価総額レンジ"] = df["時価総額（百万円）"].apply(classify_market_cap)

    # -------------------------------
    # 🧾 加重平均関数
    # -------------------------------
    def weighted_avg(subdf):
        total = (subdf["前日比（％）"] * subdf["時価総額（百万円）"]).sum()
        weight = subdf["時価総額（百万円）"].sum()
        return round(total / weight, 2) if weight != 0 else 0.00

    # -------------------------------
    # 🧾 日付＋業種＋レンジ別 集計
    # -------------------------------
    grouped = df.groupby(["日付", "業種", "時価総額レンジ"]).apply(
        lambda x: pd.Series({
            "上昇銘柄数": x["値上がり"].sum(),
            "下落銘柄数": x["値下がり"].sum(),
            "平均騰落率": weighted_avg(x),
            "売買代金合計": x["売買代金（千円）"].sum(),
            "出来高合計": x["出来高"].sum(),
        }), 
    include_groups=False
    ).reset_index()

    # -------------------------------
    # 📊 業種単位（日付別・全体）
    # -------------------------------
    total_sector = df.groupby(["日付", "業種"]).apply(
        lambda x: pd.Series({
            "上昇銘柄数": x["値上がり"].sum(),
            "下落銘柄数": x["値下がり"].sum(),
            "平均騰落率": weighted_avg(x),
            "売買代金合計": x["売買代金（千円）"].sum(),
            "出来高合計": x["出来高"].sum(),
        }), 
    include_groups=False
    ).reset_index()
    total_sector["時価総額レンジ"] = "全体"

    # -------------------------------
    # 📝 結合・出力整形
    # -------------------------------
    final_df = pd.concat([grouped, total_sector], ignore_index=True)
    final_df = final_df[[
        "日付", "業種", "時価総額レンジ", "上昇銘柄数", "下落銘柄数", "平均騰落率", "売買代金合計", "出来高合計"
    ]]

    # -------------------------------
    # 💾 出力
    # -------------------------------
    processed_dir = os.path.join("data", "processed")
    os.makedirs(processed_dir, exist_ok=True)
    today = datetime.datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(processed_dir, f"sector_summary_{file_date_str}.csv")

    final_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ Multi-day Sector + MarketCap summary saved → {output_file}")

    return output_file


if __name__ == "__main__":
    process_latest_csv()