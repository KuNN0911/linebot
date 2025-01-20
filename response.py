import uuid
import os
import re
import structlog

from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from opencc import OpenCC

logger = structlog.get_logger()

def contains_simplified_chinese(text):
    # 使用 Unicode 範圍檢查是否包含簡體中文字符
    simplified_chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
    return bool(simplified_chinese_pattern.search(text))

# 使用者問答
def get_answer(question: str):
    # Step 1: 使用 LLM 生成答案
    llm = OllamaLLM(model="llama3.1:8b-instruct-q8_0", temperature=0.1)
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
