from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from api.chatgpt import ChatGPT

import os
import urllib
import json
import base64

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# 從環境變數中讀取 Base64 編碼的憑證
base64_cred = os.environ['FIREBASE_SERVICE_ACCOUNT_KEY']

# 將 Base64 編碼的憑證解碼為 JSON 字串
json_cred = base64.b64decode(base64_cred).decode("utf-8")

# 將 JSON 字串轉換成 Python 字典
cred_dict = json.loads(json_cred)

# 使用憑證初始化 Firebase Admin SDK
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)


line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
working_status = os.getenv(
    "DEFALUT_TALKING", default="flase").lower() == "true"

client_id = os.getenv('NOTIFY_CLIENT_ID')
client_secret = os.getenv('NOTIFY_CLIENT_SECRET')
redirect_uri = f"https://{os.getenv('YOUR_VERCEL_APP_NAME')}.vercel.app/callback/notify"


app = Flask(__name__)
chatgpt = ChatGPT()


@app.route('/')
def home():
    return 'Hello, World!'


@app.route('/send-reminder', methods=['GET'])
def send_reminder():
    return send_weekly_reminder(request)


@app.route("/callback/notify", methods=['GET'])
def callback_nofity():
    assert request.headers['referer'] == 'https://notify-bot.line.me/'
    code = request.args.get('code')
    state = request.args.get('state')

    # 接下來要繼續實作的函式
    access_token = get_token(code, client_id, client_secret, redirect_uri)

    db = firestore.client()
    doc_ref = db.collection(u'users').document(state)
    doc_ref.set({
        'access_token': access_token
    })

    return '恭喜完成 LINE Notify 連動！請關閉此視窗。'


def create_auth_link(user_id, client_id=client_id, redirect_uri=redirect_uri):

    data = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'notify',
        'state': user_id
    }
    query_str = urllib.parse.urlencode(data)

    return f'https://notify-bot.line.me/oauth/authorize?{query_str}'


def get_token(code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri):
    url = 'https://notify-bot.line.me/oauth/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    page = urllib.request.urlopen(req).read()

    res = json.loads(page.decode('utf-8'))
    return res['access_token']


def send_message(access_token, text_message, picurl):

    url = 'https://notify-api.line.me/api/notify'
    headers = {"Authorization": "Bearer " + access_token}

    data = {'message': text_message}

    data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    page = urllib.request.urlopen(req).read()


def handle_message(event):
    global working_status


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
    "/指令查詢": "目前指令有：\n  /日報 \n  /erp \n  /信箱 \n  /連動日報提醒 \n  /說話 (開啟機器人對話) \n  /安靜 (關閉機器人對話) \n 👉 記得加 / ❗",
    "/日報": "https://reurl.cc/Y86yq4",
    "/erp": "https://reurl.cc/d756yq",
    "/信箱": "https://reurl.cc/6Nlrdk",
}


@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global working_status
    if event.message.type != "text":
        return

    # 如果用戶輸入的訊息是 "/連動 Line Notify"
    if event.message.text == "/連動日報提醒":
        # 創建 LINE Notify 的連結
        link = create_auth_link(event.source.user_id)
        # 使用 LineBotAPI 的 push_message 函數來傳送訊息給用戶
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text=f'請點擊以下連結以連動 LINE Notify: {link}'))
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
