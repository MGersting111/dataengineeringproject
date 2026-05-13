import argparse
import random
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from app import (
    BillOfMaterials,
    Material,
    MaterialStock,
    Order,
    OrderItem,
    Product,
    ProductStock,
    Production,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    User,
    Warehouse,
    app,
    db,
    generate_password_hash,
    get_or_create_material_stock,
    get_or_create_product_stock,
    record_material_flow,
    sync_material_total,
    sync_product_total,
)


def sim_days_since(ts: datetime, now: datetime, day_seconds: float) -> float:
    return max((now - ts).total_seconds() / max(day_seconds, 1), 0.0)


def ensure_sim_customer() -> User:
    customer = User.query.filter_by(email="sim.customer@workwear.local").first()
    if customer:
        return customer

    customer = User(
        email="sim.customer@workwear.local",
        first_name="Sim",
        last_name="Customer",
        password_hash=generate_password_hash("sim-pass-123"),
        is_company_admin=False,
    )
    db.session.add(customer)
    db.session.commit()
    return customer


def plan_product_allocation(product_id: int, quantity: int) -> list[tuple[ProductStock, int]] | None:
    rows = ProductStock.query.filter(ProductStock.product_id == product_id, ProductStock.quantity > 0).order_by(ProductStock.quantity.desc()).all()
    if not rows:
        return []

    total_available = sum(row.quantity for row in rows)
    if total_available < quantity:
        return None

    remaining = quantity
    allocations = []
    for row in rows:
        if remaining <= 0:
            break
        take = min(row.quantity, remaining)
        allocations.append((row, take))
        remaining -= take

    return allocations


def create_sales_order(max_items: int = 3) -> bool:
    open_orders = Order.query.filter(Order.shipping_status != "Delivered").count()
    if open_orders > 40:
        return False

    customer = ensure_sim_customer()
    in_stock_products = Product.query.filter(Product.stock_qty > 0).order_by(Product.stock_qty.desc()).all()
    if not in_stock_products:
        return False

    random.shuffle(in_stock_products)
    selected = in_stock_products[: random.randint(1, max_items)]

    allocation_map = {}
    warehouse_weights = defaultdict(int)
    for product in selected:
        max_qty = min(product.stock_qty, 5)
        qty = random.randint(1, max_qty)
        allocation = plan_product_allocation(product.id, qty)
        if allocation is None:
            return False
        allocation_map[product.id] = (qty, allocation)
        for row, take in allocation:
            warehouse_weights[row.warehouse_id] += take

    if warehouse_weights:
        order_warehouse_id = max(warehouse_weights.items(), key=lambda kv: kv[1])[0]
    else:
        fallback_wh = Warehouse.query.order_by(Warehouse.id.asc()).first()
        if not fallback_wh:
            return False
        order_warehouse_id = fallback_wh.id

    order = Order(
        customer_id=customer.id,
        warehouse_id=order_warehouse_id,
        shipping_status="Pending",
        total_amount=Decimal("0.00"),
        order_date=datetime.now(),
    )
    db.session.add(order)
    db.session.flush()

    total = Decimal("0.00")
    for product in selected:
        qty, allocations = allocation_map[product.id]
        line_total = Decimal(product.price) * qty
        total += line_total

        product.stock_qty -= qty
        for row, take in allocations:
            row.quantity -= take

        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                sale_price=product.price,
            )
        )

    order.total_amount = total
    for product in selected:
        sync_product_total(product.id)

    db.session.commit()
    return True


def create_purchase_order() -> bool:
    suppliers = Supplier.query.order_by(Supplier.id.asc()).all()
    warehouses = Warehouse.query.order_by(Warehouse.id.asc()).all()
    if not suppliers or not warehouses:
        return False

    open_pos = PurchaseOrder.query.filter(PurchaseOrder.status != "Received").count()
    if open_pos > 15:
        return False

    low_material_rows = MaterialStock.query.order_by(MaterialStock.quantity.asc()).limit(8).all()
    if not low_material_rows:
        return False

    chosen_stock = random.choice(low_material_rows)
    supplier = random.choice(suppliers)

    quantity = random.choice([120, 180, 260, 350, 500])
    unit_cost = Decimal(str(round(random.uniform(1.2, 14.0), 2)))

    order = PurchaseOrder(
        supplier_id=supplier.id,
        warehouse_id=chosen_stock.warehouse_id,
        status="Ordered",
        order_date=datetime.now(),
    )
    db.session.add(order)
    db.session.flush()

    db.session.add(
        PurchaseOrderItem(
            purchase_order_id=order.id,
            material_id=chosen_stock.material_id,
            quantity=quantity,
            unit_cost=unit_cost,
        )
    )
    db.session.commit()
    return True


def create_production_plan() -> bool:
    open_plans = Production.query.filter(Production.status != "Completed").count()
    if open_plans > 12:
        return False

    low_stock_rows = ProductStock.query.order_by(ProductStock.quantity.asc()).limit(8).all()
    random.shuffle(low_stock_rows)

    for row in low_stock_rows:
        if not BillOfMaterials.query.filter_by(product_id=row.product_id).first():
            continue

        qty = random.choice([15, 20, 25, 35, 50])
        db.session.add(
            Production(
                product_id=row.product_id,
                warehouse_id=row.warehouse_id,
                quantity_planned=qty,
                status="Planned",
                planned_date=datetime.now(),
            )
        )
        db.session.commit()
        return True

    return False


