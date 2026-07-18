import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "Backend"
APP_DIR = BACKEND / "app"

for path in (str(ROOT), str(BACKEND), str(APP_DIR), str(APP_DIR / "api")):
    if path not in sys.path:
        sys.path.insert(0, path)

if "Backend" not in sys.modules:
    backend_pkg = types.ModuleType("Backend")
    backend_pkg.__path__ = [str(BACKEND)]
    sys.modules["Backend"] = backend_pkg

for name, path in {
    "app": APP_DIR,
    "api": APP_DIR / "api",
    "App": BACKEND / "App",
}.items():
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(path)]
        sys.modules[name] = pkg


class ModuleProxy(types.ModuleType):
    def __init__(self, name, target):
        super().__init__(name)
        self._target = target

    def __getattr__(self, attr):
        return getattr(self._target, attr)

    def __setattr__(self, attr, value):
        if attr.startswith("_"):
            super().__setattr__(attr, value)
        else:
            setattr(self._target, attr, value)

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(dir(self._target)))


# Ensure the legacy router name points at the real chat router module so tests
# patching the compatibility module affect the active route handlers.
try:
    chat_router = importlib.import_module("app.api.chat_router")
except Exception:
    chat_router = None

if chat_router is not None:
    if "api.router" not in sys.modules:
        sys.modules["api.router"] = ModuleProxy("api.router", chat_router)
    elif not hasattr(sys.modules["api.router"], "_target"):
        sys.modules["api.router"] = ModuleProxy("api.router", chat_router)

# Make the legacy module names resolve to the same package tree.
for module_name in ("Backend.app", "app.api", "app.services", "App.services"):
    try:
        importlib.import_module(module_name)
    except Exception:
        pass
