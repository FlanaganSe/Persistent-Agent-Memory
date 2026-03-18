"""Content-addressable claim ID generation.

Claim IDs are SHA-256(claim_type:scope:content) truncated to 16 hex chars,
prefixed with 'claim-'. They are immutable after creation: edits change
content but not the claim ID.
"""

from __future__ import annotations

import hashlib


def generate_claim_id(claim_type: str, scope: str, content: str) -> str:
    """Generate a deterministic, content-addressable claim ID.

    The ID is SHA-256 of the concatenation claim_type:scope:content,
    truncated to 16 hex characters, prefixed with 'claim-'.
    """
    payload = f"{claim_type}:{scope}:{content}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"claim-{digest}"
