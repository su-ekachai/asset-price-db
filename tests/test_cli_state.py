from src.cli.state import init_state, state


def test_state_initialization():
    init_state(verbose=1)
    assert state.verbose == 1
    assert state.config is not None


def test_state_logging_levels():
    init_state(verbose=0)
    assert state.verbose == 0
    init_state(verbose=2)
    assert state.verbose == 2
