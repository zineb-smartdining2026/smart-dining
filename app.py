from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, desc, or_

app = Flask(__name__)
app.config["SECRET_KEY"] = "smart_dining_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# =========================
# MODELS
# =========================

favorites = db.Table(
    "favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("dish_id", db.Integer, db.ForeignKey("dish.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    favorite_dishes = db.relationship(
        "Dish",
        secondary=favorites,
        backref=db.backref("liked_by", lazy="dynamic"),
        lazy="dynamic",
    )


class Dish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    spicy_level = db.Column(db.String(50), nullable=False)

    ratings = db.relationship(
        "Rating", backref="dish", lazy=True, cascade="all, delete-orphan"
    )


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey("dish.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "dish_id", name="unique_user_dish_rating"),
    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# HELPERS
# =========================

def seed_dishes():
    if Dish.query.count() > 0:
        return

    dishes = [
        Dish(
            name="Kung Pao Chicken",
            price=12,
            image="kungpao.jpg",
            description="A famous Chinese dish made with diced chicken, peanuts, chili peppers, and vegetables.",
            ingredients="Chicken, peanuts, chili peppers, bell peppers, soy sauce, garlic",
            category="Main Course",
            spicy_level="Medium",
        ),
        Dish(
            name="Sweet and Sour Pork",
            price=10,
            image="sweetandsourpork.jpg",
            description="Crispy pork served with a sweet and tangy sauce, popular in Chinese cuisine.",
            ingredients="Pork, pineapple, bell peppers, vinegar, sugar, ketchup",
            category="Main Course",
            spicy_level="Low",
        ),
        Dish(
            name="Fried Rice",
            price=8,
            image="friedrice.jpg",
            description="A classic stir-fried rice dish mixed with vegetables, egg, and traditional seasonings.",
            ingredients="Rice, egg, carrots, peas, green onions, soy sauce",
            category="Rice Dish",
            spicy_level="Low",
        ),
        Dish(
            name="Dumplings (Jiaozi)",
            price=9,
            image="dumplings.jpg",
            description="Traditional Chinese dumplings filled with meat and vegetables, steamed or boiled.",
            ingredients="Flour dough, minced meat, cabbage, ginger, garlic",
            category="Snack / Appetizer",
            spicy_level="Low",
        ),
        Dish(
            name="Chow Mein",
            price=11,
            image="chowmein.jpg",
            description="Stir-fried noodles with vegetables and savory Chinese sauce.",
            ingredients="Noodles, cabbage, carrots, soy sauce, onions, bean sprouts",
            category="Noodles",
            spicy_level="Medium",
        ),
        Dish(
            name="Hot Pot",
            price=15,
            image="hotpot.jpg",
            description="A traditional communal Chinese dish with simmering broth, meat, seafood, and vegetables.",
            ingredients="Broth, beef, mushrooms, tofu, vegetables, noodles, sauces",
            category="Traditional Dish",
            spicy_level="High",
        ),
    ]

    db.session.add_all(dishes)
    db.session.commit()


def get_average_rating(dish_id):
    ratings = Rating.query.filter_by(dish_id=dish_id).all()
    if ratings:
        avg = sum(r.value for r in ratings) / len(ratings)
        return round(avg, 1)
    return None


def is_admin_user():
    return (
        current_user.is_authenticated
        and current_user.username.lower() in ["admin", "dining_admin"]
    )


# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return redirect(url_for("menu"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("menu"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("register"))

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "warning")
            return redirect(url_for("register"))

        if len(password) < 4:
            flash("Password must be at least 4 characters.", "warning")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists.", "warning")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("menu"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("login"))

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("menu"))
        else:
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/menu")
def menu():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    query = Dish.query

    if search:
        query = query.filter(
            or_(
                Dish.name.ilike(f"%{search}%"),
                Dish.description.ilike(f"%{search}%"),
                Dish.ingredients.ilike(f"%{search}%"),
            )
        )

    if category and category != "All Categories":
        query = query.filter(Dish.category == category)

    dishes = query.order_by(Dish.id.asc()).all()
    categories = sorted([row[0] for row in db.session.query(Dish.category).distinct().all()])

    favorite_dish_ids = []
    if current_user.is_authenticated:
        favorite_dish_ids = [dish.id for dish in current_user.favorite_dishes.all()]

    no_results = len(dishes) == 0

    return render_template(
        "menu.html",
        dishes=dishes,
        categories=categories,
        search=search,
        selected_category=category,
        favorite_dish_ids=favorite_dish_ids,
        no_results=no_results,
    )


