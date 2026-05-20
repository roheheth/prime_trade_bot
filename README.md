# Binance Futures Testnet Trading Bot

A clean Python CLI application for placing orders on the **Binance USDT-M Futures Testnet**. Supports MARKET, LIMIT, and STOP orders with structured logging, full input validation, and two usage modes: direct flag-based commands and an interactive guided flow.

---

## Features

- **Order types**: MARKET, LIMIT, STOP (stop-limit)
- **Sides**: BUY and SELL
- **Two CLI modes**: one-liner flags (`place`) or guided prompts (`interactive`)
- **Input validation** with clear, specific error messages before any API call is made
- **Rotating log files**: every request, response, and error is logged to `logs/`
- **Clean terminal output** using colour-coded tables — log noise stays in the file
- **Graceful error handling**: API errors, network failures, invalid input — all caught and reported clearly

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (HMAC signing, request dispatch)
│   ├── orders.py          # Order placement logic (MARKET / LIMIT / STOP)
│   ├── validators.py      # Input validation — pure functions, no side-effects
│   └── logging_config.py  # Dual-channel logging (file + console)
├── cli.py                 # CLI entry point (Click)
├── logs/
│   └── bot_YYYYMMDD.log   # Rotating log file (auto-created)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet Credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (or register a testnet account)
3. Navigate to **Account → API Management**
4. Generate a new API key and copy both the key and secret

### 2. Clone / Download the project

```bash
git clone <your-repo-url>
cd trading_bot
```

### 3. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

```env
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

---

## How to Run

### Check connectivity first

```bash
python cli.py ping
```

```
✓  Connected to Binance Futures Testnet
```

---

### Place a MARKET order

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.001
```

**Output:**

```
╔══════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot    ║
║   USDT-M Perpetuals  •  Testnet Only     ║
╚══════════════════════════════════════════╝

┌─ Order Request ──────────────────────────────┐
    Symbol   BTCUSDT
      Side   BUY
      Type   MARKET
  Quantity   0.001
└──────────────────────────────────────────────┘

Proceed with this order? [Y/n]: Y

✓  Order placed successfully!

┌─ Order Response ─────────────────────────────┐
      Order ID   4723419812
        Status   FILLED
        Symbol   BTCUSDT
          Side   BUY
          Type   MARKET
      Orig Qty   0.001
  Executed Qty   0.001
     Avg Price   57842.30
   Limit Price   —
  Time In Force  GTC
└──────────────────────────────────────────────┘
```

---

### Place a LIMIT order

```bash
python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.05 --price 3150
```

Skip the confirmation prompt with `--yes` (useful for scripting):

```bash
python cli.py place -s ETHUSDT -d SELL -t LIMIT -q 0.05 -p 3150 --yes
```

---

### Place a STOP (stop-limit) order

```bash
python cli.py place \
  --symbol BTCUSDT \
  --side SELL \
  --type STOP \
  --qty 0.001 \
  --price 55000 \
  --stop-price 57000
```

When the market hits `--stop-price`, a limit order at `--price` is automatically placed.

---

### Set time-in-force (LIMIT / STOP only)

```bash
# GTC = Good Till Cancel (default)
# IOC = Immediate or Cancel
# FOK = Fill or Kill

python cli.py place -s BTCUSDT -d BUY -t LIMIT -q 0.001 -p 56000 --tif IOC
```

---

### Interactive mode (guided prompts)

No flags required — the bot walks you through each field with explanations:

```bash
python cli.py interactive
```

```
  Symbol (e.g. BTCUSDT): BTCUSDT
  Side (BUY, SELL): BUY

  Order types available:
    [1] MARKET  — fill immediately at market price
    [2] LIMIT   — fill at your specified price
    [3] STOP    — stop-limit (trigger + limit price)

  Choose type: 1
  Quantity: 0.001
  ...
```

---

### Short flag aliases

| Long flag        | Short |
|------------------|-------|
| `--symbol`       | `-s`  |
| `--side`         | `-d`  |
| `--type`         | `-t`  |
| `--qty`          | `-q`  |
| `--price`        | `-p`  |
| `--stop-price`   | `-sp` |

---

## Logging

Logs are written to `logs/bot_YYYYMMDD.log` and rotate at 5 MB (up to 5 backups kept).

**What gets logged:**

- Every outbound HTTP request (URL + params, with signature redacted)
- Every inbound response (status code + body)
- Order acceptance/rejection with order ID and status
- All exceptions with full tracebacks

**Console output is minimal** — only `WARNING` and above appear in the terminal, so the CLI stays readable. Verbose `DEBUG` output lives only in the file.

Sample log lines:

```
2025-07-14 11:02:14 | INFO     | client              :57   | BinanceFuturesClient ready | base_url=https://testnet.binancefuture.com
2025-07-14 11:02:14 | INFO     | orders              :72   | MARKET order | symbol=BTCUSDT side=BUY qty=0.001
2025-07-14 11:02:14 | DEBUG    | client              :99   | POST https://testnet.binancefuture.com/fapi/v1/order | params={..., 'signature': '***'}
2025-07-14 11:02:15 | INFO     | orders              :117  | Order accepted | orderId=4723419812 status=FILLED executedQty=0.001
```

---

## Validation Examples

The bot validates all inputs before touching the API:

```bash
# Missing price for LIMIT order
python cli.py place -s BTCUSDT -d BUY -t LIMIT -q 0.001
# ✗  Input validation failed:
#    • --price is required for LIMIT and STOP orders.

# Invalid side
python cli.py place -s BTCUSDT -d HODL -t MARKET -q 0.001
# ✗  Input validation failed:
#    • Invalid side 'HODL'. Must be one of: BUY, SELL.

# Negative quantity
python cli.py place -s BTCUSDT -d BUY -t MARKET -q -5
# ✗  Input validation failed:
#    • Quantity must be greater than zero.
```

---

## Assumptions

- **Testnet only.** The base URL is hardcoded to `https://testnet.binancefuture.com`. Switching to mainnet would require changing the `TESTNET_BASE_URL` constant in `bot/client.py` — no other changes needed.
- **USDT-M perpetuals.** The bot targets the USDT-M (linear) futures market. Coin-M (COIN-M) contracts use a different base URL and are not supported.
- **No position sizing.** Quantity is passed as-is. Binance enforces minimum notional and lot size rules per symbol — if an order is rejected for that reason, the API error message will explain it.
- **Server time.** Timestamps use the local machine clock. If your system clock is significantly out of sync, requests may be rejected. NTP sync is assumed.
- **Testnet credentials only.** API keys from `testnet.binancefuture.com` are separate from mainnet credentials.

---

## Dependencies

| Package        | Purpose                            |
|----------------|------------------------------------|
| `requests`     | HTTP client for Binance REST API   |
| `click`        | CLI framework (commands, prompts)  |
| `python-dotenv`| Load credentials from `.env`       |
| `tabulate`     | Format order tables in terminal    |
| `colorama`     | Cross-platform ANSI colours        |

---

## Help

```bash
python cli.py --help
python cli.py place --help
python cli.py interactive --help
```
