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

import os

app = Flask(__name__)

configuration = Configuration(access_token='CHANNEL_ACCESS_TOKEN')
handler = WebhookHandler('CHANNEL_SECRET')


@app.route("/callback", methods=['POST'])
def callback():
    # Get the signature from the request header
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    # Log request details for debugging
    app.logger.info(f"Request body: {body}")
    app.logger.info(f"Request signature: {signature}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        return 'Invalid signature', 400

    return 'OK', 200


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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
