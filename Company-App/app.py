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


class WarehouseLocation(db.Model):
    __tablename__ = "warehouse_location"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False, unique=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    warehouse = db.relationship("Warehouse", backref=db.backref("location", uselist=False))


class Supplier(db.Model):
    __tablename__ = "supplier"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(120), nullable=False)


class SupplierLocation(db.Model):
    __tablename__ = "supplier_location"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False, unique=True)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    supplier = db.relationship("Supplier", backref=db.backref("location", uselist=False))


class Material(db.Model):
    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    current_stock = db.Column(db.Float, nullable=False, default=0)


class MaterialStock(db.Model):
    __tablename__ = "material_stock"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)

    material = db.relationship("Material")
    warehouse = db.relationship("Warehouse")


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


class ProductStock(db.Model):
    __tablename__ = "product_stock"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product")
    warehouse = db.relationship("Warehouse")


class MaterialFlow(db.Model):
    __tablename__ = "material_flow"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(60), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=False)
    source_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=True)
    target_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    note = db.Column(db.String(255), nullable=True)

    material = db.relationship("Material")
    source_warehouse = db.relationship("Warehouse", foreign_keys=[source_warehouse_id])
    target_warehouse = db.relationship("Warehouse", foreign_keys=[target_warehouse_id])


class Order(db.Model):
    __tablename__ = "sales_order"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    shipping_status = db.Column(db.String(50), default="Pending", nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    customer = db.relationship("User")
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


class BillOfMaterials(db.Model):
    __tablename__ = "bill_of_materials"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=False)
    quantity_required = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=True)

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


def get_or_create_material_stock(material_id: int, warehouse_id: int) -> MaterialStock:
    stock = MaterialStock.query.filter_by(material_id=material_id, warehouse_id=warehouse_id).first()
    if not stock:
        stock = MaterialStock(material_id=material_id, warehouse_id=warehouse_id, quantity=0)
        db.session.add(stock)
        db.session.flush()
    return stock


def get_or_create_product_stock(product_id: int, warehouse_id: int) -> ProductStock:
    stock = ProductStock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
    if not stock:
        stock = ProductStock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        db.session.add(stock)
        db.session.flush()
    return stock


def sync_material_total(material_id: int) -> None:
    material = db.session.get(Material, material_id)
    if not material:
        return
    total = sum(stock.quantity for stock in MaterialStock.query.filter_by(material_id=material_id).all())
    material.current_stock = round(total, 2)


def sync_product_total(product_id: int) -> None:
    product = db.session.get(Product, product_id)
    if not product:
        return
    total = sum(stock.quantity for stock in ProductStock.query.filter_by(product_id=product_id).all())
    product.stock_qty = int(total)


def record_material_flow(
    event_type: str,
    material_id: int,
    quantity: float,
    source_warehouse_id: int | None,
    target_warehouse_id: int | None,
    note: str,
) -> None:
    db.session.add(
        MaterialFlow(
            event_type=event_type,
            material_id=material_id,
            source_warehouse_id=source_warehouse_id,
            target_warehouse_id=target_warehouse_id,
            quantity=quantity,
            note=note,
        )
    )


