import asyncio

from textual.widgets import DataTable, Input, Static

from expense_tracker_tui.app import ExpenseTrackerApp, GroupScreen, LoginScreen, MainScreen
from expense_tracker_tui.client import ApiClient


def run(coro):
    return asyncio.run(coro)


async def _login(app, pilot, user, pw="password123", name=None, register=False):
    s = app.screen
    s.query_one("#user", Input).value = user
    s.query_one("#pw", Input).value = pw
    if name:
        s.query_one("#name", Input).value = name
    await pilot.click("#register" if register else "#login")
    await pilot.pause(0.3)   # Textual ignores a repeat click on a Button during its 0.2s "active" animation


def test_full_session(client, http):
    """register -> create group -> add expense -> settle -> undo -> log out"""
    async def go():
        friend = ApiClient(http=http)
        friend.register("bhanu_t", "password123", "Bhanu")
        friend.login("bhanu_t", "password123")

        app = ExpenseTrackerApp(client)
        async with app.run_test(size=(120, 40)) as pilot:
            assert isinstance(app.screen, LoginScreen)
            await _login(app, pilot, "asha_t", name="Asha", register=True)
            assert isinstance(app.screen, GroupScreen)              # no group yet -> set-up screen
            app.screen.query_one("#gname", Input).value = "Flat 4B"
            await pilot.click("#create")
            await pilot.pause()
            assert isinstance(app.screen, MainScreen)

            friend.join_group(app.group["invite_code"])             # a second member arrives
            await pilot.press("r")
            await pilot.pause()

            await pilot.press("a")
            await pilot.pause()
            app.screen.query_one("#desc", Input).value = "Groceries"
            app.screen.query_one("#amt", Input).value = "450.50"
            await pilot.click("#save")
            await pilot.pause()
            assert isinstance(app.screen, MainScreen)
            assert app.screen.query_one("#exp", DataTable).row_count == 1
            assert "owes" in str(app.screen.query_one("#bal", Static).render())

            await pilot.press("s")
            await pilot.pause()
            await pilot.click("#plan0")
            await pilot.pause()
            assert app.screen.query_one("#pay", DataTable).row_count == 1
            assert "All settled" in str(app.screen.query_one("#plan", Static).render())

            await pilot.press("u")                                   # undo the payment
            await pilot.press("u")                                   # undo the expense
            await pilot.pause()
            assert app.screen.query_one("#exp", DataTable).row_count == 0

            await pilot.press("l")
            await pilot.pause()
            assert isinstance(app.screen, LoginScreen) and app.user is None and client.token is None
    run(go())


def test_bad_inputs_show_inline_errors(client):
    async def go():
        app = ExpenseTrackerApp(client)
        async with app.run_test(size=(120, 40)) as pilot:
            await _login(app, pilot, "nobody_such")
            assert "Wrong username or password" in str(app.screen.query_one("#err", Static).render())
            await _login(app, pilot, "ab", register=True)
            assert isinstance(app.screen, LoginScreen) and "username" in str(app.screen.query_one("#err", Static).render()).lower()

            await _login(app, pilot, "eve_t", register=True)         # valid account, then bad group + expense input
            app.screen.query_one("#code", Input).value = "ZZZZZZ"
            await pilot.click("#join")
            await pilot.pause()
            assert "Invalid invite code" in str(app.screen.query_one("#err", Static).render())
            app.screen.query_one("#gname", Input).value = "Eve's place"
            await pilot.click("#create")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            app.screen.query_one("#desc", Input).value = "x"
            app.screen.query_one("#amt", Input).value = "-5"
            await pilot.click("#save")
            await pilot.pause()
            assert "greater than zero" in str(app.screen.query_one("#err", Static).render())
    run(go())


def test_expired_session_sends_user_back_to_login(client, expire_session):
    async def go():
        app = ExpenseTrackerApp(client)
        async with app.run_test(size=(120, 40)) as pilot:
            await _login(app, pilot, "carl_t", register=True)
            app.screen.query_one("#gname", Input).value = "Carl's"
            await pilot.click("#create")
            await pilot.pause()
            assert isinstance(app.screen, MainScreen)
            expire_session(client.token)                             # the server drops our session
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, LoginScreen)               # no protected screen left behind
            assert app.user is None and app.group is None and len(app.screen_stack) == 2
    run(go())


def test_expired_session_while_dialog_open(client, expire_session):
    async def go():
        app = ExpenseTrackerApp(client)
        async with app.run_test(size=(120, 40)) as pilot:
            await _login(app, pilot, "dina_t", register=True)
            app.screen.query_one("#gname", Input).value = "Dina's"
            await pilot.click("#create")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            expire_session(client.token)
            app.screen.query_one("#desc", Input).value = "Lunch"
            app.screen.query_one("#amt", Input).value = "20"
            await pilot.click("#save")
            await pilot.pause()
            assert isinstance(app.screen, LoginScreen) and len(app.screen_stack) == 2
    run(go())
