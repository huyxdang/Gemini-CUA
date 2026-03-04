import os

from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

app: FastAPI = get_fast_api_app(agents_dir=AGENT_DIR, web=False)


@app.get("/health")
def health():
    return {"status": "ok"}
