import sys
from pathlib import Path

# Add the parent of 'app' to sys.path so that 'import app.xxx' works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app.api.chat_router:app", host="0.0.0.0", port=8000, reload=True)