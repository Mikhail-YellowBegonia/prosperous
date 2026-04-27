"""
Shared fixtures and test infrastructure for the Prosperous test suite.
"""

import sys
import os
import signal
import pytest

# Ensure the project root is importable regardless of where pytest is invoked.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# ---------------------------------------------------------------------------
# RenderEngine factory
# ---------------------------------------------------------------------------


@pytest.fixture
def make_engine(monkeypatch):
    """
    Return a callable that produces a RenderEngine with a fixed 80×24 buffer.

    Side-effects suppressed:
      - os.get_terminal_size() → returns a stable (80, 24) size
      - sys.stdout.write / flush → silenced (no terminal output)
      - signal.signal(SIGWINCH, …) → no-op to avoid signal errors in threads
    """
    import io

    def _make(width=80, height=24):
        # Provide a stable terminal size; *_ absorbs the optional fd argument
        FakeTermSize = os.terminal_size((width, height))
        monkeypatch.setattr(os, "get_terminal_size", lambda *_: FakeTermSize)

        # Suppress SIGWINCH registration (not valid in all test environments)
        monkeypatch.setattr(signal, "signal", lambda *a, **kw: None)

        from prosperous.engine import RenderEngine

        engine = RenderEngine()
        return engine

    return _make


@pytest.fixture
def engine(make_engine):
    """A ready-to-use 80×24 RenderEngine."""
    return make_engine()


# ---------------------------------------------------------------------------
# Theme isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_theme():
    """
    Reset the global theme to DEFAULT_THEME before every test so that
    theme mutations in one test do not bleed into another.
    """
    from prosperous import theme as theme_module
    from prosperous.theme import DEFAULT_THEME
    import copy

    original = copy.deepcopy(DEFAULT_THEME)
    yield
    theme_module._theme = copy.deepcopy(original)
