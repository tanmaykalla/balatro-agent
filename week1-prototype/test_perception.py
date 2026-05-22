"""
Integration test — requires Balatro + Balatrobot mod running on localhost:8000.
Run with: python3 -m pytest test_perception.py -v
"""
import pytest

from perception import Action, BalatrobotPerception, GameState
from perception import smart_full_house_strategy as greedy_flush_strategy

VALID_PHASES = {"MENU", "BLIND_SELECT", "SELECTING_HAND", "ROUND_EVAL", "SHOP", "GAME_OVER"}


def test_state_read_and_action():
    """Verify: start game → read state → take action → read state."""
    perception = BalatrobotPerception()

    # Start a new game
    perception.start_game()

    # Read initial state
    state = perception.get_state()
    assert isinstance(state, GameState)
    assert state.ante_num >= 1
    assert state.money >= 0
    assert state.chips >= 0
    assert state.round_num >= 0
    assert state.phase in VALID_PHASES
    assert isinstance(state.hand, list)

    # Derive and execute one action based on current state
    action = greedy_flush_strategy(state)
    assert isinstance(action, Action)
    assert action.action_type in {
        "play", "discard", "select_blind", "skip_blind",
        "cash_out", "next_round",
    }

    perception.take_action(action)

    # State after action should still be valid
    state_after = perception.get_state()
    assert isinstance(state_after, GameState)
    assert state_after.phase in VALID_PHASES
