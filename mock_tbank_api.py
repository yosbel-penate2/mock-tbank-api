"""Mock T-Bank OpenAPI HTTP Server.

Simulates the real T-Bank secured OpenAPI REST backend so the real
tbank-mcp MCP server can connect to it as if it were production/sandbox.

Usage:
    python mock-tbank-api.py

The real tbank-mcp can then be configured with:
    TBANK_BASE_URL=http://localhost:8099
    TBANK_TOKEN=mock-token-any-value

This works because config.py already supports TBANK_BASE_URL override.
"""
from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

HERE = Path(__file__).resolve().parent / "data"
HOST = os.getenv("MOCK_HOST", "127.0.0.1")
PORT = int(os.getenv("MOCK_PORT", "8099"))
ACCEPTED_TOKEN = os.getenv("MOCK_TOKEN", "mock-token-any-value")

# ---------------------------------------------------------------------------
# Load config data
# ---------------------------------------------------------------------------

def _load(name: str) -> dict[str, Any]:
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

COMPANY = _load("empresa.json")
ACCOUNTS = _load("cuentas-bancarias.json").get("cuentas", [])

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

_invoices: list[dict[str, Any]] = []
_payments: list[dict[str, Any]] = []
_sbp_links: list[dict[str, Any]] = []
_self_employed: list[dict[str, Any]] = []
_self_employed_payments: list[dict[str, Any]] = []
_employees: list[dict[str, Any]] = []
_cards: list[dict[str, Any]] = []
_acquiring_ops: list[dict[str, Any]] = []
_salary_payments: list[dict[str, Any]] = []

_now = datetime.now(timezone.utc)


