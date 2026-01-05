"""
elements/llms/google_genai/validator.py

Validator for Google GenAI LLM - checks API key and model availability.
"""

from typing import List

from google import genai
from google.genai.errors import ClientError, ServerError
from google.api_core.exceptions import (
    InvalidArgument,
    PermissionDenied,
    Unauthenticated,
    NotFound,
    ResourceExhausted,
    GoogleAPICallError,
)

from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.llms.google_genai.config import GoogleGenAIConfig


class GoogleGenAIValidator(BaseElementValidator):
    """
    Validates Google GenAI (Gemini) LLM configuration.
    
    Checks:
    - API key validity
    - Model availability
    """

    def validate(
        self,
        config: GoogleGenAIConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate Google GenAI LLM config.
        
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        try:
            # Create client with API key
            client = genai.Client(api_key=config.api_key)
            
            # Try to get the model
            client.models.get(model=config.model_name)
            
            messages.append(self._info(
                "MODEL_AVAILABLE",
                f"Successfully connected and found model '{config.model_name}'",
                field="model_name",
            ))

        # Specific google.api_core exceptions
        except (InvalidArgument, Unauthenticated, PermissionDenied):
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                "Authentication failed - check API key",
                field="api_key",
            ))
        except NotFound:
            messages.append(self._error(
                "MODEL_NOT_FOUND",
                f"Model '{config.model_name}' not found",
                field="model_name",
            ))
        except ResourceExhausted:
            messages.append(self._error(
                "RATE_LIMITED",
                "Rate limit exceeded",
                field="api_key",
            ))
        except GoogleAPICallError as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"API error: {str(e)}",
                field="api_key",
            ))
        # google.genai SDK errors (fallback)
        except ClientError as e:
            if e.code in (400, 401, 403):
                messages.append(self._error(
                    ValidationCode.INVALID_CREDENTIALS.value,
                    "Authentication failed - check API key",
                    field="api_key",
                ))
            elif e.code == 404:
                messages.append(self._error(
                    "MODEL_NOT_FOUND",
                    f"Model '{config.model_name}' not found",
                    field="model_name",
                ))
            elif e.code == 429:
                messages.append(self._error(
                    "RATE_LIMITED",
                    "Rate limit exceeded",
                    field="api_key",
                ))
            else:
                messages.append(self._error(
                    ValidationCode.NETWORK_ERROR.value,
                    f"API error ({e.code}): {e.message}",
                    field="api_key",
                ))
        except ServerError as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Server error ({e.code}): {e.message}",
                field="api_key",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Unexpected error: {type(e).__name__}",
                field="api_key",
            ))

        return self._build_report(messages=messages)

