import uuid
import os
import re
import structlog

from fastapi import HTTPException, APIRouter, Form
from qdrant_client import QdrantClient
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from datetime import datetime
from opencc import OpenCC

logger = structlog.get_logger()

# /home/user/anaconda3/envs/Bestat/bin/python -m uvicorn qa_api:app --host 0.0.0.0 --port 8020 --reload
router = APIRouter(
    tags=["Chatbot"]
)

# 配置參數
qdrant_host = "localhost"
qdrant_port = 6335
model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
cache_folder = '/home/user/henry/bestat_local/'
device = os.environ.get("DEVICE", 'cuda')  # 如果有 GPU，改為 'cuda'
similarity_threshold = 0.99

DB_HOST = os.environ.get("DB_HOST", "localhost")

# 初始化 Qdrant 客戶端
client = QdrantClient(host=DB_HOST, port=qdrant_port)

# 初始化嵌入模型
embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={'device': device},
    encode_kwargs={'normalize_embeddings': False},
    show_progress=True,
    cache_folder=cache_folder
)

def contains_simplified_chinese(text):
    # 使用 Unicode 範圍檢查是否包含簡體中文字符
    simplified_chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
    return bool(simplified_chinese_pattern.search(text))

# 使用者問答
@router.get("/get_answer/")
def get_answer(question: str):
    """
    根據用戶問題從 Qdrant 向量集合中檢索答案，並可使用大語言模型生成補充答案。\n

    :param question: 用戶的問題文本。\n
    :return: 包含檢索或生成的答案的 JSON 響應，例如 \n
        {
            "answer": "<生成的答案>",
            "id": "<唯一識別碼>"
        }。
    :raises HTTPException: \n
        - 如果 Qdrant 或 LLM 處理過程中發生錯誤，返回 500 狀態碼及具體錯誤信息。
    """
    try:
        # Step 1: 初始化必要變數
        try:
            now = datetime.now()
            formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
            ids = str(uuid.uuid4())
            qa_collection = "qa_set"
            history_collection = "qa_History"
        except Exception as e:
            logger.exception("Error initializing variables", exception=e)
            raise HTTPException(status_code=500, detail="Error initializing variables: " + str(e))

        # Step 2: 初始化 Qdrant 向量存儲
        try:
            qa_store = QdrantVectorStore(
                client=client,
                collection_name=qa_collection,
                embedding=embeddings,
            )
            history_store = QdrantVectorStore(
                client=client,
                collection_name=history_collection,
                embedding=embeddings,
            )
        except Exception as e:
            logger.exception("Error initializing Qdrant vector store", exception=e)
            raise HTTPException(status_code=500, detail="Error initializing Qdrant vector store: " + str(e))

        # Step 3: 執行相似性檢索
        try:
            qa_context = qa_store.similarity_search_with_score(question, k=3)
        except Exception as e:
            logger.exception("Error performing similarity search", exception=e)
            raise HTTPException(status_code=500, detail="Error performing similarity search: " + str(e))
        
        # Step 4: 解析檢索結果
        try:
            enhanced_docs = []
            for doc, score in qa_context:
                if score >= similarity_threshold:
                    response = doc.metadata.get('answer', "不好意思，未找到相關答案。")
                    qa_history = [Document(
                        page_content=f"問題:{question}\n答案:{response}",
                        metadata={
                            "id": ids,
                            "time": formatted_date,
                            "question": question,
                            "answer": response,
                            "type": "historyQA", 
                            "score": 3
                        }
                    )]
                    history_store.add_documents(documents=qa_history, ids=[ids])
                    return {"answer": response, "id": ids}
                elif score <= 0.3:
                    break
                formatted_context = f"[相關度分數: {score:.4f}] 問題:{doc.page_content} 答案:{doc.metadata.get('answer')} 類別:{doc.metadata.get('type')}"
                enhanced_docs.append(Document(page_content=formatted_context))
        except Exception as e:
            logger.exception("Error parsing similarity search results", exception=e)
            raise HTTPException(status_code=500, detail="Error parsing similarity search results: " + str(e))

        # Step 5: 使用 LLM 生成答案
        try:
            llm = OllamaLLM(model="llama3.1:8b-instruct-q8_0", temperature=0.1)
            if qa_context[0][1] >= 0.5:
                doc_prompt = PromptTemplate(
                    input_variables=["input", "context"],
                    template="""
                    You are a friendly assistant for **Bestat Biotechnology Co., Ltd.**. Please adhere to the following guidelines:  

                    1. Respond to the user based on the potentially relevant background information provided below in a kind and friendly manner.  
                    2. Only provide answers based on the facts given; do not make up information.  
                    3. Answer the user's question directly.  
                    4. Avoid over-explaining or providing unnecessary information.  
                    5. Do not under any circumstances ask the user questions or seek clarification. Provide only direct answers or responses.
                    6. Respond in the language used by the user.

                    **User's Question:**  
                    {input}  

                    **Potentially Relevant Background Information:**  
                    {context}  

                    Based on the potentially relevant background information above, provide a friendly and professional response to the user's question.  
                    If there is no relevant information in the background provided, answer the user's question directly.  

                    Begin response to the user's question:(The generated response must not include above paragraph)
                    """
                )
                document_chain = doc_prompt | llm
                response = document_chain.invoke({"input": question, "context": enhanced_docs})
            else:
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
                
            qa_history = [Document(
                page_content=f"問題:{question}\n答案:{response}",
                metadata={
                    "id": ids,
                    "time": formatted_date,
                    "question": question,
                    "answer": response,
                    "type": "historyQA", 
                    "score": 3
                }
            )]
            history_store.add_documents(documents=qa_history, ids=[ids])

            return {"answer": response, "id": ids}
        except Exception as e:
            logger.exception("Error generating answer with LLM", exception=e)
            raise HTTPException(status_code=500, detail="Error generating answer with LLM: " + str(e))

    except Exception as e:
        logger.exception("Unhandled error in get_answer", exception=e)
        raise HTTPException(status_code=500, detail="Unhandled error: " + str(e))
    
