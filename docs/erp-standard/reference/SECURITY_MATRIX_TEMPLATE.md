# Security and Segregation-of-Duties Matrix Template

**Project/company:**  
**Identity provider:**  
**Tenant/company scoping implementation:**  
**Audit retention and approval owner:**  

| Object/operation | Staff | Dept manager | Warehouse | Accountant | Controller | Admin | Auditor | Company filter | Approved deviation |
|---|---|---|---|---|---|---|---|---|---|
| Customer master read/write | | | | | | | | | |
| Discount threshold override | | | | | | | | | |
| Sales order confirmation | | | | | | | | | |
| Goods issue/stock adjustment | | | | | | | | | |
| Invoice posting/reversal | | | | | | | | | |
| Bank payment creation/release | | | | | | | | | |
| Period lock adjustment | | | | | | | | | |
| Payroll/salary view/edit | | | | | | | | | |
| Bulk export / integration token | | | | | | | | | |
| Role and company-grant changes | | | | | | | | | |

**Mandatory negative tests:** unauthorized cross-company read, write, export and report; horizontal record enumeration; hidden action executed via API; self-approval; permission delegation expiry; compromised integration key; agent service account attempting forbidden writes.
