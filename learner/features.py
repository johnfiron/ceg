"""Causal numerical feature extraction from ASH market state."""
from datetime import datetime, timedelta
import math
from typing import Mapping

from .contracts import FeatureFrame, HORIZONS


EVENT_CLASSES = ("EARNINGS", "REGULATORY", "CAPITAL", "M_AND_A", "PRODUCT", "MACRO")


def _number(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _return(closes, periods):
    if len(closes) <= periods:
        return 0.0
    base = _number(closes[-periods - 1])
    return _number(closes[-1]) / base - 1.0 if base else 0.0


def build_features(sig: Mapping, state: Mapping, horizon_id: str,
                   observed_at: str, option_quote=None, greeks=None):
    if horizon_id not in HORIZONS:
        raise ValueError(f"unknown horizon {horizon_id}")
    quote = option_quote or {}
    greeks = greeks or {}
    closes = [_number(value) for value in state.get("closes") or []]
    direction = 1.0 if str(sig.get("direction")).upper() == "CALL" else -1.0
    features = {
        "bias": 1.0,
        "direction": direction,
        "signal_score": _number(sig.get("score")),
        "rvol": _number(state.get("rvol"), 1.0),
        "session_return": _number(state.get("ret") or state.get("gap_pct")),
        "gap_abs": abs(_number(state.get("gap_pct"))),
        "vwap_dist_atr": _number(state.get("vwap_dist_atr")),
        "rsi5_centered": (_number(state.get("rsi5"), 50) - 50.0) / 50.0,
        "drawdown_intraday": (
            _number(state.get("c")) / _number(state.get("h")) - 1.0
            if _number(state.get("h")) else 0.0
        ),
        "return_5": _return(closes, 5),
        "return_20": _return(closes, 20),
        "return_60": _return(closes, 60),
        "return_252": _return(closes, 252),
        "option_spread_pct": (
            _number(quote.get("spread"))
            / ((_number(quote.get("bid")) + _number(quote.get("ask"))) / 2)
            if _number(quote.get("bid")) + _number(quote.get("ask")) else 1.0
        ),
        "option_delta_abs": abs(_number(greeks.get("delta"))),
        "option_iv": _number(greeks.get("iv")),
    }
    nlp = state.get("news_nlp") or {}
    nlp_signal = None
    if nlp.get("status") == "READY":
        features.update({
            "nlp_available": 1.0,
            "nlp_sentiment": _number(nlp.get("sentiment")) * direction,
            "nlp_novelty": _number(nlp.get("novelty")),
            "nlp_confidence": _number(nlp.get("confidence")),
        })
        event = str(nlp.get("event_class") or "OTHER")
        for name in EVENT_CLASSES:
            features[f"event_{name.lower()}"] = 1.0 if event == name else 0.0
        from .contracts import NlpSignal
        nlp_signal = NlpSignal(
            content_hash=nlp["content_hash"],
            event_class=event,
            sentiment=nlp["sentiment"],
            novelty=nlp["novelty"],
            confidence=nlp["confidence"],
            model_version=nlp["model_version"],
            source_ts=nlp["source_ts"],
            inferred_at=nlp["inferred_at"],
            tickers=tuple(nlp.get("tickers") or ()),
            schema_version=nlp.get("schema_version") or "ash-learning/v1",
        )
    else:
        features.update({
            "nlp_available": 0.0,
            "nlp_sentiment": 0.0,
            "nlp_novelty": 0.0,
            "nlp_confidence": 0.0,
        })
    feature_ts = sig.get("ts") or observed_at
    return FeatureFrame(
        feature_ts=feature_ts,
        observed_at=observed_at,
        ticker=str(sig.get("ticker") or state.get("sym") or ""),
        horizon_id=horizon_id,
        features=features,
        source_versions={
            "bars": str(state.get("feed") or "unknown"),
            "options": "alpaca-indicative",
            "nlp": str(nlp.get("model_version") or "unavailable"),
        },
        nlp=nlp_signal,
    )


def intraday_due(feature_ts, horizon_id, close_hour=15, close_minute=49):
    start = datetime.fromisoformat(str(feature_ts).replace("Z", "+00:00"))
    spec = HORIZONS[horizon_id]
    if spec.label_minutes is not None:
        return start + timedelta(minutes=spec.label_minutes)
    if spec.label_sessions == 0:
        return start.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
    raise ValueError("session-based horizons require an exchange-calendar resolver")
