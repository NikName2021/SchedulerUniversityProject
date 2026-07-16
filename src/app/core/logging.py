# logging_config.py

# Конфигурация для логгера
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    # 1. ДОБАВЛЯЕМ НОВЫЙ ФОРМАТТЕР ДЛЯ ТЕКСТА
    "formatters": {
        "default_console": {
            "format": "%(levelname)-8s %(asctime)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed_text": {
            # Формат, который отлично подходит для файлов:
            # Время, Уровень, Имя логгера, Файл:Строка, Сообщение
            "format": "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    # 2. ДОБАВЛЯЕМ НОВЫЙ ОБРАБОТЧИК ДЛЯ .LOG ФАЙЛА
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default_console",
            "level": "DEBUG",
            "stream": "ext://sys.stdout",
        },
        "file_log": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "detailed_text",  # Используем наш новый текстовый форматтер
            "filename": "./logs/app.log",  # Имя файла
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 5,  # Хранить 5 старых файлов
            "encoding": "utf-8",
            "level": "INFO",  # Уровень логирования для файла
        },
        # Опционально: можно оставить и JSON-логгер, если нужно
        "file_json": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "./logs/app_logs.json",
            "maxBytes": 10485760,
            "backupCount": 5,
            "encoding": "utf-8",
            "level": "INFO",
        },
    },
    # 3. ДОБАВЛЯЕМ file_log В СПИСОК ОБРАБОТЧИКОВ
    "loggers": {
        # Корневой логгер для нашего приложения
        "": {
            # Теперь логи будут идти и в консоль, и в .log файл, и в .json
            "handlers": ["console", "file_log", "file_json"],
            "level": "INFO",
            "propagate": False,
        },
        # Логгер для uvicorn.access - логи доступа
        "uvicorn.access": {
            "handlers": ["console", "file_log", "file_json"],
            "level": "INFO",
            "propagate": False,
        },
        # Логгер для uvicorn.error - ошибки самого сервера
        "uvicorn.error": {
            "handlers": ["console", "file_log", "file_json"],
            "level": "DEBUG",
            # "propagate": False,
        },
    },
}
