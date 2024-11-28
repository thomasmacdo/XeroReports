#!/bin/bash

find . -type d -name "__pycache__" -exec rm -r {} +
find . -type f -name "*.pyc" -delete

pytest core/tests \
    -v \
    --tb=short \
    --strict-markers \
    -p no:warnings \
    "$@"