def advance_purchase_orders(day_seconds: float) -> int:
    moved = 0
    now = datetime.now()

    orders = PurchaseOrder.query.filter(PurchaseOrder.status.in_(["Ordered", "In Transit"]))\
        .order_by(PurchaseOrder.order_date.asc()).limit(8).all()

    for order in orders:
        age_days = sim_days_since(order.order_date, now, day_seconds)

        if order.status == "Ordered" and age_days >= 0.30:
            order.status = "In Transit"
            moved += 1
            continue

        if order.status == "In Transit" and age_days >= 1.00:
            order.status = "Received"
            for item in order.items:
                stock = get_or_create_material_stock(item.material_id, order.warehouse_id)
                stock.quantity = round(stock.quantity + item.quantity, 2)
                sync_material_total(item.material_id)
                record_material_flow(
                    event_type="PurchaseReceipt",
                    material_id=item.material_id,
                    quantity=item.quantity,
                    source_warehouse_id=None,
                    target_warehouse_id=order.warehouse_id,
                    note=f"PO #{order.id} (sim)",
                )
            moved += 1

    if moved:
        db.session.commit()
    return moved


def advance_sales_orders(day_seconds: float) -> int:
    moved = 0
    now = datetime.now()

    orders = Order.query.filter(Order.shipping_status != "Delivered").order_by(Order.order_date.asc()).limit(10).all()
    for order in orders:
        age_days = sim_days_since(order.order_date, now, day_seconds)

        if order.shipping_status == "Pending" and age_days >= 0.10:
            order.shipping_status = "Picking"
            moved += 1
            continue

        if order.shipping_status == "Picking" and age_days >= 0.45:
            order.shipping_status = "Shipped"
            moved += 1
            continue

        if order.shipping_status == "Shipped" and age_days >= 1.00:
            order.shipping_status = "Delivered"
            moved += 1

    if moved:
        db.session.commit()
    return moved


def start_planned_production(day_seconds: float) -> int:
    moved = 0
    now = datetime.now()

    plans = Production.query.filter_by(status="Planned").order_by(Production.planned_date.asc()).limit(6).all()
    for plan in plans:
        age_days = sim_days_since(plan.planned_date, now, day_seconds)
        if age_days >= 0.20:
            plan.status = "In Progress"
            moved += 1

    if moved:
        db.session.commit()
    return moved


def complete_production(day_seconds: float) -> int:
    completed = 0
    now = datetime.now()

    plans = Production.query.filter_by(status="In Progress").order_by(Production.planned_date.asc()).limit(6).all()
    for plan in plans:
        age_days = sim_days_since(plan.planned_date, now, day_seconds)
        if age_days < 0.80:
            continue

        bom_rows = BillOfMaterials.query.filter_by(product_id=plan.product_id).all()
        if not bom_rows:
            continue

        consumption_plan = []
        feasible = True
        for row in bom_rows:
            required = round(row.quantity_required * plan.quantity_planned, 2)
            stocks = MaterialStock.query.filter_by(material_id=row.material_id).all()
            total_available = sum(s.quantity for s in stocks)
            if total_available < required:
                feasible = False
                break

            ordered_stocks = sorted(
                stocks,
                key=lambda s: (0 if s.warehouse_id == plan.warehouse_id else 1, -s.quantity),
            )
            remaining = required
            allocations = []
            for stock in ordered_stocks:
                if remaining <= 0:
                    break
                take = min(stock.quantity, remaining)
                if take <= 0:
                    continue
                allocations.append((stock, take))
                remaining = round(remaining - take, 2)

            consumption_plan.append((row, allocations))

        if not feasible:
            continue

        for row, allocations in consumption_plan:
            for stock, take in allocations:
                stock.quantity = round(stock.quantity - take, 2)
                record_material_flow(
                    event_type="ProductionConsumption",
                    material_id=row.material_id,
                    quantity=take,
                    source_warehouse_id=stock.warehouse_id,
                    target_warehouse_id=plan.warehouse_id,
                    note=f"Production #{plan.id} (sim)",
                )
            sync_material_total(row.material_id)

        product_stock = get_or_create_product_stock(plan.product_id, plan.warehouse_id)
        product_stock.quantity += plan.quantity_planned
        sync_product_total(plan.product_id)

        plan.status = "Completed"
        completed += 1

    if completed:
        db.session.commit()
    return completed


def run_tick(day_seconds: float) -> dict:
    stats = {
        "created_sales_orders": 0,
        "created_purchase_orders": 0,
        "created_productions": 0,
        "advanced_purchase_orders": 0,
        "advanced_sales_orders": 0,
        "started_productions": 0,
        "completed_productions": 0,
    }

    stats["advanced_purchase_orders"] = advance_purchase_orders(day_seconds)
    stats["advanced_sales_orders"] = advance_sales_orders(day_seconds)
    stats["started_productions"] = start_planned_production(day_seconds)
    stats["completed_productions"] = complete_production(day_seconds)

    if random.random() < 0.38:
        stats["created_sales_orders"] = 1 if create_sales_order() else 0
    if random.random() < 0.22:
        stats["created_purchase_orders"] = 1 if create_purchase_order() else 0
    if random.random() < 0.25:
        stats["created_productions"] = 1 if create_production_plan() else 0

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate realistic operations events for the workwear business.")
    parser.add_argument("--ticks", type=int, default=30, help="How many simulation cycles to run.")
    parser.add_argument("--sleep", type=float, default=5.0, help="Seconds between cycles.")
    parser.add_argument("--day-minutes", type=float, default=2.0, help="How many real minutes represent one simulated day.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for repeatable runs.")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    day_seconds = max(args.day_minutes, 0.1) * 60.0

    with app.app_context():
        for idx in range(1, max(args.ticks, 1) + 1):
            stats = run_tick(day_seconds)
            print(f"[tick {idx}] {stats}")
            if idx < args.ticks:
                time.sleep(max(args.sleep, 0.2))


if __name__ == "__main__":
    main()
