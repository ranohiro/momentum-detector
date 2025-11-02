# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
from industry_name_mapping import industry_name_mapping

# === ディレクトリ準備 ===
raw_stock_dir = Path("data/raw/japan_all_stock")
raw_index_dir = Path("data/raw/tosho_index")
sector_dir = Path("data/processed_data/sector_summary")
momentum_dir = Path("data/processed_data/momentum_summary")
sector_dir.mkdir(parents=True, exist_ok=True)
momentum_dir.mkdir(parents=True, exist_ok=True)

# === 最新CSV取得 ===
stock_files = sorted(raw_stock_dir.glob("japan-all-stock-prices_*.csv"))
index_files = sorted(raw_index_dir.glob("tosho-index-data_*.csv"))
latest_stock = stock_files[-1]
latest_index = index_files[-1]

# 日付
date_str = latest_stock.stem.split("_")[-1]
date_slash = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
print(f"📅 対象日: {date_slash}")

# === CSV読込 ===
stock_df = pd.read_csv(latest_stock, encoding="cp932")
stock_df = stock_df[stock_df["業種"] != "株価指数"] # 「株価指数」を除外

index_df = pd.read_csv(latest_index, encoding="cp932")

# 日付列統一
for df in [stock_df, index_df]:
    if "日付" in df.columns:
        df["日付"] = pd.to_datetime(df["日付"]).dt.strftime("%Y/%m/%d")

# 業種名統一
stock_df["業種"] = stock_df["業種"].replace(industry_name_mapping)

# 数値化
stock_df["時価総額（百万円）"] = (
    stock_df["時価総額（百万円）"].astype(str).str.replace(",", "").replace("-", "0").astype(float)
)
stock_df["前日比"] = pd.to_numeric(stock_df["前日比"], errors="coerce").fillna(0)
stock_df["売買代金（千円）"] = pd.to_numeric(stock_df["売買代金（千円）"], errors="coerce").fillna(0)

# 時価総額帯分類
def classify_market_cap(x):
    if x < 10_000:
        return "小型"
    elif x < 100_000:
        return "中型"
    elif x < 1_000_000:
        return "大型"
    else:
        return "超大型"
stock_df["時価総額帯"] = stock_df["時価総額（百万円）"].apply(classify_market_cap)

# 上昇/下落フラグ
stock_df["上昇フラグ"] = stock_df["前日比"] > 0
stock_df["下落フラグ"] = stock_df["前日比"] <= 0

# === sector_summary 集計 ===
def aggregate_sector(stock_df, index_df):
    result = []
    grouped = stock_df.groupby(["業種", "時価総額帯"])
    for (industry, cap), group in grouped:
        up = group["上昇フラグ"].sum()
        down = group["下落フラグ"].sum()
        total_val = group["売買代金（千円）"].sum()
        if cap == "全体":
            weighted_avg = 0  # 後で全体を index_df から取得
        else:
            weighted_avg = (group["前日比（％）"] * group["時価総額（百万円）"]).sum() / max(group["時価総額（百万円）"].sum(),1)
        result.append({
            "日付": date_slash,
            "業種": industry,
            "時価総額帯": cap,
            "上昇銘柄数": int(up),
            "下落銘柄数": int(down),
            "時価総額加重平均騰落率": round(weighted_avg,3),
            "売買代金合計": int(total_val)
        })
    sector_df = pd.DataFrame(result)

    # 全体行追加
    new_rows = []
    for industry, group in sector_df.groupby("業種"):
        total_val = group["売買代金合計"].sum()
        weighted_avg = (group["時価総額加重平均騰落率"] * group["売買代金合計"]).sum() / max(total_val,1)
        new_rows.append({
            "日付": date_slash,
            "業種": industry,
            "時価総額帯": "全体",
            "上昇銘柄数": int(group["上昇銘柄数"].sum()),
            "下落銘柄数": int(group["下落銘柄数"].sum()),
            "時価総額加重平均騰落率": 0,  # 後で index_df から置換
            "売買代金合計": int(total_val)
        })
    sector_df = pd.concat([sector_df, pd.DataFrame(new_rows)], ignore_index=True)

    # 全体区分の平均騰落率を index_df から取得
    for idx, row in sector_df.iterrows():
        if row["時価総額帯"] == "全体":
            matched = index_df[index_df["指数名"] == row["業種"]]
            if not matched.empty:
                sector_df.at[idx, "時価総額加重平均騰落率"] = float(matched.iloc[0]["前日比（％）"])
    return sector_df

