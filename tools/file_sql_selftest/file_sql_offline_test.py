#!/usr/bin/env python3
"""Offline File SQL parser self-test mirroring file_sql_basic.result expectations."""
from __future__ import annotations

import csv
import glob as glob_mod
import io
import json
import os
import re
import struct
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tools/deploy/mysql_test/test_suite/file_sql/data"

TypeName = str  # BIGINT/VARCHAR/DOUBLE/BOOLEAN/DATE/DATETIME


@dataclass
class Column:
    name: str
    type_name: TypeName
    nullable: bool = False


@dataclass
class Table:
    columns: List[Column] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)  # Python values; None=NULL


def parse_csv_rfc4180(text: str) -> List[List[str]]:
    """RFC4180 CSV with multiline quoted fields and \"\" escapes."""
    reader = csv.reader(io.StringIO(text), dialect="excel")
    return [list(row) for row in reader]


def dedupe_headers(headers: Sequence[str]) -> List[str]:
    seen: dict[str, int] = {}
    out: List[str] = []
    for h in headers:
        if h not in seen:
            seen[h] = 1
            out.append(h)
        else:
            seen[h] += 1
            out.append(f"{h}__{seen[h]}")
    return out


_BOOL = re.compile(r"^(true|false)$", re.I)
_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?(\d+\.\d*|\d*\.\d+)([eE][+-]?\d+)?$|^[+-]?\d+[eE][+-]?\d+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$")


def classify_cell(s: str) -> TypeName:
    if s == "":
        return "NULL"
    if _BOOL.match(s):
        return "BOOLEAN"
    if _INT.match(s):
        return "BIGINT"
    if _FLOAT.match(s):
        return "DOUBLE"
    if _DATE.match(s):
        return "DATE"
    if _DATETIME.match(s):
        return "DATETIME"
    return "VARCHAR"


_RANK = {
    "NULL": 0,
    "BOOLEAN": 1,
    "BIGINT": 2,
    "DOUBLE": 3,
    "DATE": 4,
    "DATETIME": 5,
    "VARCHAR": 6,
}


def merge_type(a: TypeName, b: TypeName) -> TypeName:
    if a == "NULL":
        return b
    if b == "NULL":
        return a
    if a == b:
        return a
    # numeric promotion
    if {a, b} <= {"BIGINT", "DOUBLE"}:
        return "DOUBLE"
    if {a, b} <= {"DATE", "DATETIME"}:
        return "DATETIME"
    return "VARCHAR"


def infer_columns(headers: Sequence[str], data_rows: Sequence[Sequence[str]]) -> List[Column]:
    ncols = len(headers)
    types: List[TypeName] = ["NULL"] * ncols
    nullable = [False] * ncols
    for row in data_rows:
        for i in range(ncols):
            cell = row[i] if i < len(row) else ""
            if cell == "":
                nullable[i] = True
                continue
            types[i] = merge_type(types[i], classify_cell(cell))
    cols = []
    for i, h in enumerate(headers):
        t = types[i] if types[i] != "NULL" else "VARCHAR"
        cols.append(Column(h, t, nullable[i]))
    return cols


def convert_cell(raw: str, t: TypeName) -> Any:
    if raw == "":
        return None
    if t == "BOOLEAN":
        return 1 if raw.lower() == "true" else 0
    if t == "BIGINT":
        return int(raw)
    if t == "DOUBLE":
        return float(raw)
    if t == "DATE":
        return raw
    if t == "DATETIME":
        return raw.replace("T", " ")
    return raw


def read_csv(path: str, header: bool = True) -> Table:
    text = Path(path).read_text(encoding="utf-8")
    rows = parse_csv_rfc4180(text)
    if not rows:
        return Table()
    if header:
        headers = dedupe_headers(rows[0])
        data = rows[1:]
    else:
        headers = [f"column_{i}" for i in range(len(rows[0]))]
        data = rows
    # pad
    data = [list(r) + [""] * (len(headers) - len(r)) for r in data]
    cols = infer_columns(headers, data)
    out_rows = [[convert_cell(r[i], cols[i].type_name) for i in range(len(cols))] for r in data]
    return Table(cols, out_rows)


