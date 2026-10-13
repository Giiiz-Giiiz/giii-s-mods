#!/usr/bin/env python3
"""Re-sign the library's short-lived metadata so devices keep accepting it.

Nothing about the packages changes: the same shards, the same archives. Only
version numbers move forward and expiry dates move out:

- timestamp (expires after 2 days): every run
- snapshot (14 days): when less than 7 days are left, or a shard changed
- targets shards (60 days): when less than 30 days are left

Adding or updating packages is a maintainer's job (`giii index build` in the
GiiiCon repository); this script never does it. The format is GIX1 as in
GiiiCon's tools/src/giii_tools/index.py (ADR-009).

Keys come from the environment (PEM text): INDEX_TIMESTAMP_KEY,
INDEX_SNAPSHOT_KEY, INDEX_TARGETS_KEY.

    python3 tools/refresh.py [--site .] [--now EPOCH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

MAGIC = b"GIX1"
DOMAIN = b"GIIICON-INDEX-V1\0"
ROLES = {"root": 1, "timestamp": 2, "snapshot": 3, "targets": 4}
MAX_LEN = {"root": 8192, "timestamp": 2048, "snapshot": 16384, "targets": 65536}
DAY = 86400
EXPIRY = {"timestamp": 2 * DAY, "snapshot": 14 * DAY, "targets": 60 * DAY}


def canon(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pub_raw(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(key: Ed25519PrivateKey) -> str:
    return "ed25519:" + hashlib.sha256(pub_raw(key)).digest()[:16].hex()


def envelope(role: str, payload: dict, key: Ed25519PrivateKey) -> bytes:
    body = canon(payload)
    if len(body) > MAX_LEN[role]:
        raise SystemExit(f"{role} metadata is {len(body)} bytes (max {MAX_LEN[role]})")
    r = ROLES[role]
    sig = key.sign(DOMAIN + bytes([r]) + body)
    key.public_key().verify(sig, DOMAIN + bytes([r]) + body)
    return (
        MAGIC
        + struct.pack("<BBHI", r, 1, 0, len(body))
        + body
        + hashlib.sha256(pub_raw(key)).digest()[:16]
        + sig
    )


def payload_of(blob: bytes, role: str) -> dict:
    if blob[:4] != MAGIC:
        raise SystemExit(f"{role}: not a GIX1 file")
    r, _n, _rsv, ln = struct.unpack_from("<BBHI", blob, 4)
    if r != ROLES[role]:
        raise SystemExit(f"expected {role} metadata")
    p = json.loads(blob[12 : 12 + ln].decode("utf-8"))
    if p.get("type") != role:
        raise SystemExit(f"payload type is not {role}")
    return p


def load_key(env: str) -> Ed25519PrivateKey:
    pem = os.environ.get(env, "").strip()
    if not pem:
        raise SystemExit(f"{env} is not set")
    key = serialization.load_pem_private_key(pem.encode() + b"\n", password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit(f"{env} is not an Ed25519 key")
    return key


def latest_root(site: Path) -> dict:
    versions = sorted(int(p.stem) for p in (site / "root").glob("*.gix"))
    if not versions:
        raise SystemExit("no root metadata in the site")
    return payload_of((site / "root" / f"{versions[-1]}.gix").read_bytes(), "root")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", default=".")
    ap.add_argument("--now", type=int, help="pretend time (epoch seconds), for tests")
    a = ap.parse_args()
    site = Path(a.site)
    now = a.now or int(time.time())
    keys = {r: load_key(f"INDEX_{r.upper()}_KEY") for r in ("timestamp", "snapshot", "targets")}
    root = latest_root(site)
    for role, key in keys.items():
        if key_id(key) not in root["roles"][role]["keys"]:
            raise SystemExit(f"{role} key {key_id(key)} is not authorised by root v{root['version']}")

    ts = payload_of((site / "timestamp.gix").read_bytes(), "timestamp")
    snap = payload_of((site / "snapshot" / f"{ts['snapshot']['version']}.gix").read_bytes(), "snapshot")

    changed = False
    shards = []
    for s in snap["shards"]:
        t = payload_of((site / "targets" / f"{s['name']}.{s['version']}.gix").read_bytes(), "targets")
        if t["expires"] - now < EXPIRY["targets"] // 2:
            t = {**t, "version": t["version"] + 1, "expires": now + EXPIRY["targets"]}
            blob = envelope("targets", t, keys["targets"])
            (site / "targets" / f"{s['name']}.{t['version']}.gix").write_bytes(blob)
            s = {"name": s["name"], "version": t["version"], "length": len(blob),
                 "sha256": hashlib.sha256(blob).hexdigest()}
            print(f"targets {s['name']} v{t['version']}")
            changed = True
        shards.append(s)

    if changed or snap["expires"] - now < EXPIRY["snapshot"] // 2:
        snap = {**snap, "shards": shards, "version": snap["version"] + 1,
                "expires": now + EXPIRY["snapshot"]}
        sblob = envelope("snapshot", snap, keys["snapshot"])
        (site / "snapshot" / f"{snap['version']}.gix").write_bytes(sblob)
        ts_snap = {"version": snap["version"], "length": len(sblob),
                   "sha256": hashlib.sha256(sblob).hexdigest()}
        print(f"snapshot v{snap['version']}")
    else:
        ts_snap = ts["snapshot"]

    ts = {"type": "timestamp", "version": ts["version"] + 1,
          "expires": now + EXPIRY["timestamp"], "snapshot": ts_snap}
    (site / "timestamp.gix").write_bytes(envelope("timestamp", ts, keys["timestamp"]))
    print(f"timestamp v{ts['version']} (expires {time.strftime('%Y-%m-%d %H:%M', time.gmtime(ts['expires']))} UTC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
