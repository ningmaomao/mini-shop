from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from .extensions import db
from .models import CartItem, Inventory, Order, OrderItem, OrderStatus, Payment, ProductSKU


class DomainError(ValueError):
    pass


class EmptyCartError(DomainError):
    pass


class OutOfStockError(DomainError):
    pass


class InvalidOrderStateError(DomainError):
    pass


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DomainError("Invalid money value.") from exc


def _build_no(prefix: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}{stamp}{secrets.token_hex(4).upper()}"


class InventoryService:
    @staticmethod
    def lock_stock(sku_id: int, quantity: int) -> None:
        result = db.session.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id, Inventory.available_stock >= quantity)
            .values(
                available_stock=Inventory.available_stock - quantity,
                locked_stock=Inventory.locked_stock + quantity,
                version=Inventory.version + 1,
            )
        )
        if result.rowcount != 1:
            raise OutOfStockError(f"SKU {sku_id} is out of stock.")

    @staticmethod
    def release_locked_stock(sku_id: int, quantity: int) -> None:
        result = db.session.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id, Inventory.locked_stock >= quantity)
            .values(
                available_stock=Inventory.available_stock + quantity,
                locked_stock=Inventory.locked_stock - quantity,
                version=Inventory.version + 1,
            )
        )
        if result.rowcount != 1:
            raise DomainError(f"Locked inventory is inconsistent for SKU {sku_id}.")

    @staticmethod
    def consume_locked_stock(sku_id: int, quantity: int) -> None:
        result = db.session.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id, Inventory.locked_stock >= quantity)
            .values(
                locked_stock=Inventory.locked_stock - quantity,
                version=Inventory.version + 1,
            )
        )
        if result.rowcount != 1:
            raise DomainError(f"Locked inventory is inconsistent for SKU {sku_id}.")


class CartService:
    @staticmethod
    def add_item(user_id: int, sku_id: int, quantity: int) -> CartItem:
        if quantity <= 0:
            raise DomainError("Quantity must be greater than zero.")
        sku = db.session.get(ProductSKU, sku_id)
        if not sku or sku.status != "active" or sku.product.status != "active":
            raise DomainError("SKU is not available.")
        item = db.session.scalar(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.sku_id == sku_id)
        )
        if item:
            item.quantity += quantity
        else:
            item = CartItem(user_id=user_id, sku_id=sku_id, quantity=quantity)
            db.session.add(item)
        db.session.commit()
        return item


class OrderService:
    @staticmethod
    def create_from_cart(user_id: int, *, receiver_name: str, receiver_phone: str, receiver_address: str) -> Order:
        cart_items = db.session.scalars(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .options(selectinload(CartItem.sku).selectinload(ProductSKU.product))
        ).all()
        if not cart_items:
            raise EmptyCartError("Cart is empty.")
        if not all(v.strip() for v in [receiver_name, receiver_phone, receiver_address]):
            raise DomainError("Receiver name, phone and address are required.")

        quantities: dict[int, int] = defaultdict(int)
        for item in cart_items:
            if item.quantity <= 0:
                raise DomainError("Cart contains an invalid quantity.")
            quantities[item.sku_id] += item.quantity

        skus = db.session.scalars(
            select(ProductSKU)
            .where(ProductSKU.id.in_(list(quantities)))
            .options(selectinload(ProductSKU.product))
        ).all()
        sku_map = {sku.id: sku for sku in skus}
        if set(sku_map) != set(quantities):
            raise DomainError("Cart contains a missing SKU.")

        order = Order(
            order_no=_build_no("MS"),
            user_id=user_id,
            status=OrderStatus.PENDING_PAYMENT,
            receiver_name=receiver_name.strip(),
            receiver_phone=receiver_phone.strip(),
            receiver_address=receiver_address.strip(),
        )
        db.session.add(order)
        total = Decimal("0.00")

        try:
            db.session.flush()
            for sku_id in sorted(quantities):
                sku = sku_map[sku_id]
                quantity = quantities[sku_id]
                if sku.status != "active" or sku.product.status != "active":
                    raise DomainError(f"SKU {sku_id} is not available.")
                InventoryService.lock_stock(sku_id, quantity)
                unit_price = _money(sku.price)
                subtotal = (unit_price * quantity).quantize(Decimal("0.01"))
                total += subtotal
                spec_text = ", ".join(
                    f"{key}: {value}" for key, value in sorted((sku.spec_json or {}).items())
                ) or "Default"
                db.session.add(OrderItem(
                    order_id=order.id,
                    product_id=sku.product_id,
                    sku_id=sku.id,
                    product_name=sku.product.name,
                    sku_description=spec_text,
                    unit_price=unit_price,
                    quantity=quantity,
                    subtotal=subtotal,
                ))
            order.total_amount = total
            order.payable_amount = total
            for item in cart_items:
                db.session.delete(item)
            db.session.commit()
            return order
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def cancel(order: Order) -> Order:
        if order.status != OrderStatus.PENDING_PAYMENT:
            raise InvalidOrderStateError("Only pending-payment orders can be cancelled.")
        try:
            for item in order.items:
                InventoryService.release_locked_stock(item.sku_id, item.quantity)
            order.status = OrderStatus.CANCELLED
            db.session.commit()
            return order
        except Exception:
            db.session.rollback()
            raise