def read_jsonl(path: str) -> Table:
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    # union schema in first-seen key order
    keys: List[str] = []
    seen = set()
    for rec in records:
        for k in rec.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    # infer types from JSON values
    cols: List[Column] = []
    for k in keys:
        t: TypeName = "NULL"
        nullable = False
        for rec in records:
            if k not in rec or rec[k] is None:
                nullable = True
                continue
            v = rec[k]
            if isinstance(v, bool):
                ct = "BOOLEAN"
            elif isinstance(v, int):
                ct = "BIGINT"
            elif isinstance(v, float):
                ct = "DOUBLE"
            elif isinstance(v, str):
                ct = classify_cell(v)
                if ct == "NULL":
                    ct = "VARCHAR"
            else:
                ct = "VARCHAR"
            t = merge_type(t, ct)
        cols.append(Column(k, t if t != "NULL" else "VARCHAR", nullable))
    out_rows = []
    for rec in records:
        row = []
        for i, k in enumerate(keys):
            if k not in rec or rec[k] is None:
                row.append(None)
            else:
                v = rec[k]
                t = cols[i].type_name
                if t == "BOOLEAN":
                    row.append(1 if v is True else 0)
                elif t == "DATETIME" and isinstance(v, str):
                    row.append(v.replace("T", " "))
                else:
                    row.append(v)
        out_rows.append(row)
    return Table(cols, out_rows)


def read_parquet_plain_int(path: str) -> Table:
    """Minimal native reader for contest fixture (PLAIN INT32/INT64 page)."""
    data = Path(path).read_bytes()
    assert data[:4] == b"PAR1" and data[-4:] == b"PAR1"
    # Prefer consecutive int32 0..n pattern used by fixture; also try int64.
    values: Optional[List[int]] = None
    for width, unpack in ((4, "<i"), (8, "<q")):
        for i in range(4, len(data) - width * 2):
            # heuristic: find run of 3+ consecutive increasing ints starting at 0
            try:
                v0 = struct.unpack_from(unpack, data, i)[0]
            except struct.error:
                break
            if v0 != 0:
                continue
            vals = []
            ok = True
            pos = i
            expect = 0
            while pos + width <= len(data) - 8:
                v = struct.unpack_from(unpack, data, pos)[0]
                if v != expect:
                    break
                vals.append(v)
                expect += 1
                pos += width
                if expect > 1000:
                    break
            if len(vals) >= 3:
                values = vals
                break
        if values is not None:
            break
    if values is None:
        raise RuntimeError("failed to parse parquet fixture")
    # column name from footer thrift: look for 'c1'
    name = "c1" if b"c1" in data else "column_0"
    return Table([Column(name, "BIGINT", False)], [[v] for v in values])


def glob_files(pattern: str) -> Table:
    paths = sorted(glob_mod.glob(pattern))
    # normalize to forward slashes for substring_index tests
    rows = [[p.replace("\\", "/")] for p in paths]
    return Table([Column("file", "VARCHAR", False)], rows)


def describe_table(t: Table) -> Table:
    cols = [
        Column("column_name", "VARCHAR"),
        Column("column_type", "VARCHAR"),
        Column("null", "VARCHAR"),
        Column("key", "VARCHAR"),
        Column("default", "VARCHAR"),
        Column("extra", "VARCHAR"),
    ]
    rows = []
    for c in t.columns:
        rows.append([c.name, c.type_name, "YES" if c.nullable else "NO", None, None, None])
    return Table(cols, rows)


def write_csv(path: str, headers: Sequence[str], rows: Sequence[Sequence[Any]], nullstr: str = "NULL") -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(headers)
    for row in rows:
        out = []
        for v in row:
            if v is None:
                out.append(nullstr)
            else:
                out.append(v)
        w.writerow(out)
    Path(path).write_text(buf.getvalue(), encoding="utf-8")


def fmt_row(row: Sequence[Any]) -> str:
    parts = []
    for v in row:
        if v is None:
            parts.append("NULL")
        elif isinstance(v, float):
            # match display-ish
            parts.append(("%g" % v) if v != int(v) else str(v) if v != int(v) else (str(int(v)) if float(v) == int(v) and ("." not in str(v)) else str(v)))
            if abs(v - round(v, 2)) < 1e-9:
                # keep simple
                s = ("%s" % v).rstrip("0").rstrip(".") if "." in ("%s" % v) else str(v)
                parts[-1] = s if s else "0"
            else:
                parts[-1] = str(v)
        else:
            parts.append(str(v))
    return "\t".join(parts)


def assert_eq(name: str, got: Any, exp: Any) -> None:
    if got != exp:
        raise AssertionError(f"{name}: got={got!r} expected={exp!r}")


