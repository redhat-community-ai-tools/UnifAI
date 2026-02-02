"""Validator for OcExecTool."""

import openshift_client as oc
from typing import List

from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from .config import OcExecToolConfig


class OcExecToolValidator(BaseElementValidator):
    """Validates OpenShift cluster connection."""

    def validate(
        self,
        config: OcExecToolConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []

        try:
            with oc.api_server(config.server):
                with oc.token(config.token):
                    with oc.tls_verify(enable=not config.skip_tls_verify):
                        result = oc.invoke('whoami')
            
            stdout = (result.out() or "").strip()
            stderr = (result.err() or "").strip()
            
            if result.status() == 0:
                messages.append(self._info(
                    "CONNECTION_OK",
                    f"Connected as: {stdout}",
                    field="server",
                ))
            else:
                messages.append(self._error(
                    ValidationCode.NETWORK_ERROR.value,
                    stderr or "Connection failed",
                    field="server",
                ))

        except oc.OpenShiftPythonException as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                str(e),
                field="server",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                str(e),
                field="server",
            ))

        return self._build_report(messages=messages)
