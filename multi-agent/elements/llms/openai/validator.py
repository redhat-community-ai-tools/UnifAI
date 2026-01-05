"""
elements/llms/openai/validator.py

Validator for OpenAI LLM - checks API connectivity and model availability.
"""

from typing import List

from openai import (
    OpenAI,
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    APIStatusError,
)

from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.llms.openai.config import OpenAIConfig


class OpenAILLMValidator(BaseElementValidator):
    """
    Validates OpenAI LLM configuration.
    
    Checks:
    - API endpoint reachability
    - API key validity
    - Model availability
    """

    def validate(
        self,
        config: OpenAIConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate OpenAI LLM config.
        
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        try:
            client = OpenAI(
                base_url=str(config.base_url),
                api_key=config.api_key,
                timeout=context.timeout_seconds,
            )
            client.models.retrieve(config.model_name)
            
            messages.append(self._info(
                "MODEL_AVAILABLE",
                f"Successfully connected and found model '{config.model_name}'",
                field="model_name",
            ))

        except (AuthenticationError, PermissionDeniedError):
            # 401, 403
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                "Authentication failed - check API key",
                field="api_key",
            ))
        except BadRequestError:
            # 400 - Google uses this for invalid API keys
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                "Bad request - check API key and configuration",
                field="api_key",
            ))
        except NotFoundError:
            # 404
            messages.append(self._error(
                "MODEL_NOT_FOUND",
                f"Model '{config.model_name}' not found",
                field="model_name",
            ))
        except RateLimitError:
            # 429
            messages.append(self._error(
                "RATE_LIMITED",
                "Rate limit exceeded",
                field="base_url",
            ))
        except APITimeoutError:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="base_url",
            ))
        except APIConnectionError:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                "Cannot connect to API endpoint",
                field="base_url",
            ))
        except APIStatusError as e:
            # Any other 4xx/5xx
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"API error (HTTP {e.status_code})",
                field="base_url",
            ))

        return self._build_report(messages=messages)

