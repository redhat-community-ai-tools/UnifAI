#from global_utils.config.config import SharedConfig

class LoggingConfig():
    log_level: str = "INFO"
    log_file: str = "identity.log"
    log_file_max_size: int = 10 * 1024 * 1024  # 10MB
    log_file_backup_count: int = 5
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    log_stream_handler: bool = True
    log_file_handler: bool = True
    log_console_handler: bool = True