"""
Composition root for the Identity service.

Wires outbound adapters (Mongo, Redis) to domain ports.
Only entry points (flask_app.py, tests) create this — domain code never imports it.
"""
from pymongo import MongoClient

from config.app_config import AppConfig
from global_utils.utils.util import get_mongo_url
from adapters.outbound.mongo.token_repository import MongoTokenRepository
from tokens.service import TokenService


class AppContainer:
    """Central wiring for identity-service infrastructure."""

    def __init__(self, config: AppConfig):
        mongo_client = MongoClient(get_mongo_url())
        db = mongo_client[config.mongo_db]

        self.token_repository = MongoTokenRepository(
            db=db,
            coll_name=config.api_tokens_coll,
        )
        self.token_service = TokenService(repository=self.token_repository)
