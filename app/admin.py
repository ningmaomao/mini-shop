from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select

from .extensions import db
from .models import Category, Inventory, Product, ProductSKU
from .services import DomainError, MerchantAnalyticsService, _money

bp = Blueprint("admin", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.get("/admin")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html", metrics=MerchantAnalyticsService.dashboard())


@bp.post("/api/admin/products")
@admin_required
def create_product():
    payload = request.get_json(silent=True) or {}
    try:
        name = str(payload.get("name", "")).strip()
        category_name = str(payload.get("category_name", "")).strip()
        skus = payload.get("skus") or []
        if not name or not category_name or not isinstance(skus, list) or not skus:
            raise DomainError("name, category_name and at least one SKU are required.")
        category = db.session.scalar(select(Category).where(Category.name == category_name))
        if not category:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.flush()
        product = Product(name=name, category_id=category.id, description=str(payload.get("description", "")).strip(), status="active")
        db.session.add(product)
        db.session.flush()
        for raw_sku in skus:
            sku_code = str(raw_sku.get("sku_code", "")).strip()
            stock = int(raw_sku.get("stock", 0))
            if not sku_code or stock < 0:
                raise DomainError("Each SKU requires sku_code and non-negative stock.")
            sku = ProductSKU(product_id=product.id, sku_code=sku_code, spec_json=raw_sku.get("spec") or {}, price=_money(raw_sku.get("price")), original_price=_money(raw_sku.get("original_price")) if raw_sku.get("original_price") is not None else None, status="active")
            sku.inventory = Inventory(available_stock=stock, locked_stock=0)
            db.session.add(sku)
        db.session.commit()
        return jsonify({"product_id": product.id, "name": product.name}), 201
    except (DomainError, TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
