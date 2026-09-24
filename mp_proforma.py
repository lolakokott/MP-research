"""Lab 10: MP Materials through the Lab 09 engine (USD millions).

Run: python3 mp_proforma.py
Operating judgments: lab10.md, Forecast Assumptions.
Opening history: MP-research/mp-10k2026.pdf, PDF pp. 124 and 173.
Revolver capacity: same filing, PDF p. 102. Shares: PDF p. 124.
"""

import math


# Judgment: lab10.md values are used as written, including displayed rounding.
YEARS = range(2026, 2031)
GROWTH = 0.10
GROSS_MARGIN = 0.1410  # Pre-DD&A profit proxy, not reported gross margin.
SGA_RATIOS = (3.5406,) * 5
DEPRECIATION_RATIO = 0.0556
INVENTORY_DAYS = 325.0
CAPEX = (550.0, 206.897, 206.897, 206.897, 206.897)
TAX_RATE = 0.28
NDPR_SALES_VOLUME = (2500, 3000, 3500, 4000, 4500)  # Metric tons, 2026-2030.
FLOOR_PLAN_RATIO = 0.0  # Judgment: none / not applicable.
FLOOR_PLAN_RATE = 0.0
IMPAIRMENT = 0.0  # Judgment: no scheduled ABG impairment.
REPAYMENT = 0.0  # Judgment: no net repayment; assumes maturities refinanced.
BUYBACK = 0.0  # Judgment: preserve cash during expansion and losses.
NEW_DEBT_2030 = 300.0  # Judgment: fund the $266.25m shortfall with a cushion.
# Additional to refinancing; not committed financing or management guidance.
# Opening-balance interest convention: interest on this borrowing starts in 2031.

# Retained Lab 09 classroom judgments: not supplied by lab10.md or MP guidance.
# OTHER_WC_RATIO: keep the engine's small incremental working-capital allowance.
# MINIMUM_CASH: keep its simple liquidity buffer, not MP's contractual covenant.
# Rates: retain the original financing/valuation assumptions without market research.
OTHER_WC_RATIO = 0.008
MINIMUM_CASH = 25.0
REVOLVER_RATE = 0.06
DEBT_RATE = 0.0544
COST_OF_EQUITY = 0.10
TERMINAL_GROWTH = 0.025

# History: remaining borrowing capacity at December 31, 2025.
# Judgment: assume this ceiling is available throughout the annual forecast;
# actual covenants and the August 2030 maturity are not modeled here.
REVOLVER_LIMIT = 235.0
# History: year-end shares. Judgment: keep fixed; no incremental dilution.
SHARES = 177.357647
TOLERANCE = 1e-8

# History: December 31, 2025 balances, grouped for the existing engine.
# cash = 1166.011 cash + 664.275 short-term investments.
# debt = 998.741 balance-sheet debt + 24.270 equipment notes.
# other_liabilities = 1471.792 total liabilities - 1023.011 debt.
# other_assets = 3864.160 total assets - cash - current inventory - PP&E.
# Judgment: preferred book value remains fixed, separate from common equity.
OPENING = dict(
    revenue=224.441, inventory=171.560, ppe=1369.817,
    other_assets=492.497, cash=1830.286, floor_plan=0.0,
    debt=1023.011, other_liabilities=448.781, equity=1978.757,
    preferred=413.611, revolver=0.0,
)