def _seed_data():
    global _invoices, _payments, _sbp_links, _self_employed, _employees
    global _cards, _acquiring_ops, _salary_payments, _self_employed_payments

    _invoices = [
        {"id": "inv-001", "number": "СЧ-2024/001", "counterpartyName": "ООО «ТехноПартнер»", "counterpartyInn": "7709123456", "amount": 150000.00, "status": "paid", "createdAt": "2026-03-01T10:00:00Z", "paidAt": "2026-03-02T14:30:00Z"},
        {"id": "inv-002", "number": "СЧ-2024/002", "counterpartyName": "ООО «ТехноПартнер»", "counterpartyInn": "7709123456", "amount": 150000.00, "status": "paid", "createdAt": "2026-04-01T09:00:00Z", "paidAt": "2026-04-02T11:00:00Z"},
        {"id": "inv-003", "number": "СЧ-2024/003", "counterpartyName": "ООО «ТехноПартнер»", "counterpartyInn": "7709123456", "amount": 150000.00, "status": "paid", "createdAt": "2026-05-01T10:00:00Z", "paidAt": "2026-05-02T14:30:00Z"},
        {"id": "inv-004", "number": "СЧ-2024/004", "counterpartyName": "ИП Смирнов А.В.", "counterpartyInn": "772812345678", "amount": 25000.00, "status": "paid", "createdAt": "2026-03-15T12:00:00Z", "paidAt": "2026-03-16T09:00:00Z"},
        {"id": "inv-005", "number": "СЧ-2024/005", "counterpartyName": "ИП Смирнов А.В.", "counterpartyInn": "772812345678", "amount": 25000.00, "status": "paid", "createdAt": "2026-04-15T12:00:00Z", "paidAt": "2026-04-16T09:00:00Z"},
        {"id": "inv-006", "number": "СЧ-2024/006", "counterpartyName": "ИП Смирнов А.В.", "counterpartyInn": "772812345678", "amount": 25000.00, "status": "paid", "createdAt": "2026-05-15T12:00:00Z", "paidAt": "2026-05-16T09:00:00Z"},
        {"id": "inv-007", "number": "СЧ-2024/007", "counterpartyName": "АО «Цифровые Решения»", "counterpartyInn": "7715987654", "amount": 1200000.00, "status": "overdue", "createdAt": "2026-05-01T08:00:00Z"},
        {"id": "inv-008", "number": "СЧ-2024/008", "counterpartyName": "ООО «ТехноПартнер»", "counterpartyInn": "7709123456", "amount": 150000.00, "status": "issued", "createdAt": "2026-06-01T10:00:00Z"},
        {"id": "inv-009", "number": "СЧ-2024/009", "counterpartyName": "ИП Смирнов А.В.", "counterpartyInn": "772812345678", "amount": 25000.00, "status": "issued", "createdAt": "2026-06-07T09:00:00Z"},
    ]
    _payments = [
        {"id": "pay-001", "number": "ПП-2024/001", "accountId": "account-rub-main", "beneficiaryName": "ООО «Хостинг-Провайдер»", "beneficiaryInn": "7734123456", "amount": 45000.00, "status": "completed", "purpose": "Оплата хостинга за март 2026", "createdAt": "2026-03-05T11:00:00Z"},
        {"id": "pay-002", "number": "ПП-2024/002", "accountId": "account-rub-main", "beneficiaryName": "ООО «Хостинг-Провайдер»", "beneficiaryInn": "7734123456", "amount": 45000.00, "status": "completed", "purpose": "Оплата хостинга за апрель 2026", "createdAt": "2026-04-05T11:00:00Z"},
        {"id": "pay-003", "number": "ПП-2024/003", "accountId": "account-rub-main", "beneficiaryName": "ООО «Хостинг-Провайдер»", "beneficiaryInn": "7734123456", "amount": 45000.00, "status": "completed", "purpose": "Оплата хостинга за май 2026", "createdAt": "2026-05-05T11:00:00Z"},
        {"id": "pay-004", "number": "ПП-2024/004", "accountId": "account-rub-main", "beneficiaryName": "Cloudflare Inc.", "beneficiaryInn": "9909098765", "amount": 18000.00, "status": "completed", "purpose": "Оплата CDN за март 2026", "createdAt": "2026-03-10T12:00:00Z"},
        {"id": "pay-005", "number": "ПП-2024/005", "accountId": "account-rub-main", "beneficiaryName": "Cloudflare Inc.", "beneficiaryInn": "9909098765", "amount": 18000.00, "status": "completed", "purpose": "Оплата CDN за апрель 2026", "createdAt": "2026-04-10T12:00:00Z"},
        {"id": "pay-006", "number": "ПП-2024/006", "accountId": "account-rub-main", "beneficiaryName": "Cloudflare Inc.", "beneficiaryInn": "9909098765", "amount": 18000.00, "status": "completed", "purpose": "Оплата CDN за май 2026", "createdAt": "2026-05-10T12:00:00Z"},
        {"id": "pay-007", "number": "ПП-2024/007", "accountId": "account-rub-main", "beneficiaryName": "Vercel Inc.", "beneficiaryInn": "9912345678", "amount": 15000.00, "status": "completed", "purpose": "Оплата хостинга Vercel за март 2026", "createdAt": "2026-03-08T09:00:00Z"},
        {"id": "pay-008", "number": "ПП-2024/008", "accountId": "account-rub-main", "beneficiaryName": "Vercel Inc.", "beneficiaryInn": "9912345678", "amount": 15000.00, "status": "completed", "purpose": "Оплата хостинга Vercel за апрель 2026", "createdAt": "2026-04-08T09:00:00Z"},
        {"id": "pay-009", "number": "ПП-2024/009", "accountId": "account-rub-main", "beneficiaryName": "Vercel Inc.", "beneficiaryInn": "9912345678", "amount": 15000.00, "status": "completed", "purpose": "Оплата хостинга Vercel за май 2026", "createdAt": "2026-05-08T09:00:00Z"},
        {"id": "pay-010", "number": "ПП-2024/010", "accountId": "account-rub-main", "beneficiaryName": "ИП Кузнецов Д.М.", "beneficiaryInn": "771523456789", "amount": 240000.00, "status": "completed", "purpose": "Разработка модуля аутентификации", "createdAt": "2026-03-20T15:00:00Z"},
        {"id": "pay-011", "number": "ПП-2024/011", "accountId": "account-rub-main", "beneficiaryName": "ИП Кузнецов Д.М.", "beneficiaryInn": "771523456789", "amount": 180000.00, "status": "completed", "purpose": "Разработка API интеграции", "createdAt": "2026-04-25T15:00:00Z"},
        {"id": "pay-012", "number": "ПП-2024/012", "accountId": "account-rub-main", "beneficiaryName": "ИП Кузнецов Д.М.", "beneficiaryInn": "771523456789", "amount": 210000.00, "status": "completed", "purpose": "Разработка дашборда аналитики", "createdAt": "2026-05-28T15:00:00Z"},
        {"id": "pay-013", "number": "ПП-2024/013", "accountId": "account-rub-main", "beneficiaryName": "Яндекс.Облако", "beneficiaryInn": "7736203040", "amount": 85000.00, "status": "completed", "purpose": "Облачные вычисления за март 2026", "createdAt": "2026-04-01T10:00:00Z"},
        {"id": "pay-014", "number": "ПП-2024/014", "accountId": "account-rub-main", "beneficiaryName": "Яндекс.Облако", "beneficiaryInn": "7736203040", "amount": 92000.00, "status": "completed", "purpose": "Облачные вычисления за апрель 2026", "createdAt": "2026-05-01T10:00:00Z"},
        {"id": "pay-015", "number": "ПП-2024/015", "accountId": "account-rub-main", "beneficiaryName": "Яндекс.Облако", "beneficiaryInn": "7736203040", "amount": 78000.00, "status": "processing", "purpose": "Облачные вычисления за май 2026", "createdAt": "2026-06-01T10:00:00Z"},
        {"id": "pay-016", "number": "ПП-2024/016", "accountId": "account-rub-main", "beneficiaryName": "ООО «Хостинг-Провайдер»", "beneficiaryInn": "7734123456", "amount": 45000.00, "status": "processing", "purpose": "Оплата хостинга за июнь 2026", "createdAt": "2026-06-05T11:00:00Z"},
        {"id": "pay-017", "number": "ПП-2024/017", "accountId": "account-rub-main", "beneficiaryName": "ИП Кузнецов Д.М.", "beneficiaryInn": "771523456789", "amount": 150000.00, "status": "draft", "purpose": "Разработка мобильного приложения (1 этап)", "createdAt": "2026-06-07T09:00:00Z"},
        {"id": "pay-018", "number": "ПП-2024/018", "accountId": "account-rub-reserve", "beneficiaryName": "УФНС по г. Москве", "beneficiaryInn": "7701101245", "amount": 287000.00, "status": "completed", "purpose": "Уплата налога УСН за 1 квартал 2026", "createdAt": "2026-04-25T09:00:00Z"},
        {"id": "pay-019", "number": "ПП-2024/019", "accountId": "account-rub-reserve", "beneficiaryName": "УФНС по г. Москве", "beneficiaryInn": "7701101245", "amount": 120000.00, "status": "completed", "purpose": "Страховые взносы за 1 квартал 2026", "createdAt": "2026-04-25T09:30:00Z"},
    ]
    _sbp_links = [
        {"id": "sbp-link-001", "url": "https://pay.tbank.ru/invoice/a1b2c3d4e5f6g7h8", "amount": 25000.00, "description": "Оплата подписки SaaS — ИП Смирнов А.В.", "status": "paid", "createdAt": "2026-06-01T09:00:00Z", "paidAt": "2026-06-01T12:30:00Z"},
        {"id": "sbp-link-002", "url": "https://pay.tbank.ru/invoice/i9j8k7l6m5n4o3p2", "amount": 5000.00, "description": "Возврат средств за переплату", "status": "active", "createdAt": "2026-06-07T14:00:00Z"},
    ]
    _self_employed = [
        {"id": "se-001", "inn": "123456789012", "name": "Петров Петр Петрович", "phone": "+7 (999) 111-22-33", "email": "petrov@example.com", "status": "active", "registeredAt": "2026-04-01T10:00:00Z"},
        {"id": "se-002", "inn": "234567890123", "name": "Соколова Мария Сергеевна", "phone": "+7 (999) 444-55-66", "email": "sokolova@example.com", "status": "active", "registeredAt": "2026-05-10T14:00:00Z"},
    ]
    _employees = [
        {"id": "emp-001", "name": "Сидорова Анна Ивановна", "position": "Senior-разработчик", "salary": 250000.00, "department": "Backend"},
        {"id": "emp-002", "name": "Козлов Дмитрий Сергеевич", "position": "DevOps-инженер", "salary": 220000.00, "department": "Infrastructure"},
        {"id": "emp-003", "name": "Новикова Елена Андреевна", "position": "Product-менеджер", "salary": 180000.00, "department": "Product"},
        {"id": "emp-004", "name": "Григорьев Алексей Павлович", "position": "Frontend-разработчик", "salary": 200000.00, "department": "Frontend"},
        {"id": "emp-005", "name": "Морозова Татьяна Викторовна", "position": "Дизайнер UI/UX", "salary": 160000.00, "department": "Design"},
    ]
    _cards = [
        {"id": "card-001", "accountId": ACCOUNTS[0]["id"] if ACCOUNTS else "account-rub-main", "number": "520373****1234", "holder": "Иванов Иван Иванович", "expiry": "12/28", "status": "active", "type": "debit", "limits": {"daily": 100000.00, "monthly": 1000000.00, "single": 50000.00}},
        {"id": "card-002", "accountId": ACCOUNTS[0]["id"] if ACCOUNTS else "account-rub-main", "number": "520373****5678", "holder": "Сидорова Анна Ивановна", "expiry": "06/29", "status": "active", "type": "virtual", "limits": {"daily": 50000.00, "monthly": 300000.00, "single": 25000.00}},
        {"id": "card-003", "accountId": ACCOUNTS[0]["id"] if ACCOUNTS else "account-rub-main", "number": "520373****9012", "holder": "Козлов Дмитрий Сергеевич", "expiry": "06/29", "status": "active", "type": "virtual", "limits": {"daily": 75000.00, "monthly": 400000.00, "single": 35000.00}},
        {"id": "card-004", "accountId": ACCOUNTS[0]["id"] if ACCOUNTS else "account-rub-main", "number": "520373****3456", "holder": "Новикова Елена Андреевна", "expiry": "06/29", "status": "blocked", "type": "virtual", "limits": {"daily": 50000.00, "monthly": 200000.00, "single": 25000.00}},
    ]
    _acquiring_ops = [
        {"id": "acq-001", "terminalId": "TERM-001", "amount": 150000.00, "commission": 4350.00, "cardMask": "427638****9012", "authCode": "A12345", "rrn": "123456789012", "status": "completed", "createdAt": "2026-03-15T10:30:00Z", "settledAt": "2026-03-16T08:00:00Z"},
        {"id": "acq-002", "terminalId": "TERM-001", "amount": 25000.00, "commission": 725.00, "cardMask": "427638****3456", "authCode": "B67890", "rrn": "987654321098", "status": "completed", "createdAt": "2026-03-20T15:45:00Z", "settledAt": "2026-03-21T08:00:00Z"},
        {"id": "acq-003", "terminalId": "TERM-001", "amount": 150000.00, "commission": 4350.00, "cardMask": "427638****9012", "authCode": "C24680", "rrn": "555666777888", "status": "completed", "createdAt": "2026-04-15T10:30:00Z", "settledAt": "2026-04-16T08:00:00Z"},
        {"id": "acq-004", "terminalId": "TERM-001", "amount": 25000.00, "commission": 725.00, "cardMask": "427638****3456", "authCode": "D13579", "rrn": "111222333444", "status": "completed", "createdAt": "2026-04-20T15:45:00Z", "settledAt": "2026-04-21T08:00:00Z"},
        {"id": "acq-005", "terminalId": "TERM-001", "amount": 150000.00, "commission": 4350.00, "cardMask": "427638****9012", "authCode": "E97531", "rrn": "999888777666", "status": "completed", "createdAt": "2026-05-15T10:30:00Z", "settledAt": "2026-05-16T08:00:00Z"},
        {"id": "acq-006", "terminalId": "TERM-001", "amount": 25000.00, "commission": 725.00, "cardMask": "427638****3456", "authCode": "F11223", "rrn": "444555666777", "status": "completed", "createdAt": "2026-05-20T15:45:00Z", "settledAt": "2026-05-21T08:00:00Z"},
        {"id": "acq-007", "terminalId": "TERM-002", "amount": 500000.00, "commission": 14500.00, "cardMask": "427638****7890", "authCode": "G44556", "rrn": "333444555666", "status": "completed", "createdAt": "2026-05-25T12:00:00Z", "settledAt": "2026-05-27T08:00:00Z"},
        {"id": "acq-008", "terminalId": "TERM-001", "amount": 12000.00, "commission": 360.00, "cardMask": "427638****1111", "authCode": "H77889", "rrn": "222333444555", "status": "refunded", "createdAt": "2026-06-01T09:15:00Z"},
    ]
    _salary_payments = [
        {"id": "sal-001", "accountId": "account-rub-main", "period": "2026-03", "totalAmount": 1010000.00, "employeesCount": 3, "status": "completed", "paidAt": "2026-03-05T10:00:00Z"},
        {"id": "sal-002", "accountId": "account-rub-main", "period": "2026-04", "totalAmount": 1010000.00, "employeesCount": 3, "status": "completed", "paidAt": "2026-04-05T10:00:00Z"},
        {"id": "sal-003", "accountId": "account-rub-main", "period": "2026-05", "totalAmount": 1010000.00, "employeesCount": 5, "status": "completed", "paidAt": "2026-05-05T10:00:00Z"},
    ]
    _self_employed_payments = [
        {"id": "se-pay-001", "selfEmployedId": "se-001", "selfEmployedInn": "123456789012", "selfEmployedName": "Петров Петр Петрович", "amount": 75000.00, "commission": 450.00, "status": "completed", "purpose": "Консультационные услуги", "createdAt": "2026-04-15T11:00:00Z"},
        {"id": "se-pay-002", "selfEmployedId": "se-001", "selfEmployedInn": "123456789012", "selfEmployedName": "Петров Петр Петрович", "amount": 75000.00, "commission": 450.00, "status": "completed", "purpose": "Консультационные услуги", "createdAt": "2026-05-15T11:00:00Z"},
        {"id": "se-pay-003", "selfEmployedId": "se-002", "selfEmployedInn": "234567890123", "selfEmployedName": "Соколова Мария Сергеевна", "amount": 45000.00, "commission": 270.00, "status": "completed", "purpose": "Дизайн-макеты", "createdAt": "2026-05-20T14:00:00Z"},
    ]

