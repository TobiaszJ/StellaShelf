#!/usr/bin/env bash
cd /home/teejay/StellaShelf || exit 1
source .venv/bin/activate
exec stellashelf serve
