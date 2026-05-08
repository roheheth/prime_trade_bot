#!/usr/bin/env python3
"""
cli.py
------
Entry point for the Binance Futures Testnet trading bot.

Two ways to use it:

    # Direct mode — all flags on one line
    python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

    # Interactive mode — guided step-by-step prompts
    python cli.py interactive

    # Check connectivity
    python cli.py ping
"""

import os
import sys

import click
from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv
from tabulate import tabulate

# Initialise colorama (handles Windows ANSI codes too)
colorama_init(autoreset=True)

# Load .env before importing anything that reads env vars
load_dotenv()

from bot.client import BinanceFuturesClient, BinanceClientError
from bot.logging_config import setup_logger
from bot.orders import OrderManager
from bot.validators import (
    validate_all,
    validate_price,
    validate_quantity,
    validate_symbol,
)

logger = setup_logger()

# ── Branding ──────────────────────────────────────────────────────────────────

BANNER = f"""
{Fore.CYAN}╔══════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot    ║
║   USDT-M Perpetuals  •  Testnet Only     ║
╚══════════════════════════════════════════╝{Style.RESET_ALL}"""

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_client() -> BinanceFuturesClient:
    """Build the client from env vars, exit cleanly if creds are missing."""
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        click.echo(
            f"\n{Fore.RED}✗  API credentials not found.{Style.RESET_ALL}\n"
            "   Set BINANCE_API_KEY and BINANCE_API_SECRET in a .env file\n"
            "   (see .env.example) or export them as environment variables.\n"
        )
        sys.exit(1)

    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


def _print_request_summary(params: dict) -> None:
    rows = [
        ["Symbol",   params["symbol"]],
        ["Side",     params["side"]],
        ["Type",     params["order_type"]],
        ["Quantity", params["quantity"]],
    ]
    if params.get("price"):
        rows.append(["Price", params["price"]])
    if params.get("stop_price"):
        rows.append(["Stop Price", params["stop_price"]])

    click.echo(
        f"\n{Fore.YELLOW}┌─ Order Request "
        + "─" * 30 + f"┐{Style.RESET_ALL}"
    )
    click.echo(tabulate(rows, tablefmt="plain", colalign=("right", "left")))
    click.echo(f"{Fore.YELLOW}└" + "─" * 46 + f"┘{Style.RESET_ALL}")


def _print_order_result(result) -> None:
    if result.success:
        s = result.summary()
        click.echo(f"\n{Fore.GREEN}✓  Order placed successfully!{Style.RESET_ALL}")

        rows = [
            ["Order ID",     s.get("orderId", "—")],
            ["Status",       s.get("status", "—")],
            ["Symbol",       s.get("symbol", "—")],
            ["Side",         s.get("side", "—")],
            ["Type",         s.get("type", "—")],
            ["Orig Qty",     s.get("origQty", "—")],
            ["Executed Qty", s.get("executedQty", "—")],
            ["Avg Price",    s.get("avgPrice", "—")],
            ["Limit Price",  s.get("price", "—")],
            ["Time In Force",s.get("timeInForce", "—")],
        ]
        if s.get("stopPrice"):
            rows.append(["Stop Price", s["stopPrice"]])

        click.echo(
            f"\n{Fore.CYAN}┌─ Order Response "
            + "─" * 29 + f"┐{Style.RESET_ALL}"
        )
        click.echo(tabulate(rows, tablefmt="plain", colalign=("right", "left")))
        click.echo(f"{Fore.CYAN}└" + "─" * 46 + f"┘{Style.RESET_ALL}\n")
    else:
        click.echo(
            f"\n{Fore.RED}✗  Order failed:{Style.RESET_ALL} {result.error}\n"
        )


def _print_dry_run(params: dict, tif: str) -> None:
    """Print what WOULD be sent to Binance without actually sending it."""
    click.echo(
        f"\n{Fore.MAGENTA}{'━' * 48}"
        f"\n  DRY RUN — no order was sent to Binance"
        f"\n{'━' * 48}{Style.RESET_ALL}"
    )

    rows = [
        ["Symbol",       params["symbol"]],
        ["Side",         params["side"]],
        ["Type",         params["order_type"]],
        ["Quantity",     params["quantity"]],
    ]
    if params.get("price"):
        rows.append(["Price", params["price"]])
    if params.get("stop_price"):
        rows.append(["Stop Price", params["stop_price"]])
    if params["order_type"] in ("LIMIT", "STOP"):
        rows.append(["Time In Force", tif])

    rows.append(["Endpoint", "POST /fapi/v1/order"])
    rows.append(["Base URL",  "https://testnet.binancefuture.com"])

    click.echo(
        f"\n{Fore.MAGENTA}┌─ What would be sent "
        + "─" * 25 + f"┐{Style.RESET_ALL}"
    )
    click.echo(tabulate(rows, tablefmt="plain", colalign=("right", "left")))
    click.echo(f"{Fore.MAGENTA}└" + "─" * 46 + f"┘{Style.RESET_ALL}")
    click.echo(
        f"\n{Fore.YELLOW}  ✓  Validation passed — this order would be accepted."
        f"\n  Remove --dry-run to place it for real.{Style.RESET_ALL}\n"
    )
    logger.info(
        f"DRY RUN | symbol={params['symbol']} side={params['side']} "
        f"type={params['order_type']} qty={params['quantity']} "
        f"price={params.get('price')} stop={params.get('stop_price')} tif={tif}"
    )


