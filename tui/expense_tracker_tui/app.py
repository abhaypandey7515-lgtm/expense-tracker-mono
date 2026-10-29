"""Textual TUI. Screens: login -> group set-up -> dashboard (+ add-expense and settle-up dialogs)."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Dict, List, Optional, Tuple

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, Select, SelectionList, Static, TabbedContent, TabPane,
)

from .client import ApiClient, ApiError, AuthExpired, format_money

CATEGORIES = ["Groceries", "Rent", "Utilities", "Internet", "Food", "Transport", "Household", "Fun", "General"]

CSS = """
Screen { align: center middle; }
.card { width: 64; height: auto; max-height: 100%; border: round $primary; padding: 1 2; }
.card Input, .card Select { margin-bottom: 1; }
.title { text-style: bold; color: $accent; margin-bottom: 1; }
.err { color: $error; height: auto; }
.row { height: auto; }
.row Button { margin-right: 1; }
.panel { border: round $primary-darken-1; padding: 0 1; margin: 0 1 1 0; height: auto; }
DataTable { height: 1fr; }
SelectionList { height: 8; margin-bottom: 1; }
.groupbtn { width: 100%; margin-bottom: 1; }
"""


class LoginScreen(Screen):
    """The only screen reachable without a session."""

    BINDINGS = [Binding("ctrl+q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="card"):
            yield Label("Expense Tracker", classes="title")
            yield Input(placeholder="Username", id="user")
            yield Input(placeholder="Password (8+ characters)", password=True, id="pw")
            yield Input(placeholder="Display name (register only)", id="name")
            yield Static("", id="err", classes="err")
            with Horizontal(classes="row"):
                yield Button("Log in", id="login", variant="primary")
                yield Button("Register", id="register")
            yield Static(f"Server: {self.app.client.base_url}", id="server")

    def show_error(self, msg: str) -> None:
        self.query_one("#err", Static).update(msg)

    @on(Input.Submitted)
    def _enter(self) -> None:
        self.query_one("#login", Button).press()

    def _creds(self) -> Tuple[str, str]:
        return self.query_one("#user", Input).value.strip(), self.query_one("#pw", Input).value

    @on(Button.Pressed, "#login")
    def do_login(self) -> None:
        ok, res = self.app.call(self.app.client.login, *self._creds())
        if not ok:
            self.show_error(res)
            return
        self.query_one("#pw", Input).value = ""
        self.app.start_session(res)

    @on(Button.Pressed, "#register")
    def do_register(self) -> None:
        user, pw = self._creds()
        name = self.query_one("#name", Input).value.strip() or None
        ok, res = self.app.call(self.app.client.register, user, pw, name)
        if not ok:
            self.show_error(res)
            return
        self.do_login()  # registering logs you straight in


class GroupScreen(Screen):
    """Create a group, join one with an invite code, or pick one you already belong to."""

    def __init__(self, groups: List[Dict], can_cancel: bool = False):
        super().__init__()
        self.groups = groups
        self.can_cancel = can_cancel

    BINDINGS = [Binding("escape", "cancel", "Back")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="card"):
            yield Label("Your groups" if self.groups else "Set up your group", classes="title")
            for i, g in enumerate(self.groups):
                yield Button(f"{g['name']}  ·  code {g['invite_code']}", id=f"open{i}", classes="groupbtn")
            yield Input(placeholder="New group name (e.g. Flat 4B)", id="gname")
            yield Button("Create group", id="create", variant="primary")
            yield Label("")
            yield Input(placeholder="Or enter an invite code", id="code")
            yield Button("Join group", id="join")
            yield Static("", id="err", classes="err")

    def action_cancel(self) -> None:
        if self.can_cancel:
            self.app.pop_screen()

    def _go(self, fn: Callable, *args: Any) -> None:
        ok, res = self.app.call(fn, *args)
        if not ok:
            if self.app.user is not None:
                self.query_one("#err", Static).update(res)
            return
        self.app.open_group(res)

    @on(Button.Pressed, "#create")
    def create(self) -> None:
        self._go(self.app.client.create_group, self.query_one("#gname", Input).value)

    @on(Button.Pressed, "#join")
    def join(self) -> None:
        self._go(self.app.client.join_group, self.query_one("#code", Input).value)

    @on(Button.Pressed, ".groupbtn")
    def open_existing(self, ev: Button.Pressed) -> None:
        self.app.open_group(self.groups[int(ev.button.id[4:])])


class AddExpense(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "dismiss(False)", "Cancel")]

    def __init__(self, members: List[Dict]):
        super().__init__()
        self.members = members

    def compose(self) -> ComposeResult:
        me = self.app.user["id"]
        with VerticalScroll(classes="card"):
            yield Label("Add expense", classes="title")
            yield Input(placeholder="Description (e.g. Groceries)", id="desc")
            yield Input(placeholder="Amount (e.g. 450.50)", id="amt")
            yield Select([(c, c) for c in CATEGORIES], value="General", allow_blank=False, id="cat")
            yield Label("Paid by:")
            yield Select([(m["display_name"], m["user_id"]) for m in self.members], value=me, allow_blank=False, id="payer")
            yield Label("Split between (space toggles):")
            yield SelectionList(*[(m["display_name"], m["user_id"], True) for m in self.members], id="who")
            yield Static("", id="err", classes="err")
            with Horizontal(classes="row"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Cancel", id="cancel")

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#save")
    def save(self) -> None:
        ok, res = self.app.call(
            self.app.client.add_expense,
            self.app.group["id"],
            self.query_one("#amt", Input).value.strip(),
            self.query_one("#desc", Input).value,
            self.query_one("#cat", Select).value,
            self.query_one("#payer", Select).value,
            list(self.query_one("#who", SelectionList).selected),
        )
        if not ok:
            if self.app.user is not None:  # otherwise the session expired and we are back at login
                self.query_one("#err", Static).update(res)
            return
        self.dismiss(True)


class SettleUp(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "dismiss(False)", "Cancel")]

    def __init__(self, transfers: List[Dict]):
        super().__init__()
        self.transfers = transfers

    def compose(self) -> ComposeResult:
        with Vertical(classes="card"):
            yield Label("Record a payment", classes="title")
            if self.transfers:
                yield Label("Suggested (fewest payments). Click one once it has been paid:")
                for i, t in enumerate(self.transfers):
                    yield Button(f"{t['from_name']} pays {t['to_name']} {format_money(t['amount_minor'])}", id=f"plan{i}")
            else:
                yield Label("Everyone is settled up.")
            yield Static("", id="err", classes="err")
            yield Button("Close", id="close")

    @on(Button.Pressed)
    def pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        if bid == "close":
            self.dismiss(False)
        elif bid.startswith("plan"):
            t = self.transfers[int(bid[4:])]
            ok, res = self.app.call(self.app.client.settle, self.app.group["id"],
                                    t["from_user_id"], t["to_user_id"], t["amount_minor"])
            if not ok:
                if self.app.user is not None:
                    self.query_one("#err", Static).update(res)
                return
            self.dismiss(True)


class MainScreen(Screen):
    BINDINGS = [
        Binding("a", "add", "Add expense"),
        Binding("s", "settle", "Settle up"),
        Binding("u", "undo", "Undo"),
        Binding("r", "refresh", "Refresh"),
        Binding("g", "groups", "Groups"),
        Binding("l", "logout", "Log out"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Dashboard", id="t-dash"):
                with VerticalScroll():
                    yield Static(id="who", classes="panel")
                    yield Static(id="bal", classes="panel")
                    yield Static(id="plan", classes="panel")
                    yield Static(id="cats", classes="panel")
            with TabPane("Expenses", id="t-exp"):
                yield DataTable(id="exp", cursor_type="row", zebra_stripes=True)
            with TabPane("Payments", id="t-pay"):
                yield DataTable(id="pay", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#exp", DataTable).add_columns("Date", "What", "Category", "Paid by", "Amount")
        self.query_one("#pay", DataTable).add_columns("Date", "From", "To", "Amount")
        self.refresh_data()

    def refresh_data(self) -> None:
        c, gid = self.app.client, self.app.group["id"]
        ok, res = self.app.call(lambda: {
            "group": c.group(gid), "bal": c.balances(gid), "plan": c.plan(gid),
            "cats": c.categories(gid), "exps": c.expenses(gid), "pays": c.settlements(gid),
        })
        if not ok:
            if self.app.user is not None:
                self.notify(res, severity="error")
            return
        group, bal, plan = res["group"], res["bal"], res["plan"]
        me = self.app.user["id"]
        self.app.members = group["members"]
        self.sub_title = f"{group['name']}  ·  signed in as {self.app.user['display_name']}"

        self.query_one("#who", Static).update(
            f"[b]Group:[/b] {group['name']}    [b]Invite code:[/b] {group['invite_code']}\n"
            f"[b]Members:[/b] {', '.join(m['display_name'] for m in group['members'])}"
        )
        lines = ["[b]Balances[/b]"]
        for uid, v in sorted(bal["balances"].items(), key=lambda kv: -kv[1]):
            name = bal["names"].get(uid, "?") + (" (you)" if uid == me else "")
            if v > 0:
                lines.append(f"  {name:<20} [green]gets back {format_money(v)}[/green]")
            elif v < 0:
                lines.append(f"  {name:<20} [red]owes {format_money(-v)}[/red]")
            else:
                lines.append(f"  {name:<20} settled")
        self.query_one("#bal", Static).update("\n".join(lines))

        pl = [f"[b]Smart settle-up[/b]  (fewest payments)"]
        for t in plan["transfers"]:
            pl.append(f"  {t['from_name']} → {t['to_name']}: {format_money(t['amount_minor'])}")
        if not plan["transfers"]:
            pl.append("  All settled 🎉")
        elif plan["transactions_eliminated"]:
            pl.append(f"  [dim]{plan['simplified_transactions_count']} payments instead of "
                      f"{plan['original_transactions_count']}[/dim]")
        self.query_one("#plan", Static).update("\n".join(pl))

        cats = res["cats"]
        total = sum(x["total_minor"] for x in cats) or 1
        cl = ["[b]Spending by category[/b]"]
        for x in cats:
            cl.append(f"  {x['category']:<12} {format_money(x['total_minor']):>12}  "
                      f"{'█' * max(1, round(20 * x['total_minor'] / total))}")
        if not cats:
            cl.append("  No expenses yet. Press [b]a[/b] to add one.")
        self.query_one("#cats", Static).update("\n".join(cl))

        t = self.query_one("#exp", DataTable)
        t.clear()
        for e in res["exps"]:
            t.add_row(e["created_at"][:10], e["description"], e["category"], e["payer_name"], format_money(e["amount_minor"]))
        p = self.query_one("#pay", DataTable)
        p.clear()
        for s in res["pays"]:
            p.add_row(s["created_at"][:10], s["from_name"], s["to_name"], format_money(s["amount_minor"]))

    # ------------------------------------------------------------- actions
    def action_refresh(self) -> None:
        self.refresh_data()

    def action_add(self) -> None:
        self.app.push_screen(AddExpense(self.app.members), lambda ok: self._after(ok, "Expense added"))

    def action_settle(self) -> None:
        ok, plan = self.app.call(self.app.client.plan, self.app.group["id"])
        if not ok:
            if self.app.user is not None:
                self.notify(plan, severity="error")
            return
        self.app.push_screen(SettleUp(plan["transfers"]), lambda ok: self._after(ok, "Payment recorded"))

    def action_undo(self) -> None:
        ok, res = self.app.call(self.app.client.undo, self.app.group["id"])
        if not ok:
            if self.app.user is not None:
                self.notify(res, severity="error")
            return
        self.notify(res["message"], severity="information" if res["success"] else "warning")
        self.refresh_data()

    def action_groups(self) -> None:
        ok, groups = self.app.call(self.app.client.my_groups)
        if ok:
            self.app.push_screen(GroupScreen(groups, can_cancel=True))

    def action_logout(self) -> None:
        self.app.logout()

    def _after(self, ok: Optional[bool], msg: str) -> None:
        if self.app.user is None:  # session expired while the dialog was open
            return
        if ok:
            self.notify(msg)
        self.refresh_data()


class ExpenseTrackerApp(App):
    TITLE = "Expense Tracker"
    CSS = CSS

    def __init__(self, client: Optional[ApiClient] = None):
        super().__init__()
        self.client = client or ApiClient()
        self.user: Optional[Dict] = None
        self.group: Optional[Dict] = None
        self.members: List[Dict] = []

    def on_mount(self) -> None:
        self.push_screen(LoginScreen())

    # ------------------------------------------------------- session / auth
    def call(self, fn: Callable, *args: Any, **kw: Any) -> Tuple[bool, Any]:
        """Run an API call. Returns (True, result) or (False, message).
        If the server says the session is no longer valid, drop back to the login screen."""
        try:
            return True, fn(*args, **kw)
        except AuthExpired as e:
            self.session_expired(str(e))
            return False, str(e)
        except ApiError as e:
            return False, str(e)

    def start_session(self, user: Dict) -> None:
        self.user = user
        ok, groups = self.call(self.client.my_groups)
        if not ok:
            return
        self._reset_to(None)
        if groups:
            self.open_group(groups[0])
        else:
            self.push_screen(GroupScreen([]))

    def open_group(self, group: Dict) -> None:
        self.group = group
        self._reset_to(MainScreen())

    def logout(self) -> None:
        self.client.logout()
        self._clear()
        self._reset_to(LoginScreen())

    def session_expired(self, message: str) -> None:
        self._clear()
        self._reset_to(LoginScreen())
        self.notify(message, severity="warning")

    def _clear(self) -> None:
        self.user = self.group = None
        self.members = []

    def _reset_to(self, screen: Optional[Screen]) -> None:
        """Pop everything above the base screen so no protected screen stays in the history."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        if screen:
            self.push_screen(screen)


def main() -> None:
    parser = argparse.ArgumentParser(description="Expense Tracker TUI")
    parser.add_argument("--api", help="backend URL (default: $EXPENSE_TRACKER_API or http://127.0.0.1:8000)")
    args = parser.parse_args()
    ExpenseTrackerApp(ApiClient(args.api)).run()


if __name__ == "__main__":
    main()
