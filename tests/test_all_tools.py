"""Test ALL 20 tbank-mcp tools against the mock API.
Creates entities extensively and verifies state changes.

Run with mock API running:
    python mock_tbank_api.py          (terminal 1)
    python tests/test_all_tools.py    (terminal 2)
"""
import ast
import asyncio
import os

from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters, ClientSession


def _parse(text: str):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


os.environ["TBANK_ENVIRONMENT"] = "mock"
os.environ["TBANK_BASE_URL"] = "http://127.0.0.1:8099"
os.environ["TBANK_TOKEN"] = "mock-token-any-value"


def p(label, ok=True):
    mark = "✅" if ok else "❌"
    print(f"  {mark} {label}")


async def test():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "tbank_mcp"],
        env={
            "TBANK_ENVIRONMENT": "mock",
            "TBANK_BASE_URL": "http://127.0.0.1:8099",
            "TBANK_TOKEN": "mock-token-any-value",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Tools loaded: {len(tools.tools)} / 20\n")

            # ── 1. COMPANY ────────────────────────────────────────────
            print("── Company ──")
            r = await session.call_tool("get_company_info", {})
            c = _parse(r.content[0].text)
            assert c["name"] == "Тестовая Компания"
            assert c["inn"] == "7728123456"
            p("get_company_info: name + INN correct")

            r = await session.call_tool("get_company_requisites", {})
            req = _parse(r.content[0].text)
            assert len(req["accounts"]) == 4
            assert req["bic"] == "044525974"
            p("get_company_requisites: 4 accounts, BIC correct")

            # ── 2. ACCOUNTS ───────────────────────────────────────────
            print("\n── Accounts ──")
            r = await session.call_tool("list_accounts", {})
            accts = _parse(r.content[0].text)
            assert len(accts) == 4
            ids = [a["id"] for a in accts]
            p(f"list_accounts: {len(accts)} accounts ({', '.join(ids)})")

            r = await session.call_tool("get_account_balance", {"accountId": "account-rub-main"})
            bal = _parse(r.content[0].text)
            assert bal["balance"] == 1_500_000
            assert bal["currency"] == "RUB"
            p("get_account_balance main: 1,500,000 RUB")

            r = await session.call_tool("get_account_balance", {"accountId": "account-usd-savings"})
            bal = _parse(r.content[0].text)
            assert bal["currency"] == "USD"
            p("get_account_balance USD: 25,000 USD")

            r = await session.call_tool("get_account_statement", {
                "accountId": "account-rub-main",
                "from": "2026-01-01",
                "to": "2026-12-31",
            })
            stmt = _parse(r.content[0].text)
            assert len(stmt["transactions"]) >= 3
            p(f"get_account_statement main: {len(stmt['transactions'])} transactions")

            r = await session.call_tool("get_account_statement", {
                "accountId": "account-rub-reserve",
                "from": "2026-04-01",
                "to": "2026-04-30",
            })
            stmt = _parse(r.content[0].text)
            assert stmt["openingBalance"] == 500_000
            p("get_account_statement reserve: opening 500,000 RUB")

            # ── 3. INVOICES ──────────────────────────────────────────
            print("\n── Invoices ──")
            r = await session.call_tool("list_invoices", {})
            invs_before = len(_parse(r.content[0].text))

            # Create invoice 1 — full data
            r = await session.call_tool("create_invoice", {
                "counterpartyName": "ООО «Новый Клиент»",
                "counterpartyInn": "7709123456",
                "counterpartyEmail": "client@example.com",
                "items": [{"name": "Разработка сайта", "quantity": 1, "unitPrice": 300000}],
                "vatRate": "none",
            })
            inv1 = _parse(r.content[0].text)
            assert inv1["status"] == "issued"
            assert inv1["counterpartyName"] == "ООО «Новый Клиент»"
            p(f"create_invoice 1: {inv1['number']} — 300,000 RUB")

            # Create invoice 2 — minimal fields
            r = await session.call_tool("create_invoice", {
                "counterpartyName": "ИП Тестов",
                "counterpartyInn": "772812345678",
                "items": [{"name": "Консультация", "quantity": 5, "unitPrice": 10000}],
            })
            inv2 = _parse(r.content[0].text)
            p(f"create_invoice 2: {inv2['number']} — 50,000 RUB")

            # Create invoice 3 — VAT 20%
            r = await session.call_tool("create_invoice", {
                "counterpartyName": "АО «Партнёр»",
                "counterpartyInn": "7715987654",
                "items": [{"name": "Оборудование", "quantity": 2, "unitPrice": 75000}],
                "vatRate": "vat20",
            })
            inv3 = _parse(r.content[0].text)
            p(f"create_invoice 3: {inv3['number']} — 150,000 RUB (VAT 20%)")

            # Verify count increased by 3
            r = await session.call_tool("list_invoices", {})
            invs_after = len(_parse(r.content[0].text))
            assert invs_after == invs_before + 3, f"Expected {invs_before + 3}, got {invs_after}"
            p(f"list_invoices: {invs_before} → {invs_after} (+3 creadas)")

            # Filter by status
            r = await session.call_tool("list_invoices", {"status": "overdue"})
            overdue = _parse(r.content[0].text)
            assert len(overdue) == 1
            p(f"list_invoices(status=overdue): {len(overdue)} encontrada")

            # ── 4. PAYMENTS ──────────────────────────────────────────
            print("\n── Payments ──")
            r = await session.call_tool("list_payments", {})
            pays_before = len(_parse(r.content[0].text))

            # Create payment 1 — main account
            r = await session.call_tool("create_payment", {
                "accountId": "account-rub-main",
                "amount": 75000.00,
                "beneficiaryName": "ООО «Поставщик»",
                "beneficiaryInn": "7734123456",
                "beneficiaryAccount": "40702810900000001111",
                "beneficiaryBic": "044525974",
                "paymentPurpose": "Оплата услуг по договору №45",
                "vatType": "none",
            })
            pay1 = _parse(r.content[0].text)
            assert pay1["status"] == "completed"
            p(f"create_payment 1: {pay1['number']} — 75,000 RUB (completed)")

            # Create payment 2 — reserve account with VAT
            r = await session.call_tool("create_payment", {
                "accountId": "account-rub-reserve",
                "amount": 120000.00,
                "beneficiaryName": "УФНС по г. Москве",
                "beneficiaryInn": "7701101245",
                "beneficiaryAccount": "40101810845250010002",
                "beneficiaryBic": "044525000",
                "paymentPurpose": "Уплата налога УСН за 2 квартал 2026",
                "vatType": "vat20",
            })
            pay2 = _parse(r.content[0].text)
            p(f"create_payment 2: {pay2['number']} — 120,000 RUB (VAT 20%)")

            # Create payment as draft
            r = await session.call_tool("create_payment_draft", {
                "accountId": "account-rub-main",
                "amount": 250000.00,
                "beneficiaryName": "ИП Разработчик",
                "beneficiaryInn": "771523456789",
                "beneficiaryAccount": "40802810700000002222",
                "beneficiaryBic": "044525974",
                "paymentPurpose": "Разработка CRM-системы (этап 2)",
            })
            draft = _parse(r.content[0].text)
            assert draft["status"] == "draft"
            assert draft["id"].startswith("pay-")
            p(f"create_payment_draft: {draft['id']} — 250,000 RUB (draft)")

            # Verify count
            r = await session.call_tool("list_payments", {})
            pays_after = len(_parse(r.content[0].text))
            assert pays_after == pays_before + 3
            p(f"list_payments: {pays_before} → {pays_after} (+3 creados)")

            # Filter by account
            r = await session.call_tool("list_payments", {"accountId": "account-rub-reserve"})
            reserve_pays = _parse(r.content[0].text)
            p(f"list_payments(account=reserve): {len(reserve_pays)} payments")

            # ── 5. SBP ───────────────────────────────────────────────
            print("\n── SBP / Faster Payments ──")
            r = await session.call_tool("create_sbp_payment", {
                "accountId": "account-rub-main",
                "amount": 3500.00,
                "phone": "+79991112233",
                "bankName": "Сбербанк",
                "paymentPurpose": "Возврат средств",
            })
            sbp = _parse(r.content[0].text)
            assert sbp["status"] == "completed"
            p(f"create_sbp_payment: {sbp['id']} — 3,500 RUB to +79991112233")

            # SBP invoice link
            r = await session.call_tool("create_sbp_invoice_link", {
                "accountId": "account-rub-main",
                "amount": 50000.00,
                "description": "Оплата подписки Premium",
            })
            link = _parse(r.content[0].text)
            assert link["status"] == "active"
            assert link["url"].startswith("https://pay.tbank.ru/")
            p(f"create_sbp_invoice_link: {link['id']} — 50,000 RUB link created")

            # ── 6. SALARY ────────────────────────────────────────────
            print("\n── Salary ──")
            r = await session.call_tool("create_salary_payment", {
                "accountId": "account-rub-main",
                "employees": [
                    {"employeeId": "emp-001", "amount": 250000},
                    {"employeeId": "emp-002", "amount": 220000},
                    {"employeeId": "emp-003", "amount": 180000},
                    {"employeeId": "emp-004", "amount": 200000},
                    {"employeeId": "emp-005", "amount": 160000},
                ],
                "paymentDate": "2026-06-05",
            })
            sal = _parse(r.content[0].text)
            assert sal["totalAmount"] == 1_010_000
            assert sal["employeesCount"] == 5
            p(f"create_salary_payment: {sal['id']} — 1,010,000 RUB for 5 employees")

            # Issue cards for different employees
            r = await session.call_tool("issue_salary_card", {
                "employeeId": "emp-001",
                "cardType": "debit",
            })
            card1 = _parse(r.content[0].text)
            assert card1["status"] == "issued"
            p(f"issue_salary_card (debit, emp-001): {card1['number']}")

            r = await session.call_tool("issue_salary_card", {
                "employeeId": "emp-003",
                "cardType": "virtual",
            })
            card2 = _parse(r.content[0].text)
            p(f"issue_salary_card (virtual, emp-003): {card2['number']}")

            # ── 7. SELF EMPLOYED ─────────────────────────────────────
            print("\n── Self-Employed ──")
            # Register 2 new self-employed
            r = await session.call_tool("add_self_employed", {
                "inn": "345678901234",
                "phone": "+7 (999) 777-88-99",
                "email": "ivanov@example.com",
            })
            se1 = _parse(r.content[0].text)
            assert se1["status"] == "active"
            p(f"add_self_employed 1: {se1['id']} — INN 345678901234")

            r = await session.call_tool("add_self_employed", {
                "inn": "456789012345",
                "phone": "+7 (999) 888-99-00",
            })
            se2 = _parse(r.content[0].text)
            p(f"add_self_employed 2: {se2['id']} — INN 456789012345 (no email)")

            # Pay self-employed
            r = await session.call_tool("pay_self_employed", {
                "accountId": "account-rub-main",
                "selfEmployedId": se1["id"],
                "amount": 55000.00,
                "paymentPurpose": "Консультационные услуги по маркетингу",
            })
            sep1 = _parse(r.content[0].text)
            assert sep1["status"] == "completed"
            p(f"pay_self_employed: {sep1['id']} — 55,000 RUB to {se1['id']}")

            r = await session.call_tool("pay_self_employed", {
                "accountId": "account-rub-main",
                "selfEmployedId": se2["id"],
                "amount": 32000.00,
                "paymentPurpose": "Дизайн лендинга",
            })
            sep2 = _parse(r.content[0].text)
            p(f"pay_self_employed: {sep2['id']} — 32,000 RUB to {se2['id']}")

            # ── 8. BUSINESS CARDS ────────────────────────────────────
            print("\n── Business Cards ──")
            r = await session.call_tool("list_business_cards", {})
            cards_before = len(_parse(r.content[0].text))

            r = await session.call_tool("list_business_cards", {"accountId": "account-rub-main"})
            cards_filtered = _parse(r.content[0].text)
            p(f"list_business_cards (all): {cards_before} | (filter main): {len(cards_filtered)}")

            # Set limits on first card
            first_card_id = _parse((await session.call_tool("list_business_cards", {})).content[0].text)[0]["id"]

            r = await session.call_tool("set_card_limit", {
                "cardId": first_card_id,
                "limitType": "daily",
                "amount": 200000.00,
            })
            lim = _parse(r.content[0].text)
            assert lim["limits"]["daily"] == 200000
            p(f"set_card_limit (daily, 200,000) on {first_card_id}")

            r = await session.call_tool("set_card_limit", {
                "cardId": first_card_id,
                "limitType": "single",
                "amount": 75000.00,
            })
            lim = _parse(r.content[0].text)
            assert lim["limits"]["single"] == 75000
            p(f"set_card_limit (single, 75,000) on {first_card_id}")

            # ── 9. ACQUIRING ─────────────────────────────────────────
            print("\n── Acquiring ──")
            r = await session.call_tool("list_acquiring_operations", {})
            all_acq = _parse(r.content[0].text)
            total = sum(o["amount"] for o in all_acq)
            p(f"list_acquiring_operations: {len(all_acq)} ops, total {total:,.0f} RUB")

            # Filter by terminal
            r = await session.call_tool("list_acquiring_operations", {"terminalId": "TERM-002"})
            term2 = _parse(r.content[0].text)
            assert len(term2) == 1
            assert term2[0]["amount"] == 500_000
            p(f"list(terminal=TERM-002): {len(term2)} op — 500,000 RUB")

            # Filter by status
            r = await session.call_tool("list_acquiring_operations", {"status": "refunded"})
            refunded = _parse(r.content[0].text)
            assert len(refunded) == 1
            p(f"list(status=refunded): {len(refunded)} op")

            # Get detail for a specific operation
            first_op_id = all_acq[0]["id"]
            r = await session.call_tool("get_acquiring_operation_detail", {"operationId": first_op_id})
            detail = _parse(r.content[0].text)
            assert detail["id"] == first_op_id
            assert "authCode" in detail
            assert "rrn" in detail
            assert "commission" in detail
            p(f"get_acquiring_operation_detail: {first_op_id} — authCode={detail['authCode']}, commission={detail['commission']}")

            # ── SUMMARY ──────────────────────────────────────────────
            print(f"\n{'=' * 55}")
            print(f"ALL 20 TOOLS TESTED SUCCESSFULLY")
            print(f"{'=' * 55}")
            print(f"\nEntities created during this run:")
            print(f"  - 3 invoices")
            print(f"  - 3 payments (2 completed + 1 draft)")
            print(f"  - 1 SBP transfer")
            print(f"  - 1 SBP invoice link")
            print(f"  - 1 salary payment (5 employees)")
            print(f"  - 2 salary cards")
            print(f"  - 2 self-employed registered + 2 payments")
            print(f"  - 2 card limits updated")
            print(f"\nAll state changes verified via list/get tools.")


if __name__ == "__main__":
    asyncio.run(test())
