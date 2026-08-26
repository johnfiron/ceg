"""Small auditable online models suitable for an e2-micro."""
import hashlib
import json
import math
from pathlib import Path
from typing import Dict, Mapping


MODEL_VERSION = "ash-ftrl/v1"


class FTRLBinaryClassifier:
    """FTRL-Proximal logistic regression with a fixed hashed feature space."""

    def __init__(self, dimensions=4096, alpha=0.08, beta=1.0, l1=0.1, l2=1.0):
        self.dimensions = int(dimensions)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.l1 = float(l1)
        self.l2 = float(l2)
        self.z: Dict[int, float] = {}
        self.n: Dict[int, float] = {}
        self.updates = 0

    def _index(self, name: str) -> int:
        digest = hashlib.blake2b(str(name).encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dimensions

    def _vector(self, features: Mapping[str, float]) -> Dict[int, float]:
        out = {0: 1.0}
        for name, value in features.items():
            number = float(value)
            if number == 0 or not math.isfinite(number):
                continue
            index = 1 + self._index(name) % max(1, self.dimensions - 1)
            out[index] = out.get(index, 0.0) + max(-10.0, min(10.0, number))
        return out

    def _weight(self, index: int) -> float:
        z = self.z.get(index, 0.0)
        if abs(z) <= self.l1:
            return 0.0
        sign = -1.0 if z < 0 else 1.0
        return -(z - sign * self.l1) / (
            (self.beta + math.sqrt(self.n.get(index, 0.0))) / self.alpha + self.l2
        )

    def predict(self, features: Mapping[str, float]) -> float:
        score = sum(self._weight(index) * value for index, value in self._vector(features).items())
        score = max(-35.0, min(35.0, score))
        return 1.0 / (1.0 + math.exp(-score))

    def update(self, features: Mapping[str, float], label: int, weight=1.0) -> float:
        if label not in (0, 1):
            raise ValueError("binary label must be 0 or 1")
        vector = self._vector(features)
        probability = self.predict(features)
        for index, value in vector.items():
            gradient = (probability - label) * value * float(weight)
            old_n = self.n.get(index, 0.0)
            sigma = (math.sqrt(old_n + gradient * gradient) - math.sqrt(old_n)) / self.alpha
            self.z[index] = self.z.get(index, 0.0) + gradient - sigma * self._weight(index)
            self.n[index] = old_n + gradient * gradient
        self.updates += 1
        return probability

    def payload(self) -> dict:
        return {
            "version": MODEL_VERSION,
            "dimensions": self.dimensions,
            "alpha": self.alpha,
            "beta": self.beta,
            "l1": self.l1,
            "l2": self.l2,
            "updates": self.updates,
            "z": {str(key): value for key, value in self.z.items()},
            "n": {str(key): value for key, value in self.n.items()},
        }

    @classmethod
    def from_payload(cls, payload: Mapping) -> "FTRLBinaryClassifier":
        if payload.get("version") != MODEL_VERSION:
            raise ValueError("unsupported model version")
        model = cls(
            payload["dimensions"], payload["alpha"], payload["beta"],
            payload["l1"], payload["l2"],
        )
        model.updates = int(payload.get("updates") or 0)
        model.z = {int(key): float(value) for key, value in (payload.get("z") or {}).items()}
        model.n = {int(key): float(value) for key, value in (payload.get("n") or {}).items()}
        return model

    def save(self, path) -> None:
        target = Path(path)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(self.payload(), separators=(",", ":"), sort_keys=True))
        temp.replace(target)

    @classmethod
    def load(cls, path) -> "FTRLBinaryClassifier":
        return cls.from_payload(json.loads(Path(path).read_text()))
