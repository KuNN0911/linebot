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
import os
import torch 

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    pipeline
)

app = Flask(__name__)

configuration = Configuration(access_token='5sz8JYIDMheE123GtSUc8VlpbKLagouytDCowyK5kSjXXZSMq6doCf0igbjb0JWwsKvJL11nR/htNRBxXWVQXh8FZPRJf1LedUfdtJ7/6NejPvSxfm4IP4ZecULRJhAgPmgmx47RqvDiUJDN8qOXDAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('3a6be77370fd217863d193383981aa63')

# 1. 加載模型和數據集
base_model = "/home/user/henry/CAG/Meta-Llama-3-8B-Instruct"  # 可以更換為其他支持長上下文的模型

# Bits and Bytes config for 4-bit quantization
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=False,
)

# 載入基礎模型並應用量化設置
model = AutoModelForCausalLM.from_pretrained(
    base_model,
    quantization_config=bnb_config, 
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True
)

# 載入 tokenizer
tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
tokenizer.padding_side = 'right'
tokenizer.pad_token = tokenizer.eos_token
tokenizer.add_eos_token = True

# 將模型載入至 GPU（如果可用）
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# 建立生成管線並指定 tokenizer
pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    torch_dtype=torch.float16,
    device_map="auto",
)

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
    messages = [
        {"role": "system", "content": "You are an AI customer service who is an expert in language models!"},
        {"role": "user", "content": question},
    ]
    
    outputs = pipe(
        messages,
        max_new_tokens=256,
    )
    
    # 提取生成的回答文本
    generated_text = outputs[0]["generated_text"]
    assistant_content = [item['content'] for item in generated_text if item['role'] == 'assistant']
    print(assistant_content[0])  # 如果只有一個 assistant 回答，則可以用這種方式
    return (assistant_content[0])

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    