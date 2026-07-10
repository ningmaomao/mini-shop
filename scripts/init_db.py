from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.models import Category, Inventory, Product, ProductSKU, User


def seed() -> None:
    for email, password, role in [("admin@example.com", "admin123", "admin"), ("buyer@example.com", "buyer123", "customer")]:
        if not db.session.scalar(select(User).where(User.email == email)):
            db.session.add(User(email=email, password_hash=generate_password_hash(password), role=role))
    category = db.session.scalar(select(Category).where(Category.name == "Demo"))
    if not category:
        category = Category(name="Demo")
        db.session.add(category)
        db.session.flush()
    if not db.session.scalar(select(Product).where(Product.name == "Merchant Starter Kit")):
        product = Product(category_id=category.id, name="Merchant Starter Kit", description="Demo product for cart, inventory, order and payment flows.")
        sku = ProductSKU(sku_code="STARTER-BLACK", spec_json={"color": "black", "edition": "starter"}, price="199.00", original_price="249.00", status="active")
        sku.inventory = Inventory(available_stock=20, locked_stock=0)
        product.skus.append(sku)
        db.session.add(product)
    db.session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        if args.reset:
            db.drop_all()
        db.create_all()
        seed()
        print("Database ready. Merchant: admin@example.com / admin123; Buyer: buyer@example.com / buyer123")


if __name__ == "__main__":
    main()
