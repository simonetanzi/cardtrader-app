from app import create_app
from config import Config
from extensions import db
from models import User, Watchlist, WatchlistItem


class BootstrapConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


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


def test_env_bootstrap_creates_admin_and_normal_user(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "owner")
    monkeypatch.setenv("ADMIN_PASSWORD", "ownerpass123")
    monkeypatch.setenv("USER_USERNAME", "friend")
    monkeypatch.setenv("USER_PASSWORD", "friendpass123")

    app = create_app(BootstrapConfig)

    with app.app_context():
        owner = User.query.filter_by(username="owner").one()
        friend = User.query.filter_by(username="friend").one()
        assert owner.is_admin is True
        assert friend.is_admin is False
        assert owner.check_password("ownerpass123")
        assert friend.check_password("friendpass123")


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