def _run_order(params: dict, tif: str) -> "OrderResult":
    """Dispatch to the correct OrderManager method based on order_type."""
    client = _make_client()
    manager = OrderManager(client)
    ot = params["order_type"]

    if ot == "MARKET":
        return manager.place_market(
            symbol=params["symbol"],
            side=params["side"],
            quantity=params["quantity"],
        )
    elif ot == "LIMIT":
        return manager.place_limit(
            symbol=params["symbol"],
            side=params["side"],
            quantity=params["quantity"],
            price=params["price"],
            time_in_force=tif,
        )
    elif ot == "STOP":
        return manager.place_stop_limit(
            symbol=params["symbol"],
            side=params["side"],
            quantity=params["quantity"],
            price=params["price"],
            stop_price=params["stop_price"],
            time_in_force=tif,
        )


# ── CLI group ─────────────────────────────────────────────────────────────────


@click.group()
@click.version_option("1.0.0", prog_name="trading-bot")
def cli():
    """
    \b
    Binance Futures Testnet Trading Bot
    ------------------------------------
    Place MARKET, LIMIT, and STOP orders on the USDT-M testnet.

    \b
    Quick start:
      python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01
      python cli.py interactive
      python cli.py ping
    """


# ── `place` command ───────────────────────────────────────────────────────────


@cli.command("place")
@click.option("--symbol",     "-s",  required=True,  help="Trading pair, e.g. BTCUSDT")
@click.option("--side",       "-d",  required=True,
              type=click.Choice(["BUY", "SELL"], case_sensitive=False),
              help="Order direction: BUY or SELL")
@click.option("--type",       "-t",  "order_type", required=True,
              type=click.Choice(["MARKET", "LIMIT", "STOP"], case_sensitive=False),
              help="Order type")
@click.option("--qty",        "-q",  required=True,  help="Quantity to trade")
@click.option("--price",      "-p",  default=None,   help="Limit / stop-limit price (required for LIMIT and STOP)")
@click.option("--stop-price", "-sp", default=None,   help="Stop trigger price (required for STOP orders)")
@click.option("--tif",              default="GTC",
              type=click.Choice(["GTC", "IOC", "FOK"], case_sensitive=False),
              show_default=True, help="Time-in-force for LIMIT/STOP orders")
@click.option("--yes",        "-y",  is_flag=True,   help="Skip the confirmation prompt")
@click.option("--dry-run",    "-n",  is_flag=True,   help="Validate and preview the order without sending it to Binance")
def place_order(symbol, side, order_type, qty, price, stop_price, tif, yes, dry_run):
    """
    Place a futures order with all parameters supplied as flags.

    \b
    Examples:
      python cli.py place -s BTCUSDT -d BUY   -t MARKET -q 0.001
      python cli.py place -s ETHUSDT -d SELL  -t LIMIT  -q 0.1  -p 3200
      python cli.py place -s BTCUSDT -d SELL  -t STOP   -q 0.01 -p 59000 -sp 60000
      python cli.py place -s BTCUSDT -d BUY   -t MARKET -q 0.001 --dry-run
    """
    click.echo(BANNER)
    logger.info(
        f"CLI place command | symbol={symbol} side={side} "
        f"type={order_type} qty={qty} price={price} stop_price={stop_price} "
        f"dry_run={dry_run}"
    )

    # Validate
    result = validate_all(symbol, side, order_type, qty, price, stop_price)
    if "errors" in result:
        click.echo(f"\n{Fore.RED}✗  Input validation failed:{Style.RESET_ALL}")
        for err in result["errors"]:
            click.echo(f"   • {err}")
        click.echo()
        sys.exit(1)

    params = result["params"]
    _print_request_summary(params)

    # ── Dry run: stop here, don't touch the API ───────────────────────
    if dry_run:
        _print_dry_run(params, tif.upper())
        sys.exit(0)

    # Confirm (skip with --yes)
    if not yes:
        if not click.confirm(
            f"\n{Fore.YELLOW}Proceed with this order?{Style.RESET_ALL}",
            default=True,
        ):
            click.echo("Cancelled.\n")
            sys.exit(0)

    order_result = _run_order(params, tif.upper())
    _print_order_result(order_result)
    sys.exit(0 if order_result.success else 1)


# ── `interactive` command ─────────────────────────────────────────────────────


