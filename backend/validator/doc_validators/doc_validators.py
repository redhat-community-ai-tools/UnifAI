from typing import List
from common.interfaces import DataSourceValidator
from .duplicate_validator import DuplicateValidator
from .extension_validator import ExtensionValidator
from .size_validator import SizeValidator
from .name_duplicate_validator import NameDuplicateValidator


class DocValidators:
	"""
	Constructs the document validators pipeline.
	
	Supports two modes:
	1. Full validation (skip_validation=False): All validators run
	   Used for external API calls that didn't pre-validate
	   
	2. MD5-only validation (skip_validation=True): Only DuplicateValidator runs
	   Used for UI uploads that were pre-validated via /docs/validate endpoint
	   
	Validator execution order:
	1. ExtensionValidator - checks file type is supported
	2. SizeValidator - checks file doesn't exceed max size
	3. NameDuplicateValidator - checks no same-name doc exists for user
	4. DuplicateValidator - checks MD5 hash for content duplicates (always runs)
	"""
	
	def create_validators(self, skip_validation: bool = False) -> List[DataSourceValidator]:
		"""
		Create the list of validators to run.
		
		Args:
			skip_validation: If True, only include MD5 DuplicateValidator.
			               If False, include all validators for full validation.
			               
		Returns:
			List of validators to execute in order.
		"""
		if skip_validation:
			# UI flow: files were pre-validated, only check MD5 duplicates
			return [
				DuplicateValidator(),
			]
		
		# External API flow: full validation required
		return [
			ExtensionValidator(),
			SizeValidator(),
			NameDuplicateValidator(),
			DuplicateValidator(),
		]


