import os
from datetime import datetime
from decimal import Decimal

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "shop-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/dataengineeringproject"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    is_company_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Category(db.Model):
    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Product(db.Model):
    __tablename__ = "product"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(500), nullable=True)

    category = db.relationship("Category", backref="products")


class Warehouse(db.Model):
    __tablename__ = "warehouse"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)


class Order(db.Model):
    __tablename__ = "sales_order"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    shipping_status = db.Column(db.String(50), default="Pending", nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    customer = db.relationship("User", backref="shop_orders")
    warehouse = db.relationship("Warehouse")


class OrderItem(db.Model):
    __tablename__ = "order_item"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("sales_order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    sale_price = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", backref="items")
    product = db.relationship("Product")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def seed_initial_data() -> None:
    if not Category.query.first():
        categories = [
            Category(name="Fruits"),
            Category(name="Vegetables"),
            Category(name="Drinks"),
        ]
        db.session.add_all(categories)
        db.session.flush()

        products = [
            Product(name="Apple Box", sku="APL-BOX-01", category_id=categories[0].id, price=Decimal("9.90"), stock_qty=120, description="Fresh apples in a 2kg box."),
            Product(name="Tomato Pack", sku="TMT-PCK-01", category_id=categories[1].id, price=Decimal("4.50"), stock_qty=150, description="Ripe tomatoes for cooking."),
            Product(name="Orange Juice", sku="ORG-JCE-01", category_id=categories[2].id, price=Decimal("2.99"), stock_qty=90, description="1L not-from-concentrate orange juice."),
        ]
        db.session.add_all(products)

    if not Warehouse.query.first():
        db.session.add(Warehouse(name="Main Warehouse", address="Industry Street 10"))

    db.session.commit()


def get_cart() -> dict:
    return session.setdefault("cart", {})


def get_cart_details():
    cart = get_cart()
    if not cart:
        return [], Decimal("0.00")

    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids)).all()

    item_rows = []
    total = Decimal("0.00")
    for product in products:
        qty = int(cart.get(str(product.id), 0))
        subtotal = Decimal(product.price) * qty
        item_rows.append({"product": product, "quantity": qty, "subtotal": subtotal})
        total += subtotal

    return item_rows, total


@app.context_processor
def inject_cart_count():
    cart = get_cart()
    count = sum(int(v) for v in cart.values())
    return {"cart_count": count}


@app.route("/")
def index():
    product_count = db.session.query(func.count(Product.id)).scalar() or 0
    return render_template("index.html", product_count=product_count)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        password = request.form.get("password", "")

        if not email or not password or not first_name or not last_name:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "error")
            return redirect(url_for("register"))

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Account created successfully.", "success")
        return redirect(url_for("products"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.", "error")
            return redirect(url_for("login"))

        login_user(user)
        flash("Welcome back.", "success")
        return redirect(url_for("products"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/products")
def products():
    category_id = request.args.get("category", type=int)
    categories = Category.query.order_by(Category.name.asc()).all()

    query = Product.query.order_by(Product.name.asc())
    if category_id:
        query = query.filter_by(category_id=category_id)

    return render_template(
        "products.html",
        products=query.all(),
        categories=categories,
        selected_category=category_id,
    )


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))

    quantity = request.form.get("quantity", type=int, default=1)
    if quantity < 1:
        quantity = 1

    cart = get_cart()
    new_qty = int(cart.get(str(product_id), 0)) + quantity

    if new_qty > product.stock_qty:
        flash("Not enough stock for this product.", "error")
        return redirect(url_for("products"))

    cart[str(product_id)] = new_qty
    session.modified = True
    flash("Product added to cart.", "success")
    return redirect(url_for("products"))


@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        cart_data = get_cart()
        for key, value in request.form.items():
            if key.startswith("qty_"):
                product_id = key.replace("qty_", "")
                try:
                    qty = max(0, int(value))
                except ValueError:
                    qty = 0

                if qty == 0:
                    cart_data.pop(product_id, None)
                else:
                    product = db.session.get(Product, int(product_id))
                    if product:
                        cart_data[product_id] = min(qty, product.stock_qty)

        session.modified = True
        flash("Cart updated.", "success")
        return redirect(url_for("cart"))

    items, total = get_cart_details()
    return render_template("cart.html", items=items, total=total)


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    items, total = get_cart_details()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart"))

    warehouse = Warehouse.query.order_by(Warehouse.id.asc()).first()
    if not warehouse:
        flash("No warehouse configured.", "error")
        return redirect(url_for("cart"))

    for item in items:
        if item["quantity"] > item["product"].stock_qty:
            flash(f"Stock changed for {item['product'].name}. Please update your cart.", "error")
            return redirect(url_for("cart"))

    order = Order(customer_id=current_user.id, warehouse_id=warehouse.id, total_amount=total)
    db.session.add(order)
    db.session.flush()

    for item in items:
        product = item["product"]
        quantity = item["quantity"]

        product.stock_qty -= quantity
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                sale_price=product.price,
            )
        )

    db.session.commit()
    session["cart"] = {}
    flash(f"Order #{order.id} placed successfully.", "success")
    return redirect(url_for("account"))


@app.route("/account")
@login_required
def account():
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template("account.html", orders=orders)


with app.app_context():
    db.create_all()
    seed_initial_data()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=True)