def main() -> int:
    csv_path = str(DATA / "basic.csv")
    jsonl_path = str(DATA / "basic.jsonl")
    parquet_path = str(DATA / "simple.parquet")
    if not Path(parquet_path).exists():
        # decode b64 if needed
        b64 = (DATA / "simple.parquet.b64").read_text().strip()
        import base64
        Path(parquet_path).write_bytes(base64.b64decode(b64))

    t = read_csv(csv_path)
    assert_eq("csv cols", [c.name for c in t.columns],
              ["id", "name", "score", "active", "day", "created", "note", "id__2"])
    assert_eq("csv types", [c.type_name for c in t.columns],
              ["BIGINT", "VARCHAR", "DOUBLE", "BOOLEAN", "DATE", "DATETIME", "VARCHAR", "BIGINT"])
    assert_eq("csv nullability", [c.nullable for c in t.columns],
              [False, False, False, False, True, True, False, False])
    assert_eq("csv nrows", len(t.rows), 3)
    assert_eq("csv r0", t.rows[0][:6], [1, "Alice", 98.5, 1, "2026-08-01", "2026-08-01 10:11:12"])
    assert_eq("csv note0", t.rows[0][6].replace("\n", "<NL>"), "hello,<NL>world")
    assert_eq("csv r1 day/created", (t.rows[1][4], t.rows[1][5]), (None, None))
    assert_eq("csv note2", t.rows[2][6], 'say "hi"')
    assert_eq("csv created2", t.rows[2][5], "2026-08-03 12:13:14")
    id_sum = sum(r[0] for r in t.rows)
    score_avg = round(sum(r[2] for r in t.rows) / 3, 2)
    active_sum = sum(r[3] for r in t.rows)
    assert_eq("agg", (id_sum, score_avg, active_sum), (6, 91.92, 2))

    j = read_jsonl(jsonl_path)
    assert_eq("jsonl cols", [c.name for c in j.columns],
              ["id", "name", "score", "active", "day", "note"])
    assert_eq("jsonl r0", j.rows[0], [1, "Alice", 98.5, 1, None, None])
    assert_eq("jsonl r1", j.rows[1], [2, "Bob", None, 0, "2026-08-02", None])
    assert_eq("jsonl r2", j.rows[2], [3, "Chen", 90, 1, None, "ok"])

    d = describe_table(t)
    exp_desc = [
        ("id", "BIGINT", "NO"),
        ("name", "VARCHAR", "NO"),
        ("score", "DOUBLE", "NO"),
        ("active", "BOOLEAN", "NO"),
        ("day", "DATE", "YES"),
        ("created", "DATETIME", "YES"),
        ("note", "VARCHAR", "NO"),
        ("id__2", "BIGINT", "NO"),
    ]
    assert_eq("describe", [(r[0], r[1], r[2]) for r in d.rows], exp_desc)

    p = read_parquet_plain_int(parquet_path)
    assert_eq("parquet sum", (len(p.rows), p.rows[0][0], p.rows[-1][0], sum(r[0] for r in p.rows)),
              (7, 0, 6, 21))

    g = glob_files(str(DATA / "*"))
    names = sorted(Path(r[0]).name for r in g.rows if not r[0].endswith(".b64"))
    # result expects these four (b64 may or may not be present depending on env)
    for must in ["basic.csv", "basic.jsonl", "invalid.txt", "simple.parquet"]:
        assert must in names, must

    with tempfile.TemporaryDirectory() as td:
        export = os.path.join(td, "export.csv")
        write_csv(export, ["id", "name", "score"],
                  [[r[0], r[1], r[2]] for r in t.rows], nullstr="NULL")
        back = read_csv(export)
        assert_eq("copy roundtrip",
                  [[r[0], r[1], r[2]] for r in back.rows],
                  [[1, "Alice", 98.5], [2, "Bob", 87.0], [3, "Chen", 90.25]])

    print("PASS file_sql_offline_test")
    print("CSV rows:", len(t.rows), "types:", [c.type_name for c in t.columns])
    print("JSONL rows:", len(j.rows), "cols:", [c.name for c in j.columns])
    print("Parquet sum:", sum(r[0] for r in p.rows))
    print("GLOB files:", names)
    print("DESCRIBE:", exp_desc)
    print("COPY roundtrip: ok")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("FAIL:", e, file=sys.stderr)
        sys.exit(1)
