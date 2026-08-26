"""Resource-bounded scoring and delayed online updates."""
from datetime import datetime
import json
from pathlib import Path
import threading

from .features import build_features, intraday_due
from .horizons import HorizonEnsemble
from .store import LearningStore


RUNTIME_VERSION = "ash-learning-runtime/v1"


class LearningRuntime:
    def __init__(self, connection_factory, model_path):
        self.connection_factory = connection_factory
        self.model_path = Path(model_path)
        self.lock = threading.Lock()
        self.ensemble = (
            HorizonEnsemble.load(self.model_path)
            if self.model_path.exists() else HorizonEnsemble()
        )

    def record_candidate(self, sig, state, horizon_id, observed_at,
                         option_symbol, quote, greeks, due_at=None):
        frame = build_features(sig, state, horizon_id, observed_at, quote, greeks)
        with self.lock:
            head = self.ensemble.heads[horizon_id]
            probability = head.predict(frame.features)
            lane = head.lane()
            con = self.connection_factory()
            try:
                store = LearningStore(con)
                store.init()
                feature_id = store.save_feature(frame)
                store.save_prediction(
                    feature_id, observed_at, head.model.payload()["version"],
                    probability, lane,
                    {"runtime": RUNTIME_VERSION, "option_symbol": option_symbol},
                )
                due = (
                    datetime.fromisoformat(str(due_at).replace("Z", "+00:00"))
                    if due_at else intraday_due(frame.feature_ts, horizon_id)
                )
                if due <= datetime.fromisoformat(frame.feature_ts):
                    raise ValueError("candidate arrived after its label horizon")
                store.schedule_label(
                    feature_id, due.isoformat(), quote.get("bid"), quote.get("ask"),
                    {"option_symbol": option_symbol, "horizon_id": horizon_id},
                )
            finally:
                con.close()
        return {
            "feature_id": feature_id,
            "horizon_id": horizon_id,
            "probability": round(probability, 6),
            "lane": lane,
            "due_at": due.isoformat(),
            "model_version": head.model.payload()["version"],
        }

    def resolve_due(self, as_of, quote_provider, quote_max_age_sec=15, limit=50):
        with self.lock:
            con = self.connection_factory()
            updated = []
            try:
                store = LearningStore(con)
                store.init()
                pending = store.pending_labels(as_of, limit)
                symbols = sorted({
                    (json.loads(row.get("payload") or "{}")).get("option_symbol")
                    for row in pending
                } - {None})
                quotes = quote_provider(symbols) if symbols else {}
                for row in pending:
                    payload = json.loads(row.get("payload") or "{}")
                    quote = quotes.get(payload.get("option_symbol")) or {}
                    if quote.get("bid") is None or quote.get("ask") is None:
                        continue
                    age = quote.get("age_sec")
                    if age is None or float(age) > float(quote_max_age_sec):
                        continue
                    outcome = store.resolve_label(
                        row["id"], as_of, quote["bid"], quote["ask"],
                        "ALPACA_INDICATIVE", {"quote": quote},
                    )
                    prediction = con.execute(
                        """SELECT probability FROM learning_predictions
                           WHERE feature_id=? ORDER BY id DESC LIMIT 1""",
                        (row["feature_id"],),
                    ).fetchone()
                    features = json.loads(row["features"])
                    head = self.ensemble.heads[row["horizon_id"]]
                    predicted = float(prediction["probability"]) if prediction else head.predict(features)
                    head.model.update(features, outcome["label"])
                    head.stats.update(
                        predicted, outcome["label"], outcome["return"], row["feature_ts"][:10]
                    )
                    updated.append({
                        "label_id": row["id"],
                        "horizon_id": row["horizon_id"],
                        **outcome,
                    })
                if updated:
                    self.model_path.parent.mkdir(parents=True, exist_ok=True)
                    self.ensemble.save(self.model_path)
            finally:
                con.close()
            return updated
