from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .extensions import db
from .models import Order
from .services import DomainError, PaymentService

bp = Blueprint("payments", __name__)


@bp.post("/api/payments/mock/<order_no>")
@login_required
def mock_pay(order_no: str):
    order = db.session.scalar(select(Order).where(Order.order_no == order_no, Order.user_id == current_user.id).options(selectinload(Order.items), selectinload(Order.payments)))
    if not order:
        return jsonify({"error": "Order not found."}), 404
    try:
        payment, replayed = PaymentService.mock_pay(order, idempotency_key=request.headers.get("Idempotency-Key", ""))
    except DomainError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"payment_no": payment.payment_no, "transaction_id": payment.transaction_id, "status": payment.status, "order_status": payment.order.status, "replayed": replayed})
