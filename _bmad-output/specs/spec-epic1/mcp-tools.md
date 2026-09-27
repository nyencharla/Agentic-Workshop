# MCP tools

The case's own MCP server (CAP-1's "Constraints"), over stdio.

| Tool | Takes | Returns |
|---|---|---|
| `get_claim` | `claim_id` | The claim's `submitted_at`, and every line item with its date, city, category, merchant, amount, receipt flag, description, and CAP-2's computed facts (day total, applicable limit, percent over, days late, receipt required, duplicate) |
| `get_employee` | `employee_id` | Their level and city |
| `get_policy_limits` | `level`, `city` | The limit for each category |
| `record_decision` | `line_id`, `decision`, `clause`, `explanation` | Writes the line item's decision, clause and explanation, and sets its payout status (CAP-4) |

`get_claim` carries the computed facts directly so the agent never has to call `get_policy_limits` or do its own arithmetic to get CAP-2's facts; `get_employee` and `get_policy_limits` stay separate tools because the case brief names them individually.