sector_df = aggregate_sector(stock_df, index_df)

# ランキング（全体）
ranking = sector_df[sector_df["時価総額帯"]=="全体"].copy()
ranking["平均騰落率順位"] = ranking["時価総額加重平均騰落率"].rank(ascending=False, method="min").astype(int)
sector_df = sector_df.merge(ranking[["業種","平均騰落率順位"]], on="業種", how="left")

# 保存
output_file = sector_dir / f"{date_str}_sector_summary.csv"
sector_df.to_csv(output_file, index=False, encoding="utf-8-sig")
print(f"✅ sector_summary 保存: {output_file}")

# === momentum_summary 集計 ===
def compute_momentum(stock_files, date_str):
    stock_files_sorted = sorted(stock_files)
    
    # 最新日ファイルのインデックス
    target_idx = [i for i,f in enumerate(stock_files_sorted) if f.stem.endswith(date_str)][0]
    # 過去20営業日分
    start_idx = max(0, target_idx-19)
    recent_files = stock_files_sorted[start_idx:target_idx+1]

    df_list = []
    for f in recent_files:
        df_tmp = pd.read_csv(f, encoding="cp932")

        if "業種" in df_tmp.columns:
            df_tmp = df_tmp[df_tmp["業種"] != "株価指数"] # ダミー行削除

        df_tmp["業種"] = df_tmp["業種"].replace(industry_name_mapping)
        val_col_candidates = [c for c in df_tmp.columns if "売買代金" in c]
        if not val_col_candidates:
            continue
        val_col = val_col_candidates[0]
        df_tmp["売買代金（千円）"] = pd.to_numeric(df_tmp[val_col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
        if "日付" in df_tmp.columns:
            df_tmp["日付"] = pd.to_datetime(df_tmp["日付"], format="%Y%m%d")
        df_list.append(df_tmp[["日付","業種","売買代金（千円）"]])
        # 過去20営業日分を結合
        df_concat = pd.concat(df_list, ignore_index=True)
        df_concat = df_concat.sort_values(["業種","日付"])

    # 日付ごと業種別売買代金合計
    daily_sum = df_concat.groupby(["日付","業種"], as_index=False)["売買代金（千円）"].sum()

    # 各業種ごとの rolling 平均
    for n in [3,5,10,20]:
        col_name = f"売買代金{n}日平均"
        daily_sum[col_name] = daily_sum.groupby("業種")["売買代金（千円）"].transform(
            lambda x: x.rolling(n, min_periods=1).mean()
        )

    # 比率計算
    daily_sum["売買代金5日平均/20日平均比率"] = (daily_sum["売買代金5日平均"] / daily_sum["売買代金20日平均"]).round(3)
    daily_sum["売買代金3日平均/10日平均比率"] = (daily_sum["売買代金3日平均"] / daily_sum["売買代金10日平均"]).round(3)

    # 最新日だけ抽出
    latest_date = daily_sum["日付"].max()
    momentum_df = daily_sum[daily_sum["日付"]==latest_date].copy()

    # 保存用に日付を "YYYY/MM/DD" に変換
    momentum_df["日付"] = momentum_df["日付"].dt.strftime("%Y/%m/%d")

    return momentum_df

momentum_df = compute_momentum(stock_files, date_str)

# 保存
momentum_file = momentum_dir / f"{date_str}_momentum_summary.csv"
momentum_df.to_csv(momentum_file, index=False, encoding="utf-8-sig")
print(f"✅ momentum_summary 保存: {momentum_file}")