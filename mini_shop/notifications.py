"""Notification service used across the mini shop package."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from .models import Notification


class NotificationError(RuntimeError):
    """Raised when an invalid operation is attempted on a notification."""


class NotificationCenter:
    """Stores notifications and provides helpers to manage them.

    The notification center keeps a list of notifications per recipient. A
    ``None`` recipient id is treated as a broadcast message that is visible to
    everyone.
    """

    def __init__(self) -> None:
        self._notifications: List[Notification] = []
        self._index: Dict[str, Notification] = {}
        self._recipient_map: Dict[Optional[str], List[str]] = defaultdict(list)

    def publish(
        self,
        message: str,
        *,
        recipient_id: Optional[str] = None,
        category: str = "general",
        data: Optional[Dict[str, object]] = None,
        notification_id: Optional[str] = None,
    ) -> Notification:
        """Publish a new notification and return it.

        Parameters
        ----------
        message:
            Human readable content.
        recipient_id:
            Identifier for the intended recipient. ``None`` indicates a
            broadcast notification available to everyone.
        category:
            Used for filtering notifications by type.
        data:
            Optional machine readable payload that callers may use to provide
            context (such as order identifiers).
        notification_id:
            Allows callers to control the identifier. When ``None`` a random
            UUID4 is used.
        """

        if not message:
            raise NotificationError("message must be provided")

        notification = Notification(
            id=notification_id or str(uuid4()),
            message=message,
            created_at=datetime.utcnow(),
            recipient_id=recipient_id,
            category=category,
            data=data or {},
        )
        self._notifications.append(notification)
        self._index[notification.id] = notification
        self._recipient_map[recipient_id].append(notification.id)
        return notification

    def list_notifications(
        self,
        *,
        recipient_id: Optional[str] = None,
        include_read: bool = True,
        category: Optional[str] = None,
    ) -> List[Notification]:
        """Return notifications for the given recipient.

        Broadcast notifications are included for every recipient. When
        ``recipient_id`` is ``None`` only broadcast messages are returned.
        """

        ids = list(self._recipient_map.get(recipient_id, []))
        if recipient_id is not None:
            ids.extend(self._recipient_map.get(None, []))

        notifications = [self._index[i] for i in ids]
        if not include_read:
            notifications = [n for n in notifications if not n.is_read]
        if category is not None:
            notifications = [n for n in notifications if n.category == category]
        return sorted(notifications, key=lambda n: n.created_at, reverse=True)

    def unread(self, *, recipient_id: Optional[str] = None, category: Optional[str] = None) -> List[Notification]:
        """Convenience wrapper to only return unread notifications."""

        return self.list_notifications(
            recipient_id=recipient_id,
            include_read=False,
            category=category,
        )

    def mark_read(self, notification_id: str) -> Notification:
        """Mark a notification as read and return it."""

        notification = self._index.get(notification_id)
        if notification is None:
            raise NotificationError(f"Notification '{notification_id}' does not exist")
        notification.mark_read()
        return notification

    def mark_all_read(self, *, recipient_id: Optional[str] = None, category: Optional[str] = None) -> List[Notification]:
        """Mark all notifications for a recipient as read."""

        notifications = self.list_notifications(
            recipient_id=recipient_id,
            include_read=False,
            category=category,
        )
        for notification in notifications:
            notification.mark_read()
        return notifications

    def count_unread(self, *, recipient_id: Optional[str] = None, category: Optional[str] = None) -> int:
        """Return the number of unread notifications matching the filters."""

        return len(
            self.list_notifications(
                recipient_id=recipient_id,
                include_read=False,
                category=category,
            )
        )

    def export(self, *, recipient_id: Optional[str] = None) -> List[Dict[str, object]]:
        """Export notifications for serialisation (useful in APIs)."""

        return [
            asdict(notification)
            for notification in self.list_notifications(recipient_id=recipient_id)
        ]

    def clear(self) -> None:
        """Remove all stored notifications."""

        self._notifications.clear()
        self._index.clear()
        self._recipient_map.clear()


__all__ = ["NotificationCenter", "NotificationError"]
