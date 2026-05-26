from __future__ import annotations
from typing import TYPE_CHECKING
from flask import Flask
from config.app_config import AppConfig
from global_utils.redis import RedisKVStore, build_redis_client
from global_utils.utils.util import get_mongo_url
import logging

if TYPE_CHECKING:
    from utils.auth_manager import AuthManager

logger = logging.getLogger("auth_manager")


def build_auth_stack(app: Flask, config: AppConfig) -> tuple["AuthManager", RedisKVStore]:
    """Wire Redis + AuthManager. Returns ``(auth_manager, redis_store)`` for shared Redis use."""
    from utils.auth_manager import AuthManager

    try:
        redis_store = build_redis_store(config)
        auth_stack = AuthManager(app, redis_store)
        logger.info("Auth stack built successfully")
        return auth_stack, redis_store
    except Exception as e:
        logger.error(f"Failed to build auth stack: {e}")
        raise


def build_redis_store(config: AppConfig) -> RedisKVStore:
    client = build_redis_client(config.redis_db)
    return RedisKVStore(client)


def build_team_service(config: AppConfig, user_groups_cache=None):
    """Create MongoClient, MongoTeamRepository, and TeamService."""
    from pymongo import MongoClient
    from teams.repository.mongo_repository import MongoTeamRepository
    from teams.service import TeamService
    from directory.factory import build_directory_provider

    mongo_client = MongoClient(get_mongo_url())
    teams_db = mongo_client[config.mongo_db]
    team_repo = MongoTeamRepository(db=teams_db, coll_name=config.teams_coll)
    directory_provider = build_directory_provider(config)
    return TeamService(
        repository=team_repo,
        directory_provider=directory_provider,
        user_groups_cache=user_groups_cache,
    )
