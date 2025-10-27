"""Domain models for the mini shop application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class OrderStatus(str, Enum):
    """Enumeration describing the lifecycle of an order."""

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Product:
    """A product available for purchase."""

    id: str
    name: str
    price: float
    stock: int

    def adjust_stock(self, delta: int) -> None:
        """Update the available stock for the product.

        Parameters
        ----------
        delta:
            The change to apply to the stock quantity. This may be negative when
            items are sold.
        """

        new_stock = self.stock + delta
        if new_stock < 0:
            raise ValueError("Stock level cannot be negative")
        self.stock = new_stock


@dataclass(slots=True)
class Customer:
    """Represents a customer in the shop."""

    id: str
    name: str


@dataclass(slots=True)
class OrderItem:
    """Single line of an order."""

    product_id: str
    quantity: int
    unit_price: float

    @property
    def total(self) -> float:
        return self.quantity * self.unit_price


@dataclass(slots=True)
class Order:
    """Represents a placed order."""

    id: str
    customer_id: str
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)

    def total_amount(self) -> float:
        return sum(item.total for item in self.items)


@dataclass(slots=True)
class Notification:
    """Stores a user-facing notification."""

    id: str
    message: str
    created_at: datetime
    recipient_id: Optional[str] = None
    category: str = "general"
    is_read: bool = False
    data: Dict[str, object] = field(default_factory=dict)

    def mark_read(self) -> None:
        self.is_read = True


__all__ = [
    "Customer",
    "Notification",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
]
