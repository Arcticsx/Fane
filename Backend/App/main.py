import sys
from pathlib import Path

from .api.chat_router import app

import uvicorn

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent

for path in (str(BACKEND_DIR), str(APP_DIR), str(APP_DIR / "api"), str(BACKEND_DIR / "app")):
    if path not in sys.path:
        sys.path.insert(0, path)

if __name__ == '__main__':
    uvicorn.run("api.chat_router:app", host="0.0.0.0", port=8000, reload=True)
