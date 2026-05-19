#!/usr/bin/env bash
cd /home/teejay/StellaShelf || exit 1
# For production: set host to 127.0.0.1 and use a reverse proxy (nginx) for HTTPS + public access
# To expose to the internet, run with: host='0.0.0.0' and configure STELLASHELF_API_KEY + HTTPS
exec /home/teejay/StellaShelf/.venv/bin/python -c "import sys; sys.path.insert(0, '.'); import uvicorn; from stellashelf.api import app; uvicorn.run(app, host='127.0.0.1', port=8321, log_level='info')"
