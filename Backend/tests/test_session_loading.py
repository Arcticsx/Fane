from types import SimpleNamespace

from app.database import Context, Message, load_session


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, messages=None, context=None):
        self._messages = messages or []
        self._context = context or []

    def query(self, model):
        if model is Message:
            return FakeQuery(self._messages)
        if model is Context:
            return FakeQuery(self._context)
        raise AssertionError(f"Unexpected model: {model}")


def test_load_session_returns_two_values_for_existing_session():
    db = FakeDB(
        messages=[SimpleNamespace(id=1, sender="user", content="hello")],
        context=[SimpleNamespace(id=2, sender="assistant", content="hi")],
    )

    result = load_session(
        db,
        {"opening_prompt": "Start here"},
        {"role": "system", "content": "system"},
        {"id": 7},
    )

    assert len(result) == 2
    context, full_messages = result
    assert context[1]["content"] == "hi"
    assert full_messages[1]["content"] == "hello"
