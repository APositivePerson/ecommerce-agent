from werkzeug.serving import run_simple
from app import app

if __name__ == '__main__':
    run_simple('0.0.0.0', 5000, app, use_reloader=False, threaded=True)