def seed_initial_data() -> None:
    warehouse_defaults = [
        {
            "name": "Hamburg Central Warehouse",
            "address": "Werner-Siemens-Strasse 21, 22113 Hamburg, Germany",
            "lat": 53.5532,
            "lon": 10.1023,
        },
        {
            "name": "Dortmund Production Hub",
            "address": "Westfalendamm 98, 44141 Dortmund, Germany",
            "lat": 51.5056,
            "lon": 7.5095,
        },
        {
            "name": "Munich Distribution Center",
            "address": "Landsberger Strasse 302, 80687 Munich, Germany",
            "lat": 48.1414,
            "lon": 11.5072,
        },
    ]
    warehouses = []
    for defaults in warehouse_defaults:
        warehouse = Warehouse.query.filter_by(name=defaults["name"]).first()
        if not warehouse:
            warehouse = Warehouse(name=defaults["name"], address=defaults["address"])
            db.session.add(warehouse)
            db.session.flush()

        if not warehouse.location:
            db.session.add(
                WarehouseLocation(
                    warehouse_id=warehouse.id,
                    latitude=defaults["lat"],
                    longitude=defaults["lon"],
                )
            )
        warehouses.append(warehouse)

    category_names = ["Jackets", "Pants", "Footwear", "Safety Accessories"]
    categories = {}
    for category_name in category_names:
        category = Category.query.filter_by(name=category_name).first()
        if not category:
            category = Category(name=category_name)
            db.session.add(category)
        categories[category_name] = category

    material_defaults = [
        ("Cotton Fabric", "m", 2500),
        ("Polyester Fabric", "m", 2200),
        ("Reflective Tape", "m", 1200),
        ("Nylon Thread", "spool", 600),
        ("Heavy Duty Zipper", "pcs", 1800),
        ("Snap Buttons", "pcs", 6000),
        ("PU Sole", "pair", 900),
        ("Steel Toe Cap", "pair", 850),
        ("Laces", "pair", 1200),
        ("Cardboard Box", "pcs", 2500),
    ]
    materials = {}
    for name, unit, stock in material_defaults:
        material = Material.query.filter_by(name=name).first()
        if not material:
            material = Material(name=name, unit=unit, current_stock=stock)
            db.session.add(material)
        materials[name] = material

    supplier_defaults = [
        {
            "name": "Textile Source GmbH",
            "contact": "Eva Meyer",
            "address": "Industriepark 12, 40231 Dusseldorf, Germany",
            "city": "Dusseldorf",
            "country": "Germany",
            "lat": 51.2279,
            "lon": 6.8328,
        },
        {
            "name": "Industrial Trims AG",
            "contact": "Tom Fischer",
            "address": "Fabrikstrasse 7, 90429 Nuremberg, Germany",
            "city": "Nuremberg",
            "country": "Germany",
            "lat": 49.4588,
            "lon": 11.0389,
        },
        {
            "name": "Safety Components Ltd.",
            "contact": "Mina Roth",
            "address": "Rheinhafenweg 3, 68159 Mannheim, Germany",
            "city": "Mannheim",
            "country": "Germany",
            "lat": 49.4913,
            "lon": 8.4588,
        },
    ]

    for defaults in supplier_defaults:
        supplier = Supplier.query.filter_by(name=defaults["name"]).first()
        if not supplier:
            supplier = Supplier(name=defaults["name"], contact_person=defaults["contact"])
            db.session.add(supplier)
            db.session.flush()

        if not supplier.location:
            db.session.add(
                SupplierLocation(
                    supplier_id=supplier.id,
                    address=defaults["address"],
                    city=defaults["city"],
                    country=defaults["country"],
                    latitude=defaults["lat"],
                    longitude=defaults["lon"],
                )
            )

    db.session.flush()

    product_defaults = [
        {
            "name": "Hi-Vis Work Jacket",
            "sku": "WW-JCK-001",
            "category": "Jackets",
            "price": Decimal("129.00"),
            "stock_qty": 140,
            "description": "Weather-resistant high-visibility jacket with reflective details.",
        },
        {
            "name": "Cargo Work Pants",
            "sku": "WW-PNT-001",
            "category": "Pants",
            "price": Decimal("79.00"),
            "stock_qty": 190,
            "description": "Durable cargo pants with reinforced knees and utility pockets.",
        },
        {
            "name": "Steel Toe Safety Boots",
            "sku": "WW-BTS-001",
            "category": "Footwear",
            "price": Decimal("149.00"),
            "stock_qty": 110,
            "description": "Mid-cut safety boots with steel toe cap and anti-slip sole.",
        },
        {
            "name": "Reflective Safety Vest",
            "sku": "WW-VST-001",
            "category": "Safety Accessories",
            "price": Decimal("24.00"),
            "stock_qty": 260,
            "description": "Breathable reflective vest for high-risk work zones.",
        },
    ]
    products = {}
    for defaults in product_defaults:
        product = Product.query.filter_by(sku=defaults["sku"]).first()
        if not product:
            product = Product(
                name=defaults["name"],
                sku=defaults["sku"],
                category_id=categories[defaults["category"]].id,
                price=defaults["price"],
                stock_qty=defaults["stock_qty"],
                description=defaults["description"],
            )
            db.session.add(product)
        products[defaults["sku"]] = product

    db.session.flush()

    bom_defaults = {
        "WW-JCK-001": [
            ("Cotton Fabric", 2.2, 3.50),
            ("Polyester Fabric", 0.8, 2.80),
            ("Reflective Tape", 1.2, 1.20),
            ("Nylon Thread", 0.05, 5.00),
            ("Heavy Duty Zipper", 1, 2.50),
            ("Cardboard Box", 1, 0.80),
        ],
        "WW-PNT-001": [
            ("Cotton Fabric", 1.7, 3.50),
            ("Polyester Fabric", 0.6, 2.80),
            ("Nylon Thread", 0.04, 5.00),
            ("Snap Buttons", 4, 0.15),
            ("Cardboard Box", 1, 0.80),
        ],
        "WW-BTS-001": [
            ("PU Sole", 1, 8.00),
            ("Steel Toe Cap", 1, 12.00),
            ("Laces", 1, 1.50),
            ("Polyester Fabric", 0.4, 2.80),
            ("Cardboard Box", 1, 0.80),
        ],
        "WW-VST-001": [
            ("Polyester Fabric", 0.9, 2.80),
            ("Reflective Tape", 1.4, 1.20),
            ("Nylon Thread", 0.03, 5.00),
            ("Cardboard Box", 1, 0.80),
        ],
    }

    for sku, rows in bom_defaults.items():
        product = products[sku]
        for material_name, quantity_required, unit_cost in rows:
            material = materials[material_name]
            existing = BillOfMaterials.query.filter_by(product_id=product.id, material_id=material.id).first()
            if not existing:
                db.session.add(
                    BillOfMaterials(
                        product_id=product.id,
                        material_id=material.id,
                        quantity_required=quantity_required,
                        unit_cost=Decimal(str(unit_cost)),
                    )
                )
            elif existing.unit_cost is None:
                existing.unit_cost = Decimal(str(unit_cost))

    db.session.flush()

    material_distribution = [0.45, 0.35, 0.20]
    for _, material in materials.items():
        existing_stocks = MaterialStock.query.filter_by(material_id=material.id).all()
        if existing_stocks:
            continue

        remaining = material.current_stock
        for idx, warehouse in enumerate(warehouses):
            if idx == len(warehouses) - 1:
                qty = remaining
            else:
                qty = round(material.current_stock * material_distribution[idx], 2)
                remaining -= qty
            db.session.add(MaterialStock(material_id=material.id, warehouse_id=warehouse.id, quantity=qty))

    product_distribution = [0.50, 0.30, 0.20]
    for _, product in products.items():
        existing_stocks = ProductStock.query.filter_by(product_id=product.id).all()
        if existing_stocks:
            continue

        remaining = product.stock_qty
        for idx, warehouse in enumerate(warehouses):
            if idx == len(warehouses) - 1:
                qty = remaining
            else:
                qty = int(round(product.stock_qty * product_distribution[idx]))
                remaining -= qty
            db.session.add(ProductStock(product_id=product.id, warehouse_id=warehouse.id, quantity=qty))

    db.session.flush()

    for material in materials.values():
        sync_material_total(material.id)
    for product in products.values():
        sync_product_total(product.id)

    db.session.commit()


