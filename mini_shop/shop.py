"""Core shop logic that integrates with the notification system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from .models import Customer, Order, OrderItem, OrderStatus, Product
from .notifications import NotificationCenter


class ShopError(RuntimeError):
    """Generic exception raised for invalid operations."""


@dataclass
class ShopConfig:
    """Configuration options for :class:`MiniShop`."""

    allow_backorders: bool = False


class MiniShop:
    """In-memory implementation of a small shop.

    The goal of this class is to provide a simple interface that can be used by
    tests (and potentially other applications) without requiring an actual
    database or background workers. The notification center integration makes it
    easy to surface important events to end users.
    """

    def __init__(self, *, config: Optional[ShopConfig] = None, notifications: Optional[NotificationCenter] = None) -> None:
        self.config = config or ShopConfig()
        self.notifications = notifications or NotificationCenter()

        self._products: Dict[str, Product] = {}
        self._customers: Dict[str, Customer] = {}
        self._orders: Dict[str, Order] = {}

    # ------------------------------------------------------------------
    # Customer management
    # ------------------------------------------------------------------
    def register_customer(self, name: str) -> Customer:
        if not name:
            raise ShopError("customer name must be provided")
        identifier = str(uuid4())
        customer = Customer(id=identifier, name=name)
        self._customers[identifier] = customer
        return customer

    def get_customer(self, customer_id: str) -> Customer:
        try:
            return self._customers[customer_id]
        except KeyError as exc:
            raise ShopError(f"Unknown customer '{customer_id}'") from exc

    # ------------------------------------------------------------------
    # Product management
    # ------------------------------------------------------------------
    def add_product(self, name: str, price: float, stock: int) -> Product:
        if price < 0:
            raise ShopError("price cannot be negative")
        if stock < 0:
            raise ShopError("stock cannot be negative")
        identifier = str(uuid4())
        product = Product(id=identifier, name=name, price=price, stock=stock)
        self._products[identifier] = product
        return product

    def get_product(self, product_id: str) -> Product:
        try:
            return self._products[product_id]
        except KeyError as exc:
            raise ShopError(f"Unknown product '{product_id}'") from exc

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------
    def place_order(self, customer_id: str, items: Sequence[Tuple[str, int]]) -> Order:
        if not items:
            raise ShopError("orders must contain at least one item")
        customer = self.get_customer(customer_id)

        order_items: List[OrderItem] = []
        for product_id, quantity in items:
            if quantity <= 0:
                raise ShopError("quantity must be positive")
            product = self.get_product(product_id)
            if not self.config.allow_backorders and product.stock < quantity:
                raise ShopError(f"Insufficient stock for product '{product.name}'")
            product.adjust_stock(-quantity)
            order_items.append(OrderItem(product_id=product_id, quantity=quantity, unit_price=product.price))

        identifier = str(uuid4())
        order = Order(id=identifier, customer_id=customer.id, items=order_items)
        self._orders[identifier] = order

        self.notifications.publish(
            f"Order {order.id} placed successfully.",
            recipient_id=customer.id,
            category="orders",
            data={
                "order_id": order.id,
                "total": order.total_amount(),
            },
        )
        return order

    def get_order(self, order_id: str) -> Order:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise ShopError(f"Unknown order '{order_id}'") from exc

    def update_order_status(self, order_id: str, status: OrderStatus) -> Order:
        order = self.get_order(order_id)
        if order.status == status:
            return order
        order.status = status
        self.notifications.publish(
            f"Order {order.id} status changed to {status.value}.",
            recipient_id=order.customer_id,
            category="orders",
            data={"order_id": order.id, "status": status.value},
        )
        return order

    # ------------------------------------------------------------------
    # Notification convenience wrappers
    # ------------------------------------------------------------------
    def unread_notifications(self, *, customer_id: Optional[str] = None, category: Optional[str] = None) -> List[str]:
        """Return the message for unread notifications.

        This helper is useful for command line applications that only need the
        human readable content of each notification.
        """

        notifications = self.notifications.unread(recipient_id=customer_id, category=category)
        return [notification.message for notification in notifications]

    def notification_summary(self, customer_id: str) -> Dict[str, int]:
        """Return a count of unread notifications per category for a customer."""

        categories: Dict[str, int] = {}
        notifications = self.notifications.unread(recipient_id=customer_id)
        for notification in notifications:
            categories[notification.category] = categories.get(notification.category, 0) + 1
        return categories


__all__ = ["MiniShop", "ShopConfig", "ShopError"]
