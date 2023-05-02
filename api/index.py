from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from api.chatgpt import ChatGPT

import os

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
working_status = os.getenv(
    "DEFALUT_TALKING", default="flase").lower() == "true"

app = Flask(__name__)
chatgpt = ChatGPT()

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
    "/指令查詢": "目前指令有：\n ✏ /日誌 \n ✏ /erp \n ✏ /信箱 \n ✏ /說話 (開啟機器人對話) \n ✏ /安靜 (關閉機器人對話) \n👉 記得加 / ❗",
    "/日誌": "https://reurl.cc/Y86yq4",
    "/erp": "https://reurl.cc/d756yq",
    "/信箱": "https://reurl.cc/6Nlrdk",
}


@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global working_status
    if event.message.type != "text":
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


if __name__ == "__main__":
    app.run()
