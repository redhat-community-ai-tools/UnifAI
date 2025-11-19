import os
from urllib import request
from config.constants import DataSource
from data_sources.docs.doc_config_manager import DocConfigManager
from providers.data_sources import get_available_data_sources
from flask import Blueprint, jsonify, session
from webargs import fields
from shared.logger import logger
from global_utils.helpers.apiargs import from_query, from_body
from global_utils.celery_app.helpers import send_task
from providers.docs import get_best_match_results, upload_docs

docs_bp = Blueprint("docs", __name__)

@docs_bp.route("/upload", methods=["POST"])
@from_body({
    "files": fields.List(fields.Dict(), required=True)
})
def upload_files(files):
    try:
        upload_docs(files)
        return jsonify({"message": "Files uploaded successfully"}), 200
    except Exception as e:
        logger.error(f"Failed to upload files: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
    
@docs_bp.route("/supported-extensions", methods=["GET"])
def get_supported_extensions():
    try:
        config_manager = DocConfigManager()
        supported_extensions = config_manager.get_supported_file_types()
        return jsonify({"supported_extensions": supported_extensions}), 200
    except Exception as e:
        logger.error(f"Failed to get supported extensions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@docs_bp.route("/available.docs.get", methods=["GET"])
def available_doc_list():
    try:
        docs = get_available_data_sources(source_type=DataSource.DOCUMENT.upper_name)
        return jsonify({"docs": docs}), 200
    except Exception as e:
        logger.error(f"Failed to get available docs list: {str(e)}")
        return jsonify({"error": str(e)}), 500
    

@docs_bp.route("/embed.docs", methods=["PUT"])
@from_body({
    "docs": fields.List(fields.Dict(), required=True)
})
def embed_docs(docs):
    try:
        send_task(
            task_name="celery_app.tasks.pipeline_tasks.execute_pipeline_task",
            celery_queue="docs_queue",
            source_type="DOCUMENT",
            source_data=docs
        )
        return jsonify({"status": "task submitted"}), 202
    except Exception as e:
        logger.error(f"Failed to submit docs embedding task: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@docs_bp.route("/query.match", methods=["GET"])
@from_query({
    "query": fields.Str(required=True),
    "top_k_results": fields.Int(required=False),
    "scope": fields.Str(required=False, load_default="public"),
    "logged_in_user": fields.Str(required=False, load_default="default", data_key="loggedInUser")
})
def best_match_results(query, top_k_results, scope, logged_in_user):    
    try:
        search_results = get_best_match_results(query, top_k_results, scope, logged_in_user)
        return jsonify({"search_results": search_results}), 200
    except Exception as e:
        logger.error(f"Failed to find best match for user query: {str(e)}")
        return jsonify({"error": str(e)}), 500
    

# @docs_bp.route("/retry.embedding", methods=["PUT"])
# @from_body({
#     "pipeline_id": fields.Str(required=True, data_key="pipelineId")
# })
# def retry(pipeline_id):
#     try:
#         # get data from the mongo, set status of pipeline to RETRIED
#         # and we want to לדרוס the sources data with last_pipeline_id and update it
#         # not 100% sure if there is a reason to implement this, will be discussed when I get to GENIE-630
#         docs = []
#         embed_docs(docs)
#         return jsonify({"docs": docs}), 200
#     except Exception as e:
#         logger.error(f"Failed to get available docs list: {str(e)}")
#         return jsonify({"error": str(e)}), 500