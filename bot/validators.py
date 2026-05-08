"""
validators.py
-------------
Pure validation functions — no side-effects, no imports from the rest
of the bot. Each function returns (ok: bool, value_or_error: any).

Having this in its own file makes it easy to unit-test and reuse
across both the CLI and any future web/GUI layer.
"""

from typing import Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP"}
VALID_TIF = {"GTC", "IOC", "FOK"}

# ── Individual field validators ───────────────────────────────────────────────


def validate_symbol(symbol: str) -> Tuple[bool, str]:
    """
    Symbols must be non-empty alphanumeric strings (4–20 chars).
    We upper-case the input so 'btcusdt' works just as well as 'BTCUSDT'.
    """
    s = symbol.strip().upper()
    if not s:
        return False, "Symbol cannot be empty."
    if not s.isalnum():
        return False, (
            f"Symbol '{s}' contains invalid characters. "
            "Use alphanumeric only (e.g. BTCUSDT, ETHUSDT)."
        )
    if not (3 <= len(s) <= 20):
        return False, (
            f"Symbol '{s}' has an unusual length ({len(s)} chars). "
            "Typical symbols are 3–20 characters."
        )
    return True, s


def validate_side(side: str) -> Tuple[bool, str]:
    s = side.strip().upper()
    if s not in VALID_SIDES:
        return False, (
            f"Invalid side '{s}'. Must be one of: "
            + ", ".join(sorted(VALID_SIDES)) + "."
        )
    return True, s


def validate_order_type(order_type: str) -> Tuple[bool, str]:
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        return False, (
            f"Invalid order type '{t}'. Must be one of: "
            + ", ".join(sorted(VALID_ORDER_TYPES)) + "."
        )
    return True, t


def validate_quantity(quantity: str) -> Tuple[bool, any]:
    try:
        q = float(str(quantity).strip())
    except (ValueError, TypeError):
        return False, "Quantity must be a valid number (e.g. 0.01, 1, 100)."

    if q <= 0:
        return False, "Quantity must be greater than zero."
    if q > 1_000_000:
        # Soft sanity check — not a hard Binance rule
        return False, (
            f"Quantity {q} looks unrealistically large. "
            "Double-check — Binance may reject it anyway."
        )
    return True, round(q, 8)


def validate_price(price: str, field_name: str = "Price") -> Tuple[bool, any]:
    try:
        p = float(str(price).strip())
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number."
    if p <= 0:
        return False, f"{field_name} must be greater than zero."
    return True, round(p, 8)


def validate_tif(tif: str) -> Tuple[bool, str]:
    t = tif.strip().upper()
    if t not in VALID_TIF:
        return False, (
            f"Invalid time-in-force '{t}'. "
            "Options: GTC (Good Till Cancel), IOC (Immediate or Cancel), FOK (Fill or Kill)."
        )
    return True, t


# ── Composite validator ───────────────────────────────────────────────────────


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> dict:
    """
    Validates all inputs in one shot.

    Returns:
        {"errors": [...]}         — if any field fails
        {"params": {...}}         — all cleaned values if everything passes
    """
    errors: list[str] = []

    ok, res = validate_symbol(symbol)
    clean_symbol = res if ok else None
    if not ok:
        errors.append(res)

    ok, res = validate_side(side)
    clean_side = res if ok else None
    if not ok:
        errors.append(res)

    ok, res = validate_order_type(order_type)
    clean_type = res if ok else None
    if not ok:
        errors.append(res)

    ok, res = validate_quantity(quantity)
    clean_qty = res if ok else None
    if not ok:
        errors.append(res)

    clean_price = None
    clean_stop = None

    # Price required for LIMIT and STOP
    if clean_type in ("LIMIT", "STOP"):
        if not price:
            errors.append("--price is required for LIMIT and STOP orders.")
        else:
            ok, res = validate_price(price, "Price")
            clean_price = res if ok else None
            if not ok:
                errors.append(res)

    # Stop price only for STOP orders
    if clean_type == "STOP":
        if not stop_price:
            errors.append("--stop-price is required for STOP orders.")
        else:
            ok, res = validate_price(stop_price, "Stop price")
            clean_stop = res if ok else None
            if not ok:
                errors.append(res)

        # Basic sanity: for a BUY STOP, stop_price should typically be below price
        if clean_price and clean_stop and clean_side == "BUY":
            if clean_stop >= clean_price:
                errors.append(
                    "For a BUY STOP order, stop_price should be below price. "
                    f"Got stop_price={clean_stop}, price={clean_price}."
                )

    if errors:
        return {"errors": errors}

    return {
        "params": {
            "symbol": clean_symbol,
            "side": clean_side,
            "order_type": clean_type,
            "quantity": clean_qty,
            "price": clean_price,
            "stop_price": clean_stop,
        }
    }
