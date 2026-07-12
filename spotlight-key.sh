#!/bin/bash
cd "/mnt/hdd_juegos/Proyectos de python/Thespotlight-key" || exit 1
source .venv/bin/activate
python -m cli "$@"
