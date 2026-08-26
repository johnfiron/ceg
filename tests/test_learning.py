import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from feeds.free_sources import SecEdgarSource
from learner.contracts import FeatureFrame, NlpSignal
from learner.calendar import next_session_date
from learner.horizons import HorizonHead
from learner.online import FTRLBinaryClassifier
from learner.runtime import LearningRuntime
from learner.store import LearningStore
from learner.validation import calibration_metrics, expanding_folds


NOW = datetime(2026, 8, 26, 15, 0, tzinfo=timezone.utc)


class LearningTests(unittest.TestCase):
    def test_feature_contract_rejects_lookahead_observation(self):
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            FeatureFrame(
                feature_ts=NOW.isoformat(),
                observed_at=(NOW - timedelta(seconds=1)).isoformat(),
                ticker="SPY",
                horizon_id="0DTE_15M",
                features={"rvol": 1.2},
                source_versions={"bars": "iex"},
            )

    def test_ftrl_learns_small_separable_stream_and_round_trips(self):
        model = FTRLBinaryClassifier(alpha=0.2, l1=0)
        for _ in range(120):
            model.update({"direction": 1}, 1)
            model.update({"direction": -1}, 0)
        self.assertGreater(model.predict({"direction": 1}), 0.8)
        self.assertLess(model.predict({"direction": -1}), 0.2)
        restored = FTRLBinaryClassifier.from_payload(model.payload())
        self.assertAlmostEqual(
            restored.predict({"direction": 1}),
            model.predict({"direction": 1}),
        )

    def test_horizon_heads_do_not_pool_updates(self):
        first = HorizonHead("0DTE_15M")
        second = HorizonHead("MONTHLY_20D")
        first.update({"x": 1}, 1, 0.2, "2026-08-26")
        self.assertEqual(first.stats.updates, 1)
        self.assertEqual(second.stats.updates, 0)

    def test_store_resolves_full_spread_label_only_after_due_time(self):
        con = sqlite3.connect(":memory:")
        store = LearningStore(con)
        store.init()
        frame = FeatureFrame(
            feature_ts=NOW.isoformat(),
            observed_at=NOW.isoformat(),
            ticker="SPY",
            horizon_id="0DTE_15M",
            features={"rvol": 1.2},
            source_versions={"bars": "iex"},
        )
        feature_id = store.save_feature(frame)
        due = NOW + timedelta(minutes=15)
        store.schedule_label(feature_id, due.isoformat(), 0.95, 1.00)
        row = store.pending_labels((due + timedelta(seconds=1)).isoformat())[0]
        with self.assertRaisesRegex(ValueError, "before its horizon"):
            store.resolve_label(row["id"], NOW.isoformat(), 1.10, 1.15, "TEST")
        result = store.resolve_label(
            row["id"], due.isoformat(), 1.10, 1.15, "TEST"
        )
        self.assertEqual(result["label"], 1)
        self.assertAlmostEqual(result["return"], 0.1)

    def test_walk_forward_purges_overlapping_payoff_intervals(self):
        rows = []
        for index in range(8):
            start = NOW + timedelta(minutes=index * 10)
            rows.append({
                "feature_ts": start.isoformat(),
                "label_ts": (start + timedelta(minutes=30)).isoformat(),
            })
        train, test = next(expanding_folds(rows, min_train=5, test_size=2))
        first_test = datetime.fromisoformat(test[0]["feature_ts"])
        self.assertTrue(all(
            datetime.fromisoformat(row["label_ts"]) < first_test for row in train
        ))

    def test_calibration_reports_brier_and_log_loss(self):
        metrics = calibration_metrics([0.9, 0.1], [1, 0])
        self.assertAlmostEqual(metrics["brier"], 0.01)
        self.assertGreater(metrics["log_loss"], 0)

    def test_market_calendar_skips_good_friday_and_weekend(self):
        self.assertEqual(next_session_date("2026-04-02"), "2026-04-06")

    def test_runtime_records_then_updates_only_from_fresh_due_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/learning.db"
            runtime = LearningRuntime(
                lambda: sqlite3.connect(path),
                f"{tmp}/models.json",
            )
            result = runtime.record_candidate(
                {
                    "strategy_id": "ORB", "ticker": "SPY", "direction": "CALL",
                    "score": 1.2, "ts": NOW.isoformat(),
                },
                {"sym": "SPY", "c": 650, "h": 651, "rvol": 1.1, "feed": "iex"},
                "0DTE_15M", NOW.isoformat(), "SPYOPT",
                {"bid": 0.95, "ask": 1.0, "spread": 0.05}, {"delta": 0.5, "iv": 0.2},
                (NOW + timedelta(minutes=15)).isoformat(),
            )
            self.assertEqual(result["lane"], "EXPLORE")
            stale = runtime.resolve_due(
                (NOW + timedelta(minutes=15)).isoformat(),
                lambda _: {"SPYOPT": {"bid": 1.1, "ask": 1.15, "age_sec": 30}},
                quote_max_age_sec=15,
            )
            self.assertEqual(stale, [])
            fresh = runtime.resolve_due(
                (NOW + timedelta(minutes=15)).isoformat(),
                lambda _: {"SPYOPT": {"bid": 1.1, "ask": 1.15, "age_sec": 1}},
                quote_max_age_sec=15,
            )
            self.assertEqual(fresh[0]["label"], 1)
            self.assertEqual(runtime.ensemble.heads["0DTE_15M"].stats.updates, 1)

    def test_sec_adapter_requires_identity_and_caches_source_observation(self):
        with self.assertRaisesRegex(ValueError, "contact email"):
            SecEdgarSource("anonymous")
        response=mock.Mock()
        response.json.return_value={"cik":"0000320193"}
        response.raise_for_status.return_value=None
        source=SecEdgarSource("ASH research ops@example.test",min_interval_sec=0)
        with mock.patch("feeds.free_sources.requests.get",return_value=response) as request:
            first=source.submissions("320193")
            second=source.submissions("320193")
        self.assertEqual(first["source"],"SEC_EDGAR")
        self.assertEqual(first["payload"],second["payload"])
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
