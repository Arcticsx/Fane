from fastapi.testclient import TestClient
from Backend.app.api.chat_router import app

client = TestClient(app)

def main():
    response = client.post(
    "/chronicle",
    
    data={
        "title": "Percy Jackson",
        "synopsis": "It is a great story",
        "genre": "fantasy",
        "magic_rules_md": "",
        "context_token_limit": 1000
        }
    )

    print(response.status_code)
    print(response.json())

main()
