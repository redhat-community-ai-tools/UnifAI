from typing import Optional, Any, Tuple
from common.interfaces import DataSourceValidator, ValidationIssue
from services.documents.duplicate_checker import DocumentDuplicateChecker
from utils.storage.mongo.mongo_helpers import get_mongo_storage


class DuplicateValidator(DataSourceValidator):
	name = "DuplicateValidator"
	error_message = "This file appears to be a duplicate of an existing successfully processed file and was not added. File: {source_name}"
	error_message_key = "File duplicated error"

	def __init__(self) -> None:
		# The validator owns and initializes its dependency
		self.duplicate_checker = DocumentDuplicateChecker(get_mongo_storage())

	def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
		try:
			if self.duplicate_checker.is_duplicate(kwargs):
				return False, self.build_issue(
					self.error_message.format(source_name=kwargs.get("source_name"))
				)
		except Exception:
			return True, None

		return True, None


