from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from api.chatgpt import ChatGPT
from apscheduler.schedulers.background import BackgroundScheduler
import os

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
working_status = os.getenv(
    "DEFALUT_TALKING", default="flase").lower() == "true"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
db = SQLAlchemy(app)
chatgpt = ChatGPT()


class Subscriber(db.Model):
    id = db.Column(db.String(50), primary_key=True)


db.create_all()

# domain root


@app.route('/')
def home():
    return 'Hello, World!'


@app.route("/webhook", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# 定義關鍵字字典
keywords = {
    "/指令查詢": "目前指令有：\n ✏ /日報 \n ✏ /erp \n ✏ /信箱 \n ✏ /說話 (開啟機器人對話) \n ✏ /安靜 (關閉機器人對話) \n👉 記得加 / ❗",
    "/日報": "https://reurl.cc/Y86yq4",
    "/erp": "https://reurl.cc/d756yq",
    "/信箱": "https://reurl.cc/6Nlrdk",
}


@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global working_status
    if event.message.type != "text":
        return

    if event.message.text == "/訂閱":
        # 增加訂閱者
        subscriber = Subscriber(id=event.source.user_id)
        if subscriber is None:
        subscriber = Subscriber(id=event.source.user_id)
        db.session.add(subscriber)
        db.session.commit()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="您已成功訂閱！"))
        else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="您已經訂閱。"))
        return

    if event.message.text == "/取消訂閱":
        # 移除訂閱者
    subscriber = Subscriber.query.get(event.source.user_id)
    if subscriber is None:
        db.session.delete(subscriber)
        db.session.commit()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="您已取消訂閱每週日誌提醒。"))
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="您尚未訂閱。"))
        return

    if event.message.text == "/說話":
        working_status = True
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="開啟機器人對話，可輸入 👉 /指令查詢 👈 "))
        return

    if event.message.text == "/安靜":
        working_status = False
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="關閉機器人對話，輸入 👉 /說話 👈 則再次開啟😻"))
        return

    if event.message.text in keywords:
        # 回覆
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=keywords[event.message.text]))
        return

    if working_status:
        chatgpt.add_msg(f"HUMAN:{event.message.text}?\n")
        reply_msg = chatgpt.get_response().replace("AI:", "", 1)
        chatgpt.add_msg(f"AI:{reply_msg}\n")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_msg))


def send_reminder():
    subscribers = Subscriber.query.all()
    for subscriber in subscribers:
        try:
            line_bot_api.push_message(subscriber.id, TextSendMessage(
                text="請記得填寫日報，連結如下：\nhttps://reurl.cc/Y86yq4"))
        except LineBotApiError as e:
            print(f"無法發送訊息給 {subscriber.id}: {e}")
            # 移除已封鎖機器人或已刪除帳戶的用戶
            db.session.delete(subscriber)
            db.session.commit()


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminder, 'cron', day_of_week='sun', hour=9)
    # scheduler.add_job(send_reminder, 'interval', seconds=1)
    scheduler.start()

    app.run()