def project():
    """Return annual statements, cash movements, and reconciliation checks."""
    opening = OPENING.copy()
    results = []
    for year, sga_ratio, capex, ndpr_volume in zip(
            YEARS, SGA_RATIOS, CAPEX, NDPR_SALES_VOLUME):
        row = {"year": year, "ndpr_volume": ndpr_volume}
        row["revenue"] = opening["revenue"] * (1 + GROWTH)
        row["gross_profit"] = row["revenue"] * GROSS_MARGIN
        row["cogs"] = row["revenue"] - row["gross_profit"]
        row["sga"] = row["gross_profit"] * sga_ratio
        row["depreciation"] = opening["ppe"] * DEPRECIATION_RATIO
        row["impairment"] = IMPAIRMENT
        row["operating_income"] = (
            row["gross_profit"] - row["sga"]
            - row["depreciation"] - row["impairment"]
        )
        row["interest"] = (
            opening["floor_plan"] * FLOOR_PLAN_RATE
            + opening["debt"] * DEBT_RATE
            + opening["revolver"] * REVOLVER_RATE
        )
        row["pretax"] = row["operating_income"] - row["interest"]
        row["tax"] = max(0.0, row["pretax"]) * TAX_RATE
        row["net_income"] = row["pretax"] - row["tax"]

        row["inventory"] = row["cogs"] * INVENTORY_DAYS / 365
        row["floor_plan"] = row["inventory"] * FLOOR_PLAN_RATIO
        row["capex"] = capex
        row["ppe"] = opening["ppe"] + capex - row["depreciation"]
        row["change_other_wc"] = (
            OTHER_WC_RATIO * (row["revenue"] - opening["revenue"])
        )
        row["other_assets"] = (
            opening["other_assets"] + row["change_other_wc"] - IMPAIRMENT
        )
        row["repayment"] = REPAYMENT
        row["new_debt"] = NEW_DEBT_2030 if year == 2030 else 0.0
        row["debt"] = opening["debt"] + row["new_debt"] - REPAYMENT
        row["other_liabilities"] = opening["other_liabilities"]
        row["preferred"] = opening["preferred"]
        row["buyback"] = BUYBACK
        row["equity"] = opening["equity"] + row["net_income"] - BUYBACK
        row["change_inventory"] = row["inventory"] - opening["inventory"]
        row["change_floor_plan"] = row["floor_plan"] - opening["floor_plan"]
        # Other WC is the revenue-driven addition, excluding noncash impairment.
        row["fcfe"] = (
            row["net_income"] + row["depreciation"] + IMPAIRMENT - capex
            - row["change_inventory"] - row["change_other_wc"]
            + row["change_floor_plan"] + row["new_debt"] - REPAYMENT
        )
        cash_before_revolver = opening["cash"] + row["fcfe"] - BUYBACK
        if cash_before_revolver < MINIMUM_CASH:
            row["change_revolver"] = min(
                MINIMUM_CASH - cash_before_revolver,
                REVOLVER_LIMIT - opening["revolver"],
            )
        else:
            row["change_revolver"] = -min(
                cash_before_revolver - MINIMUM_CASH, opening["revolver"]
            )
        row["revolver"] = opening["revolver"] + row["change_revolver"]
        row["opening_cash"] = opening["cash"]
        row["cash"] = cash_before_revolver + row["change_revolver"]
        row["change_cash"] = row["cash"] - opening["cash"]
        row["assets"] = sum(row[k] for k in (
            "inventory", "ppe", "other_assets", "cash"
        ))
        row["liabilities"] = sum(row[k] for k in (
            "floor_plan", "debt", "revolver", "other_liabilities"
        ))
        row["liabilities_equity"] = (
            row["liabilities"] + row["preferred"] + row["equity"]
        )
        row["balance_gap"] = row["assets"] - row["liabilities_equity"]
        row["cash_headroom"] = row["cash"] - MINIMUM_CASH
        row["cash_ok"] = row["cash_headroom"] >= -TOLERANCE
        results.append(row)
        opening = row
    return results


def assert_balanced(results):
    """Raise with the year and gap for a failed balance or liquidity check."""
    for row in results:
        gap = row["balance_gap"]
        if not math.isfinite(gap) or abs(gap) > TOLERANCE:
            raise ValueError(f"FY{row['year']}: balance sheet gap = {gap:.10f}")
        gap = row["cash_headroom"]
        if not math.isfinite(gap) or gap < -TOLERANCE:
            raise ValueError(f"FY{row['year']}: cash minus minimum gap = {gap:.10f}")
        revolver = row["revolver"]
        if not math.isfinite(revolver) or not -TOLERANCE <= revolver <= REVOLVER_LIMIT + TOLERANCE:
            gap = revolver if revolver < 0 else revolver - REVOLVER_LIMIT
            raise ValueError(f"FY{row['year']}: revolver bound gap = {gap:.10f}")


def print_table(title, results, fields, units="USD millions"):
    print(f"\n{title} ({units})")
    print(f"{'':36}" + "".join(f"{'FY' + str(r['year']) + 'E':>14}" for r in results))
    for label, key, sign in fields:
        values = []
        for row in results:
            value = row[key] * sign
            if abs(value) < 0.05:
                value = 0.0  # Avoid displaying negative zero.
            values.append(f"{value:14,.1f}")
        print(f"{label:36}" + "".join(values))