@cli.command("interactive")
def interactive_mode():
    """
    Guided, step-by-step order placement — no flags needed.

    Great for getting familiar with the bot or placing one-off orders
    without memorising all the flag names.
    """
    click.echo(BANNER)
    click.echo(
        f"\n{Fore.CYAN}Interactive Mode — follow the prompts below."
        f"\nPress Ctrl+C at any time to cancel.{Style.RESET_ALL}\n"
    )

    try:
        # ── Symbol ──────────────────────────────────────────────────
        while True:
            raw = click.prompt("  Symbol (e.g. BTCUSDT)").strip()
            ok, res = validate_symbol(raw)
            if ok:
                symbol = res
                break
            click.echo(f"  {Fore.RED}✗ {res}{Style.RESET_ALL}")

        # ── Side ─────────────────────────────────────────────────────
        side = click.prompt(
            "  Side",
            type=click.Choice(["BUY", "SELL"], case_sensitive=False),
        ).upper()

        # ── Order type ───────────────────────────────────────────────
        click.echo(
            f"\n  Order types available:\n"
            f"    {Fore.WHITE}[1]{Style.RESET_ALL} MARKET  — fill immediately at market price\n"
            f"    {Fore.WHITE}[2]{Style.RESET_ALL} LIMIT   — fill at your specified price\n"
            f"    {Fore.WHITE}[3]{Style.RESET_ALL} STOP    — stop-limit (trigger + limit price)\n"
        )
        type_choice = click.prompt(
            "  Choose type",
            type=click.Choice(["1", "2", "3", "MARKET", "LIMIT", "STOP"], case_sensitive=False),
        )
        order_type = {"1": "MARKET", "2": "LIMIT", "3": "STOP"}.get(
            type_choice, type_choice.upper()
        )

        # ── Quantity ─────────────────────────────────────────────────
        while True:
            raw = click.prompt("  Quantity")
            ok, res = validate_quantity(raw)
            if ok:
                quantity = res
                break
            click.echo(f"  {Fore.RED}✗ {res}{Style.RESET_ALL}")

        price = None
        stop_price = None
        tif = "GTC"

        # ── Price (LIMIT / STOP) ─────────────────────────────────────
        if order_type in ("LIMIT", "STOP"):
            click.echo()
            while True:
                raw = click.prompt("  Limit Price")
                ok, res = validate_price(raw)
                if ok:
                    price = res
                    break
                click.echo(f"  {Fore.RED}✗ {res}{Style.RESET_ALL}")

        # ── Stop price (STOP only) ───────────────────────────────────
        if order_type == "STOP":
            click.echo(
                f"  {Fore.YELLOW}Tip:{Style.RESET_ALL} Stop price is the trigger. "
                "Once hit, a limit order at your price is placed."
            )
            while True:
                raw = click.prompt("  Stop Trigger Price")
                ok, res = validate_price(raw, "Stop price")
                if ok:
                    stop_price = res
                    break
                click.echo(f"  {Fore.RED}✗ {res}{Style.RESET_ALL}")

        # ── Time in force ────────────────────────────────────────────
        if order_type in ("LIMIT", "STOP"):
            click.echo(
                f"\n  Time-in-Force options:\n"
                f"    {Fore.WHITE}GTC{Style.RESET_ALL} — Good Till Cancel (stays open until filled or cancelled)\n"
                f"    {Fore.WHITE}IOC{Style.RESET_ALL} — Immediate or Cancel (fill what you can, cancel the rest)\n"
                f"    {Fore.WHITE}FOK{Style.RESET_ALL} — Fill or Kill (fill entirely or don't fill at all)\n"
            )
            tif = click.prompt(
                "  Time-in-Force",
                type=click.Choice(["GTC", "IOC", "FOK"], case_sensitive=False),
                default="GTC",
                show_default=True,
            ).upper()

        # ── Summary + confirm ────────────────────────────────────────
        params = {
            "symbol":     symbol,
            "side":       side,
            "order_type": order_type,
            "quantity":   quantity,
            "price":      price,
            "stop_price": stop_price,
        }
        _print_request_summary(params)

        # ── Dry-run option ───────────────────────────────────────────
        click.echo(
            f"\n  {Fore.MAGENTA}Tip:{Style.RESET_ALL} Use dry-run to preview "
            "without sending to Binance."
        )
        run_mode = click.prompt(
            "  How would you like to proceed?",
            type=click.Choice(["place", "dry-run", "cancel"], case_sensitive=False),
            default="place",
            show_default=True,
        ).lower()

        if run_mode == "cancel":
            click.echo("Cancelled.\n")
            return
        elif run_mode == "dry-run":
            _print_dry_run(params, tif)
            return

        result = _run_order(params, tif)
        _print_order_result(result)

    except (KeyboardInterrupt, click.Abort):
        click.echo(f"\n\n{Fore.YELLOW}Cancelled — no order was placed.{Style.RESET_ALL}\n")


# ── `ping` command ────────────────────────────────────────────────────────────


@cli.command("ping")
def ping():
    """Check connectivity to the Binance Futures Testnet."""
    client = _make_client()
    if client.ping():
        click.echo(
            f"{Fore.GREEN}✓  Connected to Binance Futures Testnet{Style.RESET_ALL}"
        )
    else:
        click.echo(
            f"{Fore.RED}✗  Could not reach Binance Futures Testnet. "
            f"Check your network.{Style.RESET_ALL}"
        )


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
