"""Versioned contracts shared by collection, inference, and validation."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, Mapping, Optional, Tuple


CONTRACT_VERSION = "ash-learning/v1"


@dataclass(frozen=True)
class HorizonSpec:
    id: str
    label_minutes: Optional[int]
    label_sessions: Optional[int]
    min_dte: int
    max_dte: int
    scan_cadence_sec: int


HORIZONS: Mapping[str, HorizonSpec] = {
    "0DTE_15M": HorizonSpec("0DTE_15M", 15, None, 0, 0, 30),
    "0DTE_60M": HorizonSpec("0DTE_60M", 60, None, 0, 0, 30),
    "0DTE_CLOSE": HorizonSpec("0DTE_CLOSE", None, 0, 0, 0, 30),
    "WEEKLY_1D": HorizonSpec("WEEKLY_1D", None, 1, 3, 10, 300),
    "WEEKLY_5D": HorizonSpec("WEEKLY_5D", None, 5, 7, 21, 300),
    "MONTHLY_20D": HorizonSpec("MONTHLY_20D", None, 20, 30, 60, 900),
}


def _iso(value: str) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.isoformat()


@dataclass(frozen=True)
class NlpSignal:
    content_hash: str
    event_class: str
    sentiment: float
    novelty: float
    confidence: float
    model_version: str
    source_ts: str
    inferred_at: str
    tickers: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = CONTRACT_VERSION

    def __post_init__(self):
        if len(self.content_hash) != 64:
            raise ValueError("content_hash must be sha256 hex")
        for name in ("sentiment", "novelty"):
            value = float(getattr(self, name))
            if value < -1.0 or value > 1.0:
                raise ValueError(f"{name} outside [-1,1]")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence outside [0,1]")
        object.__setattr__(self, "source_ts", _iso(self.source_ts))
        object.__setattr__(self, "inferred_at", _iso(self.inferred_at))

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["tickers"] = list(self.tickers)
        return payload


@dataclass(frozen=True)
class FeatureFrame:
    feature_ts: str
    observed_at: str
    ticker: str
    horizon_id: str
    features: Dict[str, float]
    source_versions: Dict[str, str]
    nlp: Optional[NlpSignal] = None
    schema_version: str = CONTRACT_VERSION

    def __post_init__(self):
        if self.horizon_id not in HORIZONS:
            raise ValueError(f"unknown horizon {self.horizon_id}")
        object.__setattr__(self, "feature_ts", _iso(self.feature_ts))
        object.__setattr__(self, "observed_at", _iso(self.observed_at))
        if datetime.fromisoformat(self.observed_at) < datetime.fromisoformat(self.feature_ts):
            raise ValueError("observed_at cannot precede feature_ts")
        clean = {}
        for key, value in self.features.items():
            number = float(value)
            if number != number or number in (float("inf"), float("-inf")):
                raise ValueError(f"non-finite feature {key}")
            clean[str(key)] = number
        object.__setattr__(self, "features", clean)

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["nlp"] = self.nlp.as_dict() if self.nlp else None
        return payload