def main():
    print("MP Materials — simplified Lab 10 scenario; assumptions in lab10.md.")
    print("Retained Lab 09 rate and liquidity settings are classroom judgments.")
    print("Gross profit is a pre-DD&A proxy; floor-plan financing is not applicable.")
    results = project()
    print_table("COMPANY-SPECIFIC OPERATING LINE", results, [
        ("NdPr sales volume", "ndpr_volume", 1),
    ], units="metric tons of NdPr oxide equivalent")
    print("NdPr volume replaces the same-store concept; revenue still grows by 10%.")
    print_table("INCOME STATEMENT", results, [
        ("Revenue", "revenue", 1), ("Cost of sales, excluding DD&A", "cogs", -1),
        ("Gross profit proxy, before DD&A", "gross_profit", 1), ("SG&A", "sga", -1),
        ("Depreciation", "depreciation", -1), ("Impairment", "impairment", -1),
        ("Operating income", "operating_income", 1), ("Interest", "interest", -1),
        ("Pretax income", "pretax", 1), ("Tax", "tax", -1),
        ("Net income", "net_income", 1),
    ])
    print_table("BALANCE SHEET", results, [
        ("Cash", "cash", 1), ("Inventory", "inventory", 1),
        ("PP&E", "ppe", 1), ("Other assets", "other_assets", 1),
        ("Total assets", "assets", 1), ("Floor plan", "floor_plan", 1),
        ("Term debt", "debt", 1), ("Revolver", "revolver", 1),
        ("Other liabilities", "other_liabilities", 1),
        ("Total liabilities", "liabilities", 1),
        ("Redeemable preferred stock", "preferred", 1), ("Common equity", "equity", 1),
        ("Liabilities + preferred + equity", "liabilities_equity", 1),
    ])
    print_table("CASH FLOW", results, [
        ("Net income", "net_income", 1), ("Depreciation addback", "depreciation", 1),
        ("Impairment addback", "impairment", 1), ("Capital spending", "capex", -1),
        ("Inventory increase", "change_inventory", -1),
        ("Other working capital increase", "change_other_wc", -1),
        ("Floor plan increase", "change_floor_plan", 1),
        ("New long-term borrowing", "new_debt", 1),
        ("Term debt repayment", "repayment", -1), ("FCFE", "fcfe", 1),
        ("Share buyback", "buyback", -1),
        ("Revolver draw / (repayment)", "change_revolver", 1),
        ("Change in cash", "change_cash", 1), ("Opening cash", "opening_cash", 1),
        ("Closing cash", "cash", 1),
    ])
    print_table("ANNUAL CHECKS", results, [
        ("Assets - liabilities - pref - equity", "balance_gap", 1),
        ("Cash minus minimum", "cash_headroom", 1),
    ])
    print(f"{'Cash at or above minimum':36}" + "".join(
        f"{'PASS' if row['cash_ok'] else 'FAIL':>14}" for row in results
    ))
    for row in results:
        status = "negative FCFE" if row["fcfe"] < 0 else "nonnegative FCFE"
        print(f"FY{row['year']}: {status} = ${row['fcfe']:,.3f} million")
    assert_balanced(results)

    # Lab 10: value only positive cash flows; do not erase statement losses.
    pv_fcfe = sum(max(0.0, row["fcfe"]) / (1 + COST_OF_EQUITY) ** t
                  for t, row in enumerate(results, 1))
    last = results[-1]
    terminal_cash_flow = last["fcfe"] + last["repayment"]
    if last["fcfe"] <= 0 or terminal_cash_flow <= 0:
        terminal_value = 0.0
        print("No terminal value: terminal FCFE is nonpositive.")
        print("Growing negative cash flow forever is not a meaningful terminal value.")
    else:
        if COST_OF_EQUITY <= TERMINAL_GROWTH:
            raise ValueError("Discount rate must exceed terminal growth.")
        terminal_value = (terminal_cash_flow * (1 + TERMINAL_GROWTH)
                          / (COST_OF_EQUITY - TERMINAL_GROWTH))
    pv_terminal = terminal_value / (1 + COST_OF_EQUITY) ** len(results)
    equity_value = pv_fcfe + pv_terminal
    print(f"\nClassroom equity value (USD millions): ${equity_value:,.2f}")
    if equity_value == 0:
        print("Share of value after 2030: N/A (zero equity value)")
    else:
        print(f"Share of value after 2030: {pv_terminal / equity_value:.2%}")
    print(f"Value per share (simplified Lab 10): ${equity_value / SHARES:,.2f}")
    print("This engine does not separately value preferred or conversion rights.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(f"REFUSED: {error}. No value per share issued.")
