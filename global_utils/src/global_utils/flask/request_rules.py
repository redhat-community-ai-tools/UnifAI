from functools import reduce
import logging

from flask import request

from global_utils.flask.correlation import (
    REQUEST_ID_HEADER,
    bind_request_id_from_headers,
    bind_session_id,
    clear_correlation_context,
)
from global_utils.utils.logging_config import get_request_id


class RequestRules:
    """ Set of "before_request/after_request" rules """
    PAYLOAD_SIZE_LIMIT = 10 * pow(100, 4)  # 1000MB=1GB

    def __init__(self, app):
        self.app = app
        self.metadata = {
            'bePort': '',
            'uiPort': '',
        }
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _before_request(self):
        bind_request_id_from_headers(request.headers)
        # Soft-bind session id from query only (no body parse).
        session_id = request.args.get("sessionId") or request.args.get("session_id")
        bind_session_id(session_id)
        self.size_limit()

    def _after_request(self, response):
        """
        Invoke these methods after each request.
        Each method must accept a single argument 'response' and return a new/updated response object.

        :param response:
        :return:
        """
        fns = [self.set_request_id_header, self.set_metadata, self._clear_context]
        return reduce(lambda prev, f: f(prev), fns, response)

    def size_limit(self):
        """ Limit content payload size to 1000MB for POST commands"""
        if request.method == "POST":
            content_length = int(request.content_length or 0)
            if content_length > self.PAYLOAD_SIZE_LIMIT:
                logging.info("Content length is too large: %s", content_length)
                raise Exception("Content length is too large")

    def set_request_id_header(self, response):
        request_id = get_request_id()
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        return response

    def set_metadata(self, response):
        """
        Return the BE PLATFORM in the headers.

        :param response:
        :return:
        """
        for key, data in self.metadata.items():
            response.headers[key] = data
        return response

    def _clear_context(self, response):
        clear_correlation_context()
        return response
