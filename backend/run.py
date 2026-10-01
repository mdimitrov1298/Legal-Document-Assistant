"""Run API: python run.py (from backend/)."""

import uvicorn

from app.core.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run("app.main:app", host=s.api_host, port=s.api_port, reload=True)
