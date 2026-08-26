# Home NLP service

The home service is required for news-sensitive entries. It is not in the
order, exit, reconciliation, risk, or heartbeat dependency chain.

## Current-device profile

The initial WSL probe found:

- 8 Intel Core Ultra 7 258V CPU cores with AVX2
- 23 GiB WSL memory and 8 GiB swap
- no NVIDIA runtime exposed to WSL

Start with one persistent CPU worker. Keep batch sizes bounded and measure
sustained latency and thermals before increasing concurrency.

## Local smoke test

Generate a random secret of at least 32 characters and keep it outside git:

```bash
export ASH_NLP_SHARED_SECRET='replace-with-a-random-secret'
export ASH_NLP_BIND=127.0.0.1
/home/nix/.venvs/ceg/bin/python -m home_nlp.server
```

The service exposes:

- `GET /health`
- signed `POST /v1/infer`

The lexical backend is the transport-safe baseline. To run persistent FinBERT
inference on the current CPU device, create a separate home-service virtual
environment and install CPU-only PyTorch before the remaining requirements:

```bash
python -m pip install -r requirements-home-nlp-cpu.txt
python -m pip install -r requirements.txt -r requirements-home-nlp.txt
```

Then set:

```bash
export ASH_NLP_BACKEND=transformers
export ASH_NLP_MODEL=ProsusAI/finbert
export ASH_NLP_CPU_THREADS=4
```

Do not install the home-only transformer stack on the e2-micro.

Fine-tuning input is JSONL with `headline`, timezone-aware `source_ts`, and a
`negative`, `neutral`, or `positive` label. The trainer sorts chronologically,
uses 70/15/15 train/calibration/test partitions, hashes the dataset, and writes
artifact metadata:

```bash
python -m home_nlp.train_teacher labels.jsonl artifacts/finbert-v1
export ASH_NLP_BACKEND=transformers
export ASH_NLP_MODEL="$PWD/artifacts/finbert-v1/model"
```

Requests include `X-ASH-Timestamp` and `X-ASH-Signature`. The signature is
HMAC-SHA256 over `timestamp + "." + exact_request_body`. Requests older than 60
seconds are rejected.

## Tailscale deployment

1. Install Tailscale on the home server and GCloud VM.
2. Put both devices in a dedicated tailnet or tag group.
3. Allow the GCloud tag to reach only the home NLP tag on TCP 8790.
4. Bind the service to the home Tailscale address, not `0.0.0.0`.
5. Restrict the host firewall to the Tailscale interface and GCloud peer.
6. Configure the same HMAC secret on both services and rotate it periodically.

Example private ASH configuration:

```json
{
  "nlp_api_url": "http://100.x.y.z:8790",
  "nlp_shared_secret": "stored-outside-git",
  "nlp_timeout_sec": 1.5,
  "nlp_min_confidence": 0.45,
  "nlp_max_age_sec": 1800
}
```

## Model scaling

`home_nlp/model.py` defines the response contract independently of model
hardware. The initial bounded lexical model verifies transport, timestamps,
event routing, novelty, and failure behavior. A larger finance model must keep
the same contract and add a new `model_version`.

For a future CPU/GPU teacher:

1. freeze and hash the training dataset;
2. preserve chronological train/calibration/test boundaries;
3. train or fine-tune outside the trading runner;
4. export a signed, versioned artifact;
5. benchmark latency, memory, calibration, and failure behavior;
6. promote explicitly, retaining the previous artifact for rollback.

The e2-micro uses a bounded asynchronous queue and content-hash cache. Timeout,
schema mismatch, stale output, or low confidence blocks only strategies that
declare `requires_nlp`.
