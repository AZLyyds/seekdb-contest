#!/usr/bin/env python3
"""Offline AI COLUMN DDL logic self-test (no observer required).

Mirrors resolver conventions used by contest AI COLUMN work:
- comment meta: __AI__|mr=<n>|sm=<n>|st=<id>|rq=<id>|rs=<id>|expr=<normalized>
- JSON columns append "Return exactly one valid JSON value"
- vector dim mismatch -> errno 7600
- AI-on-AI dependency -> errno 1235
"""
from __future__ import annotations

import re
import sys

AI_JSON_HINT = "Return exactly one valid JSON value"
AI_INT_HINT = "Return exactly one base-10 integer"
ERR_DIM = 7600
ERR_DEP = 1235


def normalize_expr(raw: str, col_type: str) -> str:
    out = raw
    if col_type == "json":
        out = out + "\n" + AI_JSON_HINT
    elif col_type in ("int", "bigint"):
        out = out + "\n" + AI_INT_HINT
    return out


def build_meta(max_retries: int, sync_mode: int, state_id: int, request_id: int,
               rspec_id: int, normalized: str) -> str:
    return (
        f"__AI__|mr={max_retries}|sm={sync_mode}|st={state_id}|rq={request_id}"
        f"|rs={rspec_id}|expr={normalized}"
    )


def parse_meta(meta: str) -> dict:
    assert meta.startswith("__AI__|"), meta
    body = meta[len("__AI__|") :]
    # expr may contain '|' so split carefully: take known keys then expr=
    m = re.match(
        r"mr=(\d+)\|sm=(\d+)\|st=(\d+)\|rq=(\d+)\|rs=(\d+)\|expr=(.*)$",
        body,
        flags=re.S,
    )
    assert m, meta
    return {
        "max_retries": int(m.group(1)),
        "sync_mode": int(m.group(2)),
        "state_column_id": int(m.group(3)),
        "request_column_id": int(m.group(4)),
        "result_spec_column_id": int(m.group(5)),
        "normalized_expr": m.group(6),
    }


def check_embed_dim(col_dim: int, embed_dim: int | None) -> int | None:
    if embed_dim is None:
        return None
    if col_dim > 0 and embed_dim != col_dim:
        return ERR_DIM
    return None


def check_dependency(ai_names: list[str], expr_refs: list[str]) -> int | None:
    ai = {n.lower() for n in ai_names}
    for ref in expr_refs:
        if ref.lower() in ai:
            return ERR_DEP
    return None


def hidden_names(ai_col_id: int) -> list[str]:
    return [
        f"__ai_state_{ai_col_id}",
        f"__ai_request_{ai_col_id}",
        f"__ai_rspec_{ai_col_id}",
    ]


def main() -> int:
    # JSON prompt persistence
    norm = normalize_expr("AI_COMPLETE('m', concat('Classify: ', content))", "json")
    assert AI_JSON_HINT in norm
    meta = build_meta(2, 0, 18, 19, 20, norm)
    parsed = parse_meta(meta)
    assert parsed["max_retries"] == 2
    assert parsed["state_column_id"] == 18
    assert AI_JSON_HINT in parsed["normalized_expr"]

    # emb retries=3
    meta2 = build_meta(3, 0, 21, 22, 23, "AI_EMBED('m', content)")
    assert parse_meta(meta2)["max_retries"] == 3

    # dim mismatch
    assert check_embed_dim(4, 3) == ERR_DIM
    assert check_embed_dim(4, 4) is None
    assert check_embed_dim(4, None) is None

    # dependency
    assert check_dependency(["first_ai", "second_ai"], ["content"]) is None
    assert check_dependency(["first_ai", "second_ai"], ["first_ai"]) == ERR_DEP

    # 3 hidden per AI column
    names = hidden_names(16)
    assert len(names) == 3
    assert names[0].startswith("__ai_state_")

    # ALTER provisional id math: max_used=2 (id,content), add AI -> id 3, hidden 4/5/6
    max_used = 2
    pending_after_ai = 1
    ai_id = max_used + pending_after_ai
    assert ai_id == 3
    assert [ai_id + 1, ai_id + 2, ai_id + 3] == [4, 5, 6]

    print("ai_column_offline_selftest: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
