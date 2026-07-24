from unittest.mock import MagicMock

from database import save_session


def test_save_session_accepts_persona_name_and_persona_id():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.lastrowid = 7
    conn.cursor.return_value = cursor

    session_id = save_session(
        conn,
        persona_name="Ada",
        persona_id="42",
        messages=[{"role": "user", "content": "Hello"}],
        context=[],
        session_id=None,
    )

    assert session_id == 7

    insert_call = next(
        call for call in cursor.execute.call_args_list
        if "INSERT INTO sessions" in call.args[0]
    )
    assert insert_call.args[1][0] == "Ada"
    assert insert_call.args[1][1] == "42"
