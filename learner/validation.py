"""Chronological, overlap-aware evaluation helpers."""
from datetime import datetime, timedelta
import math
from typing import Iterable, Mapping, Sequence


def _dt(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("validation timestamps must include timezone")
    return parsed


def expanding_folds(rows: Sequence[Mapping], min_train=60, test_size=20,
                    embargo_minutes=0):
    """Yield train/test rows with payoff-overlap purging and an embargo."""
    ordered = sorted(rows, key=lambda row: _dt(row["feature_ts"]))
    start = max(1, int(min_train))
    size = max(1, int(test_size))
    embargo = timedelta(minutes=max(0, int(embargo_minutes)))
    for test_start in range(start, len(ordered), size):
        test = ordered[test_start:test_start + size]
        if not test:
            break
        first_test = _dt(test[0]["feature_ts"])
        last_test_end = max(_dt(row["label_ts"]) for row in test)
        train = []
        for row in ordered[:test_start]:
            feature_ts = _dt(row["feature_ts"])
            label_ts = _dt(row["label_ts"])
            overlaps = feature_ts <= last_test_end and label_ts >= first_test
            embargoed = label_ts + embargo >= first_test
            if not overlaps and not embargoed:
                train.append(row)
        if train:
            yield train, test


def calibration_metrics(probabilities: Iterable[float], labels: Iterable[int],
                        bins=10):
    pairs = [(float(p), int(y)) for p, y in zip(probabilities, labels)]
    if not pairs:
        return {"n": 0, "brier": None, "log_loss": None, "bins": []}
    eps = 1e-12
    brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs)
    log_loss = -sum(
        y * math.log(max(eps, min(1 - eps, p)))
        + (1 - y) * math.log(max(eps, min(1 - eps, 1 - p)))
        for p, y in pairs
    ) / len(pairs)
    buckets = []
    bins = max(2, int(bins))
    for index in range(bins):
        lo, hi = index / bins, (index + 1) / bins
        values = [(p, y) for p, y in pairs if lo <= p < hi or (index == bins - 1 and p == 1)]
        if values:
            buckets.append({
                "lo": lo,
                "hi": hi,
                "n": len(values),
                "predicted": sum(p for p, _ in values) / len(values),
                "observed": sum(y for _, y in values) / len(values),
            })
    return {
        "n": len(pairs),
        "brier": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "bins": buckets,
    }


def cost_metrics(returns: Iterable[float]):
    values = [float(value) for value in returns]
    gains = sum(value for value in values if value > 0)
    losses = sum(abs(value) for value in values if value < 0)
    return {
        "n": len(values),
        "expectancy": round(sum(values) / len(values), 8) if values else None,
        "profit_factor": round(gains / losses, 6) if losses else (999.0 if gains else 0.0),
        "win_rate": round(sum(value > 0 for value in values) / len(values), 6) if values else None,
    }
