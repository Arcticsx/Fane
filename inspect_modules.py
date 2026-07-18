import sys
sys.path.insert(0, r'c:\Users\super\OneDrive\Desktop\bj\SARP-AI-main\Backend')
import sitecustomize
import api.router as router_module
import app.api.chat_router as chat_router
print('router module id', id(router_module))
print('router module name', router_module.__name__)
print('sys.modules entry', sys.modules['api.router'] is router_module)
print('chat router id', id(chat_router))
print('same module?', chat_router is router_module)
print('chat submodule name', chat_router.__name__)
print('router_module attr', router_module.get_recent_sessions)
print('chat attr', chat_router.get_recent_sessions)
