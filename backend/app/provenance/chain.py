"""Hash chain primitives for tamper-evident provenance events.

Design:
  - Every event's `self_hash = sha256(prev_hash | canonical_json(event_fields))`.
  - The first event's `prev_hash` is the session's `genesis_hash`
    (32 random bytes picked at session start — prevents cross-session replay).
  - Canonical JSON uses sorted keys + no whitespace + UTF-8, so the same
    semantic content always hashes to the same bytes regardless of insertion
    order or client formatting.

Based on Crosby & Wallach (USENIX Security 2009), "Efficient Data Structures
for Tamper-Evident Logging" — the linear chain form.  We keep the schema
Merkle-upgradeable (a future migration can add a `merkle_root` column on
`provenance_sessions` without touching these records).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass


def genesis_hash() -> str:
    """32 random bytes, hex-encoded.  Seeds a new session's chain."""
    return os.urandom(32).hex()


def canonical_json(obj: dict) -> str:
    """Stable serialisation for hashing.  Do NOT change — it would break all
    previously-signed chains."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_self_hash(prev_hash: str, event_fields: dict) -> str:
    """Hash = SHA-256(prev_hash || canonical_json(fields)).

    `event_fields` MUST exclude `self_hash` (obviously) and `prev_hash`
    (redundant — prev_hash is the first operand).  Caller's responsibility.
    """
    body = canonical_json(event_fields)
    return hashlib.sha256(f"{prev_hash}|{body}".encode("utf-8")).hexdigest()


@dataclass
class VerificationResult:
    valid: bool
    total_events: int
    broken_at: int | None = None  # sequence number where chain first fails
    reason: str | None = None


def verify_chain(
    genesis: str, events: list[dict]
) -> VerificationResult:
    """Walk the chain and confirm every link.

    `events` is a list of dicts with keys: sequence, prev_hash, self_hash,
    and the payload fields used for hashing.  Order by sequence ascending.
    """
    if not events:
        return VerificationResult(valid=True, total_events=0)

    expected_prev = genesis
    for ev in events:
        seq = ev.get("sequence", -1)
        if ev.get("prev_hash") != expected_prev:
            return VerificationResult(
                valid=False,
                total_events=len(events),
                broken_at=seq,
                reason=f"prev_hash mismatch at sequence {seq}",
            )
        fields = {k: v for k, v in ev.items() if k not in ("self_hash", "prev_hash")}
        computed = compute_self_hash(expected_prev, fields)
        if computed != ev.get("self_hash"):
            return VerificationResult(
                valid=False,
                total_events=len(events),
                broken_at=seq,
                reason=f"self_hash mismatch at sequence {seq}",
            )
        expected_prev = ev["self_hash"]

    return VerificationResult(valid=True, total_events=len(events))
