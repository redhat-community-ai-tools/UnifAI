from __future__ import annotations
from typing import Any, Dict, Tuple
from functools import cached_property
from dataclasses import dataclass
from config.constants import DataSource
from global_utils.helpers.helpers import calculate_date_range
from shared.source_types import SlackMetadata, SlackTypeData
from .base import RegistrationBase, BaseSourceData
from validator.validator import Validator, SlackValidators

@dataclass(frozen=True)
class SlackSourceData(BaseSourceData):
    pass
    
class SlackRegistration(RegistrationBase):
    """Registration flow for Slack sources."""
    DATA_SOURCE_TYPE = DataSource.SLACK.upper_name

    def __init__(
        self, 
        mongo_storage: Any, 
        upload_by: str, 
        instance: Dict[str, Any],
        skip_validation: bool = False
    ) -> None:
        super().__init__(mongo_storage, upload_by, instance, skip_validation)
        self._validator = Validator(SlackValidators().create_validators())

    @cached_property
    def source_data(self) -> SlackSourceData:
        source_id = self.instance.get("channel_id", "")
        source_name = self.instance.get("channel_name", "")
        pipeline_id = f"{DataSource.SLACK.value}_{source_id}"
        form_data = self.instance.get("metadata", {})
        return SlackSourceData(
            source_id=source_id,
            source_name=source_name,
            pipeline_id=pipeline_id,
            form_data=form_data,
        )

    def run_validator(self) -> Tuple[bool, Dict[str, Any] | None]:
        validation_args = {
            "channel_id": self.source_data.source_id,
            "channel_name": self.source_data.source_name,
        }
        is_valid, issue = self._validator.validate(**validation_args)

        if not is_valid:
            issue_key = (issue or {}).get("issue_key", "ValidationError")
            message = (issue or {}).get("message", "Validation error")
            validator_name = (issue or {}).get("validator_name", "Validator")
            return False, {
                "channel_name": self.source_data.source_name,
                "issue_type": issue_key,
                "message": message,
                "validator": validator_name,
            }

        return True, None

    def _build_metadata(self) -> SlackMetadata:
        return SlackMetadata(
            channel_id=self.source_data.source_id,
            channel_name=self.source_data.source_name,
            is_private=self.instance.get("is_private", False),
            upload_by=self.upload_by,
        )

    def _build_type_data(self) -> Dict[str, Any]:
        date_range = self.source_data.form_data.get("dateRange")
        start_datetime, end_datetime = calculate_date_range(date_range)
        slack_type_data = SlackTypeData(
            is_private=self.instance.get("is_private", False),
            start_timestamp=start_datetime,
            end_timestamp=end_datetime,
            **self.source_data.form_data,
        )
        return slack_type_data.model_dump()


