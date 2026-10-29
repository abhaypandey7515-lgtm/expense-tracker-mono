# Expense Tracker TUI

Textual terminal client for the [backend](../backend). It talks to the backend over HTTP and
never touches the database.

    pip install -e .
    expense-tracker-tui                      # server defaults to http://127.0.0.1:8000
    expense-tracker-tui --api http://host:8000   # or set EXPENSE_TRACKER_API

Keys: `a` add expense, `s` settle up, `u` undo, `r` refresh, `g` groups, `l` log out, `q` quit.

Tests run the real backend in-process: `pip install -e ".[dev]" && pytest` (needs `../backend`'s
dependencies installed, see the root README).
