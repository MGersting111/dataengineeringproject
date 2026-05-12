import os
from datetime import datetime
from decimal import Decimal

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "company-dev-secret")
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


class Warehouse(db.Model):
    __tablename__ = "warehouse"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)


class Supplier(db.Model):
    __tablename__ = "supplier"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(120), nullable=False)


class Material(db.Model):
    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    current_stock = db.Column(db.Float, nullable=False, default=0)


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
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(500), nullable=True)

    category = db.relationship("Category")


class BillOfMaterials(db.Model):
    __tablename__ = "bill_of_materials"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=False)
    quantity_required = db.Column(db.Float, nullable=False)

    product = db.relationship("Product")
    material = db.relationship("Material")


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_order"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="Ordered")

    supplier = db.relationship("Supplier")
    warehouse = db.relationship("Warehouse")


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_item"

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)

    purchase_order = db.relationship("PurchaseOrder", backref="items")
    material = db.relationship("Material")


class Production(db.Model):
    __tablename__ = "production"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    quantity_planned = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="Planned")
    planned_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship("Product")
    warehouse = db.relationship("Warehouse")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def seed_initial_data() -> None:
    if not Warehouse.query.first():
        db.session.add(Warehouse(name="Main Warehouse", address="Industry Street 10"))

    if not Category.query.first():
        db.session.add_all([Category(name="Fruits"), Category(name="Vegetables"), Category(name="Drinks")])

    if not Material.query.first():
        db.session.add_all(
            [
                Material(name="Packaging", unit="pcs", current_stock=1200),
                Material(name="Glass Bottle", unit="pcs", current_stock=600),
                Material(name="Label", unit="pcs", current_stock=800),
            ]
        )

    if not Supplier.query.first():
        db.session.add_all(
            [
                Supplier(name="Nordic Packaging GmbH", contact_person="Eva Meyer"),
                Supplier(name="Bottles Direct AG", contact_person="Tom Fischer"),
            ]
        )

    db.session.commit()


@app.route("/")
@login_required
def dashboard():
    stats = {
        "products": Product.query.count(),
        "materials": Material.query.count(),
        "purchase_orders": PurchaseOrder.query.count(),
        "productions": Production.query.count(),
    }
    latest_productions = Production.query.order_by(Production.planned_date.desc()).limit(5).all()
    latest_purchase_orders = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).limit(5).all()
    return render_template(
        "dashboard.html",
        stats=stats,
        latest_productions=latest_productions,
        latest_purchase_orders=latest_purchase_orders,
    )


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
            is_company_admin=True,
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Company account created.", "success")
        return redirect(url_for("dashboard"))

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
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact_person = request.form.get("contact_person", "").strip()

        if not name or not contact_person:
            flash("Please provide supplier name and contact person.", "error")
            return redirect(url_for("suppliers"))

        db.session.add(Supplier(name=name, contact_person=contact_person))
        db.session.commit()
        flash("Supplier added.", "success")
        return redirect(url_for("suppliers"))

    return render_template("suppliers.html", suppliers=Supplier.query.order_by(Supplier.name.asc()).all())


@app.route("/materials", methods=["GET", "POST"])
@login_required
def materials():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        unit = request.form.get("unit", "").strip()
        current_stock = request.form.get("current_stock", type=float, default=0)

        if not name or not unit:
            flash("Name and unit are required.", "error")
            return redirect(url_for("materials"))

        db.session.add(Material(name=name, unit=unit, current_stock=current_stock))
        db.session.commit()
        flash("Material added.", "success")
        return redirect(url_for("materials"))

    return render_template("materials.html", materials=Material.query.order_by(Material.name.asc()).all())


@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float, default=0)
        stock_qty = request.form.get("stock_qty", type=int, default=0)
        description = request.form.get("description", "").strip()

        if not name or not sku or not category_id:
            flash("Name, SKU and category are required.", "error")
            return redirect(url_for("products"))

        if Product.query.filter_by(sku=sku).first():
            flash("SKU already exists.", "error")
            return redirect(url_for("products"))

        db.session.add(
            Product(
                name=name,
                sku=sku,
                category_id=category_id,
                price=Decimal(str(price)),
                stock_qty=stock_qty,
                description=description,
            )
        )
        db.session.commit()
        flash("Product added.", "success")
        return redirect(url_for("products"))

    return render_template("products.html", products=Product.query.order_by(Product.name.asc()).all(), categories=categories)


