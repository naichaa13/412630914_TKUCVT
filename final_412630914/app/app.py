
from flask import Flask
import os, socket, psycopg2, sys

app = Flask(__name__)

def get_db_status():
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "db"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "password"),
            dbname=os.environ.get("DB_NAME", "postgres"),
            connect_timeout=2
        )
        conn.close()
        return True
    except:
        return False

@app.route("/healthz")
def healthz():
    if get_db_status():
        return "ok", 200
    else:
        return "db connection failed", 503

@app.route("/")
def hello():
    if get_db_status():
        return f"System OK | from {socket.gethostname()}"
    return "DB Offline", 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

