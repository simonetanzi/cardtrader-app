from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_guest = db.Column(db.Boolean, default=False, nullable=False)
    cardtrader_api_token = db.Column(db.Text)
    active_watchlist_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def has_cardtrader_api_token(self):
        return bool((self.cardtrader_api_token or "").strip())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="Main watchlist")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    items = db.relationship(
        "WatchlistItem",
        backref="watchlist",
        cascade="all, delete-orphan",
        order_by="WatchlistItem.name",
    )


class WatchlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey("watchlist.id"), nullable=False)
    blueprint_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(255))
    game_id = db.Column(db.Integer)
    expansion_name = db.Column(db.String(255))
    collector_number = db.Column(db.String(80))
    image_url = db.Column(db.String(500))
    max_price_cents = db.Column(db.Integer)
    allowed_languages = db.Column(db.String(120), nullable=False, default="en")
    minimum_condition = db.Column(db.String(40), nullable=False, default="Moderately Played")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def allowed_language_list(self):
        return [lang for lang in self.allowed_languages.split(",") if lang]

    def to_check_dict(self):
        return {
            "id": self.id,
            "blueprint_id": self.blueprint_id,
            "name": self.name,
            "version": self.version,
            "game_id": self.game_id,
            "expansion_name": self.expansion_name,
            "collector_number": self.collector_number,
            "image_url": self.image_url,
            "max_price_cents": self.max_price_cents,
            "allowed_languages": self.allowed_language_list(),
            "minimum_condition": self.minimum_condition,
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
