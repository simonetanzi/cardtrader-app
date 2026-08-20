import os
import re
import secrets
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import inspect, text

from catalog import CONDITIONS, DEFAULT_LANGUAGES, LANGUAGES, MAGIC_GAME_ID, MAGIC_GAME_NAME, find_blueprint, search_blueprints
from config import Config
from extensions import db, login_manager
from models import User, Watchlist, WatchlistItem
from price_check import (
    money_from_cents,
    product_condition,
    product_language,
    run_price_check,
    seller_name,
)


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)

    register_template_helpers(app)
    register_csrf(app)
    register_commands(app)
    register_routes(app)

    with app.app_context():
        initialize_database()

    return app


def register_template_helpers(app):
    @app.context_processor
    def inject_helpers():
        token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return {
            "csrf_token": token,
            "cardtrader_card_url": build_cardtrader_card_url,
            "game_name": get_game_name,
            "language_label": get_language_label,
            "money_from_cents": money_from_cents,
            "seller_name": seller_name,
            "product_condition": product_condition,
            "product_language": product_language,
            "api_configured": (
                current_user.is_authenticated
                and (
                    current_user.has_cardtrader_api_token
                    or bool(app.config["CARDTRADER_API_TOKEN"])
                )
            ),
        }


def register_csrf(app):
    @app.before_request
    def protect_post_requests():
        if request.method != "POST":
            return
        expected = session.get("csrf_token")
        received = request.form.get("csrf_token")
        if not expected or not received or not secrets.compare_digest(expected, received):
            abort(400, "Invalid form token.")


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        created_users = initialize_database()
        if created_users:
            print(f"Created user(s): {', '.join(created_users)}")
        else:
            print("Database initialized. Set ADMIN_USERNAME/ADMIN_PASSWORD or USER_USERNAME/USER_PASSWORD to create users.")


def initialize_database():
    db.create_all()
    ensure_database_schema()
    created_users = []
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    customer_username = os.environ.get("USER_USERNAME")
    customer_password = os.environ.get("USER_PASSWORD")

    if create_user_from_env(admin_username, admin_password, is_admin=True):
        created_users.append(admin_username)
    if create_user_from_env(customer_username, customer_password, is_admin=False):
        created_users.append(customer_username)
    if current_app.config.get("ENABLE_GUEST_ACCOUNT", False):
        guest_username = current_app.config["GUEST_USERNAME"]
        if create_guest_user(guest_username):
            created_users.append(guest_username)

    ensure_admin_user(admin_username)
    return created_users


def create_guest_user(username):
    username = (username or "guest").strip()
    user = User.query.filter_by(username=username).first()
    if user:
        if not user.is_guest:
            return False
        return False

    user = User(username=username, is_guest=True)
    # Guest access is passwordless. Keep an unguessable hash so the normal login
    # form can never be used to authenticate this shared account.
    user.set_password(secrets.token_urlsafe(48))
    db.session.add(user)
    db.session.commit()
    return True


def create_user_from_env(username, password, is_admin=False):
    username = (username or "").strip()
    if not username or not password:
        return False
    if User.query.filter_by(username=username).first():
        return False

    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return True


def ensure_admin_user(username=None):
    if username:
        user = User.query.filter_by(username=username).first()
        if (
            user
            and not user.is_guest
            and not user.is_admin
            and User.query.filter_by(is_admin=True).count() == 0
        ):
            user.is_admin = True
            db.session.commit()
            return

    if User.query.filter_by(is_admin=True).count() == 0:
        first_user = User.query.filter_by(is_guest=False).order_by(User.id).first()
        if first_user:
            first_user.is_admin = True
            db.session.commit()


def ensure_database_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("user")}
    user_table = db.engine.dialect.identifier_preparer.quote("user")
    boolean_default = "FALSE" if db.engine.dialect.name == "postgresql" else "0"
    with db.engine.begin() as connection:
        if "is_admin" not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE {user_table} "
                    f"ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT {boolean_default}"
                )
            )
        if "is_guest" not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE {user_table} "
                    f"ADD COLUMN is_guest BOOLEAN NOT NULL DEFAULT {boolean_default}"
                )
            )
        if "cardtrader_api_token" not in existing_columns:
            connection.execute(text(f"ALTER TABLE {user_table} ADD COLUMN cardtrader_api_token TEXT"))
        if "active_watchlist_id" not in existing_columns:
            connection.execute(text(f"ALTER TABLE {user_table} ADD COLUMN active_watchlist_id INTEGER"))


