"""SQLite point-in-time evidence store for predictions and delayed labels."""
from datetime import datetime
import json
import sqlite3

from .contracts import FeatureFrame, NlpSignal


SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_nlp_signals(
  content_hash TEXT PRIMARY KEY, source_ts TEXT NOT NULL, inferred_at TEXT NOT NULL,
  event_class TEXT NOT NULL, sentiment REAL NOT NULL, novelty REAL NOT NULL,
  confidence REAL NOT NULL, model_version TEXT NOT NULL, schema_version TEXT NOT NULL,
  tickers TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_features(
  id INTEGER PRIMARY KEY AUTOINCREMENT, feature_ts TEXT NOT NULL, observed_at TEXT NOT NULL,
  ticker TEXT NOT NULL, horizon_id TEXT NOT NULL, features TEXT NOT NULL,
  source_versions TEXT NOT NULL, nlp_hash TEXT, schema_version TEXT NOT NULL,
  UNIQUE(feature_ts,ticker,horizon_id)
);
CREATE TABLE IF NOT EXISTS learning_predictions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, feature_id INTEGER NOT NULL,
  predicted_at TEXT NOT NULL, model_version TEXT NOT NULL, probability REAL NOT NULL,
  lane TEXT NOT NULL, payload TEXT,
  UNIQUE(feature_id,model_version)
);
CREATE TABLE IF NOT EXISTS learning_labels(
  id INTEGER PRIMARY KEY AUTOINCREMENT, feature_id INTEGER NOT NULL,
  due_at TEXT NOT NULL, resolved_at TEXT, entry_bid REAL, entry_ask REAL,
  exit_bid REAL, exit_ask REAL, full_spread_return REAL, label INTEGER,
  source TEXT, payload TEXT, UNIQUE(feature_id,due_at)
);
CREATE TABLE IF NOT EXISTS learning_models(
  horizon_id TEXT PRIMARY KEY, model_version TEXT NOT NULL, state TEXT NOT NULL,
  updated_at TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_trials(
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
  horizon_id TEXT NOT NULL, code_version TEXT NOT NULL, data_hash TEXT NOT NULL,
  specification TEXT NOT NULL, result TEXT
);
CREATE INDEX IF NOT EXISTS idx_learning_labels_due
  ON learning_labels(resolved_at,due_at);
CREATE INDEX IF NOT EXISTS idx_learning_features_horizon
  ON learning_features(horizon_id,ticker,feature_ts);
"""


def _parse(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


class LearningStore:
    def __init__(self, connection):
        self.con = connection
        self.con.row_factory = sqlite3.Row

    def init(self):
        self.con.executescript(SCHEMA)
        self.con.commit()

    def save_nlp(self, signal: NlpSignal):
        payload = signal.as_dict()
        self.con.execute(
            """INSERT OR IGNORE INTO learning_nlp_signals(
                 content_hash,source_ts,inferred_at,event_class,sentiment,novelty,
                 confidence,model_version,schema_version,tickers,payload)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                signal.content_hash, signal.source_ts, signal.inferred_at,
                signal.event_class, signal.sentiment, signal.novelty,
                signal.confidence, signal.model_version, signal.schema_version,
                json.dumps(list(signal.tickers)), json.dumps(payload, separators=(",", ":")),
            ),
        )
        self.con.commit()

    def save_feature(self, frame: FeatureFrame):
        if frame.nlp:
            self.save_nlp(frame.nlp)
        self.con.execute(
            """INSERT INTO learning_features(
                 feature_ts,observed_at,ticker,horizon_id,features,source_versions,
                 nlp_hash,schema_version)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(feature_ts,ticker,horizon_id) DO UPDATE SET
                 observed_at=excluded.observed_at,features=excluded.features,
                 source_versions=excluded.source_versions,nlp_hash=excluded.nlp_hash""",
            (
                frame.feature_ts, frame.observed_at, frame.ticker, frame.horizon_id,
                json.dumps(frame.features, separators=(",", ":"), sort_keys=True),
                json.dumps(frame.source_versions, separators=(",", ":"), sort_keys=True),
                frame.nlp.content_hash if frame.nlp else None, frame.schema_version,
            ),
        )
        row = self.con.execute(
            """SELECT id FROM learning_features
               WHERE feature_ts=? AND ticker=? AND horizon_id=?""",
            (frame.feature_ts, frame.ticker, frame.horizon_id),
        ).fetchone()
        self.con.commit()
        return int(row["id"])

    def save_prediction(self, feature_id, predicted_at, model_version,
                        probability, lane, payload=None):
        probability = float(probability)
        if not 0 <= probability <= 1:
            raise ValueError("probability outside [0,1]")
        self.con.execute(
            """INSERT OR REPLACE INTO learning_predictions(
                 feature_id,predicted_at,model_version,probability,lane,payload)
               VALUES(?,?,?,?,?,?)""",
            (
                int(feature_id), _parse(predicted_at).isoformat(), str(model_version),
                probability, str(lane), json.dumps(payload or {}, separators=(",", ":")),
            ),
        )
        self.con.commit()

    def schedule_label(self, feature_id, due_at, entry_bid, entry_ask, payload=None):
        due = _parse(due_at).isoformat()
        self.con.execute(
            """INSERT OR IGNORE INTO learning_labels(
                 feature_id,due_at,entry_bid,entry_ask,payload)
               VALUES(?,?,?,?,?)""",
            (
                int(feature_id), due, float(entry_bid), float(entry_ask),
                json.dumps(payload or {}, separators=(",", ":")),
            ),
        )
        self.con.commit()

    def pending_labels(self, as_of, limit=100):
        rows = self.con.execute(
            """SELECT l.*,f.ticker,f.horizon_id,f.feature_ts,f.features
               FROM learning_labels l JOIN learning_features f ON f.id=l.feature_id
               WHERE l.resolved_at IS NULL AND l.due_at<=?
               ORDER BY l.due_at,l.id LIMIT ?""",
            (_parse(as_of).isoformat(), max(1, int(limit))),
        ).fetchall()
        return [dict(row) for row in rows]

    def resolve_label(self, label_id, resolved_at, exit_bid, exit_ask, source, payload=None):
        row = self.con.execute(
            "SELECT * FROM learning_labels WHERE id=?", (int(label_id),)
        ).fetchone()
        if not row:
            raise ValueError("label not found")
        resolved = _parse(resolved_at)
        if resolved < _parse(row["due_at"]):
            raise ValueError("cannot resolve a label before its horizon")
        entry_ask = float(row["entry_ask"] or 0)
        if entry_ask <= 0:
            raise ValueError("entry ask must be positive")
        full_spread_return = (float(exit_bid) - entry_ask) / entry_ask
        label = 1 if full_spread_return > 0 else 0
        self.con.execute(
            """UPDATE learning_labels SET resolved_at=?,exit_bid=?,exit_ask=?,
                 full_spread_return=?,label=?,source=?,payload=? WHERE id=?""",
            (
                resolved.isoformat(), float(exit_bid), float(exit_ask),
                round(full_spread_return, 8), label, str(source),
                json.dumps(payload or {}, separators=(",", ":")), int(label_id),
            ),
        )
        self.con.commit()
        return {"return": round(full_spread_return, 8), "label": label}
