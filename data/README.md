# Data Files

These JSON files configure the mock T-Bank API server's pre-loaded data.

| File | Purpose | Required |
|------|---------|----------|
| `empresa.json` | Company legal entity (name, INN, KPP, OGRN, bank details, tax scheme) | Yes |
| `cuentas-bancarias.json` | Bank accounts list with balances | Yes |
| `clientes.json` | Client/counterparty directory | No |
| `proveedores.json` | Supplier directory | No |
| `plan-de-cuentas.json` | Chart of accounts for accounting | No |
| `escenarios-prueba.json` | Test scenario definitions | No |

The server reads these at startup. Missing files are silently ignored.
