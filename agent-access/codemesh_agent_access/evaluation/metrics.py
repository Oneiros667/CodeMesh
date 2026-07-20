from __future__ import annotations

import math
from pathlib import PurePosixPath
from statistics import median
from typing import Any

from .models import CandidateRecord, RetrievalTarget


def normalize_path(value: str | None) -> str:
    if not value:
        return ""
    return str(PurePosixPath(value.replace("\\", "/"))).casefold().lstrip("./")


def target_matches(candidate: CandidateRecord, target: RetrievalTarget) -> bool:
    if (
        target.stable_key
        and (candidate.stable_key or "").casefold() != target.stable_key.casefold()
    ):
        return False
    if (
        target.node_id
        and (candidate.node_id or "").casefold() != target.node_id.casefold()
    ):
        return False
    if target.file_path and normalize_path(candidate.file_path) != normalize_path(
        target.file_path
    ):
        return False
    return True


def target_ranks(
    candidates: list[CandidateRecord], targets: list[RetrievalTarget]
) -> list[int | None]:
    return [
        next(
            (
                index
                for index, item in enumerate(candidates, start=1)
                if target_matches(item, target)
            ),
            None,
        )
        for target in targets
    ]


def ranking_metrics(
    candidates: list[CandidateRecord], targets: list[RetrievalTarget], k: int
) -> dict[str, float | int | None]:
    if not targets:
        return {
            "precision_at_k": 1.0,
            "recall_at_k": 1.0,
            "reciprocal_rank": 1.0,
            "ndcg_at_k": 1.0,
            "primary_rank": None,
        }

    ranks = target_ranks(candidates, targets)
    matched = sum(rank is not None and rank <= k for rank in ranks)
    relevant_candidates = sum(
        any(target_matches(candidate, target) for target in targets)
        for candidate in candidates[:k]
    )
    first_rank = min((rank for rank in ranks if rank is not None), default=None)

    gains = []
    for candidate in candidates[:k]:
        relevance = max(
            (
                target.relevance
                for target in targets
                if target_matches(candidate, target)
            ),
            default=0,
        )
        gains.append((2**relevance - 1))
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    ideal = sorted((2**target.relevance - 1 for target in targets), reverse=True)[:k]
    idcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal))
    primary = [
        rank for rank, target in zip(ranks, targets, strict=True) if target.primary
    ]

    return {
        "precision_at_k": relevant_candidates / max(1, min(k, len(candidates))),
        "recall_at_k": matched / len(targets),
        "reciprocal_rank": 0.0 if first_rank is None else 1.0 / first_rank,
        "ndcg_at_k": 0.0 if idcg == 0 else dcg / idcg,
        "primary_rank": min(
            (rank for rank in primary if rank is not None), default=None
        ),
    }


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile_value * len(ordered)))
    return round(ordered[rank - 1], 3)


def p50(values: list[float]) -> float:
    return round(float(median(values)), 3) if values else 0.0


def ranking_stability(rankings: list[list[CandidateRecord]]) -> float:
    if len(rankings) <= 1:
        return 1.0
    canonical = [_identity(item) for item in rankings[0]]
    return sum(
        [_identity(item) for item in ranking] == canonical for ranking in rankings[1:]
    ) / (len(rankings) - 1)


def dotted_value(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _identity(candidate: CandidateRecord) -> tuple[str, str, str]:
    return (
        (candidate.stable_key or "").casefold(),
        normalize_path(candidate.file_path),
        (candidate.node_id or "").casefold(),
    )
