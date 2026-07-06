from extensions import db
from models import User, Watchlist, WatchlistItem


def set_csrf(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf"


def post(client, path, data=None, **kwargs):
    payload = dict(data or {})
    payload["csrf_token"] = "test-csrf"
    return client.post(path, data=payload, **kwargs)


def make_user(username, password="password123", is_admin=False):
    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, username, password="password123"):
    set_csrf(client)
    return post(client, "/login", {"username": username, "password": password})


def make_watchlist_with_item(user):
    watchlist = Watchlist(name="Customer list", user_id=user.id)
    db.session.add(watchlist)
    db.session.flush()
    item = WatchlistItem(
        watchlist_id=watchlist.id,
        blueprint_id=6,
        name="Ghalta, Primal Hunger",
        game_id=1,
        allowed_languages="en",
    )
    db.session.add(item)
    db.session.commit()
    return watchlist, item


def test_admin_can_create_normal_user(app_context):
    owner = make_user("owner", is_admin=True)
    client = app_context.test_client()
    login(client, owner.username)

    response = post(
        client,
        "/admin/users",
        {"username": "friend", "password": "temporary123"},
    )

    assert response.status_code == 302
    friend = User.query.filter_by(username="friend").one()
    assert friend.check_password("temporary123")
    assert friend.is_admin is False


def test_non_admin_cannot_manage_users(app_context):
    user = make_user("friend")
    client = app_context.test_client()
    login(client, user.username)

    response = client.get("/admin/users")

    assert response.status_code == 403


def test_admin_delete_user_removes_watchlists_and_items(app_context):
    owner = make_user("owner", is_admin=True)
    friend = make_user("friend")
    watchlist, item = make_watchlist_with_item(friend)
    client = app_context.test_client()
    login(client, owner.username)

    response = post(client, f"/admin/users/{friend.id}/delete")

    assert response.status_code == 302
    assert db.session.get(User, friend.id) is None
    assert db.session.get(Watchlist, watchlist.id) is None
    assert db.session.get(WatchlistItem, item.id) is None


def test_user_can_change_own_password(app_context):
    user = make_user("friend", password="oldpass123")
    client = app_context.test_client()
    login(client, user.username, "oldpass123")

    response = post(
        client,
        "/config",
        {
            "form_action": "change_password",
            "current_password": "oldpass123",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )

    assert response.status_code == 302
    assert User.query.filter_by(username="friend").one().check_password("newpass123")


def test_user_cannot_edit_another_users_watchlist_item(app_context):
    owner = make_user("owner")
    friend = make_user("friend")
    _watchlist, item = make_watchlist_with_item(friend)
    client = app_context.test_client()
    login(client, owner.username)

    response = post(
        client,
        f"/watchlist/item/{item.id}/update",
        {"max_price": "1.00", "minimum_condition": "Near Mint", "lang_en": "on"},
    )

    assert response.status_code == 404