_seed_data()

_ts_counter = 0
def _ts():
    global _ts_counter
    _ts_counter += 1
    return (_now + timedelta(seconds=_ts_counter)).strftime("%Y-%m-%dT%H:%M:%S.") + f"{(_now.microsecond + _ts_counter) % 1000000:06d}Z"

def _next_id(prefix, existing):
    return f"{prefix}-{len(existing) + 1:03d}"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Mock T-Bank API", version="1.0.0", docs_url=None, redoc_url=None)


@app.middleware("http")
async def check_auth(request: Request, call_next):
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "")
    if not token or token != ACCEPTED_TOKEN:
        return JSONResponse(status_code=401, content={"error": "Unauthorized", "message": "Invalid or missing token"})
    return await call_next(request)


# ---- Company ----

@app.get("/api/v1/company")
async def get_company_info():
    return {
        "name": COMPANY.get("nombreCorto") or "Тестовая Компания",
        "fullName": COMPANY.get("nombre", "ООО «Тестовая Компания»"),
        "inn": COMPANY.get("inn", "7728123456"),
        "kpp": COMPANY.get("kpp", "772801001"),
        "ogrn": COMPANY.get("ogrn", "1187746000001"),
        "legalAddress": COMPANY.get("direccionLegal", "115035, г. Москва, ул. Садовническая, д. 82"),
        "registrationDate": COMPANY.get("fechaRegistro", "2024-01-15"),
        "taxationScheme": COMPANY.get("regimenFiscal", "USN (6%)"),
        "legalStatus": "active",
    }


