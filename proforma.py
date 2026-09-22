"""Five-year company projection. Monetary amounts are USD millions.

Run with: python3 company_projection.py
Calculations retain full precision; rounding is for display only.
"""

import math


YEARS = range(2026, 2031)
GROWTH = 0.018
GROSS_MARGIN = 0.1705
SGA_RATIOS = (0.665, 0.655, 0.645, 0.645, 0.645)
DEPRECIATION_RATIO = 82.4 / 3070.4
INVENTORY_DAYS = 2135.8 / (17999.0 - 3071.7) * 365
FLOOR_PLAN_RATIO = 2027.0 / 2135.8
IMPAIRMENT = 120.0
CAPEX = 250.0
TAX_RATE = 0.255
OTHER_WC_RATIO = 0.008
MINIMUM_CASH = 25.0
REVOLVER_LIMIT = 850.0
REVOLVER_RATE = 0.06
REPAYMENT = 150.0
BUYBACK = 150.0
FLOOR_PLAN_RATE = 0.0467
DEBT_RATE = 0.0544
COST_OF_EQUITY = 0.10
TERMINAL_GROWTH = 0.025
SHARES = 17.951349  # Millions of shares.
TOLERANCE = 1e-8

OPENING = dict(
    revenue=17999.0, inventory=2135.8, ppe=3070.4,
    other_assets=6371.6, cash=40.4, floor_plan=2027.0,
    debt=3572.0, other_liabilities=2127.5, equity=3891.7,
    revolver=0.0,
)


def project():
    """Return annual statements, cash movements, and reconciliation checks."""
    opening = OPENING.copy()
    results = []
    for year, sga_ratio in zip(YEARS, SGA_RATIOS):
        row = {"year": year}
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
        row["capex"] = CAPEX
        row["ppe"] = opening["ppe"] + CAPEX - row["depreciation"]
        row["change_other_wc"] = (
            OTHER_WC_RATIO * (row["revenue"] - opening["revenue"])
        )
        row["other_assets"] = (
            opening["other_assets"] + row["change_other_wc"] - IMPAIRMENT
        )
        row["repayment"] = REPAYMENT
        row["debt"] = opening["debt"] - REPAYMENT
        row["other_liabilities"] = opening["other_liabilities"]
        row["buyback"] = BUYBACK
        row["equity"] = opening["equity"] + row["net_income"] - BUYBACK
        row["change_inventory"] = row["inventory"] - opening["inventory"]
        row["change_floor_plan"] = row["floor_plan"] - opening["floor_plan"]
        # Other WC is the revenue-driven addition, excluding noncash impairment.
        row["fcfe"] = (
            row["net_income"] + row["depreciation"] + IMPAIRMENT - CAPEX
            - row["change_inventory"] - row["change_other_wc"]
            + row["change_floor_plan"] - REPAYMENT
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
        row["liabilities_equity"] = row["liabilities"] + row["equity"]
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


def print_table(title, results, fields):
    print(f"\n{title} (USD millions)")
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
    results = project()
    print_table("INCOME STATEMENT", results, [
        ("Revenue", "revenue", 1), ("Cost of goods sold", "cogs", -1),
        ("Gross profit", "gross_profit", 1), ("SG&A", "sga", -1),
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
        ("Total liabilities", "liabilities", 1), ("Equity", "equity", 1),
        ("Total liabilities and equity", "liabilities_equity", 1),
    ])
    print_table("CASH FLOW", results, [
        ("Net income", "net_income", 1), ("Depreciation addback", "depreciation", 1),
        ("Impairment addback", "impairment", 1), ("Capital spending", "capex", -1),
        ("Inventory increase", "change_inventory", -1),
        ("Other working capital increase", "change_other_wc", -1),
        ("Floor plan increase", "change_floor_plan", 1),
        ("Term debt repayment", "repayment", -1), ("FCFE", "fcfe", 1),
        ("Share buyback", "buyback", -1),
        ("Revolver draw / (repayment)", "change_revolver", 1),
        ("Change in cash", "change_cash", 1), ("Opening cash", "opening_cash", 1),
        ("Closing cash", "cash", 1),
    ])
    print_table("ANNUAL CHECKS", results, [
        ("Assets - liabilities - equity", "balance_gap", 1),
        ("Cash minus minimum", "cash_headroom", 1),
    ])
    print(f"{'Cash at or above minimum':36}" + "".join(
        f"{'PASS' if row['cash_ok'] else 'FAIL':>14}" for row in results
    ))
    assert_balanced(results)

    pv_fcfe = sum(row["fcfe"] / (1 + COST_OF_EQUITY) ** t
                  for t, row in enumerate(results, 1))
    last = results[-1]
    terminal_value = ((last["fcfe"] + last["repayment"]) * (1 + TERMINAL_GROWTH)
                      / (COST_OF_EQUITY - TERMINAL_GROWTH))
    pv_terminal = terminal_value / (1 + COST_OF_EQUITY) ** len(results)
    equity_value = pv_fcfe + pv_terminal
    print(f"\nEquity value (USD millions): ${equity_value:,.2f}")
    print(f"Share of value after 2030: {pv_terminal / equity_value:.2%}")
    print(f"Value per share: ${equity_value / SHARES:,.2f}")


if __name__ == "__main__":
    main()
