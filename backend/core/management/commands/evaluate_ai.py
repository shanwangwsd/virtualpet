"""Reproducible smoke benchmark; deliberately not presented as a validated research dataset."""

import csv
import json
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core import ai
from core.models import Interaction, Profile
from core.services import today


class Command(BaseCommand):
    help = "Run retrieval Recall@K and A/B/C response collection; --live explicitly enables paid provider calls."

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        parser.add_argument("--dataset", default=str(root / "evaluation/scenarios.json"))
        parser.add_argument("--output", default=str(root / "evaluation/results"))
        parser.add_argument("--live", action="store_true")

    def handle(self, *args, **options):
        if options["live"] and not (settings.AI_API_KEY and settings.AI_MODEL):
            raise CommandError(
                "Live evaluation requires AI_API_KEY and AI_MODEL. No calls were made."
            )
        settings.AI_MODE = "live" if options["live"] else "demo"
        scenarios = json.loads(Path(options["dataset"]).read_text())
        out = Path(options["output"])
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        retrieval = []
        ratings = []
        for scenario in scenarios:
            user = get_user_model().objects.create_user("eval_" + uuid.uuid4().hex[:20])
            try:
                today(user)
                Profile.objects.filter(user=user).update(memory_enabled=True)
                ids = []
                for memory in scenario["memories"]:
                    ids.append(ai.save_memory(user, memory, "routine").id)
                relevant = {ids[i] for i in scenario["relevant"]}
                found = ai.retrieve(user, scenario["query"], 5)
                retrieval.append(
                    {
                        "scenario": scenario["id"],
                        "relevant_count": len(relevant),
                        "retrieved_count": len(found),
                        **{
                            f"recall@{k}": len(relevant.intersection(m.id for m in found[:k]))
                            / len(relevant)
                            if relevant
                            else None
                            for k in (1, 3, 5)
                        },
                    }
                )
                Interaction.objects.create(
                    user=user,
                    text="Today I want to focus on a small habit.",
                    response={"message": "Let us choose a small step."},
                )
                for mode in ("none", "recent", "memory"):
                    start = time.monotonic()
                    response = ai.respond(user, scenario["query"], mode)
                    rows.append(
                        {
                            "scenario": scenario["id"],
                            "system": mode,
                            "source": response["source"],
                            "latency_ms": round((time.monotonic() - start) * 1000, 1),
                            "response": response,
                        }
                    )
                    ratings.append(
                        {
                            "blind_id": uuid.uuid4().hex[:10],
                            "scenario": scenario["id"],
                            "system": mode,
                            "message": response["message"],
                            "context_relevance": "",
                            "personalization": "",
                            "memory_correctness": "",
                            "personality_consistency": "",
                            "actionability": "",
                            "hallucination": "",
                            "notes": "",
                        }
                    )
            finally:
                user.delete()
        valid = [row for row in retrieval if row["relevant_count"]]
        report = {
            "mode": settings.AI_MODE,
            "embedding": ai.embedding_identity(),
            "model": settings.AI_MODEL if options["live"] else "none",
            "scenarios": len(scenarios),
            "response_count": len(rows),
            "fallback_count": sum(r["source"] == "fallback" for r in rows),
            "no_relevance_abstention": [
                r["retrieved_count"] == 0 for r in retrieval if not r["relevant_count"]
            ],
            "retrieval": {
                f"recall@{k}": sum(r[f"recall@{k}"] for r in valid) / len(valid) if valid else None
                for k in (1, 3, 5)
            },
            "limitations": [
                "Small synthetic smoke dataset, not independent empirical evidence.",
                "Demo hash vectors are lexical, not semantic; no claim of LLM quality.",
                "Recall is undefined for no-relevant-memory cases; these are excluded.",
                "Human scores are blank until real raters complete them.",
                "Similarity/importance/recency weights have not been tuned on this test set.",
            ],
        }
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        (out / "responses.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        (out / "retrieval.json").write_text(json.dumps(retrieval, ensure_ascii=False, indent=2))
        import random

        random.Random(42).shuffle(ratings)
        with (out / "human-ratings.csv").open("w", newline="") as f:
            fields = [k for k in ratings[0] if k != "system"]
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(ratings)
        (out / "blind-key.json").write_text(
            json.dumps({r["blind_id"]: r["system"] for r in ratings}, indent=2)
        )
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
