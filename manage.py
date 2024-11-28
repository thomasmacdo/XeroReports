#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def main():
    """Run administrative tasks."""
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
