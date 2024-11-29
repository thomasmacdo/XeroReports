#!/bin/bash

find . -type d -name "__pycache__" -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Set test database environment variables
export SQL_ENGINE="django.db.backends.postgresql"
export SQL_DATABASE="xero_db"
export SQL_USER="xero_user"
export SQL_PASSWORD="xero_password"
export SQL_HOST="localhost"
export SQL_PORT="5432"

pytest core/tests \
    -v \
    --tb=short \
    --strict-markers \
    -p no:warnings \
    "$@"