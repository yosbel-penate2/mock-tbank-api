"""End-to-end test: real tbank-mcp → mock HTTP API → test data.

Run with the mock API server already running:
    python mock_tbank_api.py            (in one terminal)
    python tests/test_e2e.py            (in another)
"""
import ast
import asyncio
import os

from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters, ClientSession


def _parse(text: str):
    """The real tbank-mcp handlers use str() on dicts, producing
    Python repr (single quotes, None, True/False) not JSON.
    We parse with ast.literal_eval to handle both formats."""
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text

os.environ["TBANK_ENVIRONMENT"] = "mock"
os.environ["TBANK_BASE_URL"] = "http://127.0.0.1:8099"
os.environ["TBANK_TOKEN"] = "mock-token-any-value"


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
            print(f"Tools loaded: {len(tools.tools)}")

            # 1. get_company_info
            r = await session.call_tool("get_company_info", {})
            data = _parse(r.content[0].text)
            print(f"1. Company: {data['name']} (INN: {data['inn']}) ✅")

            # 2. list_accounts
            r = await session.call_tool("list_accounts", {})
            accts = _parse(r.content[0].text)
            print(f"2. Accounts: {len(accts)} cuentas ✅")
            for a in accts:
                print(f"   {a['id']}: {a['balance']:,.0f} {a['currency']}")

            # 3. get_account_balance
            r = await session.call_tool("get_account_balance", {"accountId": "account-rub-main"})
            bal = _parse(r.content[0].text)
            print(f"3. Balance (main): {bal['balance']:,.0f} {bal['currency']} ✅")

            # 4. list_invoices
            r = await session.call_tool("list_invoices", {})
            invs = _parse(r.content[0].text)
            total = sum(i.get("amount") or i.get("totalAmount", 0) for i in invs)
            print(f"4. Invoices: {len(invs)} emitidas, total {total:,.0f} RUB ✅")

            # 5. list_payments
            r = await session.call_tool("list_payments", {})
            pays = _parse(r.content[0].text)
            total_p = sum(p["amount"] for p in pays)
            print(f"5. Payments: {len(pays)} realizados, total {total_p:,.0f} RUB ✅")

            # 6. create_invoice
            r = await session.call_tool("create_invoice", {
                "counterpartyName": "E2E Test Client",
                "counterpartyInn": "7709123456",
                "items": [{"name": "Test", "quantity": 1, "unitPrice": 99999}],
            })
            inv = _parse(r.content[0].text)
            print(f"6. Created invoice: {inv['number']} ({inv['status']}) ✅")

            # 7. create_payment
            r = await session.call_tool("create_payment", {
                "accountId": "account-rub-main",
                "amount": 50000.00,
                "beneficiaryName": "E2E Test Vendor",
                "beneficiaryInn": "7712345678",
                "beneficiaryAccount": "40702810900000009999",
                "beneficiaryBic": "044525974",
                "paymentPurpose": "E2E test payment",
                "vatType": "none",
            })
            pay = _parse(r.content[0].text)
            print(f"7. Created payment: {pay['number']} ({pay['status']}) ✅")

            # 8. list_acquiring_operations
            r = await session.call_tool("list_acquiring_operations", {})
            acq = _parse(r.content[0].text)
            total_acq = sum(o["amount"] for o in acq)
            print(f"8. Acquiring: {len(acq)} ops, total {total_acq:,.0f} RUB ✅")

            # 9. list_business_cards
            r = await session.call_tool("list_business_cards", {})
            cards = _parse(r.content[0].text)
            print(f"9. Cards: {len(cards)} tarjetas ✅")

            print()
            print("=" * 55)
            print("ALL E2E TESTS PASSED")
            print("=" * 55)
            print()
            print("Flow: tbank-mcp (MCP stdio) → mock-tbank-api (HTTP REST)")
            print("      ↑                    ↑")
            print("   your real MCP        your mock backend")
            print()
            print("To go to production, just change:")
            print("  TBANK_ENVIRONMENT=production")
            print("  TBANK_TOKEN=<real_token>")


if __name__ == "__main__":
    asyncio.run(test())