@app.route("/")
@login_required
def dashboard():
    stats = {
        "products": Product.query.count(),
        "materials": Material.query.count(),
        "warehouses": Warehouse.query.count(),
        "purchase_orders": PurchaseOrder.query.count(),
        "productions": Production.query.count(),
        "sales_orders": Order.query.count(),
    }
    latest_productions = Production.query.order_by(Production.planned_date.desc()).limit(5).all()
    latest_purchase_orders = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).limit(5).all()
    latest_sales_orders = Order.query.order_by(Order.order_date.desc()).limit(5).all()
    return render_template(
        "dashboard.html",
        stats=stats,
        latest_productions=latest_productions,
        latest_purchase_orders=latest_purchase_orders,
        latest_sales_orders=latest_sales_orders,
    )


@app.route("/warehouses")
@login_required
def warehouses():
    all_warehouses = Warehouse.query.order_by(Warehouse.name.asc()).all()
    warehouse_materials = {}
    warehouse_products = {}

    for warehouse in all_warehouses:
        warehouse_materials[warehouse.id] = MaterialStock.query.filter_by(warehouse_id=warehouse.id).order_by(MaterialStock.quantity.desc()).limit(6).all()
        warehouse_products[warehouse.id] = ProductStock.query.filter_by(warehouse_id=warehouse.id).order_by(ProductStock.quantity.desc()).limit(6).all()

    return render_template(
        "warehouses.html",
        warehouses=all_warehouses,
        warehouse_materials=warehouse_materials,
        warehouse_products=warehouse_products,
    )


