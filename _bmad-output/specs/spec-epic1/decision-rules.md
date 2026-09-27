# Decision rules

What CAP-1's agent decides with, and what CAP-2's computed facts must supply for it.

## Clause precedence (CAP-1)

Apply the first that fires, in order:

1. **Section 3** — alcohol (3.1), personal expenses (3.2), parking tickets and fines (3.3): reject.
2. **5.1** — same date, merchant and amount as an earlier item on the same claim: reject.
3. **1.2** — dated more than 60 days before the claim's submission: reject.
4. **4.1** — software or equipment: approve only if the description carries an IT approval code, else reject.
5. **The applicable limit** (2.1 meals, 2.2 hotels, 2.3 flights, 6.1 ground transport): at or under, approve under that clause; over by ≤20%, flag under that clause; over by >20%, reject under that clause. Never cite 2.4 itself — it is the rule that produces this decision, not the clause recorded.
6. **1.3** — over $25 with no receipt: flag.
7. **Else** — approve under the category's own clause (2.1, 2.2, 2.3 or 6.1).

Clause 7.1 (the payout gate) is never cited on a line item; it governs payout status only (`SPEC.md` CAP-4).

## Computed facts (CAP-2)

Each must be true for the line item before the agent sees it, computed in code:

| Fact | Computation |
|---|---|
| Day total | Sum of `amount` for same-category (meals, or ground transport) items on the same date and claim, **excluding any item already decided reject under section 3, 5.1 or 1.2** |
| Applicable limit | `seed/limits.csv` row for the employee's level and the city the expense happened in (not the employee's home city) |
| Percent over | `(day total or item amount − limit) / limit`, for the category the limit applies to |
| Days late | Claim's `submitted_at` minus the item's `date` |
| Receipt required | `amount > 25` |
| Duplicate | Another item on the same claim with the same date, merchant and amount |

An item's day total, once it is itself rejected, is excluded from other items' day totals for that same day (it does not double-penalize the day).
