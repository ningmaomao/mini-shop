from __future__ import annotations

from pathlib import Path

from flask import Flask

from .admin import bp as admin_bp
from .auth import bp as auth_bp
from .config import Config
from .extensions import db, login_manager
from .models import User
from .orders import bp as orders_bp
from .payments import bp as payments_bp
from .shop import bp as shop_bp


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_bp)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    return app
