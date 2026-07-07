#!/usr/bin/env python
import requests

print("=" * 60)
print("TESTING CHRONICLE CHAT ENDPOINT")
print("=" * 60)

# Create session
form_data = {
    'title': 'Test Session',
    'synopsis': 'Test chronicle story',
    'genre': 'Fantasy',
    'context_token_limit': '2000'
}

print("\n1. Creating session...")
r = requests.post('http://127.0.0.1:8000/story', data=form_data)
if r.status_code != 200:
    print(f"   ERROR: {r.status_code} - {r.text}")
    exit(1)

session_data = r.json()
session_id = session_data['id']
print(f"   ✓ Session created: {session_id}")
print(f"   Title: {session_data['title']}")

# Test chat endpoint
print("\n2. Testing chat endpoint...")
chat_payload = {'user_input': 'Hello! Tell me a story.'}
r2 = requests.post(f'http://127.0.0.1:8000/story/{session_id}/chat', json=chat_payload)
print(f"   Status: {r2.status_code}")

if r2.status_code == 200:
    resp = r2.json()
    print(f"   ✓ Chat successful!")
    print(f"   User input: {resp['user_input']}")
    print(f"   Response: {resp['response'][:150]}...")
    print(f"   Chapter ID: {resp['chapter_id']}")
    print(f"   Timestamp: {resp['timestamp']}")
else:
    print(f"   ✗ ERROR {r2.status_code}")
    print(f"   Response: {r2.text[:500]}")

# Test second message in same chapter
print("\n3. Testing second message...")
chat_payload2 = {'user_input': 'What happens next?'}
r3 = requests.post(f'http://127.0.0.1:8000/story/{session_id}/chat', json=chat_payload2)
print(f"   Status: {r3.status_code}")

if r3.status_code == 200:
    resp = r3.json()
    print(f"   ✓ Second message successful!")
    print(f"   Response: {resp['response'][:150]}...")
else:
    print(f"   ✗ ERROR {r3.status_code}")
    print(f"   Response: {r3.text[:500]}")

print("\n" + "=" * 60)
print("CHRONICLE CHAT TESTS COMPLETE")
print("=" * 60)
