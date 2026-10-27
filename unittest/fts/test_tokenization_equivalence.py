"""Record/compare deterministic TOKENIZE results across seekdb binaries."""
import argparse
import json
import os
from pathlib import Path
import random
import re
import subprocess


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def snapshot():
    randomizer = random.Random(20261026)
    samples = ['', 'hello hello world world', 'Hello HELLO hello', '世界 世界 数据库 数据库',
               'THE and is the an', 'ＡＢＣ abc 123 ＡＢＣ', 'İstanbul Σίσυφος Straße',
               '😀 hello 😀 中文', 'a\tb\nc\rd', 'x' * 1000, '重复词 ' * 500, 'hello\x00world', '\x00abc\x7fxyz', '\n\x00\t\r', 'abc\x1fDEF']
    pieces = ['hello', 'WORLD', 'SeekDB', '全文索引', '数据库', '中文', '東京', '123',
              '3.14159', '😀', 'naïve', 'café', 'Σ', '-', '.', ',', '\n', '\t', 'the']
    for _ in range(120):
        samples.append(' '.join(randomizer.choice(pieces) for _ in range(randomizer.randrange(1, 70))))
    queries = []
    labels = []
    for parser in ['ik', 'beng', 'space', 'ngram']:
        for text in samples:
            queries.append("SELECT TOKENIZE(CONVERT(UNHEX('" + text.encode().hex() +
                           "') USING utf8mb4), '" + parser + "', '[{\"output\":\"all\"}]');")
            labels.append([parser, text])
    client = os.environ.get('MYSQL_CLIENT', str(Path(__file__).resolve().parents[2] /
                            'deps/3rd/u01/obclient/bin/obclient'))
    result = subprocess.run([client, '-h127.0.0.1', '-P' + os.environ.get('SEEKDB_TEST_PORT', '10105'),
                             '-uroot', '-N', '-s', '--default-character-set=utf8mb4', '--raw'],
                            input='SET NAMES utf8mb4;\n' + '\n'.join(queries) + '\n',
                            text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise AssertionError(result.stderr)
    rows = result.stdout.splitlines()
    if len(rows) != len(labels):
        raise AssertionError((len(rows), len(labels), rows[:5]))
    captured = [[label, canonical(None if row == 'NULL' else json.loads(row))]
                for label, row in zip(labels, rows)]
    # A fast ASCII path must retain unsupported-charset and binary behavior,
    # including after the shared IK dictionaries have already been warmed.
    for parser in ['ik', 'beng']:
        for charset in ['utf8mb4', 'utf16', 'utf16le', 'gbk', 'latin1', 'binary']:
            for value in ['hello HELLO world 123', '数据库 中文 OceanBase']:
                literal = "CONVERT(UNHEX('" + value.encode().hex() + "') USING utf8mb4)"
                query = f"SELECT TOKENIZE(CONVERT({literal} USING {charset}),'{parser}');"
                result = subprocess.run(
                    [client, '-h127.0.0.1', '-P' + os.environ.get('SEEKDB_TEST_PORT', '10105'),
                     '-uroot', '-N', '-s', '--raw', '--default-character-set=utf8mb4', '-e', query],
                    text=True, capture_output=True, timeout=30)
                if result.returncode:
                    error = re.search(r'ERROR (\d+)', result.stderr)
                    assert error is not None, result.stderr
                    outcome = ['error', error.group(1)]
                else:
                    outcome = ['tokens', canonical(json.loads(result.stdout))]
                captured.append([['charset', parser, charset, value], outcome])
    return captured


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['record', 'verify'])
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    actual = snapshot()
    if args.mode == 'record':
        args.path.write_text(json.dumps(actual, ensure_ascii=False))
    else:
        expected = json.loads(args.path.read_text())
        if len(expected) != len(actual):
            raise AssertionError((len(expected), len(actual)))
        for before, after in zip(expected, actual):
            if before != after:
                raise AssertionError({'before': before, 'after': after})
    print(f'{args.mode}: {len(actual)} token and frequency results checked')
