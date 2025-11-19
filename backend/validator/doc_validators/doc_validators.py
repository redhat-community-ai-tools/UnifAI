from typing import List
from common.interfaces import DataSourceValidator
from .duplicate_validator import DuplicateValidator


class DocValidators:
	"""
	Constructs the document validators pipeline.
	"""
	def create_validators(self) -> List[DataSourceValidator]:
		return [
			DuplicateValidator(),
		]