@app.get("/api/v1/company/requisites")
async def get_company_requisites():
    bank = COMPANY.get("datosBanco", {})
    accts = []
    for a in ACCOUNTS:
        accts.append({
            "id": a.get("id"), "number": a.get("numero"),
            "currency": a.get("moneda", "RUB"), "bankName": a.get("banco", bank.get("banco", "АО «Т-Банк»")),
            "bic": a.get("bic", bank.get("bic", "044525974")),
        })
    return {
        "bankName": bank.get("banco", "АО «Т-Банк»"),
        "bic": bank.get("bic", "044525974"),
        "corrAccount": bank.get("cuentaCorresponsal", "30101810145250000974"),
        "accounts": accts or [{"id": "account-rub-main", "number": "40702810123450000001", "currency": "RUB"}],
    }


# ---- Accounts ----

@app.get("/api/v1/accounts")
async def list_accounts():
    result = []
    for a in ACCOUNTS:
        result.append({
            "id": a.get("id"), "number": a.get("numero"), "currency": a.get("moneda", "RUB"),
            "type": a.get("tipo", "settlement"), "status": "active", "openingDate": "2024-01-20",
            "balance": a.get("saldoInicial", 0), "available": a.get("saldoInicial", 0),
            "bankName": a.get("banco", "АО «Т-Банк»"), "bic": a.get("bic", "044525974"),
        })
    return result


