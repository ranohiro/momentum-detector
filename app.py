from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi, MessagingApiBlob
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhook.models import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
import os

# Flaskアプリ初期化
app = Flask(__name__)

# LINEの環境変数（HerokuのConfig Varsに設定します）
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")

# Messaging APIとWebhookパーサーをセットアップ
parser = WebhookParser(LINE_CHANNEL_SECRET)
messaging_api = MessagingApi(channel_access_token=LINE_CHANNEL_TOKEN)

@app.route("/")
def home():
    return "Momentum Bot is running on Heroku 🚀"

# LINEからのWebhookを受け取る
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(400)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            user_message = event.message.text
            reply_text = f"あなたのメッセージ: {user_message}\n（このBotは稼働しています）"
            messaging_api.reply_message(
                reply_token=event.reply_token,
                messages=[{"type": "text", "text": reply_text}]
            )

    return "OK"

if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", 5000)))