@app.route("/bom", methods=["GET", "POST"])
@login_required
def bom():
    products = Product.query.order_by(Product.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()

    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        material_id = request.form.get("material_id", type=int)
        quantity_required = request.form.get("quantity_required", type=float, default=0)

        if not product_id or not material_id or quantity_required <= 0:
            flash("Please provide valid BOM values.", "error")
            return redirect(url_for("bom"))

        db.session.add(
            BillOfMaterials(
                product_id=product_id,
                material_id=material_id,
                quantity_required=quantity_required,
            )
        )
        db.session.commit()
        flash("BOM entry added.", "success")
        return redirect(url_for("bom"))

    entries = BillOfMaterials.query.order_by(BillOfMaterials.id.desc()).all()
    return render_template("bom.html", products=products, materials=materials, entries=entries)


@app.route("/purchase-orders", methods=["GET", "POST"])
@login_required
def purchase_orders():
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()
    warehouse = Warehouse.query.order_by(Warehouse.id.asc()).first()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id", type=int)
        material_id = request.form.get("material_id", type=int)
        quantity = request.form.get("quantity", type=float, default=0)
        unit_cost = request.form.get("unit_cost", type=float, default=0)

        if not warehouse or not supplier_id or not material_id or quantity <= 0 or unit_cost < 0:
            flash("Please provide valid purchase order values.", "error")
            return redirect(url_for("purchase_orders"))

        order = PurchaseOrder(supplier_id=supplier_id, warehouse_id=warehouse.id, status="Ordered")
        db.session.add(order)
        db.session.flush()

        db.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                material_id=material_id,
                quantity=quantity,
                unit_cost=Decimal(str(unit_cost)),
            )
        )
        db.session.commit()
        flash(f"Purchase order #{order.id} created.", "success")
        return redirect(url_for("purchase_orders"))

    orders = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).all()
    return render_template(
        "purchase_orders.html",
        suppliers=suppliers,
        materials=materials,
        orders=orders,
    )


@app.route("/purchase-orders/<int:order_id>/receive", methods=["POST"])
@login_required
def receive_purchase_order(order_id: int):
    order = db.session.get(PurchaseOrder, order_id)
    if not order:
        flash("Purchase order not found.", "error")
        return redirect(url_for("purchase_orders"))

    if order.status == "Received":
        flash("Order already received.", "error")
        return redirect(url_for("purchase_orders"))

    for item in order.items:
        item.material.current_stock += item.quantity

    order.status = "Received"
    db.session.commit()
    flash(f"Purchase order #{order.id} received and stock updated.", "success")
    return redirect(url_for("purchase_orders"))


@app.route("/production", methods=["GET", "POST"])
@login_required
def production():
    products = Product.query.order_by(Product.name.asc()).all()
    warehouse = Warehouse.query.order_by(Warehouse.id.asc()).first()

    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        quantity_planned = request.form.get("quantity_planned", type=int, default=0)

        if not warehouse or not product_id or quantity_planned <= 0:
            flash("Please provide valid production values.", "error")
            return redirect(url_for("production"))

        db.session.add(
            Production(
                product_id=product_id,
                warehouse_id=warehouse.id,
                quantity_planned=quantity_planned,
                status="Planned",
            )
        )
        db.session.commit()
        flash("Production plan created.", "success")
        return redirect(url_for("production"))

    plans = Production.query.order_by(Production.planned_date.desc()).all()
    return render_template("production.html", products=products, plans=plans)


@app.route("/production/<int:production_id>/complete", methods=["POST"])
@login_required
def complete_production(production_id: int):
    plan = db.session.get(Production, production_id)
    if not plan:
        flash("Production plan not found.", "error")
        return redirect(url_for("production"))

    if plan.status == "Completed":
        flash("Production already completed.", "error")
        return redirect(url_for("production"))

    bom_entries = BillOfMaterials.query.filter_by(product_id=plan.product_id).all()
    for entry in bom_entries:
        required = entry.quantity_required * plan.quantity_planned
        if entry.material.current_stock < required:
            flash(f"Not enough material stock: {entry.material.name}", "error")
            return redirect(url_for("production"))

    for entry in bom_entries:
        required = entry.quantity_required * plan.quantity_planned
        entry.material.current_stock -= required

    plan.product.stock_qty += plan.quantity_planned
    plan.status = "Completed"
    db.session.commit()

    flash(f"Production #{plan.id} completed and inventory updated.", "success")
    return redirect(url_for("production"))


with app.app_context():
    db.create_all()
    seed_initial_data()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5002")), debug=True)
