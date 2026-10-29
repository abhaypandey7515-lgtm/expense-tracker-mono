import pytest

from expense_tracker_tui.client import ApiClient, ApiError, AuthExpired, format_money, minor_to_decimal_str


def test_money_formatting():
    assert format_money(-123456) == "-₹1,234.56"
    assert format_money(5) == "₹0.05"
    assert minor_to_decimal_str(45050) == "450.50" and minor_to_decimal_str(7) == "0.07"


def test_error_messages_are_readable(client):
    with pytest.raises(ApiError) as e:
        client.login("nobody_here", "whatever1")
    assert str(e.value) == "Wrong username or password" and not isinstance(e.value, AuthExpired)
    with pytest.raises(ApiError) as e:
        client.register("ab", "password123")
    assert "username" in str(e.value).lower()


def test_logout_kills_the_server_session(client, http):
    client.register("client_user", "password123")
    client.login("client_user", "password123")
    token = client.token
    assert client.my_groups() == []
    client.logout()
    stolen = ApiClient(http=http)
    stolen.token = token                      # a copied token no longer works
    with pytest.raises(AuthExpired):
        stolen.my_groups()


def test_unreachable_server_message():
    c = ApiClient("http://127.0.0.1:1")      # nothing listens here
    with pytest.raises(ApiError) as e:
        c.login("a", "b")
    assert "Cannot reach the server" in str(e.value)
