# Mini Shop

A production-oriented lightweight merchant e-commerce system built with Flask.

Mini Shop is designed as a compact reference implementation for merchant commerce: product and SKU management, inventory locking, carts, order state transitions, idempotent payment handling, and an operational dashboard.

> This project is **production-oriented**, not yet production-ready. The payment adapter is mocked. Before handling real money it still needs migrations, CSRF protection, rate limiting, signed payment adapters, observability and a production security review.

## What makes it different from a toy shop

- SKU-level inventory instead of product-level stock
- `available_stock` and `locked_stock`
- conditional SQL inventory updates to reduce overselling risk
- product, SKU, price and receiver snapshots in orders
- explicit order states
- payment idempotency keys and unique transaction IDs
- service-layer transaction boundaries
- merchant operating metrics and low-stock alerts

## Architecture

```text
Flask blueprints
      |
      v
Commerce services
Cart / Inventory / Order / Payment / Analytics
      |
      v
SQLAlchemy domain models
      |
      v
SQLite for local development
```

The project intentionally stays a modular monolith. For a single merchant, microservices would add deployment and consistency cost before they add business value.

## Commerce flow

```text
Cart
  |
  v
Create order
  |
  +--> lock inventory
  |    available -= quantity
  |    locked    += quantity
  |
  v
PENDING_PAYMENT
  | \
  |  \ cancel --> release inventory --> CANCELLED
  |
  v
Mock payment
  |
  +--> consume locked stock
  +--> unique idempotency key
  +--> unique transaction ID
  |
  v
PAID
```

## Quick start

Python 3.12 is recommended.

```bash
python -m venv .venv
pip install -r requirements.txt
python scripts/init_db.py --reset
python run.py
```

Open port `8000`.

Demo accounts:

```text
Merchant: admin@example.com / admin123
Buyer:    buyer@example.com / buyer123
```

These credentials are demo-only.

## Docker

```bash
docker compose up --build
```

## Main APIs

### Add to cart

```http
POST /api/cart/items
Content-Type: application/json

{"sku_id": 1, "quantity": 2}
```

### Create order

```http
POST /api/orders/from-cart
Content-Type: application/json

{
  "receiver_name": "Ning Mao",
  "receiver_phone": "13800000000",
  "receiver_address": "Beijing"
}
```

### Mock payment

```http
POST /api/payments/mock/MS...
Idempotency-Key: checkout-2026-001
```

Repeating a payment with the same idempotency key returns the existing payment instead of consuming stock twice.

### Merchant creates product and SKUs

```http
POST /api/admin/products
Content-Type: application/json

{
  "name": "Coffee Set",
  "category_name": "Kitchen",
  "description": "Merchant demo product",
  "skus": [
    {
      "sku_code": "COFFEE-BLACK-01",
      "spec": {"color": "black"},
      "price": "99.00",
      "original_price": "129.00",
      "stock": 20
    }
  ]
}
```

## Validation

```bash
pytest
```

Integration tests cover cart-to-order, stock locking, payment stock consumption, idempotency, order cancellation and inventory release.

## Important design decisions

### Inventory is not one number

`available_stock` means stock that can still be sold. `locked_stock` means stock reserved by unpaid orders.

Creating an order moves available stock to locked stock. Paying consumes locked stock. Cancelling returns locked stock to available stock.

### Orders store snapshots

Order items store product name, SKU description, unit price and subtotal. Orders store receiver name, phone and address. Historical orders therefore do not mutate when products or addresses change.

### Payment is idempotent

`Payment.idempotency_key` and `Payment.transaction_id` are unique. The mock adapter models repeated payment notifications without repeated order or inventory changes.

## Roadmap

1. Flask-Migrate / Alembic migrations
2. PostgreSQL deployment profile
3. CSRF protection and rate limiting
4. signed WeChat Pay / Alipay adapters
5. refund state machine and audit log
6. shipment tracking
7. unpaid-order inventory reservation expiration
8. background jobs
9. RFM, repurchase rate, AOV and inventory turnover analytics
10. AI merchant insight assistant backed by verified business metrics

## Positioning

**Mini Shop is a lightweight merchant e-commerce and business analytics system built with Flask. It covers SKU management, inventory locking, order state transitions, idempotent payment processing, merchant dashboards and data-driven business foundations.**
