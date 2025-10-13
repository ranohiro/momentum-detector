# google_sheets_uploader.py
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import glob
import os

# ------------------------------
# ① Googleスプレッドシート認証
# ------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"  # サービスアカウントJSON
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

# ------------------------------
# ② スプレッドシートID
# ------------------------------
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"
sh = gc.open_by_key(SPREADSHEET_ID)

# ------------------------------
# ③ 最新の processed CSV を取得
# ------------------------------
processed_dir = os.path.join("data", "processed")
csv_files = sorted(glob.glob(os.path.join(processed_dir, "sector_summary_*.csv")))
if not csv_files:
    raise FileNotFoundError("❌ Processed CSV が見つかりません")

csv_file = csv_files[-1]  # 最新ファイル
print(f"📄 Uploading CSV → {csv_file}")

# CSVを読み込み
df = pd.read_csv(csv_file)

# ------------------------------
# ④ sector_momentum_log（最新データは先頭に追加、100日分データ保持）
# ------------------------------
log_sheet = sh.worksheet("sector_momentum_log")

# 現在のデータを取得
existing_data = log_sheet.get_all_values()

# ヘッダー行があるか判定
header = existing_data[0] if existing_data else [
    "日付", "業種", "時価総額レンジ", "上昇銘柄数", "下落銘柄数", "平均騰落率", "売買代金合計", "出来高合計"
]
existing_body = existing_data[1:] if len(existing_data) > 1 else []

# 既存日付を取得（1列目）
existing_dates = [row[0] for row in existing_body] if existing_body else []

# 今回のCSV日付
csv_date = str(df["日付"].iloc[0])

if csv_date in existing_dates:
    print(f"⚠️ {csv_date} のデータは既に存在するため、追記をスキップします。")
else:
    # 新しいデータを上（2行目）に追加
    log_values = df.values.tolist()
    log_sheet.insert_rows(log_values, row=2)
    print(f"✅ {csv_date} のデータを先頭に追加しました ({len(log_values)} 行)")

    # データ総数を確認（ヘッダーを除く）
    updated_data = log_sheet.get_all_values()[1:]
    if len(updated_data) > 100:
        # 超過分を削除
        rows_to_delete = list(range(102, len(updated_data) + 2))  # 101行目以降（ヘッダー＋100営業日）
        for r in reversed(rows_to_delete):  # 後ろから削除
            log_sheet.delete_rows(r)
        print(f"🧹 古いデータを削除しました（100営業日を維持）")

# ------------------------------
# ⑤ トップ5 / ワースト5 作成
# ------------------------------
# "全体"の行のみ抽出
df_overall = df[df["時価総額レンジ"] == "全体"].copy()

# トップ5
df_top5 = df_overall.sort_values("平均騰落率", ascending=False).head(5)
df_top5 = df_top5.reset_index(drop=True)
df_top5["日付"] = csv_date
df_top5["区分"] = "Top5"
df_top5["ランク"] = range(1, len(df_top5)+1)
df_top5 = df_top5[["日付", "ランク", "区分", "業種", "平均騰落率"]]

# ワースト5
df_bottom5 = df_overall.sort_values("平均騰落率", ascending=True).head(5)
df_bottom5 = df_bottom5.reset_index(drop=True)
df_bottom5["日付"] = csv_date
df_bottom5["区分"] = "Worst5"
df_bottom5["ランク"] = range(1, len(df_bottom5)+1)
df_bottom5 = df_bottom5[["日付", "ランク", "区分", "業種", "平均騰落率"]]

# ------------------------------
# ⑥ top_sector_today 更新（ヘッダー付き）
# ------------------------------
top_sheet = sh.worksheet("top_sector_today")
top_sheet.clear()

# ✅ ヘッダー行を含めて出力
top_sheet.append_row(df_top5.columns.tolist())
top_sheet.append_rows(df_top5.values.tolist())

print("✅ top_sector_today（トップ5）更新完了")

# ------------------------------
# ⑦ bottom_sector_today 更新（新規追加）
# ------------------------------
# シートが存在しない場合は作成
try:
    bottom_sheet = sh.worksheet("bottom_sector_today")
except gspread.exceptions.WorksheetNotFound:
    bottom_sheet = sh.add_worksheet(title="bottom_sector_today", rows=50, cols=10)

bottom_sheet.clear()
bottom_sheet.append_row(df_bottom5.columns.tolist())
bottom_sheet.append_rows(df_bottom5.values.tolist())

print("✅ bottom_sector_today（ワースト5）更新完了")