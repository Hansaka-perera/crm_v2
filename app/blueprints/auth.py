from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, Email, ValidationError

from app.models import User

bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(message="Please enter your email address.")],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Please enter your password.")],
    )
    remember = BooleanField("Remember me")

    def validate_email(self, field):
        value = (field.data or "").strip().lower()

        # Allow local development accounts such as admin@itglow.local.
        if value.endswith("@itglow.local"):
            username = value.removesuffix("@itglow.local")

            if not username or any(char.isspace() for char in username):
                raise ValidationError("Enter a valid local email address.")

            field.data = value
            return

        # Validate ordinary email addresses normally.
        Email()(self, field)


def is_safe_redirect_url(target):
    """Allow redirects only to the same host."""
    if not target:
        return False

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))

    return (
        redirect_url.scheme in ("http", "https")
        and redirect_url.netloc == host_url.netloc
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("contacts.people"))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        user = User.query.filter(
            User.email.ilike(email)
        ).first()

        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)

            next_url = request.args.get("next")

            if next_url and is_safe_redirect_url(next_url):
                return redirect(next_url)

            return redirect(url_for("contacts.people"))

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    logout_user()

    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
