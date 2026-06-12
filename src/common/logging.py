"""Minimal logging helper for project modules."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger by name."""
    return logging.getLogger(name)