@app.route("/sales-orders")
@login_required
def sales_orders():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    return render_template("sales_orders.html", orders=orders)


@app.route("/sales-orders/<int:order_id>/advance", methods=["POST"])
@login_required
def advance_sales_order(order_id: int):
    order = db.session.get(Order, order_id)
    if not order:
        flash("Sales order not found.", "error")
        return redirect(url_for("sales_orders"))

    transitions = {
        "Pending": "Picking",
        "Picking": "Shipped",
        "Shipped": "Delivered",
    }
    next_status = transitions.get(order.shipping_status)
    if not next_status:
        flash("Sales order is already delivered.", "error")
        return redirect(url_for("sales_orders"))

    order.shipping_status = next_status
    db.session.commit()
    flash(f"Sales order #{order.id} moved to {next_status}.", "success")
    return redirect(url_for("sales_orders"))


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
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        country = request.form.get("country", "").strip()
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)

        if not name or not contact_person or not address or not city or not country:
            flash("Please provide full supplier location data.", "error")
            return redirect(url_for("suppliers"))

        if latitude is None or longitude is None:
            flash("Please provide latitude and longitude.", "error")
            return redirect(url_for("suppliers"))

        supplier = Supplier(name=name, contact_person=contact_person)
        db.session.add(supplier)
        db.session.flush()

        db.session.add(
            SupplierLocation(
                supplier_id=supplier.id,
                address=address,
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude,
            )
        )
        db.session.commit()
        flash("Supplier added.", "success")
        return redirect(url_for("suppliers"))

    return render_template("suppliers.html", suppliers=Supplier.query.order_by(Supplier.name.asc()).all())


