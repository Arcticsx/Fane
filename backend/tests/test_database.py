# Tests for database.py functions
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from database import save_session, get_sessions, pick_session, delete_session


class TestSaveSession:
    """Test suite for save_session() function."""

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_new_session(self, mock_success, mock_cursor, mock_conn):
        """Test saving a new session without session_id."""
        # Arrange
        persona_name = "Lyra"
        messages = [
            {"role": "system", "content": "You are Lyra..."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        mock_cursor.lastrowid = 1

        # Act
        save_session(persona_name, messages)

        # Assert
        mock_cursor.execute.assert_any_call(
            """
            INSERT INTO sessions(persona, created_at, updated_at)
            VALUES (?, ?, ?)
        """,
            pytest.approx,  # placeholder; checked below
        )
        # Verify INSERT INTO sessions was called
        insert_call = next(
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO sessions" in c[0][0]
        )
        args = insert_call[0][1]
        assert args[0] == persona_name
        # created_at and updated_at should be equal on new insert
        assert args[1] == args[2]
        mock_conn.commit.assert_called()

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.info')
    def test_save_session_empty_messages_returns_early(self, mock_info, mock_cursor, mock_conn):
        """Test that empty messages list triggers early return without DB call."""
        # Arrange
        persona_name = "Lyra"
        messages = []

        # Act
        save_session(persona_name, messages)

        # Assert
        mock_cursor.execute.assert_not_called()
        mock_conn.commit.assert_not_called()
        mock_info.assert_called_once_with("No messages to save.")

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_update_existing_session(self, mock_success, mock_cursor, mock_conn):
        """Test updating an existing session with a valid session_id."""
        # Arrange
        persona_name = "Lyra"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        session_id = 42

        # Act
        save_session(persona_name, messages, session_id)

        # Assert
        update_call = next(
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE sessions" in c[0][0]
        )
        args = update_call[0][1]
        assert args[0] == persona_name
        assert args[2] == session_id

        delete_call = next(
            c for c in mock_cursor.execute.call_args_list
            if "DELETE FROM messages" in c[0][0]
        )
        assert delete_call[0][1] == (session_id,)

        # INSERT INTO sessions should NOT be called
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO sessions" in c[0][0]
        ]
        assert len(insert_calls) == 0

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_skips_system_messages(self, mock_success, mock_cursor, mock_conn):
        """Test that system messages are not inserted into the messages table."""
        # Arrange
        persona_name = "Lyra"
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        mock_cursor.lastrowid = 1

        # Act
        save_session(persona_name, messages)

        # Assert
        msg_inserts = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO messages" in c[0][0]
        ]
        inserted_senders = [c[0][1][1] for c in msg_inserts]
        assert "system" not in inserted_senders
        assert "user" in inserted_senders
        assert "assistant" in inserted_senders

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_inserts_messages_in_order(self, mock_success, mock_cursor, mock_conn):
        """Test that non-system messages are inserted in original order."""
        # Arrange
        persona_name = "Lyra"
        messages = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Second"},
            {"role": "user", "content": "Third"},
        ]
        mock_cursor.lastrowid = 5

        # Act
        save_session(persona_name, messages)

        # Assert
        msg_inserts = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO messages" in c[0][0]
        ]
        contents = [c[0][1][2] for c in msg_inserts]
        assert contents == ["First", "Second", "Third"]

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_all_system_messages_does_not_insert_any(self, mock_success, mock_cursor, mock_conn):
        """Test that a messages list containing only system messages inserts nothing."""
        # Arrange
        persona_name = "Lyra"
        messages = [{"role": "system", "content": "Only a system prompt"}]
        mock_cursor.lastrowid = 1

        # Act
        save_session(persona_name, messages)

        # Assert
        msg_inserts = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO messages" in c[0][0]
        ]
        assert len(msg_inserts) == 0
        mock_conn.commit.assert_called()

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_prints_success_message(self, mock_success, mock_cursor, mock_conn):
        """Test that success message is always printed after save."""
        # Arrange
        messages = [{"role": "user", "content": "Test"}]
        mock_cursor.lastrowid = 1

        # Act
        save_session("Lyra", messages)

        # Assert
        mock_success.assert_called_once_with("Session saved.")

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_prints_success_message_on_update(self, mock_success, mock_cursor, mock_conn):
        """Test that success message is printed on update too."""
        # Arrange
        messages = [{"role": "user", "content": "Test"}]

        # Act
        save_session("Lyra", messages, session_id=7)

        # Assert
        mock_success.assert_called_once_with("Session saved.")

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_none_session_id_creates_new(self, mock_success, mock_cursor, mock_conn):
        """Test that None session_id creates a new session (no UPDATE)."""
        # Arrange
        messages = [{"role": "user", "content": "Test"}]
        mock_cursor.lastrowid = 3

        # Act
        save_session("Lyra", messages, None)

        # Assert
        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE sessions" in c[0][0]
        ]
        assert len(update_calls) == 0

        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO sessions" in c[0][0]
        ]
        assert len(insert_calls) == 1

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_uses_lastrowid_for_messages(self, mock_success, mock_cursor, mock_conn):
        """Test that new session uses cursor.lastrowid as session_id for messages."""
        # Arrange
        messages = [{"role": "user", "content": "Hello"}]
        mock_cursor.lastrowid = 99

        # Act
        save_session("Lyra", messages)

        # Assert
        msg_insert = next(
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO messages" in c[0][0]
        )
        assert msg_insert[0][1][0] == 99  # session_id in INSERT INTO messages

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_special_characters_in_messages(self, mock_success, mock_cursor, mock_conn):
        """Test saving messages with special characters."""
        # Arrange
        messages = [
            {"role": "user", "content": "Hello! @#$%^&*()"},
            {"role": "assistant", "content": "Response with 'quotes' and \"double quotes\""}
        ]
        mock_cursor.lastrowid = 1

        # Act
        save_session("Lyra", messages)

        # Assert — just verify no exception and commit is called
        mock_conn.commit.assert_called()

    @patch('database.conn')
    @patch('database.cursor')
    @patch('database.success')
    def test_save_session_long_messages_list(self, mock_success, mock_cursor, mock_conn):
        """Test saving session with many messages."""
        # Arrange
        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(100)
        ]
        mock_cursor.lastrowid = 1

        # Act
        save_session("Lyra", messages)

        # Assert
        msg_inserts = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO messages" in c[0][0]
        ]
        assert len(msg_inserts) == 100


