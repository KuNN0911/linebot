from qdrant_client import QdrantClient

# 連接到本地 Qdrant
client = QdrantClient(host="localhost", port=6335)

# 列出所有集合
collections = client.get_collections()
print(collections)
