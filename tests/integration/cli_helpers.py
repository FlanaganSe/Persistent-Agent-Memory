"""Shared helpers for CLI integration tests."""

from __future__ import annotations

import json
from typing import Any


def extract_json(output: str) -> Any:
    """Extract JSON object from CLI output that may contain stderr noise.

    The Typer CliRunner mixes stdout and stderr. This finds the first
    JSON object in the output and parses it, ignoring any trailing text.
    """
    idx = output.find("{")
    if idx == -1:
        msg = f"No JSON found in output: {output[:200]}"
        raise ValueError(msg)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(output, idx)
    return obj
