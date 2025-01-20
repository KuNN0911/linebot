# from flask import Flask, request, abort

# from linebot.v3 import (
#     WebhookHandler
# )
# from linebot.v3.exceptions import (
#     InvalidSignatureError
# )
# from linebot.v3.messaging import (
#     Configuration,
#     ApiClient,
#     MessagingApi,
#     ReplyMessageRequest,
#     TextMessage
# )
# from linebot.v3.webhooks import (
#     MessageEvent,
#     TextMessageContent
# )
# from response import get_answer
# import os

# app = Flask(__name__)

# configuration = Configuration(access_token='5sz8JYIDMheE123GtSUc8VlpbKLagouytDCowyK5kSjXXZSMq6doCf0igbjb0JWwsKvJL11nR/htNRBxXWVQXh8FZPRJf1LedUfdtJ7/6NejPvSxfm4IP4ZecULRJhAgPmgmx47RqvDiUJDN8qOXDAdB04t89/1O/w1cDnyilFU=')
# handler = WebhookHandler('3a6be77370fd217863d193383981aa63')


# @app.route("/callback", methods=['POST'])
# def callback():
#     # Get the signature from the request header
#     signature = request.headers.get('X-Line-Signature')
#     body = request.get_data(as_text=True)

#     # Log request details for debugging
#     app.logger.info(f"Request body: {body}")
#     app.logger.info(f"Request signature: {signature}")

#     try:
#         handler.handle(body, signature)
#     except InvalidSignatureError:
#         app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
#         return 'Invalid signature', 400

#     return 'OK', 200

# @handler.add(MessageEvent, message=TextMessageContent)
# def handle_message(event):
#     user_input = event.message.text  # 使用者的問題
#     # 使用 get_answer 函數處理問題
#     response = get_answer(question=user_input)
    
#     # 發送回應給使用者
#     with ApiClient(configuration) as api_client:
#         line_bot_api = MessagingApi(api_client)
#         line_bot_api.reply_message_with_http_info(
#             ReplyMessageRequest(
#                 reply_token=event.reply_token,
#                 messages=[TextMessage(text=response)]
#             )
#         )

# if __name__ == "__main__":
#     app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
import os
import json
import logging
from flask import Flask, request, abort, Response
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, QuickReply, QuickReplyItem, MessageAction
)
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from response import get_answer  # 引入 get_answer 函數

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 Flask 應用
app = Flask(__name__)

# 初始化 Line Bot API
configuration = Configuration(access_token='5sz8JYIDMheE123GtSUc8VlpbKLagouytDCowyK5kSjXXZSMq6doCf0igbjb0JWwsKvJL11nR/htNRBxXWVQXh8FZPRJf1LedUfdtJ7/6NejPvSxfm4IP4ZecULRJhAgPmgmx47RqvDiUJDN8qOXDAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('3a6be77370fd217863d193383981aa63')

# 設置 Prometheus 指標
MESSAGES_PROCESSED = Counter('messages_processed_total', 'Total number of messages processed')
RESPONSE_TIME = Histogram('response_time_seconds', 'Response time in seconds')

def create_text_message(text, quick_reply=None):
    if quick_reply:
        return TextMessage(text=text, quick_reply=quick_reply)
    return TextMessage(text=text)

def create_quick_reply():
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="選項1", text="選項1")),
        QuickReplyItem(action=MessageAction(label="選項2", text="選項2"))
    ])

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_input = event.message.text.strip()
    try:
        # 使用 get_answer 處理文字回應
        response = get_answer(question=user_input)

        # 發送回應給使用者
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[create_text_message(response, create_quick_reply())]
                )
            )
    except Exception as e:
        logger.error(f"處理消息時出錯: {str(e)}")
        error_message = create_text_message("抱歉，處理時發生錯誤。請稍後再試。")
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[error_message]
                )
            )

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8081))
    app.run(host='0.0.0.0', port=port, debug=False)
