# Mock T-Bank API Server

FastAPI-based mock server that simulates the [T-Bank (Т-Банк) OpenAPI REST backend](https://www.tbank.ru/business/).
Designed to be a drop-in replacement for development and testing — the real
[`tbank-mcp`](https://opencode.ai) MCP server connects to it without any code changes.

## Quick Start

```bash
pip install -r requirements.txt
python mock_tbank_api.py
```

```text
🚀 Mock T-Bank API running on http://127.0.0.1:8099
🔑 Accepted token: mock-token-any-value
📂 Data loaded from: C:\...\mock-tbank-api\data\
```

Configure your real `tbank-mcp`:

```env
TBANK_ENVIRONMENT=mock
TBANK_BASE_URL=http://127.0.0.1:8099
TBANK_TOKEN=mock-token-any-value
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  AI Agent / MCP Client                              │
│  (opencode, Claude, etc.)                           │
└──────────────┬──────────────────────────────────────┘
               │ tools (get_company_info, create_payment, …)
               ▼
┌─────────────────────────────────────────────────────┐
│  tbank-mcp (real) — stdio MCP server                │
│  src/tbank_mcp/                                     │
│  Reads TBANK_BASE_URL + TBANK_TOKEN from env        │
└──────────────┬──────────────────────────────────────┘
               │ HTTP REST (Bearer auth)
               ▼
┌─────────────────────────────────────────────────────┐
│  Mock T-Bank API  ←  YOU ARE HERE                   │
│  mock_tbank_api.py  (FastAPI on 127.0.0.1:8099)     │
│  Data loaded from data/*.json                        │
└─────────────────────────────────────────────────────┘
```

**Key insight:** The real `tbank-mcp` already supports `TBANK_BASE_URL` override
in its `config.py`. No source changes needed — just point it at the mock.

## Endpoints

### Company
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/company` | Legal entity details (name, INN, KPP, OGRN, tax scheme) |
| GET | `/api/v1/company/requisites` | Bank accounts, BIC, correspondent account |

### Accounts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/accounts` | All accounts with balances |
| GET | `/api/v1/accounts/{id}/balance` | Single account balance |
| GET | `/api/v1/accounts/{id}/statement` | Transactions for a period (`?from=&to=`) |

### Payments
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/payments` | Create and execute a payment |
| POST | `/api/v1/payments/draft` | Create a draft payment |
| GET | `/api/v1/payments` | List payments (`?status=&accountId=`) |
| POST | `/api/v1/payments/sbp` | Create SBP (Faster Payments) transfer |

### Invoices
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/invoices` | Create an invoice |
| GET | `/api/v1/invoices` | List invoices (`?status=`) |

### Salary
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/salary/payments` | Execute salary payment |
| POST | `/api/v1/salary/cards` | Issue a salary card |

### Self-Employed (Самозанятые)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/self-employed` | Register a self-employed individual |
| POST | `/api/v1/self-employed/payments` | Pay a self-employed individual |

### Business Cards
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/cards` | List business cards (`?accountId=`) |
| POST | `/api/v1/cards/{id}/limits` | Update card spending limits |

### Acquiring
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/acquiring/operations` | List acquiring operations (`?status=&terminalId=`) |
| GET | `/api/v1/acquiring/operations/{id}` | Single operation detail |

### SBP Links (Payment Links)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/sbp-links` | Create a B2B payment link via SBP |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth required) |

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `MOCK_HOST` | `127.0.0.1` | Listen address |
| `MOCK_PORT` | `8099` | Listen port |
| `MOCK_TOKEN` | `mock-token-any-value` | Bearer token the mock accepts |

Copy `.env.example` to `.env` to override:

```bash
cp .env.example .env
# then edit .env
```

## Data Files (`data/`)

| File | Content |
|------|---------|
| `empresa.json` | Company details (legal name, INN, addresses, bank info, tax scheme) |
| `cuentas-bancarias.json` | 4 bank accounts (RUB main, RUB reserve, USD savings, investment) |
| `clientes.json` | 3 clients with contact info |
| `proveedores.json` | 4 suppliers (hosting, cloud, CDN, freelance) |
| `plan-de-cuentas.json` | Chart of accounts (accounting categories) |
| `escenarios-prueba.json` | Test scenarios for various business flows |

The mock pre-seeds 3 months of operational history:
- 9 invoices (paid, overdue, issued)
- 19 payments (completed, processing, draft)
- 8 acquiring operations (completed, refunded)
- 3 salary payments
- 2 self-employed individuals with 3 payments
- 4 business cards (active, blocked)
- 2 SBP payment links

## Pre-populated State (3 months)

### Invoices (9)
- inv-001/002/003: ООО «ТехноПартнер» — 150,000 RUB each (paid, monthly)
- inv-004/005/006: ИП Смирнов А.В. — 25,000 RUB each (paid, monthly)
- inv-007: АО «Цифровые Решения» — 1,200,000 RUB (overdue)
- inv-008/009: issued (recent)

### Payments (19)
- pay-001/002/003: Хостинг-Провайдер — 45,000 (monthly)
- pay-004/005/006: Cloudflare CDN — 18,000 (monthly)
- pay-007/008/009: Vercel — 15,000 (monthly)
- pay-010/011/012: ИП Кузнецов Д.М. — 240k/180k/210k (development)
- pay-013/014/015: Яндекс.Облако — 85k/92k/78k (monthly)
- pay-016: Хостинг (processing)
- pay-017: Кузнецов draft
- pay-018/019: Taxes (reserve account)

### Acquiring (8)
- TERM-001: 6 completed (150k + 25k monthly), 1 refunded (12k)
- TERM-002: 1 completed (500k large deal)

### Accounts
| ID | Type | Balance | Currency |
|----|------|---------|----------|
| account-rub-main | settlement | 1,500,000 | RUB |
| account-rub-reserve | settlement | 500,000 | RUB |
| account-usd-savings | savings | 25,000 | USD |
| account-investment | investment | 300,000 | RUB |

## Development

### With the real tbank-mcp

1. Start mock: `python mock_tbank_api.py`
2. Start MCP: `python -m tbank_mcp` (with `.env` configured)
3. Run E2E tests: `python tests/test_e2e.py`

### Manual testing with curl

```bash
# Health
curl http://127.0.0.1:8099/health

# Company info
curl -H "Authorization: Bearer mock-token-any-value" http://127.0.0.1:8099/api/v1/company

# List accounts
curl -H "Authorization: Bearer mock-token-any-value" http://127.0.0.1:8099/api/v1/accounts

# Create invoice
curl -X POST http://127.0.0.1:8099/api/v1/invoices \
  -H "Authorization: Bearer mock-token-any-value" \
  -H "Content-Type: application/json" \
  -d '{"counterpartyName":"Test Client","counterpartyInn":"7709123456","items":[{"name":"Service","quantity":1,"unitPrice":100000}]}'
```

### Resetting state

Stop and restart the server. All in-memory state is lost and re-seeded from
`data/*.json` on each start.

## Switching to Production

Only the `.env` changes:

```env
TBANK_ENVIRONMENT=production
TBANK_BASE_URL=https://secured-openapi.tbank.ru
TBANK_TOKEN=<your_real_token>
```

No code changes. No configuration changes to the MCP server.

## AI Agent Instructions

This section is written for AI coding agents (opencode, Claude, Cursor, etc.)
that may be asked to work with or deploy this mock server.

### Context

- This mock simulates the T-Bank OpenAPI, which is the HTTP REST backend used
  by the `tbank-mcp` MCP server.
- All 20+ endpoints from the real API are implemented.
- The mock maintains state in memory and pre-seeds 3 months of history.
- Auth: Bearer token (default `mock-token-any-value`).

### Integration with tbank-mcp

The real tbank-mcp lives at `C:\Users\m1911770\AppData\Local\Temp\opencode\tbank-mcp\`
and reads `TBANK_BASE_URL` from its `.env`. No source changes needed.

```python
os.environ["TBANK_ENVIRONMENT"] = "mock"
os.environ["TBANK_BASE_URL"] = "http://127.0.0.1:8099"
os.environ["TBANK_TOKEN"] = "mock-token-any-value"
```

### Response format

The real tbank-mcp handlers use `str(dict)` to return results, which produces
Python repr (single quotes, `None`, `True/False`) instead of JSON. When
writing tests, parse responses with `ast.literal_eval()`:

```python
import ast
data = ast.literal_eval(response.content[0].text)
```

### Available tools (from tbank-mcp)

Once connected to the mock, the following MCP tools are available and fully
functional:

- `get_company_info`, `get_company_requisites`
- `list_accounts`, `get_account_balance`, `get_account_statement`
- `create_payment`, `create_payment_draft`, `list_payments`
- `create_sbp_payment`
- `create_invoice`, `list_invoices`
- `create_salary_payment`, `issue_salary_card`
- `add_self_employed`, `pay_self_employed`
- `list_business_cards`, `set_card_limit`
- `list_acquiring_operations`, `get_acquiring_operation_detail`
- `create_sbp_invoice_link`

### Testing

```bash
# 1. Start mock (background)
python mock_tbank_api.py &

# 2. Run E2E test suite (connects via real tbank-mcp)
python tests/test_e2e.py
```

The E2E test (`tests/test_e2e.py`) validates 9 scenarios:
1. Company info returned correctly
2. 4 bank accounts listed with balances
3. Account balance endpoint works
4. 9 pre-seeded invoices
5. 19 pre-seeded payments
6. Creating a new invoice
7. Creating and executing a payment
8. 8 acquiring operations
9. 4 business cards

### Important notes

- The mock API and the built-in `tbank_*` tools in this agent are **different**.
  The built-in tools call the real T-Bank sandbox. The mock is a separate HTTP
  server that the real tbank-mcp connects to.
- Query parameter `from` is a Python reserved word. FastAPI endpoints use
  `from_: str = Query("", alias="from")`.
- The mock accepts MOCK_TOKEN from env. If not set, defaults to
  `mock-token-any-value`.
- Health endpoint (`/health`) does not require auth. All other endpoints
  return 401 if token is missing or wrong.

## License

MIT
