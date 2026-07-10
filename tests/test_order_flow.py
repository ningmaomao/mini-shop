from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Category, Inventory, Order, OrderStatus, Payment, Product, ProductSKU, User


def test_order_payment_is_idempotent_and_consumes_locked_stock():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        buyer = User(email="buyer@example.com", password_hash=generate_password_hash("buyer123"), role="customer")
        category = Category(name="Test")
        product = Product(name="Test Product", category=category)
        sku = ProductSKU(sku_code="TEST-001", price="19.90", spec_json={"color": "black"})
        sku.inventory = Inventory(available_stock=5, locked_stock=0)
        product.skus.append(sku)
        db.session.add_all([buyer, product])
        db.session.commit()
        sku_id = sku.id

    client = app.test_client()
    client.post("/login", data={"email": "buyer@example.com", "password": "buyer123"})
    assert client.post("/api/cart/items", json={"sku_id": sku_id, "quantity": 2}).status_code == 201
    created = client.post("/api/orders/from-cart", json={"receiver_name": "Buyer", "receiver_phone": "13800000000", "receiver_address": "Beijing"})
    assert created.status_code == 201
    order_no = created.get_json()["order_no"]

    with app.app_context():
        inventory = db.session.scalar(select(Inventory))
        assert inventory.available_stock == 3
        assert inventory.locked_stock == 2

    first = client.post(f"/api/payments/mock/{order_no}", headers={"Idempotency-Key": "pay-001"})
    second = client.post(f"/api/payments/mock/{order_no}", headers={"Idempotency-Key": "pay-001"})
    assert first.status_code == 200
    assert second.get_json()["replayed"] is True

    with app.app_context():
        inventory = db.session.scalar(select(Inventory))
        order = db.session.scalar(select(Order).where(Order.order_no == order_no))
        assert inventory.available_stock == 3
        assert inventory.locked_stock == 0
        assert order.status == OrderStatus.PAID
        assert len(db.session.scalars(select(Payment)).all()) == 1
