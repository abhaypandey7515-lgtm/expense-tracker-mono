# Expense Tracker

A group expense tracker with a **FastAPI backend** and a **Textual terminal UI**.
People register, log in, create or join a group with an invite code, record shared expenses,
see who owes whom, settle up with the fewest payments, and undo mistakes.

```
backend/   FastAPI + async SQLAlchemy + SQLite   (auth, groups, ledger, debt simplification, undo)
tui/       Textual client that talks to the backend over HTTP
```

Derived from the backend and TUI of [chore-mono-public](https://github.com/itztonydev/chore-mono-public)
(see the first commit); the chore rotation, sarcastic alerts, Google/Ed25519 login and the web
frontend were removed.

## Run it

```bash
# terminal 1: backend  (API docs at http://127.0.0.1:8000/docs)
cd backend && pip install -e . && uvicorn app.main:app

# terminal 2: TUI
cd tui && pip install -e . && expense-tracker-tui
```

Or `docker compose up` for the backend. Configuration is in `backend/.env.example`.

## Tests

```bash
cd backend && pip install -e ".[dev]" && pytest        # API, authorization, DSA engines
cd tui     && pip install -e ".[dev]" && pytest        # client + full TUI sessions against the real backend
```

## Backend architecture

| Layer         | Where                    | Role                                                                                                           |
| ------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| API           | `app/api/v1/endpoints/`  | `auth`, `groups`, `expenses` routers                                                                           |
| Authorization | `app/api/deps.py`        | `get_current_user` (session token -> user, 401) and `require_member` (membership of the group in the URL, 403) |
| Services      | `app/services/ledger.py` | queries that feed the algorithms                                                                               |
| Models        | `app/models/`            | tables `users, sessions, groups, members, expenses, expense_shares, settlements, actions`                      |
| Core          | `app/core/`              | PBKDF2 hashing and tokens (`security.py`), integer money (`money.py`), UUIDv7 ids, settings                    |

### Security model

- Passwords: PBKDF2-HMAC-SHA256, 200,000 iterations, 16-byte random salt, constant-time compare.
  Unknown usernames are hashed anyway and get the same error as a wrong password.
- Sessions: random 256-bit token stored in the `sessions` table with an expiry (7 days). Logout
  deletes the row, so the token dies immediately.
- Authorization: every group route depends on `require_member`; non-members get 403, and a group
  that doesn't exist looks the same as one you are not in.

### Money

Stored as integer paise (never floats). Requests take decimal amounts (`"450.50"`); responses
use integer `*_minor` fields. Equal splits give leftover paise to the first participants so
shares always add up exactly; custom shares must sum to the total.

### Algorithms

- **Hash map** - net balance per member (`compute_net_balances`).
- **Directed graph** - debtor -> creditor edges, netted pairwise (`build_obligation_graph`).
- **Heaps** - greedy min-cash-flow matching of the largest debtor with the largest creditor:
  at most N-1 payments, O(N log N) (`simplify_balances`).
- **Stack** - undo rebuilds the group's LIFO stack from the `actions` table and pops it; expenses
  and payments are soft-deleted (`voided`) so history is kept.

## TUI flow

Login/Register -> (no group yet: create one or join with an invite code) -> dashboard with
Balances, Smart settle-up, Spending by category, plus Expenses and Payments tabs.
Keys: `a` add expense, `s` settle up, `u` undo, `r` refresh, `g` groups, `l` log out, `q` quit.
The login screen is the only screen reachable without a session. If the server rejects the
token (expired or logged out elsewhere) the TUI clears its state and returns to the login screen.

## Known limitations

No login rate limiting; the session token lives in memory only (log in again after restarting
the TUI); one currency; no password reset; the TUI makes blocking HTTP calls (fine on localhost,
a worker thread would be better over a slow link).