class PaymentService:
    @staticmethod
    def mock_pay(order: Order, *, idempotency_key: str) -> tuple[Payment, bool]:
        key = idempotency_key.strip()
        if not key:
            raise DomainError("Idempotency-Key header is required.")
        existing = db.session.scalar(select(Payment).where(Payment.idempotency_key == key))
        if existing:
            if existing.order_id != order.id:
                raise DomainError("Idempotency key already belongs to another order.")
            return existing, True
        if order.status == OrderStatus.PAID:
            latest = db.session.scalar(
                select(Payment)
                .where(Payment.order_id == order.id, Payment.status == "paid")
                .order_by(Payment.id.desc())
            )
            if latest:
                return latest, True
        if order.status != OrderStatus.PENDING_PAYMENT:
            raise InvalidOrderStateError(f"Order cannot be paid from status '{order.status}'.")

        payment = Payment(
            payment_no=_build_no("PAY"),
            order_id=order.id,
            channel="mock",
            amount=_money(order.payable_amount),
            status="paid",
            transaction_id=_build_no("TXN"),
            idempotency_key=key,
            paid_at=datetime.now(UTC),
        )
        try:
            for item in order.items:
                InventoryService.consume_locked_stock(item.sku_id, item.quantity)
            order.status = OrderStatus.PAID
            order.paid_at = datetime.now(UTC)
            db.session.add(payment)
            db.session.commit()
            return payment, False
        except IntegrityError:
            db.session.rollback()
            replay = db.session.scalar(select(Payment).where(Payment.idempotency_key == key))
            if replay and replay.order_id == order.id:
                return replay, True
            raise
        except Exception:
            db.session.rollback()
            raise


class MerchantAnalyticsService:
    @staticmethod
    def dashboard() -> dict[str, Any]:
        paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.COMPLETED]
        gmv = db.session.scalar(
            select(func.coalesce(func.sum(Order.payable_amount), 0)).where(Order.status.in_(paid_statuses))
        )
        order_count = db.session.scalar(select(func.count(Order.id)))
        pending_count = db.session.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING_PAYMENT)
        )
        low_stock = db.session.scalars(
            select(Inventory).where(Inventory.available_stock <= 5).order_by(Inventory.available_stock.asc()).limit(10)
        ).all()
        return {
            "gmv": str(_money(gmv)),
            "order_count": int(order_count or 0),
            "pending_count": int(pending_count or 0),
            "low_stock": [
                {"sku_id": item.sku_id, "available_stock": item.available_stock, "locked_stock": item.locked_stock}
                for item in low_stock
            ],
        }
