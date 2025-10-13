import pandas as pd
from linebot import LineBotApi
from linebot.models import FlexSendMessage
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# -----------------------------
# 1. 設定
# -----------------------------
LINE_CHANNEL_TOKEN = "vJmDAp8HblPph+TnPMLPXxFvYYt/7DI9RPUMa11RenAx/fKUft1yil7GJHecW7/yiN26gCg8UVoWx21wdHA+bFZCP1x6NhBCV109rul1ZDtvQUkfgPe4U6WMpUNPYoR4auUkOkrBaTGvDok3OU18wwdB04t89/1O/w1cDnyilFU="
RECIPIENT_ID = "ranohiro9868"

GOOGLE_SHEET_ID = "1CTRQdjsgFsRPgRdsT_c_rJheztivNAa1gyTKjxL-QR4"
SERVICE_ACCOUNT_FILE = "credentials.json"  # サービスアカウントJSON

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)

# -----------------------------
# 2. Google Sheets読込関数
# -----------------------------
def read_sheet(sheet_name: str):
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=GOOGLE_SHEET_ID, range=f"{sheet_name}!A1:Z100").execute()
    values = result.get("values", [])
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    return df

# -----------------------------
# 3. Flex用テキスト生成
# -----------------------------
def make_sector_text(df, title):
    if df.empty:
        return f"{title}\nデータなし"
    lines = [title]
    for _, row in df.iterrows():
        name = row["業種"]
        if "平均騰落率" in row:
            rate = float(row["平均騰落率"])
            lines.append(f"{name} {rate:+.2f}%")
        elif "比率(5日/20日)" in row:
            flow = float(row["比率(5日/20日)"])
            streak = row.get("連続増加日数", "1")
            lines.append(f"{name} {flow:+.2f}% ({streak}日連続)")
    return "\n".join(lines)

# -----------------------------
# 4. メイン処理
# -----------------------------
def main():
    top_df = read_sheet("top_sector_today")
    bottom_df = read_sheet("bottom_sector_today")
    flow_df = read_sheet("momentum_ranking")

    top_text = make_sector_text(top_df, "📊 上昇セクタートップ")
    bottom_text = make_sector_text(bottom_df, "📉 下落セクターワースト")
    flow_text = make_sector_text(flow_df, "💰 資金流入ランキング（全体）")

    full_text = f"{top_text}\n\n{bottom_text}\n\n{flow_text}"

    # Flex Message作成
    flex_message = FlexSendMessage(
        alt_text="業種別モメンタム速報",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": full_text,
                        "wrap": True,
                        "size": "md"
                    }
                ]
            }
        }
    )

    # 送信
    line_bot_api.push_message(RECIPIENT_ID, flex_message)
    print("✅ LINE送信完了")

if __name__ == "__main__":
    main()