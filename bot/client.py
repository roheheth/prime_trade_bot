"""
client.py
---------
Low-level wrapper around the Binance Futures Testnet REST API.
Handles auth (HMAC-SHA256 signing), request dispatch, and
error normalisation. Nothing business-logic lives here.
"""

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import setup_logger

logger = setup_logger()

TESTNET_BASE_URL = "https://testnet.binancefuture.com"


class BinanceClientError(Exception):
    """Raised for API-level or network-level failures."""


class BinanceFuturesClient:
    """
    Thin HTTP client for Binance USDT-M Futures (testnet by default).

    Responsibilities:
    - Sign requests with HMAC-SHA256
    - Attach API key header
    - Normalise HTTP/JSON errors into BinanceClientError
    - Log every outbound request and inbound response
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = 10,
    ):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self.api_key = api_key
        self._api_secret = api_secret  # prefixed underscore — treat as private
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self.api_key})

        logger.info(
            f"BinanceFuturesClient ready | base_url={self.base_url}"
        )

    # ── Signing ───────────────────────────────────────────────────────

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        """HMAC-SHA256 over the URL-encoded param string."""
        payload = urlencode(params)
        return hmac.new(
            self._api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    # ── HTTP helpers ──────────────────────────────────────────────────

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False,
    ) -> Dict:
        params = dict(params or {})
        if signed:
            params["timestamp"] = self._timestamp()
            params["signature"] = self._sign(params)

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"GET {url} | params={self._redact(params)}")

        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise BinanceClientError(
                "Request timed out — Binance Testnet may be slow, try again."
            )
        except requests.exceptions.ConnectionError as exc:
            raise BinanceClientError(f"Network error: {exc}")

        return self._parse(resp)

    def _post(
        self,
        endpoint: str,
        params: Dict[str, Any],
        signed: bool = True,
    ) -> Dict:
        params = dict(params)
        if signed:
            params["timestamp"] = self._timestamp()
            params["signature"] = self._sign(params)

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"POST {url} | params={self._redact(params)}")

        try:
            # Binance futures expects params in the query string for POST too
            resp = self._session.post(url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise BinanceClientError("Request timed out.")
        except requests.exceptions.ConnectionError as exc:
            raise BinanceClientError(f"Network error: {exc}")

        return self._parse(resp)

    def _parse(self, resp: requests.Response) -> Dict:
        """Deserialise response; raise BinanceClientError on non-200."""
        logger.debug(
            f"Response | status={resp.status_code} | body={resp.text[:600]}"
        )

        try:
            data = resp.json()
        except Exception:
            raise BinanceClientError(
                f"Non-JSON response (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        if resp.status_code != 200:
            code = data.get("code", "?")
            msg = data.get("msg", "unknown error")
            logger.error(f"API error | code={code} | msg={msg}")
            raise BinanceClientError(f"Binance API error {code}: {msg}")

        return data

    @staticmethod
    def _redact(params: Dict) -> Dict:
        """Hide the signature field in log output."""
        return {k: ("***" if k == "signature" else v) for k, v in params.items()}

    # ── Public API methods ────────────────────────────────────────────

    def ping(self) -> bool:
        """Returns True if the testnet is reachable."""
        try:
            self._get("/fapi/v1/ping")
            return True
        except BinanceClientError:
            return False

    def place_order(self, **kwargs) -> Dict:
        """POST /fapi/v1/order — pass order params as keyword arguments."""
        logger.info(f"Dispatching order | {kwargs}")
        return self._post("/fapi/v1/order", params=kwargs)

    def get_account(self) -> Dict:
        return self._get("/fapi/v2/account", signed=True)

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict:
        params = {"symbol": symbol} if symbol else {}
        return self._get("/fapi/v1/exchangeInfo", params=params)
