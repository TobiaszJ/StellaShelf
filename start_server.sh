#!/usr/bin/env bash
cd /home/teejay/StellaShelf || exit 1
exec /home/teejay/StellaShelf/.venv/bin/python -c "import sys; sys.path.insert(0, '.'); import uvicorn; from stellashelf.api import app; uvicorn.run(app, host='0.0.0.0', port=8321, log_level='info')"
