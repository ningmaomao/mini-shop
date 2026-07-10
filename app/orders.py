from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .extensions import db
from .models import Order
from .services import DomainError, OrderService

bp = Blueprint("orders", __name__)


def _order_json(order: Order) -> dict:
    return {"order_no": order.order_no, "status": order.status, "total_amount": str(order.total_amount), "payable_amount": str(order.payable_amount), "receiver": {"name": order.receiver_name, "phone": order.receiver_phone, "address": order.receiver_address}, "items": [{"product_name": item.product_name, "sku_description": item.sku_description, "unit_price": str(item.unit_price), "quantity": item.quantity, "subtotal": str(item.subtotal)} for item in order.items]}


def _load_user_order(order_no: str) -> Order | None:
    return db.session.scalar(select(Order).where(Order.order_no == order_no, Order.user_id == current_user.id).options(selectinload(Order.items), selectinload(Order.payments)))


@bp.post("/api/orders/from-cart")
@login_required
def create_order_from_cart():
    payload = request.get_json(silent=True) or {}
    try:
        order = OrderService.create_from_cart(current_user.id, receiver_name=str(payload.get("receiver_name", "")), receiver_phone=str(payload.get("receiver_phone", "")), receiver_address=str(payload.get("receiver_address", "")))
    except DomainError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_order_json(order)), 201


@bp.get("/api/orders/<order_no>")
@login_required
def get_order(order_no: str):
    order = _load_user_order(order_no)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    return jsonify(_order_json(order))


@bp.post("/api/orders/<order_no>/cancel")
@login_required
def cancel_order(order_no: str):
    order = _load_user_order(order_no)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    try:
        OrderService.cancel(order)
    except DomainError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(_order_json(order))
