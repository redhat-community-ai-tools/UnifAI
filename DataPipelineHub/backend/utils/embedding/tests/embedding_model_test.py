import requests
import os
import numpy as np
from langchain_openai import OpenAIEmbeddings
from config.app_config import AppConfig

config = AppConfig()

model_name = config.embedding_model_name # or your specific model name
base_url = config.embedding_model_base_url
api_key = config.embedding_model_api_key 

# Initialize the embeddings client
embeddings = OpenAIEmbeddings(
    model=model_name,
    openai_api_base=base_url,
    openai_api_key=api_key,
    tiktoken_enabled=False
)

# Test query
query = "This is a test sentence for embedding."
#query = "Hello, can you embed this sentence? Is this a test sentence? More and more and more."
#query = "This is a test sentence for embedding"

# Get embedding
vector = embeddings.embed_query(query)

# Optional: convert to numpy array
np_vector_openai = np.array(vector)

print("Embedding vector (first 5 values):", np_vector_openai[:5])
print("Vector length:", len(np_vector_openai))

##############################################################################################################################################
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

os.environ["REQUESTS_CA_BUNDLE"] = config.requests_ca_bundle

base_url = f"{config.embedding_model_base_url}/embeddings"
data = {
    "model": model_name,
    "input": query
}

res = requests.post(base_url, headers=headers, json=data)
np_vector_openai_direct_api = res.json()["data"][0]["embedding"]

print("Embedding vector (first 5 values):", np_vector_openai_direct_api[:5])
print("Vector length:", len(np_vector_openai_direct_api))

# Compare the generated embedding vectors between the two methods: direct API call and openai library
cos_sim = np.dot(np_vector_openai, np_vector_openai_direct_api) / (np.linalg.norm(np_vector_openai) * np.linalg.norm(np_vector_openai_direct_api))
print(f"Cosine similarity between vectors: {cos_sim:.4f}")


##############################################################################################################################################
# TODO: Here is the orignal code we have been using for embedding, relying on sentence_transformers library:

# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer("all-MiniLM-L6-v2")

# print(model.get_sentence_embedding_dimension())
# embeddings = model.encode(query, show_progress_bar=False)
