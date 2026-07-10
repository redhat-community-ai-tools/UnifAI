"""
elements/llms/anthropic/validator.py

Validator for Anthropic (Claude) LLM - checks API key and model availability.
"""

from typing import List

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.llms.common.validation_codes import LLMValidationCode
from mas.elements.llms.anthropic.config import AnthropicConfig


class AnthropicValidator(BaseElementValidator):
    """
    Validates Anthropic (Claude) LLM configuration.

    Checks:
    - API key validity
    - Model availability
    """

    def validate(
        self,
        config: AnthropicConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate Anthropic LLM config.

        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        try:
            client = Anthropic(api_key=config.api_key)

            # Confirms both the API key and that the model exists/is accessible.
            client.models.retrieve(config.model_name)

            messages.append(self._info(
                LLMValidationCode.MODEL_AVAILABLE.value,
                f"Successfully connected and found model '{config.model_name}'",
                field="model_name",
            ))

        except (AuthenticationError, PermissionDeniedError):
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                "Authentication failed - check API key",
                field="api_key",
            ))
        except NotFoundError:
            messages.append(self._error(
                LLMValidationCode.MODEL_NOT_FOUND.value,
                f"Model '{config.model_name}' not found",
                field="model_name",
            ))
        except RateLimitError:
            messages.append(self._error(
                LLMValidationCode.RATE_LIMITED.value,
                "Rate limit exceeded",
            ))
        except APIConnectionError as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Connection error: {str(e)}",
            ))
        except APIStatusError as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"API error ({e.status_code}): {str(e)}",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Unexpected error: {type(e).__name__}",
            ))

        return self._build_report(messages=messages)
