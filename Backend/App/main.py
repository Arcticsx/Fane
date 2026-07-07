from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

for path in (str(REPO_ROOT), str(BACKEND_DIR), str(APP_DIR), str(APP_DIR / "api"), str(BACKEND_DIR / "app")):
    if path not in sys.path:
        sys.path.insert(0, path)

if __package__ in {None, ""}:
    from Backend.app.api.chat_router import app
else:
    from .api.chat_router import app

import uvicorn

if __name__ == '__main__':
    uvicorn.run("Backend.app.api.chat_router:app", host="0.0.0.0", port=8000, reload=True)