# 更新qa_History評分
@router.patch("/qa_History/update_score/", summary="更新qa_History評分")
async def update_score(
    id: str = Form(...),  # 問答對的唯一標識符
    score: int = Form(...)  # 必填的新分數
):
    """
    根據 ID 更新指定問答對的評分。\n

    :param id: 要更新的問答對 ID。\n
    :param score: 新的評分內容（整數）。\n
    :return: 包含成功消息的 JSON 響應，例如 {"message": "QA History score with ID 'example_id' updated successfully."}。\n
    :raises HTTPException: \n
        - 如果指定的 ID 不存在，返回 404 狀態碼。
        - 如果更新過程發生錯誤，返回 500 狀態碼及錯誤詳情。
    """
    try:
        # Step 1: 初始化 Qdrant 向量存儲
        try:
            collection_name = "qa_History"  # 預設集合名稱
            vector_store = QdrantVectorStore(
                client=client,
                collection_name=collection_name,
                embedding=embeddings,
            )
        except Exception as e:
            logger.exception("Error initializing Qdrant vector store", exception=e)
            raise HTTPException(status_code=500, detail="Error initializing Qdrant vector store: " + str(e))
        
        # Step 2: 根據 ID 檢索數據點
        try:
            existing_docs = client.retrieve(
                collection_name=collection_name,
                ids=[id]
            )
            if not existing_docs:
                raise HTTPException(status_code=404, detail=f"QA pair with ID '{id}' not found in Qdrant collection.")
        except Exception as e:
            logger.exception("Error retrieving data from Qdrant", exception=e)
            raise HTTPException(status_code=500, detail="Error retrieving data from Qdrant: " + str(e))

        # Step 3: 更新數據並重新插入
        try:
            # 取出已存在的數據點
            existing_doc = existing_docs[0]

            # 更新分數並嵌入新數據
            updated_doc = Document(
                page_content=existing_doc.payload["page_content"],
                metadata={
                    "id": id,
                    "time": existing_doc.payload["metadata"]["time"],
                    "question": existing_doc.payload["metadata"]["question"],
                    "answer": existing_doc.payload["metadata"]["answer"],
                    "type": existing_doc.payload["metadata"]["type"],
                    "score": score
                },
            )

            # 用相同的 ID 更新到 Qdrant 集合中
            vector_store.add_documents(
                documents=[updated_doc],
                ids=[id],
            )

        except Exception as e:
            logger.exception("Error updating QA History score", exception=e)
            raise HTTPException(status_code=500, detail="Error updating QA History score: " + str(e))

        # 成功返回
        return {"message": f"QA History score with ID '{id}' updated successfully."}

    except Exception as e:
        logger.exception("Unhandled error in update_score", exception=e)
        raise HTTPException(status_code=500, detail="Unhandled error: " + str(e))