@app.get("/api/v1/accounts/{account_id}/balance")
async def get_account_balance(account_id: str):
    for a in ACCOUNTS:
        if a.get("id") == account_id:
            return {"accountId": account_id, "balance": a.get("saldoInicial", 0), "available": a.get("saldoInicial", 0), "currency": a.get("moneda", "RUB")}
    return {"accountId": account_id, "balance": 0, "available": 0, "currency": "RUB"}


@app.get("/api/v1/accounts/{account_id}/statement")
async def get_account_statement(account_id: str, from_: str = Query("", alias="from"), to: str = ""):
    if account_id == "account-rub-reserve":
        return {"accountId": account_id, "period": {"from": from_, "to": to}, "currency": "RUB", "openingBalance": 500000.00, "closingBalance": 93000.00,
                "transactions": [{"date": "2026-04-25", "description": "Уплата налога УСН за 1 кв. 2026", "amount": -287000.00, "type": "debit"},
                                 {"date": "2026-04-25", "description": "Страховые взносы за 1 кв. 2026", "amount": -120000.00, "type": "debit"}]}
    if account_id == "account-usd-savings":
        return {"accountId": account_id, "period": {"from": from_, "to": to}, "currency": "USD", "openingBalance": 25000.00, "closingBalance": 23200.00,
                "transactions": [{"date": "2026-05-10", "description": "Оплата Cloudflare Inc.", "amount": -1800.00, "type": "debit"}]}
    return {"accountId": account_id, "period": {"from": from_, "to": to}, "currency": "RUB", "openingBalance": 1420000.00, "closingBalance": 1500000.00,
            "transactions": [
                {"date": "2026-06-01", "description": "Поступление от ООО «ТехноПартнер»", "amount": 150000.00, "type": "credit"},
                {"date": "2026-05-28", "description": "Оплата ИП Кузнецов Д.М.", "amount": -210000.00, "type": "debit"},
                {"date": "2026-05-25", "description": "Поступление (acquiring)", "amount": 500000.00, "type": "credit"},
                {"date": "2026-05-05", "description": "Выплата зарплаты", "amount": -1010000.00, "type": "debit"},
            ]}


