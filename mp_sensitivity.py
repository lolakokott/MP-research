"""Lab 11 one-at-a-time sensitivities for the unchanged Lab 10 model.

Usage: python3 mp_sensitivity.py
Selected ranges affect 2026-2030: gross margin 12.10%/14.10%/16.10%,
and capex 90%/100%/110% of the existing base path (USD millions).
All sensitivity results are printed directly in the terminal.
"""

from copy import deepcopy
from decimal import Decimal
import math
import sys

# Keep importing the model from creating bytecode cache files.
sys.dont_write_bytecode = True
import mp_proforma as model


UNITS = {
    "GROWTH": "annual decimal rate", "GROSS_MARGIN": "fraction of revenue",
    "SGA_RATIO": "multiple of pre-DD&A gross profit",
    "DEPRECIATION_RATIO": "fraction of opening net PP&E",
    "INVENTORY_DAYS": "days", "TAX_RATE": "fraction of positive pretax income",
    "FLOOR_PLAN_RATIO": "fraction of inventory",
    "FLOOR_PLAN_RATE": "annual decimal rate", "IMPAIRMENT": "USD millions",
    "REPAYMENT": "USD millions", "BUYBACK": "USD millions",
    "OTHER_WC_RATIO": "fraction of incremental revenue",
    "MINIMUM_CASH": "USD millions", "REVOLVER_RATE": "annual decimal rate",
    "DEBT_RATE": "annual decimal rate", "REVOLVER_LIMIT": "USD millions",
    "CAPEX": "USD millions", "NEW_DEBT": "USD millions",
    "NDPR_SALES_VOLUME": "metric tons of NdPr oxide equivalent",
    "COST_OF_EQUITY": "annual decimal rate",
    "TERMINAL_GROWTH": "annual decimal rate", "SHARES": "millions of shares",
}
OUTPUT_UNITS = {"operating_profit": "USD millions", "fcfe": "USD millions",
                "value_per_share": "USD/share"}


def validate_drivers(config, base):
    drivers = config["drivers"]
    if len(drivers) != 2 or len({d["name"] for d in drivers}) != 2:
        raise ValueError("Specify exactly two distinct drivers.")
    for driver in drivers:
        name, years = driver["name"], driver["years"]
        if name not in UNITS:
            raise ValueError(f"Unknown independent driver: {name}")
        if not years or len(set(years)) != len(years) or any(y not in model.YEARS for y in years):
            raise ValueError(f"{name}: specify distinct forecast years.")
        valuation = name in base["valuation"]
        if valuation and set(years) != set(model.YEARS):
            raise ValueError(f"{name} is a whole-valuation input; specify all forecast years.")
        for level in ("lower", "base", "higher"):
            values = driver[level]
            if set(values) != {str(y) for y in years}:
                raise ValueError(f"{name}/{level}: supply exactly the selected years.")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in values.values()):
                raise ValueError(f"{name}/{level}: finite numeric values required.")
            if valuation and len(set(values.values())) != 1:
                raise ValueError(f"{name}: the existing valuation uses one constant value.")
        for year in years:
            key = str(year)
            expected = base["valuation"][name] if valuation else base["annual"][year][name]
            if driver["base"][key] != expected:
                raise ValueError(f"{name}/{year}: supplied base differs from preserved base {expected}.")
            if not driver["lower"][key] <= expected <= driver["higher"][key]:
                raise ValueError(f"{name}/{year}: require lower <= base <= higher.")
    return drivers


def evaluate(inputs):
    """Keep signed FCFE and all check failures; never repair a failed scenario."""
    run = {"inputs": deepcopy(inputs), "statements": [], "checks": [],
           "valid": False, "outputs": dict.fromkeys(OUTPUT_UNITS),
           "valuation": {"available": False}}
    try:
        rows = model.project(inputs)
        run["statements"] = rows
        for row in rows:
            finite = all(math.isfinite(v) for v in row.values() if isinstance(v, (int, float)))
            check = {
                "year": row["year"], "balance_gap_USD_millions": row["balance_gap"],
                "cash_headroom_USD_millions": row["cash_headroom"],
                "revolver_USD_millions": row["revolver"],
                "revolver_limit_USD_millions": row["revolver_limit"],
                "finite": finite,
                "balance_pass": abs(row["balance_gap"]) <= model.TOLERANCE,
                "cash_pass": row["cash_headroom"] >= -model.TOLERANCE,
                "revolver_pass": -model.TOLERANCE <= row["revolver"] <= row["revolver_limit"] + model.TOLERANCE,
            }
            check["pass"] = all(check[k] for k in ("finite", "balance_pass", "cash_pass", "revolver_pass"))
            run["checks"].append(check)
        run["valid"] = all(c["pass"] for c in run["checks"])
        run["outputs"].update(operating_profit=rows[-1]["operating_income"], fcfe=rows[-1]["fcfe"])
        if not run["valid"]:
            run["valuation"]["reason"] = "Accounting or liquidity check failed; excluded from spans and comparisons."
            return run
        model.assert_balanced(rows)
        assumptions = inputs["valuation"]
        rate, growth, shares = (assumptions[k] for k in ("COST_OF_EQUITY", "TERMINAL_GROWTH", "SHARES"))
        terminal_fcfe = rows[-1]["fcfe"] + rows[-1]["repayment"]
        if rows[-1]["fcfe"] <= 0 or terminal_fcfe <= 0:
            run["valuation"]["reason"] = (
                "Final-year FCFE is nonpositive: the existing terminal-value condition fails. "
                "The legacy zero-value fallback is not reported as a valid valuation. Signed FCFE is retained.")
        elif rate <= growth or rate <= -1 or growth <= -1 or shares <= 0:
            run["valuation"]["reason"] = "Invalid discount rate, terminal growth, or share denominator."
        else:
            # Preserve the existing classroom positive-only explicit FCFE rule.
            explicit_pv = sum(max(0.0, r["fcfe"]) / (1 + rate) ** t for t, r in enumerate(rows, 1))
            terminal_value = terminal_fcfe * (1 + growth) / (rate - growth)
            terminal_pv = terminal_value / (1 + rate) ** len(rows)
            price = (explicit_pv + terminal_pv) / shares
            if not math.isfinite(price):
                raise ValueError("Nonfinite valuation result.")
            run["outputs"]["value_per_share"] = price
            run["valuation"] = {"available": True, "explicit_pv": explicit_pv,
                                "terminal_value": terminal_value, "terminal_pv": terminal_pv,
                                "limitation": "Existing classroom method: negative explicit FCFE excluded from valuation; preferred/conversion rights not separately valued."}
    except (ValueError, ArithmeticError) as error:
        run["valid"] = False
        run["outputs"]["value_per_share"] = None
        run["valuation"] = {"available": False, "reason": str(error)}
    return run


