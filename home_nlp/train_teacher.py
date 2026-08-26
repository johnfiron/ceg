#!/usr/bin/env python3
"""Chronologically fine-tune a finance headline teacher on the home server."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random


LABELS = {"negative": 0, "neutral": 1, "positive": 2}


class HeadlineDataset:
    def __init__(self, rows, tokenizer):
        self.rows = rows
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        encoded = self.tokenizer(
            row["headline"], truncation=True, max_length=256
        )
        encoded["labels"] = LABELS[row["label"]]
        return encoded


def _load(path):
    raw = Path(path).read_bytes()
    rows = []
    for line in raw.decode().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        label = str(row.get("label") or "").lower()
        headline = str(row.get("headline") or "").strip()
        source_ts = str(row.get("source_ts") or "")
        parsed = datetime.fromisoformat(source_ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None or label not in LABELS or not headline:
            raise ValueError("each row requires headline, timezone source_ts, and valid label")
        rows.append({"headline": headline, "source_ts": parsed.isoformat(), "label": label})
    rows.sort(key=lambda row: row["source_ts"])
    if len(rows) < 100:
        raise ValueError("at least 100 chronologically labeled headlines are required")
    return rows, hashlib.sha256(raw).hexdigest()


def _split(rows):
    train_end = int(len(rows) * 0.70)
    calibration_end = int(len(rows) * 0.85)
    return rows[:train_end], rows[train_end:calibration_end], rows[calibration_end:]


def _metrics(prediction):
    import math
    logits, labels = prediction
    correct = 0
    loss = 0.0
    for scores, label in zip(logits, labels):
        values = [float(value) for value in scores]
        maximum = max(values)
        exps = [math.exp(value - maximum) for value in values]
        probabilities = [value / sum(exps) for value in exps]
        correct += int(max(range(len(values)), key=values.__getitem__) == int(label))
        loss -= math.log(max(1e-12, probabilities[int(label)]))
    return {
        "accuracy": correct / max(1, len(labels)),
        "log_loss": loss / max(1, len(labels)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl")
    parser.add_argument("output")
    parser.add_argument("--base-model", default="ProsusAI/finbert")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=53)
    args = parser.parse_args()

    try:
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit(
            "install requirements-home-nlp.txt in the home-service environment"
        ) from exc

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows, data_hash = _load(args.jsonl)
    train_rows, calibration_rows, test_rows = _split(rows)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=3,
        id2label={0: "negative", 1: "neutral", 2: "positive"},
        label2id=LABELS,
    )
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    training = TrainingArguments(
        output_dir=str(output / "checkpoints"),
        learning_rate=2e-5,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="log_loss",
        greater_is_better=False,
        report_to=[],
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training,
        train_dataset=HeadlineDataset(train_rows, tokenizer),
        eval_dataset=HeadlineDataset(calibration_rows, tokenizer),
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=_metrics,
    )
    trainer.train()
    test_metrics = trainer.evaluate(HeadlineDataset(test_rows, tokenizer), metric_key_prefix="test")
    artifact = output / "model"
    trainer.save_model(str(artifact))
    tokenizer.save_pretrained(str(artifact))
    metadata = {
        "schema": "ash-nlp-training/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_model": args.base_model,
        "dataset_sha256": data_hash,
        "rows": len(rows),
        "train_rows": len(train_rows),
        "calibration_rows": len(calibration_rows),
        "test_rows": len(test_rows),
        "chronological": True,
        "seed": args.seed,
        "metrics": test_metrics,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
