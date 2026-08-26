"""Signed, bounded-latency client for the required home NLP service."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import queue
import threading
import time
from typing import Mapping, Optional

import requests

from learner.contracts import CONTRACT_VERSION, NlpSignal


class NlpUnavailable(RuntimeError):
    pass


class NlpClient:
    def __init__(self, base_url, shared_secret, timeout=1.5,
                 failure_threshold=3, cooldown_sec=30):
        self.base_url = str(base_url or "").rstrip("/")
        self.secret = str(shared_secret or "").encode()
        if not self.base_url:
            raise ValueError("NLP base URL required")
        if len(self.secret) < 32:
            raise ValueError("NLP shared secret must contain at least 32 characters")
        self.timeout = max(0.1, float(timeout))
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_sec = max(1, int(cooldown_sec))
        self.failures = 0
        self.opened_at = None

    def _circuit_open(self):
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown_sec:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def _failed(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()

    def infer(self, payload: Mapping) -> NlpSignal:
        if self._circuit_open():
            raise NlpUnavailable("home NLP circuit open")
        body = json.dumps(dict(payload), separators=(",", ":"), sort_keys=True).encode()
        timestamp = f"{time.time():.6f}"
        signature = hmac.new(
            self.secret, timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        try:
            response = requests.post(
                self.base_url + "/v1/infer",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-ASH-Timestamp": timestamp,
                    "X-ASH-Signature": signature,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("signal") or {}
            if raw.get("schema_version") != CONTRACT_VERSION:
                raise NlpUnavailable("home NLP schema mismatch")
            signal = NlpSignal(
                content_hash=raw["content_hash"],
                event_class=raw["event_class"],
                sentiment=raw["sentiment"],
                novelty=raw["novelty"],
                confidence=raw["confidence"],
                model_version=raw["model_version"],
                source_ts=raw["source_ts"],
                inferred_at=raw["inferred_at"],
                tickers=tuple(raw.get("tickers") or ()),
                schema_version=raw["schema_version"],
            )
            self.failures = 0
            self.opened_at = None
            return signal
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            self._failed()
            raise NlpUnavailable(str(exc)) from exc


class NlpQueue:
    """One bounded worker keeps NLP network latency outside the runner cycle."""

    def __init__(self, client: NlpClient, max_pending=128, cache_ttl_sec=900):
        self.client = client
        self.pending = queue.Queue(maxsize=max(1, int(max_pending)))
        self.cache_ttl_sec = max(1, int(cache_ttl_sec))
        self.cache = {}
        self.errors = {}
        self.inflight = set()
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._work, name="ash-nlp", daemon=True)
        self._thread.start()

    @staticmethod
    def key(payload: Mapping):
        body = json.dumps(dict(payload), separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(body).hexdigest()

    def submit(self, payload: Mapping):
        key = self.key(payload)
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < self.cache_ttl_sec:
            return key, True
        with self._lock:
            if key in self.inflight:
                return key, True
            self.inflight.add(key)
        try:
            self.pending.put_nowait((key, dict(payload)))
            return key, True
        except queue.Full:
            with self._lock:
                self.inflight.discard(key)
            self.errors[key] = (time.monotonic(), "NLP queue full")
            return key, False

    def get(self, key: str) -> Optional[NlpSignal]:
        cached = self.cache.get(key)
        if not cached:
            return None
        if time.monotonic() - cached[0] >= self.cache_ttl_sec:
            self.cache.pop(key, None)
            return None
        return cached[1]

    def status(self, key: str):
        signal = self.get(key)
        error = self.errors.get(key)
        return {
            "ready": signal is not None,
            "error": error[1] if error else None,
            "queue_depth": self.pending.qsize(),
            "circuit_open": self.client._circuit_open(),
        }

    def stop(self):
        self._stopped.set()

    def _work(self):
        while not self._stopped.is_set():
            try:
                key, payload = self.pending.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self.cache[key] = (time.monotonic(), self.client.infer(payload))
                self.errors.pop(key, None)
            except NlpUnavailable as exc:
                self.errors[key] = (time.monotonic(), str(exc))
            finally:
                with self._lock:
                    self.inflight.discard(key)
                self.pending.task_done()
