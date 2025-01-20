# import os
# import json
# import logging
# from flask import Flask, request, abort
# from linebot.v3 import WebhookHandler
# from linebot.v3.exceptions import InvalidSignatureError

# from linebot.v3.messaging import (
#     Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
#     TextMessage, QuickReply, QuickReplyItem, MessageAction
# )
# from response import get_answer  # 引入 RAG 回應功能

# # 配置日誌
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # # 載入環境變量
# # from dotenv import load_dotenv
# # load_dotenv()

# # 初始化 Flask 應用
# app = Flask(__name__)

# # 初始化 Line Bot API
# configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
# handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# # 快速回覆選項
# def create_quick_reply():
#     return QuickReply(items=[
#         QuickReplyItem(action=MessageAction(label="選項1", text="選項1")),
#         QuickReplyItem(action=MessageAction(label="選項2", text="選項2"))
#     ])

# def create_text_message(text, quick_reply=None):
#     if quick_reply:
#         return TextMessage(text=text, quick_reply=quick_reply)
#     return TextMessage(text=text)

# @app.route("/callback", methods=['POST'])
# def callback():
#     signature = request.headers['X-Line-Signature']
#     body = request.get_data(as_text=True)
#     logger.info("Request body: " + body)
#     try:
#         handler.handle(body, signature)
#     except InvalidSignatureError:
#         logger.error("無效的簽名。請檢查您的頻道訪問令牌/頻道密鑰。")
#         abort(400)
#     return 'OK'

# @handler.add(MessageEvent, message=TextMessageContent)
# def handle_text_message(event):
#     user_id = event.source.user_id
#     text = event.message.text.strip()
#     logger.info(f'{user_id}: {text}')

#     try:
#         # 使用 RAG 回應邏輯
#         response_data = get_answer(question=text)
#         answer = response_data.get("answer", "抱歉，我無法處理您的問題。請稍後再試！")

#         # 構建回覆訊息
#         messages = [create_text_message(answer, create_quick_reply())]

#         # 發送回覆
#         with ApiClient(configuration) as api_client:
#             line_bot_api = MessagingApi(api_client)
#             line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages))

#     except Exception as e:
#         logger.error(f"處理消息時出錯: {str(e)}")
#         error_message = create_text_message("抱歉，似乎出現了一個問題。讓我們稍後再試。")
#         with ApiClient(configuration) as api_client:
#             line_bot_api = MessagingApi(api_client)
#             line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[error_message]))

# if __name__ == "__main__":
#     port = int(os.environ.get('PORT', 5000))
#     app.run(host='0.0.0.0', port=port)
from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

app = Flask(__name__)

configuration = Configuration(access_token='YOUR_CHANNEL_ACCESS_TOKEN')
handler = WebhookHandler('YOUR_CHANNEL_SECRET')


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )

import os

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)