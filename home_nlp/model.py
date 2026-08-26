"""CPU-safe headline model with a replaceable large-model backend."""
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import math
import os
import re
import threading
from typing import Iterable, Mapping

from learner.contracts import NlpSignal


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]{1,30}")
MODEL_VERSION = "ash-finance-headline/lexical-v1"

POSITIVE = {
    "accelerate", "approval", "beat", "beats", "breakthrough", "expand",
    "growth", "improve", "profit", "raise", "raised", "record", "surge",
    "upgrade", "upgrades", "win", "wins",
}
NEGATIVE = {
    "bankruptcy", "cut", "cuts", "decline", "downgrade", "fraud", "halt",
    "investigation", "loss", "miss", "misses", "recall", "reduce", "risk",
    "subpoena", "warning", "weak",
}
NEGATORS = {"no", "not", "never", "without", "denies", "denied"}
EVENT_WORDS = {
    "EARNINGS": {"earnings", "revenue", "eps", "guidance", "quarter"},
    "REGULATORY": {"sec", "fda", "doj", "regulator", "investigation", "approval"},
    "CAPITAL": {"offering", "buyback", "dividend", "debt", "financing"},
    "M_AND_A": {"acquire", "acquisition", "merger", "bid", "takeover"},
    "PRODUCT": {"launch", "contract", "patent", "recall", "trial"},
    "MACRO": {"fed", "inflation", "jobs", "gdp", "rates", "tariff"},
}


def headline_hash(headline: str, source: str, source_ts: str) -> str:
    canonical = "\n".join((headline.strip(), source.strip().lower(), str(source_ts).strip()))
    return hashlib.sha256(canonical.encode()).hexdigest()


class FinanceHeadlineModel:
    """Bounded-memory finance lexicon baseline and future teacher adapter."""

    def __init__(self, novelty_window=2048):
        self._recent = deque(maxlen=max(32, int(novelty_window)))
        self._lock = threading.Lock()
        self.backend = os.environ.get("ASH_NLP_BACKEND", "lexical").strip().lower()
        self._transformer = None
        self.model_version = MODEL_VERSION
        if self.backend == "transformers":
            self._transformer = TransformerSentiment()
            self.model_version = self._transformer.model_version
        elif self.backend != "lexical":
            raise RuntimeError(f"unsupported ASH_NLP_BACKEND {self.backend}")

    @staticmethod
    def tokens(headline: str):
        return [token.lower() for token in TOKEN_RE.findall(headline or "")]

    def _sentiment(self, tokens: Iterable[str]) -> tuple[float, float]:
        tokens = list(tokens)
        score = 0.0
        hits = 0
        for index, token in enumerate(tokens):
            value = 1.0 if token in POSITIVE else -1.0 if token in NEGATIVE else 0.0
            if not value:
                continue
            if any(word in NEGATORS for word in tokens[max(0, index - 3):index]):
                value *= -1
            score += value
            hits += 1
        sentiment = math.tanh(score / max(1.0, math.sqrt(hits)))
        confidence = min(0.9, 0.35 + 0.12 * hits) if hits else 0.2
        return sentiment, confidence

    @staticmethod
    def _event(tokens: Iterable[str]) -> tuple[str, float]:
        counts = Counter(tokens)
        ranked = []
        for event, words in EVENT_WORDS.items():
            ranked.append((sum(counts[word] for word in words), event))
        hits, event = max(ranked)
        return (event, min(0.95, 0.45 + hits * 0.15)) if hits else ("OTHER", 0.25)

    def _novelty(self, tokens: Iterable[str]) -> float:
        current = frozenset(tokens)
        if not current:
            return 0.0
        with self._lock:
            similarities = [
                len(current & prior) / max(1, len(current | prior))
                for prior in self._recent
            ]
            self._recent.append(current)
        return 1.0 - max(similarities, default=0.0)

    def infer(self, payload: Mapping) -> NlpSignal:
        headline = str(payload.get("headline") or "").strip()
        if not headline or len(headline) > 2000:
            raise ValueError("headline must contain 1..2000 characters")
        source = str(payload.get("source") or "unknown")[:120]
        source_ts = str(payload.get("source_ts") or "")
        datetime.fromisoformat(source_ts.replace("Z", "+00:00"))
        tokens = self.tokens(headline)
        if self._transformer:
            sentiment, sentiment_confidence = self._transformer.infer(headline)
        else:
            sentiment, sentiment_confidence = self._sentiment(tokens)
        event, event_confidence = self._event(tokens)
        novelty = self._novelty(tokens)
        confidence = min(sentiment_confidence, event_confidence)
        return NlpSignal(
            content_hash=headline_hash(headline, source, source_ts),
            event_class=event,
            sentiment=round(sentiment, 6),
            novelty=round(novelty, 6),
            confidence=round(confidence, 6),
            model_version=self.model_version,
            source_ts=source_ts,
            inferred_at=datetime.now(timezone.utc).isoformat(),
            tickers=tuple(sorted({str(x).upper() for x in payload.get("tickers") or [] if x})),
        )


class TransformerSentiment:
    """Persistent Hugging Face finance model loaded only on the home service."""

    def __init__(self):
        model_name = os.environ.get("ASH_NLP_MODEL", "ProsusAI/finbert").strip()
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "transformer backend requires torch and transformers on the home server"
            ) from exc
        threads = max(1, min(os.cpu_count() or 1, int(os.environ.get("ASH_NLP_CPU_THREADS", "4"))))
        torch.set_num_threads(threads)
        self.classifier = pipeline(
            "text-classification",
            model=model_name,
            tokenizer=model_name,
            device=-1,
        )
        self.model_version = f"ash-finance-headline/transformers/{model_name}"

    def infer(self, headline):
        result = self.classifier(
            str(headline), truncation=True, max_length=256, top_k=None
        )
        rows = result[0] if result and isinstance(result[0], list) else result
        scores = {str(row.get("label") or "").lower(): float(row.get("score") or 0) for row in rows}
        positive = scores.get("positive", 0.0)
        negative = scores.get("negative", 0.0)
        neutral = scores.get("neutral", 0.0)
        sentiment = positive - negative
        confidence = max(positive, negative, neutral)
        return max(-1.0, min(1.0, sentiment)), max(0.0, min(1.0, confidence))
