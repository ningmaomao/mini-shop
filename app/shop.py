from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .extensions import db
from .models import CartItem, Product, ProductSKU
from .services import CartService, DomainError

bp = Blueprint("shop", __name__)


def _cart_item_json(item: CartItem) -> dict:
    return {"sku_id": item.sku_id, "sku_code": item.sku.sku_code, "product_name": item.sku.product.name, "spec": item.sku.spec_json, "unit_price": str(item.sku.price), "quantity": item.quantity}


@bp.get("/")
@login_required
def index():
    products = db.session.scalars(select(Product).where(Product.status == "active").options(selectinload(Product.skus).selectinload(ProductSKU.inventory)).order_by(Product.created_at.desc())).all()
    return render_template("shop/index.html", products=products)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/api/cart")
@login_required
def get_cart():
    items = db.session.scalars(select(CartItem).where(CartItem.user_id == current_user.id).options(selectinload(CartItem.sku).selectinload(ProductSKU.product)).order_by(CartItem.id.asc())).all()
    return jsonify({"items": [_cart_item_json(item) for item in items]})


@bp.post("/api/cart/items")
@login_required
def add_cart_item():
    payload = request.get_json(silent=True) or {}
    try:
        item = CartService.add_item(current_user.id, int(payload.get("sku_id")), int(payload.get("quantity", 1)))
    except (DomainError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_cart_item_json(item)), 201