def parse_price_to_cents(raw_value):
    value = (raw_value or "").strip().replace(",", ".")
    if not value:
        return None
    return int(round(float(value) * 100))


def slugify(text):
    text = (text or "").lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def get_game_name(game_id):
    if game_id == MAGIC_GAME_ID:
        return MAGIC_GAME_NAME
    return f"Game {game_id}"


def get_language_label(language_code):
    for code, label in LANGUAGES:
        if code == language_code:
            return label
    return language_code


def build_cardtrader_card_url(card):
    if isinstance(card, dict):
        image_url = card.get("image_url")
        name = card.get("name", "")
        expansion_name = card.get("expansion_name", "")
    else:
        image_url = getattr(card, "image_url", None)
        name = getattr(card, "name", "")
        expansion_name = getattr(card, "expansion_name", "")

    if image_url:
        filename = str(image_url).rsplit("/", 1)[-1]
        if filename.startswith("preview_"):
            filename = filename.replace("preview_", "", 1)
        for extension in [".jpg", ".jpeg", ".png", ".webp"]:
            if filename.endswith(extension):
                filename = filename[: -len(extension)]
                break
        if filename:
            return f"https://www.cardtrader.com/en/cards/{filename}"

    return f"https://www.cardtrader.com/en/cards/{slugify(f'{name} {expansion_name}')}"


def user_watchlists():
    return Watchlist.query.filter_by(user_id=current_user.id).order_by(Watchlist.id).all()


def get_or_create_active_watchlist():
    watchlist = None

    if current_user.active_watchlist_id:
        watchlist = Watchlist.query.filter_by(
            id=current_user.active_watchlist_id,
            user_id=current_user.id,
        ).first()

    if watchlist is None:
        watchlist = Watchlist.query.filter_by(user_id=current_user.id).order_by(Watchlist.id).first()

    if watchlist is None:
        watchlist = Watchlist(name="Watchlist 1", user_id=current_user.id)
        db.session.add(watchlist)
        db.session.flush()

    if current_user.active_watchlist_id != watchlist.id:
        current_user.active_watchlist_id = watchlist.id
        db.session.commit()

    return watchlist


def make_next_watchlist_name():
    return f"Watchlist {len(user_watchlists()) + 1}"


def wants_safe_redirect(target):
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme


def reject_guest_watchlist_management():
    if current_user.is_guest:
        abort(403, "The guest demo uses one shared watchlist.")