def analyze(config):
    base_inputs = model.fresh_base_inputs()
    drivers = validate_drivers(config, base_inputs)
    base = evaluate(deepcopy(base_inputs))
    report = {"base_inputs": base_inputs, "initial_base": base,
              "final_year": max(model.YEARS), "cash_flow_label": "FCFE",
              "output_units": OUTPUT_UNITS, "sensitivities": []}
    for driver in drivers:
        name = driver["name"]
        group = {"driver": name, "input_units": UNITS[name], "years": driver["years"], "runs": {}}
        for level in ("lower", "base", "higher"):
            inputs = deepcopy(base_inputs)
            for year in driver["years"]:
                target = inputs["valuation"] if name in inputs["valuation"] else inputs["annual"][year]
                target[name] = driver[level][str(year)]
            run = evaluate(inputs)
            run["selected_input_values"] = deepcopy(driver[level])
            run["changes_from_base"] = {
                key: (run["outputs"][key] - base["outputs"][key]
                      if run["valid"] and base["valid"] and run["outputs"][key] is not None
                      and base["outputs"][key] is not None else None)
                for key in OUTPUT_UNITS}
            group["runs"][level] = run
        group["spans"] = {}
        for key in OUTPUT_UNITS:
            values = [r["outputs"][key] for r in group["runs"].values()
                      if r["valid"] and r["outputs"][key] is not None]
            group["spans"][key] = {"value": max(values) - min(values) if values else None,
                                    "valid_count": len(values), "units": OUTPUT_UNITS[key]}
        report["sensitivities"].append(group)
    # An explicit final base rerun, using another fresh copy, verifies restoration.
    report["restored_base"] = evaluate(model.fresh_base_inputs())
    report["base_restored"] = report["restored_base"] == base and model.fresh_base_inputs() == base_inputs
    if not report["base_restored"]:
        raise AssertionError("Base restoration failed.")
    return report


def display(report):
    print(f"Final-year outputs: FY{report['final_year']}; free cash flow label: FCFE")
    for group in report["sensitivities"]:
        print(f"\n{group['driver']} ({group['input_units']}); changed years: {group['years']}")
        for level, run in group["runs"].items():
            print(f"  {level}: inputs={run['selected_input_values']}; {'PASS' if run['valid'] else 'INVALID'}")
            for key, units in OUTPUT_UNITS.items():
                value, delta = run["outputs"][key], run["changes_from_base"][key]
                v = f"{value:,.6f}" if value is not None else "N/A"
                d = f"{delta:+,.6f}" if delta is not None else "N/A"
                print(f"    {key}: {v} {units}; change from base: {d} {units}")
            for check in run["checks"]:
                print(f"    CHECK {check['year']}: {'PASS' if check['pass'] else 'FAIL'}; "
                      f"balance gap={check['balance_gap_USD_millions']:+.9f}; "
                      f"cash headroom={check['cash_headroom_USD_millions']:+.6f}; "
                      f"revolver={check['revolver_USD_millions']:.6f}/{check['revolver_limit_USD_millions']:.6f} USD millions")
            print("    Valuation:", run["valuation"].get("reason", run["valuation"].get("limitation")))
        for key, span in group["spans"].items():
            value = "N/A" if span["value"] is None else f"{span['value']:,.6f}"
            print(f"  Span {key}: {value} {span['units']} ({span['valid_count']}/3 valid results)")
    print("\nBase restored and rerun:", "PASS" if report["base_restored"] else "FAIL")
    for check in report["restored_base"]["checks"]:
        print(f"  Base FY{check['year']} accounting/liquidity: {'PASS' if check['pass'] else 'FAIL'}")


def selected_config():
    """Use the selected ranges; derive capex from the preserved model base."""
    years = list(range(2026, 2031))
    base = model.fresh_base_inputs()
    return {"drivers": [
        {"name": "GROSS_MARGIN", "years": years,
         "lower": {str(y): 0.121 for y in years},
         "base": {str(y): 0.141 for y in years},
         "higher": {str(y): 0.161 for y in years}},
        {"name": "CAPEX", "years": years,
         **{level: {str(y): float(Decimal(str(base["annual"][y]["CAPEX"])) * factor)
                    for y in years}
            for level, factor in (("lower", Decimal("0.9")),
                                  ("base", Decimal("1")),
                                  ("higher", Decimal("1.1")))}}
    ]}


def main():
    report = analyze(selected_config())
    display(report)


if __name__ == "__main__":
    main()
