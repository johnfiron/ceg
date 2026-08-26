#!/usr/bin/env python3
"""Private ASH NLP API. Bind to a Tailscale address in production."""
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import threading

from flask import Flask, jsonify, request

from home_nlp.model import FinanceHeadlineModel


MAX_BODY = 16_384
REPLAY_WINDOW_SEC = 60


def _secret():
    value = os.environ.get("ASH_NLP_SHARED_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("ASH_NLP_SHARED_SECRET must contain at least 32 characters")
    return value.encode()


def _authorized(body: bytes):
    timestamp = request.headers.get("X-ASH-Timestamp", "")
    signature = request.headers.get("X-ASH-Signature", "")
    try:
        sent = datetime.fromtimestamp(float(timestamp), timezone.utc)
    except (TypeError, ValueError, OSError):
        return False, "invalid timestamp"
    age = abs((datetime.now(timezone.utc) - sent).total_seconds())
    if age > REPLAY_WINDOW_SEC:
        return False, "expired request"
    expected = hmac.new(_secret(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "invalid signature"
    return True, None


def create_app(model=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY
    model = model or FinanceHeadlineModel()
    cache = OrderedDict()
    cache_lock = threading.Lock()

    @app.get("/health")
    def health():
        try:
            _secret()
            configured = True
        except RuntimeError:
            configured = False
        return jsonify({
            "ok": configured,
            "service": "ash-home-nlp",
            "backend": model.backend,
            "model_version": model.model_version,
        }), (200 if configured else 503)

    @app.post("/v1/infer")
    def infer():
        body = request.get_data(cache=True)
        try:
            ok, error = _authorized(body)
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503
        if not ok:
            return jsonify({"ok": False, "error": error}), 401
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            key = hashlib.sha256(body).hexdigest()
            with cache_lock:
                cached = cache.get(key)
                if cached:
                    cache.move_to_end(key)
                    return jsonify({**cached, "cached": True})
            signal = model.infer(payload).as_dict()
            response = {"ok": True, "signal": signal, "cached": False}
            with cache_lock:
                cache[key] = response
                cache.move_to_end(key)
                while len(cache) > 4096:
                    cache.popitem(last=False)
            return jsonify(response)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("ASH_NLP_BIND", "127.0.0.1")
    port = int(os.environ.get("ASH_NLP_PORT", "8790"))
    app.run(host=host, port=port, debug=False, threaded=True)