@app.route("/materials", methods=["GET", "POST"])
@login_required
def materials():
    warehouses = Warehouse.query.order_by(Warehouse.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        unit = request.form.get("unit", "").strip()
        current_stock = request.form.get("current_stock", type=float, default=0)
        warehouse_id = request.form.get("warehouse_id", type=int)

        if not name or not unit:
            flash("Name and unit are required.", "error")
            return redirect(url_for("materials"))

        material = Material(name=name, unit=unit, current_stock=max(current_stock, 0))
        db.session.add(material)
        db.session.flush()

        if warehouse_id:
            stock = get_or_create_material_stock(material.id, warehouse_id)
            stock.quantity += max(current_stock, 0)
            sync_material_total(material.id)

        db.session.commit()
        flash("Material added.", "success")
        return redirect(url_for("materials"))

    return render_template(
        "materials.html",
        materials=Material.query.order_by(Material.name.asc()).all(),
        warehouses=warehouses,
    )


@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    categories = Category.query.order_by(Category.name.asc()).all()
    warehouses = Warehouse.query.order_by(Warehouse.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float, default=0)
        stock_qty = request.form.get("stock_qty", type=int, default=0)
        warehouse_id = request.form.get("warehouse_id", type=int)
        description = request.form.get("description", "").strip()

        if not name or not sku or not category_id:
            flash("Name, SKU and category are required.", "error")
            return redirect(url_for("products"))

        if Product.query.filter_by(sku=sku).first():
            flash("SKU already exists.", "error")
            return redirect(url_for("products"))

        product = Product(
            name=name,
            sku=sku,
            category_id=category_id,
            price=Decimal(str(price)),
            stock_qty=max(stock_qty, 0),
            description=description,
        )
        db.session.add(product)
        db.session.flush()

        if warehouse_id and stock_qty > 0:
            stock = get_or_create_product_stock(product.id, warehouse_id)
            stock.quantity += stock_qty
            sync_product_total(product.id)

        db.session.commit()
        flash("Product added.", "success")
        return redirect(url_for("products"))

    return render_template(
        "products.html",
        products=Product.query.order_by(Product.name.asc()).all(),
        categories=categories,
        warehouses=warehouses,
    )


@app.route("/products/<int:product_id>")
@login_required
def product_detail(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))

    product_stocks = ProductStock.query.filter_by(product_id=product.id).order_by(ProductStock.quantity.desc()).all()
    bom_entries = BillOfMaterials.query.filter_by(product_id=product.id).order_by(BillOfMaterials.id.asc()).all()

    # Cost block: compute unit cost from BOM entries that have unit_cost set
    total_unit_cost = sum(
        float(e.unit_cost) * e.quantity_required for e in bom_entries if e.unit_cost is not None
    )

    # Find the next open production for this product (Planned or In Progress)
    open_production = (
        Production.query
        .filter(Production.product_id == product.id, Production.status.in_(["Planned", "In Progress"]))
        .order_by(Production.planned_date.desc())
        .first()
    )
    planned_qty = open_production.quantity_planned if open_production else 1

    return render_template(
        "product_detail.html",
        product=product,
        product_stocks=product_stocks,
        bom_entries=bom_entries,
        total_unit_cost=total_unit_cost,
        planned_qty=planned_qty,
        open_production=open_production,
    )


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
    bom_by_product = {}
    for entry in entries:
        bom_by_product.setdefault(entry.product_id, []).append(entry)

    return render_template(
        "bom.html",
        products=products,
        materials=materials,
        entries=entries,
        bom_by_product=bom_by_product,
    )


@app.route("/bom/<int:product_id>")
@login_required
def bom_product_detail(product_id: int):
    return redirect(url_for("product_detail", product_id=product_id))


@app.route("/purchase-orders", methods=["GET", "POST"])
@login_required
def purchase_orders():
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()
    warehouses = Warehouse.query.order_by(Warehouse.name.asc()).all()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id", type=int)
        warehouse_id = request.form.get("warehouse_id", type=int)
        material_id = request.form.get("material_id", type=int)
        quantity = request.form.get("quantity", type=float, default=0)
        unit_cost = request.form.get("unit_cost", type=float, default=0)

        if not warehouse_id or not supplier_id or not material_id or quantity <= 0 or unit_cost < 0:
            flash("Please provide valid purchase order values.", "error")
            return redirect(url_for("purchase_orders"))

        order = PurchaseOrder(supplier_id=supplier_id, warehouse_id=warehouse_id, status="Ordered")
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
        warehouses=warehouses,
        orders=orders,
    )


@app.route("/purchase-orders/<int:order_id>/receive", methods=["POST"])
@login_required
def receive_purchase_order(order_id: int):
    order = db.session.get(PurchaseOrder, order_id)
    if not order:
        flash("Purchase order not found.", "error")
        return redirect(url_for("purchase_orders"))

    status_flow = {
        "Ordered": "In Transit",
        "In Transit": "Received",
    }
    next_status = status_flow.get(order.status)
    if not next_status:
        flash("Purchase order is already received.", "error")
        return redirect(url_for("purchase_orders"))

    if next_status == "Received":
        for item in order.items:
            stock = get_or_create_material_stock(item.material_id, order.warehouse_id)
            stock.quantity += item.quantity
            sync_material_total(item.material_id)
            record_material_flow(
                event_type="PurchaseReceipt",
                material_id=item.material_id,
                quantity=item.quantity,
                source_warehouse_id=None,
                target_warehouse_id=order.warehouse_id,
                note=f"PO #{order.id}",
            )

    order.status = next_status
    db.session.commit()
    flash(f"Purchase order #{order.id} moved to {next_status}.", "success")
    return redirect(url_for("purchase_orders"))


