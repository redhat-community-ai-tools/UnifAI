import logging
import os

_configured = False


def configure_logging(service_name: str, log_level: str | None = None) -> None:
    global _configured
    if _configured:
        return

    level_name = (log_level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if os.environ.get("OTEL_LOGS_ENABLED", "").lower() not in ("1", "true", "yes"):
        _configured = True
        return

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    logger_provider = LoggerProvider(
        resource=Resource.create({"service.name": service_name}),
    )
    exporter = OTLPLogExporter(insecure=True)  # endpoint from OTEL_EXPORTER_OTLP_ENDPOINT
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    set_logger_provider(logger_provider)

    root = logging.getLogger()
    root.addHandler(LoggingHandler(level=level, logger_provider=logger_provider))
    _configured = True

class Logger:
    _instance = None

    def __new__(cls, logger_name="custom_logger"):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize_logger(logger_name)
        return cls._instance

    def _initialize_logger(self, logger_name):
        """Set up the logger configuration."""
        self.logger = logging.getLogger(logger_name)
        if not self.logger.handlers:  # Ensure handlers are not duplicated
            self.logger.setLevel(logging.INFO)

            # Create a console handler
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)

            # Create a formatter and set it for the handler
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

            # Suppress propagation to the root logger to avoid duplication
            self.logger.propagate = False

    def get_logger(self):
        """Provide access to the singleton logger."""
        return self.logger

    def update_log_level(self, log_level: str) -> None:
        """Update the logger level based on the input."""
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)
        self.logger.info(f"Logger level set to {log_level.upper()}")


# Singleton instance of the logger
Logger_instance = Logger()
logger = Logger_instance.get_logger()