# ---- Payments ----

@app.post("/api/v1/payments")
async def create_payment(body: dict):
    pay = {"id": _next_id("pay", _payments), "number": f"ПП-2024/{len(_payments)+1:03d}", "status": "completed", "createdAt": _ts(), **body}
    _payments.append(pay)
    return pay


@app.post("/api/v1/payments/draft")
async def create_payment_draft(body: dict):
    pay = {"id": _next_id("pay", _payments), "status": "draft", "createdAt": _ts(), **body}
    _payments.append(pay)
    return pay


@app.get("/api/v1/payments")
async def list_payments(status: str = "", accountId: str = "", from_: str = Query("", alias="from"), to: str = ""):
    result = _payments
    if status:
        result = [p for p in result if p.get("status") == status]
    if accountId:
        result = [p for p in result if p.get("accountId") == accountId]
    return result


@app.post("/api/v1/payments/sbp")
async def create_sbp_payment(body: dict):
    return {"id": f"sbp-{uuid.uuid4().hex[:12]}", "status": "completed", "amount": body.get("amount"), "phone": body.get("phone"),
            "commission": round(body.get("amount", 0) * 0.005, 2), "createdAt": _ts()}


# ---- Salary ----

@app.post("/api/v1/salary/payments")
async def create_salary_payment(body: dict):
    employees = body.get("employees", [])
    total = sum(e.get("amount", 0) for e in employees)
    sal = {"id": f"sal-{uuid.uuid4().hex[:12]}", "status": "processing", "totalAmount": total, "employeesCount": len(employees),
           "paymentDate": body.get("paymentDate", _now.strftime("%Y-%m-%d")), "createdAt": _ts()}
    _salary_payments.append(sal)
    return sal


@app.post("/api/v1/salary/cards")
async def issue_salary_card(body: dict):
    emp_id = body.get("employeeId", "emp-001")
    emp = next((e for e in _employees if e["id"] == emp_id), {"name": "Сотрудник"})
    return {"id": f"card-{uuid.uuid4().hex[:12]}", "employeeId": emp_id, "employeeName": emp["name"],
            "cardType": body.get("cardType", "debit"), "status": "issued",
            "number": "520373****" + str((len(_cards) + 1) * 1111)[:4], "expiry": "12/28", "issuedAt": _ts()}


