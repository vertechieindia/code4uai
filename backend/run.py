"""Dev API entrypoint — run from `backend/` with Poetry's env.

    poetry run python run.py

Or: poetry shell, then python run.py
"""
from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "code4u.interfaces.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
