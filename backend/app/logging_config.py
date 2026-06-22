from __future__ import annotations

import logging.config


LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s [%(name)s] %(message)s",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s [%(name)s] %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
        "app": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            "datefmt": LOG_DATE_FORMAT,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "app": {
            "formatter": "app",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {"handlers": ["app"], "level": "INFO"},
}


def configure_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
