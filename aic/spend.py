"""Project-wide API spend guard (cap US$30 for the whole project, per the brief).

Console spend limits are monthly, and this project spans two months, so the
total is also enforced here. Actual cost is computed from each batch's usage
figures when it is collected and logged in data/interim/spend_log.csv
(committed). Before a batch is submitted, logged spend plus the new estimate
must stay under the cap, and anything over US$10 needs an explicit yes from Luc.
"""

import csv

from aic import ROOT

CAP_USD = 30.00
ASK_ABOVE_USD = 10.00
BATCH_DISCOUNT = 0.5
PRICES = {  # US$ per 1M tokens (input, output), standard rates
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
}
LOG = ROOT / "data/interim/spend_log.csv"
FIELDS = ["batch_id", "script", "model", "requests", "input_tokens", "output_tokens", "cost_usd"]


def usage_cost(model: str, usage: dict, batch: bool = True) -> float:
    p_in, p_out = PRICES[model]
    inp = (usage.get("input_tokens") or 0) + 1.25 * (usage.get("cache_creation_input_tokens") or 0) \
        + 0.1 * (usage.get("cache_read_input_tokens") or 0)
    cost = (inp * p_in + (usage.get("output_tokens") or 0) * p_out) / 1e6
    return cost * (BATCH_DISCOUNT if batch else 1)


def entries() -> list[dict]:
    return list(csv.DictReader(LOG.open())) if LOG.exists() else []


def spent() -> float:
    return sum(float(e["cost_usd"]) for e in entries())


def pending() -> float:
    """Estimates of batches submitted but not yet collected (from each pass's batches.jsonl)."""
    import json

    collected = {e["batch_id"] for e in entries()}
    total = 0.0
    for log in (ROOT / "data/interim/pass_a/batches.jsonl", ROOT / "data/interim/pass_b/batches.jsonl"):
        if log.exists():
            for line in log.read_text().splitlines():
                b = json.loads(line)
                if b["batch_id"] not in collected:
                    total += float(b.get("estimate_usd") or 0)
    return total


def record(batch_id: str, script: str, model: str, usages: list[dict]) -> float:
    """Log a collected batch's actual cost (replacing any earlier entry for the same batch)."""
    cost = sum(usage_cost(model, u) for u in usages)
    rows = [e for e in entries() if e["batch_id"] != batch_id]
    rows.append({"batch_id": batch_id, "script": script, "model": model, "requests": len(usages),
                 "input_tokens": sum(u.get("input_tokens") or 0 for u in usages),
                 "output_tokens": sum(u.get("output_tokens") or 0 for u in usages), "cost_usd": f"{cost:.4f}"})
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    return cost


def check_budget(estimate: float) -> str | None:
    """Return a reason to refuse, or None if the batch fits the budget."""
    total, waiting = spent(), pending()
    if total + waiting + estimate > CAP_USD:
        return (f"would exceed the US${CAP_USD:.0f} project cap (spent US${total:.2f} + in flight "
                f"US${waiting:.2f} + this estimate US${estimate:.2f})")
    return None
