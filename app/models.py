from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


class OrderStatus:
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDING = "refunding"
    REFUNDED = "refunded"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="customer", index=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(32), nullable=False, default="active", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    category = db.relationship("Category", backref=db.backref("products", lazy=True))
    skus = db.relationship(
        "ProductSKU",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProductSKU(db.Model):
    __tablename__ = "product_skus"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    sku_code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    spec_json = db.Column(db.JSON, nullable=False, default=dict)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    original_price = db.Column(db.Numeric(12, 2), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active", index=True)

    product = db.relationship("Product", back_populates="skus")
    inventory = db.relationship(
        "Inventory",
        back_populates="sku",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Inventory(db.Model):
    __tablename__ = "inventories"

    id = db.Column(db.Integer, primary_key=True)
    sku_id = db.Column(db.Integer, db.ForeignKey("product_skus.id"), nullable=False, unique=True)
    available_stock = db.Column(db.Integer, nullable=False, default=0)
    locked_stock = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    sku = db.relationship("ProductSKU", back_populates="inventory")


class CartItem(db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "sku_id", name="uq_cart_user_sku"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sku_id = db.Column(db.Integer, db.ForeignKey("product_skus.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    sku = db.relationship("ProductSKU", lazy="joined")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default=OrderStatus.PENDING_PAYMENT, index=True)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    payable_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    receiver_name = db.Column(db.String(120), nullable=False)
    receiver_phone = db.Column(db.String(40), nullable=False)
    receiver_address = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    shipped_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    payments = db.relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, nullable=False)
    sku_id = db.Column(db.Integer, nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    sku_description = db.Column(db.String(300), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_no = db.Column(db.String(64), unique=True, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    channel = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    transaction_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    idempotency_key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)

    order = db.relationship("Order", back_populates="payments")
