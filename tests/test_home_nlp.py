import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from feeds.nlp_client import NlpClient, NlpUnavailable
from home_nlp.model import FinanceHeadlineModel
from home_nlp.server import create_app
from home_nlp.train_teacher import _load, _split


SECRET = "test-secret-" + "x" * 32


class HomeNlpTests(unittest.TestCase):
    def setUp(self):
        self.secret = mock.patch.dict(os.environ, {"ASH_NLP_SHARED_SECRET": SECRET})
        self.secret.start()
        self.client = create_app(FinanceHeadlineModel()).test_client()

    def tearDown(self):
        self.secret.stop()

    @staticmethod
    def payload():
        return {
            "headline": "Company beats earnings and raises guidance",
            "source": "wire",
            "source_ts": datetime.now(timezone.utc).isoformat(),
            "tickers": ["XYZ"],
        }

    def _signed(self, body, timestamp=None):
        timestamp = timestamp or f"{time.time():.6f}"
        signature = hmac.new(
            SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        return {"X-ASH-Timestamp": timestamp, "X-ASH-Signature": signature}

    def test_signed_inference_returns_versioned_finance_signal(self):
        body = json.dumps(self.payload(), separators=(",", ":"), sort_keys=True).encode()
        response = self.client.post(
            "/v1/infer", data=body, content_type="application/json",
            headers=self._signed(body),
        )
        self.assertEqual(response.status_code, 200)
        signal = response.get_json()["signal"]
        self.assertEqual(signal["event_class"], "EARNINGS")
        self.assertGreater(signal["sentiment"], 0)
        self.assertEqual(signal["tickers"], ["XYZ"])

    def test_unsigned_and_replayed_requests_fail_closed(self):
        body = json.dumps(self.payload()).encode()
        self.assertEqual(
            self.client.post("/v1/infer", data=body).status_code, 401
        )
        old = f"{time.time() - 120:.6f}"
        self.assertEqual(
            self.client.post("/v1/infer", data=body, headers=self._signed(body, old)).status_code,
            401,
        )

    def test_client_opens_circuit_after_repeated_failures(self):
        client = NlpClient("http://nlp.test", SECRET, failure_threshold=2)
        with mock.patch(
            "feeds.nlp_client.requests.post",
            side_effect=requests.ConnectionError("down"),
        ):
            with self.assertRaises(NlpUnavailable):
                client.infer(self.payload())
            with self.assertRaises(NlpUnavailable):
                client.infer(self.payload())
            with self.assertRaisesRegex(NlpUnavailable, "circuit open"):
                client.infer(self.payload())

    def test_teacher_dataset_split_is_chronological_and_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"labels.jsonl"
            rows=[]
            for index in range(100):
                rows.append(json.dumps({
                    "headline":f"headline {index}",
                    "label":("negative","neutral","positive")[index%3],
                    "source_ts":f"2026-01-{1+index//24:02d}T{index%24:02d}:00:00+00:00",
                }))
            path.write_text("\n".join(rows))
            loaded,digest=_load(path)
            train,calibration,test=_split(loaded)
        self.assertEqual((len(train),len(calibration),len(test)),(70,15,15))
        self.assertLess(train[-1]["source_ts"],calibration[0]["source_ts"])
        self.assertLess(calibration[-1]["source_ts"],test[0]["source_ts"])
        self.assertEqual(len(digest),64)


if __name__ == "__main__":
    unittest.main()
