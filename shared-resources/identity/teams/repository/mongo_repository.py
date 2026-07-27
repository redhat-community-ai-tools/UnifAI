from typing import List, Optional

import pymongo
from pymongo.database import Database

from teams.models import Team
from teams.repository.repository import TeamRepository


class MongoTeamRepository(TeamRepository):
    def __init__(self, db: Database, coll_name: str = "teams"):
        self.col = db[coll_name]
        self.col.create_index("name", unique=True)
        self.col.create_index("members.id")
        self.col.create_index("members.group_members")

    def create(self, doc: Team) -> str:
        result = self.col.insert_one({
            "_id": doc.team_id,
            **doc.model_dump(mode="json"),
        })
        if not result.acknowledged:
            raise RuntimeError(f"Failed to insert team: {doc.team_id}")
        return doc.team_id

    def get(self, team_id: str) -> Team:
        raw = self.col.find_one({"_id": team_id})
        if not raw:
            raise KeyError(team_id)
        return Team(**raw)

    def find_by_member(self, member_id: str,
                       group_ids: Optional[List[str]] = None) -> List[Team]:
        """Teams visible to *member_id*.

        * ``group_ids is None``: legacy — include stale ``group_members`` matches.
        * ``group_ids == []``: Rover groups known empty — direct membership only.
        * non-empty ``group_ids``: LDAP/Rover is authoritative for group access;
          do not match standalone ``group_members`` (avoids stale snapshots).
        """
        conditions = [
            {"members.id": member_id},
            {"members": member_id},
        ]
        if group_ids is None:
            conditions.append({"members.group_members": member_id})
        elif group_ids:
            conditions.append({
                "members": {"$elemMatch": {"type": "group", "id": {"$in": group_ids}}},
            })
        cursor = self.col.find({"$or": conditions}).sort("created_at", pymongo.DESCENDING)
        return [Team(**doc) for doc in cursor]

    def find_by_name(self, name: str) -> Optional[Team]:
        raw = self.col.find_one({"name": name})
        return Team(**raw) if raw else None

    def update(self, doc: Team) -> str:
        result = self.col.replace_one(
            {"_id": doc.team_id},
            doc.model_dump(mode="json"),
        )
        if result.matched_count == 0:
            raise KeyError(f"No team found with id: {doc.team_id}")
        return doc.team_id

    def delete(self, team_id: str) -> None:
        result = self.col.delete_one({"_id": team_id})
        if result.deleted_count == 0:
            raise KeyError(team_id)

    def update_group_members(self, group_id: str,
                             member_ids: List[str]) -> int:
        result = self.col.update_many(
            {"members": {"$elemMatch": {"type": "group", "id": group_id}}},
            {"$set": {"members.$[elem].group_members": member_ids}},
            array_filters=[{"elem.type": "group", "elem.id": group_id}],
        )
        return result.modified_count
