import pytest
from unittest.mock import MagicMock
from app.personalities import get_personalities, create_personality, pick_personality

@pytest.fixture
def mock_db_col(mocker):
    # Patch the personalities_col in app.personalities module
    mock_col = mocker.patch("app.personalities.personalities_col")
    return mock_col

@pytest.fixture
def mock_cli(mocker):
    # Patch cli functions used in app.personalities
    mock_header = mocker.patch("app.personalities.header")
    mock_prompt_input = mocker.patch("app.personalities.prompt_input")
    mock_info = mocker.patch("app.personalities.info")
    return {
        "header": mock_header,
        "prompt_input": mock_prompt_input,
        "info": mock_info
    }

def test_get_personalities(mock_db_col):
    # Set up mock return value for personalities_col.find
    mock_data = [
        {"key": "1", "name": "Lyra", "system": "sys1", "Scenario": "scen1", "opening_prompt": "hello"},
        {"key": "2", "name": "Eldrin", "system": "sys2", "Scenario": "scen2", "opening_prompt": "hi"}
    ]
    mock_db_col.find.return_value = mock_data

    result = get_personalities()

    # Assert find called correctly
    mock_db_col.find.assert_called_once_with({}, {"_id": 0})
    # Assert result is correctly transformed to a dict keyed by 'key'
    assert result == {
        "1": {"key": "1", "name": "Lyra", "system": "sys1", "Scenario": "scen1", "opening_prompt": "hello"},
        "2": {"key": "2", "name": "Eldrin", "system": "sys2", "Scenario": "scen2", "opening_prompt": "hi"}
    }

def test_get_personalities_empty(mock_db_col):
    mock_db_col.find.return_value = []
    result = get_personalities()
    assert result == {}

def test_create_personality_existing(mock_db_col, mock_cli):
    # Setup mock data for existing personas
    mock_db_col.find.return_value = [
        {"key": "1", "name": "Lyra"},
        {"key": "2", "name": "Eldrin"}
    ]
    # Setup user inputs
    mock_cli["prompt_input"].side_effect = [
        " Nova  ",
        "A futuristic hacker",
        "Inside a high-tech lab",
        "  I'm in.  "
    ]

    result = create_personality()

    # Check prompt_input calls
    assert mock_cli["prompt_input"].call_count == 4
    mock_cli["header"].assert_called_once_with("Create a new persona")

    expected_persona = {
        "key": "3",
        "name": "Nova",
        "system": "A futuristic hacker",
        "Scenario": "Inside a high-tech lab",
        "opening_prompt": "I'm in."
    }

    # Check DB write
    mock_db_col.insert_one.assert_called_once_with(expected_persona)
    mock_cli["info"].assert_called_once_with("Persona 'Nova' created!")
    assert result == expected_persona

def test_create_personality_empty(mock_db_col, mock_cli):
    # Setup empty db mock
    mock_db_col.find.return_value = []
    # Setup user inputs
    mock_cli["prompt_input"].side_effect = [
        "Nova",
        "A futuristic hacker",
        "Inside a high-tech lab",
        "I'm in."
    ]

    result = create_personality()

    expected_persona = {
        "key": "1",
        "name": "Nova",
        "system": "A futuristic hacker",
        "Scenario": "Inside a high-tech lab",
        "opening_prompt": "I'm in."
    }

    mock_db_col.insert_one.assert_called_once_with(expected_persona)
    assert result == expected_persona

def test_pick_personality_valid_choice(mock_db_col, mock_cli, capsys):
    mock_db_col.find.return_value = [
        {"key": "1", "name": "Lyra", "system": "sys1", "Scenario": "scen1", "opening_prompt": "hello"},
        {"key": "2", "name": "Eldrin", "system": "sys2", "Scenario": "scen2", "opening_prompt": "hi"}
    ]
    mock_cli["prompt_input"].return_value = " 2 "

    result = pick_personality()

    mock_cli["header"].assert_called_once_with("Pick a personality")
    captured = capsys.readouterr()
    assert "  1. Lyra" in captured.out
    assert "  2. Eldrin" in captured.out
    assert "  N. Create new persona" in captured.out
    assert result == {"key": "2", "name": "Eldrin", "system": "sys2", "Scenario": "scen2", "opening_prompt": "hi"}

def test_pick_personality_create_new(mock_db_col, mock_cli, mocker):
    mock_db_col.find.return_value = [
        {"key": "1", "name": "Lyra"}
    ]
    mock_cli["prompt_input"].return_value = "n"
    
    # Mock create_personality to avoid calling its prompts/logic
    mock_new_persona = {"key": "2", "name": "Nova"}
    mock_create = mocker.patch("app.personalities.create_personality", return_value=mock_new_persona)

    result = pick_personality()

    mock_create.assert_called_once()
    assert result == mock_new_persona

def test_pick_personality_invalid_choice(mock_db_col, mock_cli, capsys):
    mock_db_col.find.return_value = [
        {"key": "1", "name": "Lyra", "system": "sys1", "Scenario": "scen1", "opening_prompt": "hello"},
        {"key": "2", "name": "Eldrin", "system": "sys2", "Scenario": "scen2", "opening_prompt": "hi"}
    ]
    mock_cli["prompt_input"].return_value = "invalid"

    result = pick_personality()

    mock_cli["info"].assert_called_once_with("Invalid choice, defaulting to first persona.")
    assert result == {"key": "1", "name": "Lyra", "system": "sys1", "Scenario": "scen1", "opening_prompt": "hello"}

def test_pick_personality_empty_db_create_new(mock_db_col, mock_cli, mocker):
    mock_db_col.find.return_value = []
    mock_cli["prompt_input"].return_value = "n"
    
    mock_new_persona = {"key": "1", "name": "Nova"}
    mock_create = mocker.patch("app.personalities.create_personality", return_value=mock_new_persona)

    result = pick_personality()

    mock_create.assert_called_once()
    assert result == mock_new_persona

def test_pick_personality_empty_db_invalid_choice(mock_db_col, mock_cli, mocker):
    mock_db_col.find.return_value = []
    mock_cli["prompt_input"].return_value = "invalid"

    mock_new_persona = {"key": "1", "name": "Nova"}
    mock_create = mocker.patch("app.personalities.create_personality", return_value=mock_new_persona)

    result = pick_personality()

    mock_create.assert_called_once()
    assert result == mock_new_persona

