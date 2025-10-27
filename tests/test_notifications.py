import pytest

from mini_shop.models import OrderStatus
from mini_shop.notifications import NotificationCenter, NotificationError
from mini_shop.shop import MiniShop, ShopError


def create_shop() -> MiniShop:
    return MiniShop()


def test_notification_created_when_order_is_placed():
    shop = create_shop()
    customer = shop.register_customer("Alice")
    product = shop.add_product("Coffee Beans", price=12.5, stock=10)

    order = shop.place_order(customer.id, [(product.id, 2)])

    unread = shop.notifications.unread(recipient_id=customer.id)
    assert len(unread) == 1
    notification = unread[0]
    assert notification.data["order_id"] == order.id
    assert "placed" in notification.message


def test_mark_notification_as_read():
    shop = create_shop()
    customer = shop.register_customer("Bob")
    product = shop.add_product("Tea", price=6.0, stock=3)

    shop.place_order(customer.id, [(product.id, 1)])
    notification = shop.notifications.unread(recipient_id=customer.id)[0]

    shop.notifications.mark_read(notification.id)

    assert shop.notifications.unread(recipient_id=customer.id) == []


def test_order_status_update_creates_notification():
    shop = create_shop()
    customer = shop.register_customer("Carol")
    product = shop.add_product("Filter", price=4.0, stock=4)

    order = shop.place_order(customer.id, [(product.id, 1)])
    shop.notifications.mark_all_read(recipient_id=customer.id)

    shop.update_order_status(order.id, OrderStatus.SHIPPED)

    unread = shop.notifications.unread(recipient_id=customer.id)
    assert len(unread) == 1
    assert unread[0].data == {"order_id": order.id, "status": "shipped"}


def test_notification_filters_and_counts():
    center = NotificationCenter()
    for idx in range(3):
        center.publish(f"System message {idx}")
    for idx in range(2):
        center.publish(f"Order update {idx}", recipient_id="user-1", category="orders")

    assert center.count_unread(recipient_id="user-1") == 5
    assert center.count_unread(recipient_id="user-1", category="orders") == 2

    order_notifications = center.list_notifications(recipient_id="user-1", include_read=False, category="orders")
    assert len(order_notifications) == 2

    center.mark_all_read(recipient_id="user-1", category="orders")
    assert center.count_unread(recipient_id="user-1", category="orders") == 0
    assert center.count_unread(recipient_id="user-1") == 3


def test_errors_are_raised_for_invalid_operations():
    center = NotificationCenter()
    with pytest.raises(NotificationError):
        center.publish("")

    with pytest.raises(NotificationError):
        center.mark_read("missing")

    shop = create_shop()
    with pytest.raises(ShopError):
        shop.place_order("unknown", [])
