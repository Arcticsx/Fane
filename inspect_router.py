import sys
sys.path.insert(0, r'c:\Users\super\OneDrive\Desktop\bj\SARP-AI-main\Backend')
import sitecustomize
import api.router as router_module

def fake(conn):
    return ['x']

router_module.get_recent_sessions = fake
print(router_module.get_recent_sessions)
print(router_module.__dict__['get_recent_sessions'])