@app.route("/dish/<int:dish_id>")
def dish_details(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    average_rating = get_average_rating(dish_id)

    user_rating = None
    if current_user.is_authenticated:
        existing_rating = Rating.query.filter_by(
            user_id=current_user.id,
            dish_id=dish_id
        ).first()
        if existing_rating:
            user_rating = existing_rating.value

    return render_template(
        "dish_details.html",
        dish=dish,
        avg_rating=average_rating,
        user_rating=user_rating,
    )




# =========================
# FAVORITES
# =========================

@app.route("/add_favorite/<int:dish_id>")
@login_required
def add_favorite(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    if not current_user.favorite_dishes.filter(Dish.id == dish_id).first():
        current_user.favorite_dishes.append(dish)
        db.session.commit()
        flash("Added to favorites!", "success")
    return redirect(request.referrer or url_for("menu"))


@app.route("/remove_favorite/<int:dish_id>")
@login_required
def remove_favorite(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    existing = current_user.favorite_dishes.filter(Dish.id == dish_id).first()
    if existing:
        current_user.favorite_dishes.remove(dish)
        db.session.commit()
        flash("Removed from favorites.", "info")
    return redirect(request.referrer or url_for("favorites_page"))


@app.route("/favorites")
@login_required
def favorites_page():
    dishes = current_user.favorite_dishes.order_by(Dish.id.asc()).all()
    favorite_dish_ids = [dish.id for dish in dishes]
    return render_template(
        "favorites.html",
        dishes=dishes,
        favorite_dish_ids=favorite_dish_ids,
    )


@app.route("/recommendations")
@login_required
def recommendations():
    favorite_dishes = current_user.favorite_dishes.all()
    favorite_ids = [dish.id for dish in favorite_dishes]
    favorite_categories = list({dish.category for dish in favorite_dishes})

    recommended = []

    if favorite_categories:
        rows = (
            db.session.query(Dish, func.avg(Rating.value).label("avg_rating"))
            .outerjoin(Rating, Dish.id == Rating.dish_id)
            .filter(Dish.category.in_(favorite_categories))
            .filter(~Dish.id.in_(favorite_ids) if favorite_ids else True)
            .group_by(Dish.id)
            .order_by(desc("avg_rating"), Dish.name.asc())
            .all()
        )
        recommended = [dish for dish, _ in rows]

    if len(recommended) < 6:
        exclude_ids = favorite_ids + [dish.id for dish in recommended]
        rows = (
            db.session.query(Dish, func.avg(Rating.value).label("avg_rating"))
            .outerjoin(Rating, Dish.id == Rating.dish_id)
            .filter(~Dish.id.in_(exclude_ids) if exclude_ids else True)
            .group_by(Dish.id)
            .order_by(desc("avg_rating"), Dish.name.asc())
            .limit(6)
            .all()
        )

        for dish, _ in rows:
            if dish.id not in [d.id for d in recommended]:
                recommended.append(dish)

    recommended = recommended[:6]
    return render_template("recommendations.html", dishes=recommended)


@app.route("/profile")
@login_required
def profile():
    favorites_count = current_user.favorite_dishes.count()
    ratings_count = Rating.query.filter_by(user_id=current_user.id).count()
    return render_template(
        "profile.html",
        user=current_user,
        favorites_count=favorites_count,
        ratings_count=ratings_count,
    )


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if not is_admin_user():
        flash("Access denied. Admin only.", "danger")
        return redirect(url_for("menu"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        image = request.form.get("image", "").strip()
        description = request.form.get("description", "").strip()
        ingredients = request.form.get("ingredients", "").strip()
        category = request.form.get("category", "").strip()
        spicy_level = request.form.get("spicy_level", "").strip()

        if not all([name, price, image, description, ingredients, category, spicy_level]):
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("admin"))

        try:
            price_value = int(price)
        except ValueError:
            flash("Price must be a valid number.", "warning")
            return redirect(url_for("admin"))

        new_dish = Dish(
            name=name,
            price=price_value,
            image=image,
            description=description,
            ingredients=ingredients,
            category=category,
            spicy_level=spicy_level,
        )
        db.session.add(new_dish)
        db.session.commit()

        flash("Dish added successfully.", "success")
        return redirect(url_for("admin"))

    dishes = Dish.query.order_by(Dish.id.desc()).all()
    return render_template("admin.html", dishes=dishes)


@app.route("/delete_dish/<int:dish_id>", methods=["POST"])
@login_required
def delete_dish(dish_id):
    if not is_admin_user():
        flash("Access denied. Admin only.", "danger")
        return redirect(url_for("menu"))

    dish = Dish.query.get_or_404(dish_id)
    db.session.delete(dish)
    db.session.commit()
    flash("Dish deleted successfully.", "success")
    return redirect(url_for("admin"))


@app.route("/toggle_favorite/<int:dish_id>", methods=["POST"])
@login_required
def toggle_favorite(dish_id):
    dish = Dish.query.get_or_404(dish_id)

    existing = current_user.favorite_dishes.filter(Dish.id == dish_id).first()

    if existing:
        current_user.favorite_dishes.remove(dish)
        db.session.commit()
        return {
            "success": True,
            "status": "removed",
            "dish_id": dish_id,
            "message": "Removed from favorites."
        }
    else:
        current_user.favorite_dishes.append(dish)
        db.session.commit()
        return {
            "success": True,
            "status": "added",
            "dish_id": dish_id,
            "message": "Added to favorites!"
        }

@app.route("/rate/<int:dish_id>", methods=["POST"])
@login_required
def rate_dish(dish_id):
    value = int(request.form.get("value"))

    rating = Rating.query.filter_by(
        user_id=current_user.id,
        dish_id=dish_id
    ).first()

    if rating:
        rating.value = value
    else:
        rating = Rating(
            user_id=current_user.id,
            dish_id=dish_id,
            value=value
        )
        db.session.add(rating)

    db.session.commit()

    avg = db.session.query(func.avg(Rating.value)).filter_by(dish_id=dish_id).scalar()

    return jsonify({
        "success": True,
        "avg_rating": round(avg, 1) if avg else 0
    })

@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


with app.app_context():
    db.create_all()
    seed_dishes()


if __name__ == "__main__":
    app.run(debug=True)

    