def register_routes(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and not user.is_guest and user.check_password(password):
                login_user(user)
                target = request.args.get("next")
                if wants_safe_redirect(target):
                    return redirect(target)
                return redirect(url_for("index"))
            flash("Login failed. Check the username and password.", "error")

        return render_template(
            "login.html",
            guest_enabled=app.config["ENABLE_GUEST_ACCOUNT"],
        )

    @app.route("/guest-login", methods=["POST"])
    def guest_login():
        if not app.config["ENABLE_GUEST_ACCOUNT"]:
            abort(404)
        user = User.query.filter_by(
            username=app.config["GUEST_USERNAME"],
            is_guest=True,
        ).first()
        if user is None:
            abort(503, "Guest account is not available.")
        login_user(user)
        return redirect(url_for("index"))

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/config", methods=["GET", "POST"])
    @login_required
    def config_page():
        if current_user.is_guest:
            flash("The shared guest account cannot change credentials or API settings.", "info")
            return redirect(url_for("index"))
        if request.method == "POST":
            form_action = request.form.get("form_action", "api_token")
            if form_action == "change_password":
                current_password = request.form.get("current_password", "")
                new_password = request.form.get("new_password", "")
                confirm_password = request.form.get("confirm_password", "")

                if not current_user.check_password(current_password):
                    flash("Current password is incorrect.", "error")
                    return redirect(url_for("config_page"))
                if len(new_password) < 8:
                    flash("New password must be at least 8 characters.", "error")
                    return redirect(url_for("config_page"))
                if new_password != confirm_password:
                    flash("New password and confirmation do not match.", "error")
                    return redirect(url_for("config_page"))

                current_user.set_password(new_password)
                db.session.commit()
                flash("Password changed.", "success")
            else:
                token = request.form.get("cardtrader_api_token", "").strip()
                current_user.cardtrader_api_token = token
                db.session.commit()
                flash("CardTrader API token saved for your user.", "success")
            return redirect(url_for("config_page"))

        return render_template("config.html")

    @app.route("/")
    @login_required
    def index():
        query = request.args.get("q", "").strip()
        partial = request.args.get("partial") == "1"
        matches = search_blueprints(query, partial=partial) if query else []
        watchlist = get_or_create_active_watchlist()
        watchlist_blueprint_ids = {item.blueprint_id for item in watchlist.items}
        return render_template(
            "search.html",
            query=query,
            partial=partial,
            matches=matches,
            watchlist=watchlist,
            watchlists=user_watchlists(),
            watchlist_blueprint_ids=watchlist_blueprint_ids,
        )

    @app.route("/watchlist")
    @login_required
    def watchlist():
        watchlist = get_or_create_active_watchlist()
        return render_template(
            "watchlist.html",
            watchlist=watchlist,
            watchlists=user_watchlists(),
            languages=LANGUAGES,
            conditions=CONDITIONS,
        )

    @app.route("/watchlist/switch", methods=["POST"])
    @login_required
    def switch_watchlist():
        reject_guest_watchlist_management()
        watchlist_id_raw = request.form.get("watchlist_id", "").strip()
        try:
            watchlist_id = int(watchlist_id_raw)
        except ValueError:
            abort(400)

        watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first()
        if watchlist is None:
            abort(404)

        current_user.active_watchlist_id = watchlist.id
        db.session.commit()
        return redirect(request.referrer or url_for("watchlist"))

    @app.route("/watchlist/create", methods=["POST"])
    @login_required
    def create_watchlist():
        reject_guest_watchlist_management()
        name = request.form.get("name", "").strip() or make_next_watchlist_name()
        watchlist = Watchlist(name=name[:120], user_id=current_user.id)
        db.session.add(watchlist)
        db.session.flush()
        current_user.active_watchlist_id = watchlist.id
        db.session.commit()
        flash("New watchlist created.", "success")
        return redirect(url_for("watchlist"))

    @app.route("/watchlist/rename", methods=["POST"])
    @login_required
    def rename_watchlist():
        reject_guest_watchlist_management()
        watchlist = get_or_create_active_watchlist()
        name = request.form.get("name", "").strip()
        if not name:
            flash("Watchlist name cannot be empty.", "error")
            return redirect(url_for("watchlist"))

        watchlist.name = name[:120]
        db.session.commit()
        flash("Watchlist renamed.", "success")
        return redirect(url_for("watchlist"))

    @app.route("/watchlist/delete-active", methods=["POST"])
    @login_required
    def delete_active_watchlist():
        reject_guest_watchlist_management()
        watchlist = get_or_create_active_watchlist()
        if len(user_watchlists()) <= 1:
            flash("You must keep at least one watchlist.", "error")
            return redirect(url_for("watchlist"))

        db.session.delete(watchlist)
        db.session.flush()
        replacement = Watchlist.query.filter_by(user_id=current_user.id).order_by(Watchlist.id).first()
        current_user.active_watchlist_id = replacement.id if replacement else None
        db.session.commit()
        flash("Active watchlist deleted.", "info")
        return redirect(url_for("watchlist"))

    @app.route("/watchlist/add", methods=["POST"])
    @login_required
    def add_to_watchlist():
        watchlist = get_or_create_active_watchlist()
        blueprint = find_blueprint(request.form.get("blueprint_id"))
        if blueprint is None:
            abort(404)

        existing = WatchlistItem.query.filter_by(
            watchlist_id=watchlist.id,
            blueprint_id=blueprint["blueprint_id"],
        ).first()
        if existing:
            flash("That card is already in the watchlist.", "info")
            return redirect(url_for("watchlist"))

        item = WatchlistItem(
            watchlist_id=watchlist.id,
            blueprint_id=blueprint["blueprint_id"],
            name=blueprint.get("name", ""),
            version=blueprint.get("version"),
            game_id=blueprint.get("game_id"),
            expansion_name=blueprint.get("expansion_name"),
            collector_number=blueprint.get("collector_number"),
            image_url=blueprint.get("image_url"),
            allowed_languages=",".join(DEFAULT_LANGUAGES),
        )
        db.session.add(item)
        db.session.commit()
        flash("Card added to watchlist.", "success")
        return redirect(url_for("watchlist"))

    @app.route("/watchlist/toggle", methods=["POST"])
    @login_required
    def toggle_watchlist_item():
        watchlist = get_or_create_active_watchlist()
        blueprint = find_blueprint(request.form.get("blueprint_id"))
        if blueprint is None:
            abort(404)

        existing = WatchlistItem.query.filter_by(
            watchlist_id=watchlist.id,
            blueprint_id=blueprint["blueprint_id"],
        ).first()

        if existing:
            db.session.delete(existing)
            db.session.commit()
            flash("Card removed from watchlist.", "info")
        else:
            item = WatchlistItem(
                watchlist_id=watchlist.id,
                blueprint_id=blueprint["blueprint_id"],
                name=blueprint.get("name", ""),
                version=blueprint.get("version"),
                game_id=blueprint.get("game_id"),
                expansion_name=blueprint.get("expansion_name"),
                collector_number=blueprint.get("collector_number"),
                image_url=blueprint.get("image_url"),
                allowed_languages=",".join(DEFAULT_LANGUAGES),
            )
            db.session.add(item)
            db.session.commit()
            flash("Card added to watchlist.", "success")

        return redirect(request.referrer or url_for("index"))

    @app.route("/watchlist/update-all", methods=["POST"])
    @login_required
    def update_all_watchlist_items():
        watchlist = get_or_create_active_watchlist()
        valid_language_codes = [code for code, _label in LANGUAGES]

        for item in watchlist.items:
            try:
                item.max_price_cents = parse_price_to_cents(
                    request.form.get(f"max_price_{item.id}")
                )
            except ValueError:
                flash(f"Target price for {item.name} must be a number.", "error")
                return redirect(url_for("watchlist"))

            condition = request.form.get(f"minimum_condition_{item.id}")
            if condition in CONDITIONS:
                item.minimum_condition = condition

            selected_languages = request.form.getlist(f"allowed_languages_{item.id}")
            selected_languages = [
                language for language in selected_languages
                if language in valid_language_codes
            ]
            item.allowed_languages = ",".join(selected_languages or DEFAULT_LANGUAGES)

        db.session.commit()
        flash("Watchlist settings updated.", "success")
        return redirect(url_for("watchlist"))

    @app.route("/watchlist/item/<int:item_id>/update", methods=["POST"])
    @login_required
    def update_watchlist_item(item_id):
        item = db.session.get(WatchlistItem, item_id)
        if item is None or item.watchlist.user_id != current_user.id:
            abort(404)

        selected_languages = [
            code for code, _label in LANGUAGES if request.form.get(f"lang_{code}") == "on"
        ]
        if not selected_languages:
            selected_languages = DEFAULT_LANGUAGES

        try:
            item.max_price_cents = parse_price_to_cents(request.form.get("max_price"))
        except ValueError:
            flash("Target price must be a number, for example 1.25.", "error")
            return redirect(url_for("watchlist"))

        condition = request.form.get("minimum_condition")
        if condition in CONDITIONS:
            item.minimum_condition = condition
        item.allowed_languages = ",".join(selected_languages)
        db.session.commit()
        flash("Watchlist item updated.", "success")
        return redirect(url_for("watchlist"))

    @app.route("/watchlist/item/<int:item_id>/delete", methods=["POST"])
    @login_required
    def delete_watchlist_item(item_id):
        item = db.session.get(WatchlistItem, item_id)
        if item is None or item.watchlist.user_id != current_user.id:
            abort(404)
        db.session.delete(item)
        db.session.commit()
        flash("Card removed from watchlist.", "info")
        return redirect(url_for("watchlist"))

    @app.route("/price-check", methods=["GET", "POST"])
    @login_required
    def price_check():
        watchlist = get_or_create_active_watchlist()
        report = None
        if request.method == "POST":
            report = run_price_check(watchlist.items)
        return render_template(
            "price_check.html",
            watchlist=watchlist,
            watchlists=user_watchlists(),
            report=report,
        )


app = create_app()


if __name__ == "__main__":
    app.run(host=os.environ.get("FLASK_RUN_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
