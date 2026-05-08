"""
orders.py
---------
Business logic for order placement. OrderManager sits between the CLI
and the raw HTTP client — it constructs param dicts, calls the client,
and wraps responses in a structured OrderResult object.

Adding a new order type means adding one method here,
not touching the client or CLI.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient, BinanceClientError
from .logging_config import setup_logger

logger = setup_logger()


# ── Result wrapper ────────────────────────────────────────────────────────────


@dataclass
class OrderResult:
    """
    Carries the outcome of a single order attempt.
    `success` tells you whether to show order details or an error message.
    """
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def summary(self) -> Dict[str, Any]:
        """Extracts the fields we care about for display."""
        if not self.success:
            return {"status": "FAILED", "reason": self.error}

        d = self.data
        stop = d.get("stopPrice", "0")
        result = {
            "orderId":       d.get("orderId"),
            "symbol":        d.get("symbol"),
            "type":          d.get("type"),
            "side":          d.get("side"),
            "status":        d.get("status"),
            "origQty":       d.get("origQty"),
            "executedQty":   d.get("executedQty"),
            "avgPrice":      d.get("avgPrice") or "—",
            "price":         d.get("price") or "—",
            "timeInForce":   d.get("timeInForce", "—"),
            "updateTime":    d.get("updateTime"),
        }
        if stop and stop != "0":
            result["stopPrice"] = stop
        return result


# ── Order Manager ─────────────────────────────────────────────────────────────


class OrderManager:
    """
    High-level order placement API.
    All order types go through `_execute()` which handles the
    try/except and logging in one place.
    """

    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    # ── Public methods ────────────────────────────────────────────────

    def place_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> OrderResult:
        """Place a market order. Executes immediately at best available price."""
        logger.info(
            f"MARKET order | symbol={symbol} side={side} qty={quantity}"
        )
        params = {
            "symbol":   symbol.upper(),
            "side":     side.upper(),
            "type":     "MARKET",
            "quantity": self._fmt(quantity),
        }
        return self._execute(params)

    def place_limit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """Place a limit order at a specific price."""
        logger.info(
            f"LIMIT order | symbol={symbol} side={side} qty={quantity} "
            f"price={price} tif={time_in_force}"
        )
        params = {
            "symbol":      symbol.upper(),
            "side":        side.upper(),
            "type":        "LIMIT",
            "quantity":    self._fmt(quantity),
            "price":       self._fmt(price),
            "timeInForce": time_in_force,
        }
        return self._execute(params)

    def place_stop_limit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_price: float,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """
        Place a stop-limit order.

        When the market hits `stop_price`, a limit order at `price` is placed.
        Useful for cutting losses or entering on breakouts.
        """
        logger.info(
            f"STOP order | symbol={symbol} side={side} qty={quantity} "
            f"price={price} stop={stop_price} tif={time_in_force}"
        )
        params = {
            "symbol":      symbol.upper(),
            "side":        side.upper(),
            "type":        "STOP",
            "quantity":    self._fmt(quantity),
            "price":       self._fmt(price),
            "stopPrice":   self._fmt(stop_price),
            "timeInForce": time_in_force,
        }
        return self._execute(params)

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _fmt(value: float) -> str:
        """
        Binance expects numeric params as strings.
        We strip trailing zeros so 1.50000000 → '1.5'.
        """
        return f"{value:.8f}".rstrip("0").rstrip(".")

    def _execute(self, params: Dict[str, Any]) -> OrderResult:
        """
        Sends the order and wraps the outcome in an OrderResult.
        All exceptions are caught here so callers never need a try/except.
        """
        try:
            logger.debug(f"Order params dispatched: {params}")
            response = self.client.place_order(**params)
            logger.info(
                f"Order accepted | orderId={response.get('orderId')} "
                f"status={response.get('status')} "
                f"executedQty={response.get('executedQty')}"
            )
            return OrderResult(success=True, data=response)

        except BinanceClientError as exc:
            logger.error(f"Order rejected by API: {exc}")
            return OrderResult(success=False, error=str(exc))

        except Exception as exc:
            logger.exception(f"Unexpected error during order placement: {exc}")
            return OrderResult(
                success=False,
                error=f"Unexpected error: {exc}",
            )
