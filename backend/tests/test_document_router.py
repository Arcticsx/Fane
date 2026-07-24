import importlib
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def test_story_document_route_is_registered():
    chat_module = importlib.import_module("api.chat_router")

    route_paths = {
        route.path
        for route in chat_module.app.routes
        if hasattr(route, "path")
    }

    assert "/story/{id}/docs" in route_paths