@app.route("/production", methods=["GET", "POST"])
@login_required
def production():
    products = Product.query.order_by(Product.name.asc()).all()
    warehouses = Warehouse.query.order_by(Warehouse.name.asc()).all()

    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        warehouse_id = request.form.get("warehouse_id", type=int)
        quantity_planned = request.form.get("quantity_planned", type=int, default=0)

        if not warehouse_id or not product_id or quantity_planned <= 0:
            flash("Please provide valid production values.", "error")
            return redirect(url_for("production"))

        db.session.add(
            Production(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity_planned=quantity_planned,
                status="Planned",
            )
        )
        db.session.commit()
        flash("Production plan created.", "success")
        return redirect(url_for("production"))

    plans = Production.query.order_by(Production.planned_date.desc()).all()
    return render_template("production.html", products=products, warehouses=warehouses, plans=plans)


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

    if plan.status == "Planned":
        flash("Start production first.", "error")
        return redirect(url_for("production"))

    bom_entries = BillOfMaterials.query.filter_by(product_id=plan.product_id).all()
    if not bom_entries:
        flash("No BOM entries found for this product.", "error")
        return redirect(url_for("production"))

    consumption_plan = []
    for entry in bom_entries:
        required = round(entry.quantity_required * plan.quantity_planned, 2)
        stocks = MaterialStock.query.filter_by(material_id=entry.material_id).all()

        total_available = sum(stock.quantity for stock in stocks)
        if total_available < required:
            flash(f"Not enough material stock: {entry.material.name}", "error")
            return redirect(url_for("production"))

        ordered = sorted(
            stocks,
            key=lambda row: (0 if row.warehouse_id == plan.warehouse_id else 1, -row.quantity),
        )
        remaining = required
        line_allocations = []
        for stock in ordered:
            if remaining <= 0:
                break
            take_qty = min(stock.quantity, remaining)
            if take_qty <= 0:
                continue
            line_allocations.append((stock, take_qty))
            remaining = round(remaining - take_qty, 2)

        consumption_plan.append((entry, line_allocations))

    for entry, allocations in consumption_plan:
        for stock, take_qty in allocations:
            stock.quantity = round(stock.quantity - take_qty, 2)
            record_material_flow(
                event_type="ProductionConsumption",
                material_id=entry.material_id,
                quantity=take_qty,
                source_warehouse_id=stock.warehouse_id,
                target_warehouse_id=plan.warehouse_id,
                note=f"Production #{plan.id}",
            )
        sync_material_total(entry.material_id)

    finished_goods = get_or_create_product_stock(plan.product_id, plan.warehouse_id)
    finished_goods.quantity += plan.quantity_planned
    sync_product_total(plan.product_id)

    plan.status = "Completed"
    db.session.commit()

    flash(f"Production #{plan.id} completed and inventory updated.", "success")
    return redirect(url_for("production"))


@app.route("/production/<int:production_id>/start", methods=["POST"])
@login_required
def start_production(production_id: int):
    plan = db.session.get(Production, production_id)
    if not plan:
        flash("Production plan not found.", "error")
        return redirect(url_for("production"))

    if plan.status != "Planned":
        flash("Only planned productions can be started.", "error")
        return redirect(url_for("production"))

    plan.status = "In Progress"
    db.session.commit()
    flash(f"Production #{plan.id} started.", "success")
    return redirect(url_for("production"))


with app.app_context():
    db.create_all()
    seed_initial_data()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5002")), debug=True)
