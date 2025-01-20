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
import re
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from opencc import OpenCC
import os

app = Flask(__name__)

configuration = Configuration(access_token='5sz8JYIDMheE123GtSUc8VlpbKLagouytDCowyK5kSjXXZSMq6doCf0igbjb0JWwsKvJL11nR/htNRBxXWVQXh8FZPRJf1LedUfdtJ7/6NejPvSxfm4IP4ZecULRJhAgPmgmx47RqvDiUJDN8qOXDAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('3a6be77370fd217863d193383981aa63')


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
    user_input = event.message.text  # 使用者的問題
    # 使用 get_answer 函數處理問題
    response = get_answer(question=user_input)
    
    # 發送回應給使用者
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=response)]
            )
        )
def contains_simplified_chinese(text):
    # 使用 Unicode 範圍檢查是否包含簡體中文字符
    simplified_chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
    return bool(simplified_chinese_pattern.search(text))

def get_answer(question: str):
    llm = OllamaLLM(model="llama3.1:8b-instruct-q8_0", temperature=0.1, base_url="http://localhost:11436")
    casual_prompt = PromptTemplate(
        input_variables=["input"],
        template="""
        You are a friendly assistant for **Bestat Biotechnology Co., Ltd.**. Please adhere to the following guidelines:  

        1. Respond to the user in a kind and friendly manner.  
        2. Answer the user's question directly.  
        3. Do not under any circumstances ask the user questions or seek clarification. Provide only direct answers or responses.
        4. Respond in the language used by the user.


        **User's Question:**
        {input}  

        Begin response to the user's question: (The generated response must not include above paragraph)
        """
    )
    casual_chain = casual_prompt | llm
    response = casual_chain.invoke({"input": question})

    if contains_simplified_chinese(response):
        converter = OpenCC('s2t')  # 簡體轉繁體
        response = converter.convert(response)

    return response

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    