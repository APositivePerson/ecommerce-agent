#!/bin/bash
cd /home/wangziyi/.openclaw/workspace/ecommerce_agent
source .venv/bin/activate
exec python -c "
from werkzeug.serving import run_simple
from app import app
run_simple('0.0.0.0', 5000, app, use_reloader=False, threaded=True)
"
