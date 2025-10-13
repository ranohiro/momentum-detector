import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# === Google Sheets 接続設定 ===
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"
SOURCE_SHEET = "sector_momentum_log"
OUTPUT_SHEET = "momentum_ranking"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# === データ取得 ===
ws = sh.worksheet(SOURCE_SHEET)
data = pd.DataFrame(ws.get_all_records())

# === データ前処理 ===
# 空行・NaN行の除外
data = data.dropna(subset=["日付", "業種", "時価総額レンジ", "売買代金合計"], how="any")

# 日付列を安全に変換（変換できない値はNaTにして除外）
data["日付"] = pd.to_datetime(data["日付"], format="%Y/%m/%d", errors="coerce")
data = data.dropna(subset=["日付"])

# 型変換（売買代金合計をfloat化）
data["売買代金合計"] = pd.to_numeric(data["売買代金合計"], errors="coerce")
data = data.dropna(subset=["売買代金合計"])

# === 集計処理 ===
result_list = []

for (sector, cap_range), group in data.groupby(["業種", "時価総額レンジ"]):
    group = group.sort_values("日付")

    if len(group) < 5:
        continue  # データ不足の場合はスキップ

    # 売買代金の移動平均
    group["avg_5d"] = group["売買代金合計"].rolling(window=5).mean()
    group["avg_20d"] = group["売買代金合計"].rolling(window=20).mean()

    # 比率（流入度合い）
    group["ratio"] = group["avg_5d"] / group["avg_20d"]

    # 連続増加日数
    inc = (group["売買代金合計"].diff() > 0)
    count = 0
    consecutive = []
    for flag in inc:
        if flag:
            count += 1
        else:
            count = 0
        consecutive.append(count)
    group["連続増加日数"] = consecutive

    # 最新日だけ抽出
    latest = group.iloc[-1]
    result_list.append({
        "日付": latest["日付"].strftime("%Y/%m/%d"),
        "業種": sector,
        "時価総額レンジ": cap_range,
        "5日平均": round(latest["avg_5d"], 0) if pd.notnull(latest["avg_5d"]) else None,
        "20日平均": round(latest["avg_20d"], 0) if pd.notnull(latest["avg_20d"]) else None,
        "比率(5日/20日)": round(latest["ratio"], 2) if pd.notnull(latest["ratio"]) else None,
        "連続増加日数": latest["連続増加日数"],
        "モメンタム方向": "流入" if latest["ratio"] > 1 else "流出"
    })

# === 出力 ===
df_out = pd.DataFrame(result_list)
if df_out.empty:
    print("⚠️ 有効なデータが見つかりませんでした。")
else:
    df_out = df_out.sort_values("比率(5日/20日)", ascending=False).reset_index(drop=True)
    df_out["順位"] = df_out.index + 1

    # Google Sheets 出力
    try:
        ws_out = sh.worksheet(OUTPUT_SHEET)
        ws_out.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws_out = sh.add_worksheet(title=OUTPUT_SHEET, rows="500", cols="10")

    ws_out.update([df_out.columns.values.tolist()] + df_out.values.tolist())
    print("✅ モメンタム分析が完了しました。")