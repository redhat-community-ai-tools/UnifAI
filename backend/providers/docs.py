import base64
import os
import tempfile
from typing import List
from flask import jsonify
from config.app_config import AppConfig
from utils.storage.mongo.mongo_storage import MongoStorage
from shared.logger import logger
from global_utils.utils.util import get_mongo_url
from werkzeug.utils import secure_filename
from providers.data_sources import initialize_embedding_generator, initialize_vector_storage
from config.constants import SourceType
import pymongo

app_config = AppConfig.get_instance()
upload_folder = app_config.upload_folder

mongo_client = pymongo.MongoClient(get_mongo_url())
data_source_repo = MongoStorage(get_mongo_url())

def upload_docs(files):
    try:
        for file in files:
            filename = secure_filename(file["name"])
            content = base64.b64decode(file["content"])
            with open(os.path.join(upload_folder, filename), "wb") as f:
                f.write(content)
    except Exception as e:
        logger.error(f"Failed to upload files: {str(e)}")
        return jsonify({"error": str(e)}), 500

def get_best_match_results(query: str, top_k_results: int = 5, scope: str = "public", logged_in_user: str = "default"):
    # Create embedding generator
    embedding_generator = initialize_embedding_generator()
    
    # Create vector storage
    vector_storage = initialize_vector_storage(embedding_generator.embedding_dim, SourceType.DOCUMENT.value)
    
    query_embedding = embedding_generator.generate_query_embedding(query)
    
    search_results = vector_storage.search(
        query_embedding=query_embedding,
        top_k=top_k_results,
        filters={"upload_by": logged_in_user} if scope == "private" else {}
    )

    return search_results
