import sys
sys.path.insert(0, r'c:\Users\super\OneDrive\Desktop\bj\SARP-AI-main\Backend')
import sitecustomize
from app.api.chat_router import app
from fastapi.testclient import TestClient

client = TestClient(app)
body = {
    'persona_key': 'hehe',
    'messages': [],
    'context': [],
    'session_id': None,
    'user_input': 'hello'
}
resp = client.post('/chat', json=body)
print(resp.status_code)
print(resp.text)
