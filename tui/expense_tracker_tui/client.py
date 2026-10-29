"""HTTP client for the Expense Tracker backend. The TUI never touches the database."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"


class ApiError(Exception):
    """A request failed. str(e) is a message safe to show to the user."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class AuthExpired(ApiError):
    """The server no longer accepts our session token (expired, logged out elsewhere, or missing)."""


def format_money(minor: int, symbol: str = "₹") -> str:
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    return f"{sign}{symbol}{minor // 100:,}.{minor % 100:02d}"


def minor_to_decimal_str(minor: int) -> str:
    """Exact: 45050 -> '450.50' (the API takes decimal strings for requests)."""
    return f"{minor // 100}.{minor % 100:02d}"


def _detail(resp: httpx.Response) -> str:
    try:
        d = resp.json().get("detail")
    except Exception:
        return f"Server error ({resp.status_code})"
    if isinstance(d, list) and d:  # FastAPI validation errors
        msg = str(d[0].get("msg", "Invalid input"))
        loc = [str(x) for x in d[0].get("loc", []) if x not in ("body", "query", "path")]
        msg = msg.removeprefix("Value error, ")
        return f"{loc[-1]}: {msg}" if loc else msg
    return str(d) if d else f"Request failed ({resp.status_code})"


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, http: Optional[httpx.Client] = None):
        self.base_url = (base_url or os.environ.get("EXPENSE_TRACKER_API") or DEFAULT_URL).rstrip("/")
        self._http = http or httpx.Client(base_url=self.base_url, timeout=10.0)
        self.token: Optional[str] = None

    # ------------------------------------------------------------ plumbing
    def _request(self, method: str, path: str, *, json: Any = None, auth: bool = True) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"} if (auth and self.token) else {}
        try:
            resp = self._http.request(method, f"{API_PREFIX}{path}", json=json, headers=headers)
        except httpx.HTTPError:
            raise ApiError(f"Cannot reach the server at {self.base_url}") from None
        if resp.status_code == 401 and auth:
            self.token = None
            raise AuthExpired("Session expired. Please log in again.", 401)
        if resp.is_success:
            return None if resp.status_code == 204 else resp.json()
        raise ApiError(_detail(resp), resp.status_code)

    # ---------------------------------------------------------------- auth
    def register(self, username: str, password: str, display_name: Optional[str] = None) -> Dict:
        return self._request("POST", "/auth/register", auth=False,
                             json={"username": username, "password": password, "display_name": display_name or None})

    def login(self, username: str, password: str) -> Dict:
        data = self._request("POST", "/auth/login", auth=False, json={"username": username, "password": password})
        self.token = data["token"]
        return data["user"]

    def logout(self) -> None:
        """Ends the session on the server too, so the token is dead even if someone copied it."""
        try:
            if self.token:
                self._request("POST", "/auth/logout")
        except ApiError:
            pass  # already expired or server unreachable: either way we are logging out locally
        self.token = None

    # -------------------------------------------------------------- groups
    def my_groups(self) -> List[Dict]:
        return self._request("GET", "/groups")

    def create_group(self, name: str) -> Dict:
        return self._request("POST", "/groups", json={"name": name})

    def join_group(self, invite_code: str) -> Dict:
        return self._request("POST", "/groups/join", json={"invite_code": invite_code})

    def group(self, gid: str) -> Dict:
        return self._request("GET", f"/groups/{gid}")

    # ------------------------------------------------------------ expenses
    def expenses(self, gid: str) -> List[Dict]:
        return self._request("GET", f"/groups/{gid}/expenses")

    def add_expense(self, gid: str, amount: str, description: str, category: str,
                    payer_id: Optional[str], participants: Optional[List[str]]) -> Dict:
        return self._request("POST", f"/groups/{gid}/expenses", json={
            "amount": amount, "description": description, "category": category,
            "payer_id": payer_id, "participants": participants})

    def settlements(self, gid: str) -> List[Dict]:
        return self._request("GET", f"/groups/{gid}/settlements")

    def settle(self, gid: str, from_user_id: str, to_user_id: str, amount_minor: int) -> Dict:
        return self._request("POST", f"/groups/{gid}/settlements", json={
            "from_user_id": from_user_id, "to_user_id": to_user_id, "amount": minor_to_decimal_str(amount_minor)})

    def balances(self, gid: str) -> Dict:
        return self._request("GET", f"/groups/{gid}/balances")

    def plan(self, gid: str) -> Dict:
        return self._request("GET", f"/groups/{gid}/plan")

    def categories(self, gid: str) -> List[Dict]:
        return self._request("GET", f"/groups/{gid}/categories")

    def undo(self, gid: str) -> Dict:
        return self._request("POST", f"/groups/{gid}/undo")
