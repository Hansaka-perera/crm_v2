from flask import Flask, render_template

from config import Config
from app.extensions import csrf, db, login_manager


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.main import bp as main_bp
    from app.blueprints.contacts import bp as contacts_bp
    from app.blueprints.deals import bp as deals_bp
    from app.blueprints.leads import bp as leads_bp
    from app.blueprints.activities import bp as activities_bp
    from app.blueprints.insights import bp as insights_bp
    from app.blueprints.inbox import bp as inbox_bp
    from app.blueprints.customers import bp as customers_bp
    from app.blueprints.api import bp as api_bp
    from app.blueprints.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(deals_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp)

    csrf.exempt(api_bp)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template(
            "errors/error.html",
            code=403,
            title="Forbidden",
            message="You do not have permission to do that.",
            section="setup",
        ), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template(
            "errors/error.html",
            code=404,
            title="Not found",
            message="That page or record does not exist.",
            section="setup",
        ), 404

    with app.app_context():
        db.create_all()
        from app.seed import ensure_defaults

        ensure_defaults()

    return app
