# g_sheets_multi_uploader.py（範囲指定版）
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import glob
import os
import re
from datetime import datetime

# ------------------------------
# ① Googleスプレッドシート認証
# ------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

# ------------------------------
# ② スプレッドシート設定
# ------------------------------
SPREADSHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"
sh = gc.open_by_key(SPREADSHEET_ID)
log_sheet = sh.worksheet("sector_momentum_log")

# ------------------------------
# ③ アップロード対象CSVを取得
# ------------------------------
processed_dir = os.path.join("data", "processed")
csv_files = sorted(glob.glob(os.path.join(processed_dir, "sector_summary_*.csv")))
if not csv_files:
    raise FileNotFoundError("❌ Processed CSV が見つかりません")

# ------------------------------
# ④ 日付範囲指定
# ------------------------------
# YYYY-MM-DD形式で指定
start_date = datetime.strptime("2025-09-25", "%Y-%m-%d").date()
end_date = datetime.strptime("2025-10-10", "%Y-%m-%d").date()

# CSVファイル名から日付抽出＆範囲フィルタ
def extract_date_from_filename(path):
    m = re.search(r"sector_summary_(\d{8})\.csv", path)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    return None

csv_files_to_upload = [
    f for f in csv_files
    if extract_date_from_filename(f) and start_date <= extract_date_from_filename(f) <= end_date
]

if not csv_files_to_upload:
    print("⚠️ 指定範囲内のCSVファイルはありません。")
    exit()

print(f"📦 アップロード対象CSV数: {len(csv_files_to_upload)} 件")

# ------------------------------
# ⑤ 既存データの確認
# ------------------------------
existing_data = log_sheet.get_all_values()
existing_body = existing_data[1:] if len(existing_data) > 1 else []
existing_dates = [row[0] for row in existing_body] if existing_body else []

# ------------------------------
# ⑥ CSVを順次アップロード
# ------------------------------
for csv_file in csv_files_to_upload:
    df = pd.read_csv(csv_file)
    csv_date = str(df["日付"].iloc[0])

    if csv_date in existing_dates:
        print(f"⚠️ {csv_date} のデータは既に存在するためスキップします。")
        continue

    log_values = df.values.tolist()
    log_sheet.insert_rows(log_values, row=2)
    print(f"✅ {csv_date} のデータをアップロードしました ({len(log_values)} 行)")

print("🎉 指定範囲分のアップロードが完了しました。")