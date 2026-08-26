"""Independent delayed-label learners for each option horizon."""
from dataclasses import dataclass, field
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Dict, Mapping

from .contracts import HORIZONS
from .online import FTRLBinaryClassifier, MODEL_VERSION


HEAD_VERSION = "ash-horizon-head/v1"


@dataclass
class HeadStats:
    updates: int = 0
    brier_sum: float = 0.0
    gross_win: float = 0.0
    gross_loss: float = 0.0
    wins: int = 0
    days: set = field(default_factory=set)

    def update(self, probability, label, realized_return, trade_day):
        self.updates += 1
        self.brier_sum += (float(probability) - int(label)) ** 2
        if realized_return > 0:
            self.gross_win += float(realized_return)
            self.wins += 1
        elif realized_return < 0:
            self.gross_loss += abs(float(realized_return))
        if trade_day:
            self.days.add(str(trade_day)[:10])

    def metrics(self):
        pf = self.gross_win / self.gross_loss if self.gross_loss else (
            999.0 if self.gross_win else 0.0
        )
        alpha, beta = 1 + self.wins, 1 + self.updates - self.wins
        mean = alpha / (alpha + beta)
        sd = math.sqrt(alpha * beta / (((alpha + beta) ** 2) * (alpha + beta + 1)))
        return {
            "updates": self.updates,
            "days": len(self.days),
            "brier": round(self.brier_sum / self.updates, 6) if self.updates else None,
            "profit_factor": round(pf, 4),
            "win_probability": round(mean, 4),
            "win_probability_lower": round(max(0.0, mean - 1.64 * sd), 4),
        }

    def payload(self):
        return {
            "updates": self.updates,
            "brier_sum": self.brier_sum,
            "gross_win": self.gross_win,
            "gross_loss": self.gross_loss,
            "wins": self.wins,
            "days": sorted(self.days),
        }

    @classmethod
    def from_payload(cls, payload):
        return cls(
            updates=int(payload.get("updates") or 0),
            brier_sum=float(payload.get("brier_sum") or 0),
            gross_win=float(payload.get("gross_win") or 0),
            gross_loss=float(payload.get("gross_loss") or 0),
            wins=int(payload.get("wins") or 0),
            days=set(payload.get("days") or ()),
        )


class HorizonHead:
    def __init__(self, horizon_id, model=None, stats=None):
        if horizon_id not in HORIZONS:
            raise ValueError(f"unknown horizon {horizon_id}")
        self.horizon_id = horizon_id
        self.model = model or FTRLBinaryClassifier()
        self.stats = stats or HeadStats()

    def predict(self, features: Mapping[str, float]):
        return self.model.predict(features)

    def update(self, features, label, realized_return, trade_day, weight=1.0):
        probability = self.model.update(features, int(label), weight)
        self.stats.update(probability, int(label), float(realized_return), trade_day)
        return probability

    def lane(self, min_days=30, min_profit_factor=1.15,
             max_brier=0.25, min_lower_win=0.45):
        metrics = self.stats.metrics()
        if metrics["days"] < int(min_days):
            return "EXPLORE"
        if (
            metrics["profit_factor"] >= float(min_profit_factor)
            and metrics["brier"] is not None
            and metrics["brier"] <= float(max_brier)
            and metrics["win_probability_lower"] >= float(min_lower_win)
        ):
            return "ACTIVE"
        return "PAUSED"

    def payload(self):
        return {
            "version": HEAD_VERSION,
            "horizon_id": self.horizon_id,
            "model": self.model.payload(),
            "stats": self.stats.payload(),
        }

    @classmethod
    def from_payload(cls, payload):
        if payload.get("version") != HEAD_VERSION:
            raise ValueError("unsupported horizon head version")
        return cls(
            payload["horizon_id"],
            FTRLBinaryClassifier.from_payload(payload["model"]),
            HeadStats.from_payload(payload["stats"]),
        )


class HorizonEnsemble:
    def __init__(self):
        self.heads: Dict[str, HorizonHead] = {
            horizon_id: HorizonHead(horizon_id) for horizon_id in HORIZONS
        }

    def payload(self):
        return {
            "version": HEAD_VERSION,
            "saved_at": datetime.now().astimezone().isoformat(),
            "heads": {key: head.payload() for key, head in self.heads.items()},
        }

    def save(self, path):
        target = Path(path)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(self.payload(), separators=(",", ":"), sort_keys=True))
        temporary.replace(target)

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text())
        if payload.get("version") != HEAD_VERSION:
            raise ValueError("unsupported ensemble version")
        ensemble = cls()
        ensemble.heads = {
            key: HorizonHead.from_payload(value)
            for key, value in payload.get("heads", {}).items()
        }
        return ensemble
