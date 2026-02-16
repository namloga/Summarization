"""
Entrypoint: запуск FastAPI-сервера (uvicorn).
Запуск из папки backend: python -m src.main
Production: задайте PORT (и при необходимости RELOAD=0).
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("RELOAD", "1").strip().lower() in ("1", "true", "yes")
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
    )