# ---- Self-employed ----

@app.post("/api/v1/self-employed")
async def add_self_employed(body: dict):
    se = {"id": _next_id("se", _self_employed), "status": "active", "registeredAt": _ts(), **body}
    _self_employed.append(se)
    return se


@app.post("/api/v1/self-employed/payments")
async def pay_self_employed(body: dict):
    se_id = body.get("selfEmployedId", "se-001")
    se = next((s for s in _self_employed if s["id"] == se_id), {"name": "Самозанятый"})
    sep = {"id": f"se-pay-{uuid.uuid4().hex[:12]}", "selfEmployedId": se_id, "selfEmployedInn": se.get("inn"),
           "selfEmployedName": se.get("name"), "amount": body.get("amount"), "status": "completed",
           "commission": round(body.get("amount", 0) * 0.006, 2), "purpose": body.get("paymentPurpose"), "createdAt": _ts()}
    _self_employed_payments.append(sep)
    return sep


# ---- Invoices ----

@app.post("/api/v1/invoices")
async def create_invoice(body: dict):
    items = body.get("items", [])
    total = sum(i.get("quantity", 1) * i.get("unitPrice", 0) for i in items)
    inv = {"id": _next_id("inv", _invoices), "number": f"СЧ-2024/{len(_invoices)+1:03d}", "status": "issued",
           "totalAmount": total, "createdAt": _ts(), **{k: v for k, v in body.items() if k != "items"}, "items": items}
    _invoices.append(inv)
    return inv


@app.get("/api/v1/invoices")
async def list_invoices(status: str = ""):
    result = _invoices
    if status:
        result = [inv for inv in result if inv.get("status") == status]
    return result


@app.post("/api/v1/sbp-links")
async def create_sbp_invoice_link(body: dict):
    link = {"id": f"sbp-link-{uuid.uuid4().hex[:12]}", "url": f"https://pay.tbank.ru/invoice/{uuid.uuid4().hex[:16]}",
            "amount": body.get("amount"), "description": body.get("description"), "status": "active",
            "expiresAt": (_now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"), "createdAt": _ts()}
    _sbp_links.append(link)
    return link


# ---- Business cards ----

@app.get("/api/v1/cards")
async def list_business_cards(accountId: str = ""):
    if accountId:
        return [c for c in _cards if c.get("accountId") == accountId]
    return _cards


@app.post("/api/v1/cards/{card_id}/limits")
async def set_card_limit(card_id: str, body: dict):
    limit_type = body.get("limitType")
    amount = body.get("amount")
    for card in _cards:
        if card["id"] == card_id:
            card.setdefault("limits", {})[limit_type] = amount
            return {"cardId": card_id, "limits": card["limits"], "updatedAt": _ts()}
    return {"cardId": card_id, "limits": {limit_type: amount}, "updatedAt": _ts()}


# ---- Acquiring ----

@app.get("/api/v1/acquiring/operations")
async def list_acquiring_operations(status: str = "", terminalId: str = ""):
    result = _acquiring_ops
    if status:
        result = [op for op in result if op.get("status") == status]
    if terminalId:
        result = [op for op in result if op.get("terminalId") == terminalId]
    return result


@app.get("/api/v1/acquiring/operations/{operation_id}")
async def get_acquiring_operation_detail(operation_id: str):
    op = next((o for o in _acquiring_ops if o["id"] == operation_id), None)
    if op is None:
        return {"id": operation_id, "terminalId": "TERM-001", "amount": 50000.00, "status": "completed"}
    return op


# ---- Health check ----

@app.get("/health")
async def health():
    return {"status": "ok", "mock": True, "version": "1.0.0"}


if __name__ == "__main__":
    print(f"🚀 Mock T-Bank API running on http://{HOST}:{PORT}")
    print(f"🔑 Accepted token: {ACCEPTED_TOKEN}")
    print(f"📂 Data loaded from: {HERE}")
    print()
    print("Configure your real tbank-mcp with:")
    print(f"  TBANK_BASE_URL=http://{HOST}:{PORT}")
    print(f"  TBANK_TOKEN={ACCEPTED_TOKEN}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