class TestDeleteSession:
    """Test suite for delete_session() function."""

    @patch('database.conn')
    @patch('database.cursor')
    def test_delete_session_removes_session_and_messages(self, mock_cursor, mock_conn):
        """Test that deleting a session removes its messages and the session itself."""
        session_id = 7

        result = delete_session(session_id)

        delete_messages_call = next(
            c for c in mock_cursor.execute.call_args_list
            if "DELETE FROM messages" in c[0][0]
        )
        delete_session_call = next(
            c for c in mock_cursor.execute.call_args_list
            if "DELETE FROM sessions" in c[0][0]
        )

        assert result is True
        assert delete_messages_call[0][1] == (session_id,)
        assert delete_session_call[0][1] == (session_id,)
        mock_conn.commit.assert_called_once()


class TestGetSessions:
    """Test suite for get_sessions() function."""

    @patch('database.cursor')
    def test_get_sessions_returns_sessions(self, mock_cursor):
        """Test that get_sessions returns list of sessions with correct fields."""
        # Arrange
        persona_name = "Lyra"
        mock_cursor.fetchall.return_value = [
            (1, "Lyra", "2024-01-01T10:00:00", "2024-01-01T11:00:00"),
            (2, "Lyra", "2024-01-02T10:00:00", "2024-01-02T11:00:00"),
        ]

        # Act
        result = get_sessions(persona_name)

        # Assert
        assert len(result) == 2
        assert result[0] == {
            "id": 1,
            "persona": "Lyra",
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T11:00:00",
        }

    @patch('database.cursor')
    def test_get_sessions_returns_empty_list(self, mock_cursor):
        """Test that get_sessions returns empty list when no sessions exist."""
        # Arrange
        mock_cursor.fetchall.return_value = []

        # Act
        result = get_sessions("UnknownPersona")

        # Assert
        assert result == []

    @patch('database.cursor')
    def test_get_sessions_filters_by_persona(self, mock_cursor):
        """Test that query filters by the given persona name."""
        # Arrange
        mock_cursor.fetchall.return_value = []

        # Act
        get_sessions("Lyra")

        # Assert
        call_args = mock_cursor.execute.call_args
        assert "WHERE persona = ?" in call_args[0][0]
        assert call_args[0][1] == ("Lyra",)

    @patch('database.cursor')
    def test_get_sessions_orders_by_updated_at_descending(self, mock_cursor):
        """Test that sessions are ordered by updated_at DESC."""
        # Arrange
        mock_cursor.fetchall.return_value = []

        # Act
        get_sessions("Lyra")

        # Assert
        sql = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY updated_at DESC" in sql

    @patch('database.cursor')
    def test_get_sessions_limits_to_five(self, mock_cursor):
        """Test that query limits results to 5."""
        # Arrange
        mock_cursor.fetchall.return_value = []

        # Act
        get_sessions("Lyra")

        # Assert
        sql = mock_cursor.execute.call_args[0][0]
        assert "LIMIT 5" in sql

    @patch('database.cursor')
    def test_get_sessions_returned_dicts_have_correct_keys(self, mock_cursor):
        """Test that returned dicts contain exactly the expected keys."""
        # Arrange
        mock_cursor.fetchall.return_value = [
            (3, "Lyra", "2024-03-01T00:00:00", "2024-03-02T00:00:00"),
        ]

        # Act
        result = get_sessions("Lyra")

        # Assert
        assert set(result[0].keys()) == {"id", "persona", "created_at", "updated_at"}

    @patch('database.cursor')
    def test_get_sessions_no_messages_field(self, mock_cursor):
        """Test that returned sessions do not contain a messages field."""
        # Arrange
        mock_cursor.fetchall.return_value = [
            (1, "Lyra", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
        ]

        # Act
        result = get_sessions("Lyra")

        # Assert
        assert "messages" not in result[0]


class TestPickSession:
    """Test suite for pick_session() function."""

    @patch('database.get_sessions')
    def test_pick_session_no_sessions_returns_none(self, mock_get_sessions):
        """Test that pick_session returns None if no sessions exist."""
        # Arrange
        mock_get_sessions.return_value = []

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result is None
        mock_get_sessions.assert_called_once_with("Lyra")

    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_returns_none_on_n(self, mock_get_sessions, mock_print_sessions, mock_prompt_input):
        """Test that entering 'n' or 'N' returns None."""
        # Arrange
        mock_get_sessions.return_value = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_prompt_input.return_value = " N "

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result is None
        mock_print_sessions.assert_called_once()

    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_returns_session_on_valid_index(self, mock_get_sessions, mock_print_sessions, mock_prompt_input):
        """Test that entering a valid index returns the correct session."""
        # Arrange
        sessions = [
            {"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"},
            {"id": 2, "persona": "Lyra", "created_at": "2024-01-02", "updated_at": "2024-01-02"},
        ]
        mock_get_sessions.return_value = sessions
        mock_prompt_input.return_value = "2"

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result == sessions[1]

    @patch('builtins.print')
    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_exits_on_exit(self, mock_get_sessions, mock_print_sessions, mock_prompt_input, mock_print):
        """Test that entering 'exit' raises SystemExit(0)."""
        # Arrange
        mock_get_sessions.return_value = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_prompt_input.return_value = " ExIt "

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            pick_session("Lyra")

        assert exc_info.value.code == 0
        mock_print.assert_any_call("Exiting program. Goodbye!")

    @patch('builtins.print')
    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_empty_input_then_valid(self, mock_get_sessions, mock_print_sessions, mock_prompt_input, mock_print):
        """Test that empty input loops until a valid input is given."""
        # Arrange
        sessions = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_get_sessions.return_value = sessions
        mock_prompt_input.side_effect = ["", "1"]

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result == sessions[0]
        mock_print.assert_any_call("Input cannot be empty. Please try again.")

    @patch('builtins.print')
    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_out_of_bounds_then_valid(self, mock_get_sessions, mock_print_sessions, mock_prompt_input, mock_print):
        """Test that out of bounds index prints error and loops until valid."""
        # Arrange
        sessions = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_get_sessions.return_value = sessions
        mock_prompt_input.side_effect = ["0", "2", "1"]

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result == sessions[0]
        mock_print.assert_any_call("Please enter a number between 1 and 1.")

    @patch('builtins.print')
    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_invalid_format_then_valid(self, mock_get_sessions, mock_print_sessions, mock_prompt_input, mock_print):
        """Test that non-numeric input prints error and loops until valid."""
        # Arrange
        sessions = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_get_sessions.return_value = sessions
        mock_prompt_input.side_effect = ["not-a-number", "1"]

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result == sessions[0]
        mock_print.assert_any_call("Invalid input. Enter a number, N, or Exit.")

    @patch('builtins.print')
    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_keyboard_interrupt(self, mock_get_sessions, mock_print_sessions, mock_prompt_input, mock_print):
        """Test that KeyboardInterrupt returns None and prints cancellation message."""
        # Arrange
        mock_get_sessions.return_value = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_prompt_input.side_effect = KeyboardInterrupt

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result is None
        mock_print.assert_any_call("\nInput cancelled.")

    @patch('builtins.print')
    @patch('database.prompt_input')
    @patch('database.print_sessions')
    @patch('database.get_sessions')
    def test_pick_session_eof_error(self, mock_get_sessions, mock_print_sessions, mock_prompt_input, mock_print):
        """Test that EOFError returns None and prints cancellation message."""
        # Arrange
        mock_get_sessions.return_value = [{"id": 1, "persona": "Lyra", "created_at": "2024-01-01", "updated_at": "2024-01-01"}]
        mock_prompt_input.side_effect = EOFError

        # Act
        result = pick_session("Lyra")

        # Assert
        assert result is None
        mock_print.assert_any_call("\nInput cancelled.")