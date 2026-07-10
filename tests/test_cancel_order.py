from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Category, Inventory, OrderStatus, Product, ProductSKU, User


def test_cancel_releases_locked_inventory():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        buyer = User(email="buyer@example.com", password_hash=generate_password_hash("buyer123"), role="customer")
        category = Category(name="Test")
        product = Product(name="Cancelable Product", category=category)
        sku = ProductSKU(sku_code="CANCEL-001", price="10.00", spec_json={})
        sku.inventory = Inventory(available_stock=2, locked_stock=0)
        product.skus.append(sku)
        db.session.add_all([buyer, product])
        db.session.commit()
        sku_id = sku.id

    client = app.test_client()
    client.post("/login", data={"email": "buyer@example.com", "password": "buyer123"})
    client.post("/api/cart/items", json={"sku_id": sku_id, "quantity": 1})
    order = client.post("/api/orders/from-cart", json={"receiver_name": "Buyer", "receiver_phone": "13800000000", "receiver_address": "Beijing"}).get_json()
    response = client.post(f"/api/orders/{order['order_no']}/cancel")
    assert response.status_code == 200
    assert response.get_json()["status"] == OrderStatus.CANCELLED

    with app.app_context():
        inventory = db.session.scalar(select(Inventory))
        assert inventory.available_stock == 2
        assert inventory.locked_stock == 0
