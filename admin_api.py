"""Compatibility entry point for running the CardBot admin API from repo root."""

from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("admin.api.app:app", host="0.0.0.0", port=8000, reload=False)
