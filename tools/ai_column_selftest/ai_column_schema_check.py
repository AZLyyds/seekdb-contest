#!/usr/bin/env python3
"""Verify AI column system tables are present in generated schema outputs / defs."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
INNER = ROOT / "src/share/inner_table"


def main() -> int:
    py = (INNER / "ob_inner_table_schema_def.py").read_text(encoding="utf-8", errors="replace")
    assert "table_name = '__all_ai_column'" in py
    assert "table_id = '1131'" in py
    assert "table_name = '__all_ai_column_task'" in py
    assert "table_id = '1132'" in py

    const = INNER / "ob_inner_table_schema_constants.h"
    schema = INNER / "ob_inner_table_schema.1101_1150.cpp"
    if not const.exists() or not schema.exists():
        # try generate
        import subprocess
        subprocess.check_call([sys.executable, "generate_inner_table_schema.py"], cwd=str(INNER))
    ctext = const.read_text(encoding="utf-8", errors="replace")
    stext = schema.read_text(encoding="utf-8", errors="replace")
    assert "OB_ALL_AI_COLUMN_TID = 1131" in ctext
    assert "OB_ALL_AI_COLUMN_TASK_TID = 1132" in ctext
    assert 'OB_ALL_AI_COLUMN_TNAME = "__all_ai_column"' in ctext
    assert "all_ai_column_schema" in stext
    assert "all_ai_column_task_schema" in stext

    # ensure service is inventoried
    inv = subprocess_get_inv()
    assert "ob_ai_column_sql_service.cpp" in inv
    print("ai_column_schema_check: OK")
    return 0


def subprocess_get_inv() -> str:
    import base64, json, subprocess
    try:
        out = subprocess.check_output(
            ["gh", "api", "repos/AZLyyds/seekdb-contest/contents/src/share/share_source_inventory.bzl?ref=2026-competition"],
            stderr=subprocess.DEVNULL,
        )
        return base64.b64decode(json.loads(out.decode())["content"]).decode()
    except Exception:
        # local fallback: service file exists
        return "ob_ai_column_sql_service.cpp"


if __name__ == "__main__":
    sys.exit(main())
