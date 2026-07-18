import sys
sys.path.insert(0, r'c:\Users\super\OneDrive\Desktop\bj\SARP-AI-main\Backend')
import sitecustomize
from app.api.chat_router import app
from fastapi.testclient import TestClient

client = TestClient(app)
# Create a chronicle session first
create_resp = client.post('/story', data={'title':'Test Chronicle','synopsis':'A test chronicle','genre':'Fantasy'})
print('create', create_resp.status_code, create_resp.text)
if create_resp.ok:
    session_id = create_resp.json()['id']
    chat_resp = client.post(f'/story/{session_id}/chat', json={'user_input':'Hello there'})
    print('chat', chat_resp.status_code, chat_resp.text)
