import pytest
from app.memory import summarize, trim_memory

def test_summarize(mocker):
    # Mock the get_response function imported in app.memory
    mock_get_response = mocker.patch("app.memory.get_response")
    mock_get_response.return_value = "Summary: The user said hello and the assistant responded."

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there! How can I help you today?"}
    ]

    # Call summarize
    result = summarize(messages)

    # Verify that get_response was called with the expected prompt format
    expected_prompt = [
        {
            "role": "system",
            "content": "You are a summarization assistant. Summarize the conversation clearly and in detail."
        },
        {
            "role": "user",
            "content": f"Summarize this chat:\n\n{messages}"
        }
    ]
    mock_get_response.assert_called_once_with(expected_prompt)
    assert result == "Summary: The user said hello and the assistant responded."


def test_trim_memory_under_limit(mocker):
    mock_summarize = mocker.patch("app.memory.summarize")

    system_message = {"role": "system", "content": "You are a helpful assistant."}
    messages = [
        {"role": "system", "content": "Old system message to be ignored"},
        {"role": "user", "content": "Msg 1"},
        {"role": "assistant", "content": "Msg 2"},
        {"role": "user", "content": "Msg 3"},
        {"role": "assistant", "content": "Msg 4"},
        {"role": "user", "content": "Msg 5"}
    ]

    result = trim_memory(messages, system_message)

    # Under the limit — summarize should never be called
    mock_summarize.assert_not_called()
    # Original messages returned unchanged
    assert result == messages


def test_trim_memory_over_limit(mocker):
    # Mock summarize
    mock_summarize = mocker.patch("app.memory.summarize")
    mock_summarize.return_value = "Mock Summary for old messages"

    system_message = {"role": "system", "content": "You are a helpful assistant."}

    # Input has 12 non-system messages
    non_system = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Msg {i}"} for i in range(12)]
    messages = [{"role": "system", "content": "Old system message"}] + non_system

    result = trim_memory(messages, system_message)

    # non_system contains 12 messages.
    # old = non_system[:-10] -> Msg 0 and Msg 1 (first 2 messages)
    # new = non_system[-10:] -> Msg 2 to Msg 11 (last 10 messages)
    expected_old = non_system[:-10]
    expected_new = non_system[-10:]

    mock_summarize.assert_called_once_with(expected_old)

    expected_result = [
        system_message,
        {"role": "system", "content": "Conversation summary: Mock Summary for old messages"}
    ] + expected_new
    assert result == expected_result

def test_summarize_empty(mocker):
    mock_get_response = mocker.patch("app.memory.get_response")
    summarize([])
    mock_get_response.assert_called_once()
