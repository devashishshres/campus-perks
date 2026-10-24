#!/usr/bin/env python3
"""Per-student state for the campus-perks Skill.

Stores the student's profile and offer decisions under HOME so the data survives
Skill updates. Standard library only.

Commands:
  profile --show | --set JSON     Read or save the student's profile.
  diff --offers FILE [--record]   Split offers into new / changed / unchanged / suppressed.
  mark --id ID --status STATUS    Record claimed / saved / dismissed (optional --activated DATE).
  list                            Print all saved offer records.
  reset --yes                     Delete all saved state for this Skill.

Add --sample to any command to use assets/sample_offers.json (for diff) and a
separate sample state file that never touches the student's real data.

Exit codes: 0 ok, 2 bad input, 3 unreadable state file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "campus-perks"
SCHEMA_VERSION = 1
STATUSES = ("claimed", "saved", "dismissed")
SUPPRESSED_STATUSES = ("claimed", "dismissed")
REQUIRED_FIELDS = ("id", "provider", "benefit", "official_url")
TERM_FIELDS = ("benefit", "eligibility", "deadline", "payment_required", "renewal_terms")
OPTIONAL_FIELDS = ("eligibility", "deadline", "payment_required", "renewal_terms", "last_checked")
PROFILE_FIELDS = {"university": str, "country": str, "interests": list, "free_only": bool}
MAX_OFFERS = 200

EXIT_OK, EXIT_BAD_INPUT, EXIT_BAD_STATE = 0, 2, 3
SKILL_DIR = Path(__file__).resolve().parent.parent


class InputError(Exception):
    """Bad arguments or offer data (exit 2)."""


class StateError(Exception):
    """Saved state cannot be read (exit 3)."""


# ---------- storage ----------

def state_path(sample: bool) -> Path:
    base = Path(os.environ.get("HOME", str(Path.home()))) / ".config" / SKILL_NAME
    return base / ("state.sample.json" if sample else "state.json")


def empty_state() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "profile": None, "offers": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"saved state at {path} is unreadable: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("offers"), dict):
        raise StateError(f"saved state at {path} has an unexpected shape")
    data.setdefault("profile", None)
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Write atomically so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)  # personal data: owner-only
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------- validation ----------

def today() -> str:
    return date.today().isoformat()


def parse_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise InputError(f"date must be YYYY-MM-DD, got {value!r}") from exc


def clean_text(value: Any, field: str, max_len: int = 500) -> str:
    if value is None:
        return "unknown"
    if not isinstance(value, (str, int, float, bool)):
        raise InputError(f"field {field!r} must be text")
    text = " ".join(str(value).split())
    return (text or "unknown")[:max_len]


def normalize_offer(raw: Any, index: int) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise InputError(f"offer #{index} is not an object")
    missing = [f for f in REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        raise InputError(f"offer #{index} is missing {', '.join(missing)}")
    offer = {f: clean_text(raw.get(f), f) for f in REQUIRED_FIELDS + OPTIONAL_FIELDS}
    offer["id"] = offer["id"].lower()
    if not offer["official_url"].startswith("https://"):
        raise InputError(f"offer {offer['id']!r}: official_url must start with https://")
    if offer["last_checked"] == "unknown":
        offer["last_checked"] = today()
    return offer


def load_offers(path: Path) -> list[dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"offers file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"offers file is not valid JSON: {exc}") from exc
    raw = data.get("offers") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise InputError('offers file must be {"offers": [...]} or a list')
    if len(raw) > MAX_OFFERS:
        raise InputError(f"too many offers ({len(raw)}); max is {MAX_OFFERS}")
    offers = [normalize_offer(item, i) for i, item in enumerate(raw, 1)]
    ids = [o["id"] for o in offers]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise InputError(f"duplicate offer ids: {', '.join(dupes)}")
    return offers


def fingerprint(offer: dict[str, str]) -> str:
    """Hash of the terms a student cares about; last_checked is excluded."""
    material = json.dumps({f: offer.get(f, "unknown").lower() for f in TERM_FIELDS}, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


# ---------- commands ----------

def cmd_profile(args: argparse.Namespace, state: dict[str, Any], path: Path) -> dict[str, Any]:
    if args.set is None:
        return {"profile": state["profile"]}
    try:
        incoming = json.loads(args.set)
    except json.JSONDecodeError as exc:
        raise InputError(f"profile is not valid JSON: {exc}") from exc
    if not isinstance(incoming, dict):
        raise InputError("profile must be a JSON object")
    unknown = sorted(set(incoming) - set(PROFILE_FIELDS))
    if unknown:
        raise InputError(f"unknown profile fields: {', '.join(unknown)}")
    profile = dict(state["profile"] or {})
    for field, expected in PROFILE_FIELDS.items():
        if field not in incoming:
            continue
        value = incoming[field]
        if not isinstance(value, expected):
            raise InputError(f"profile field {field!r} must be {expected.__name__}")
        if expected is list:
            value = [clean_text(v, field, 40).lower() for v in value][:20]
        elif expected is str:
            value = clean_text(value, field, 120)
        profile[field] = value
    profile["updated"] = today()
    state["profile"] = profile
    save_state(path, state)
    return {"profile": profile, "saved": True}


def cmd_diff(args: argparse.Namespace, state: dict[str, Any], path: Path) -> dict[str, Any]:
    offers_file = Path(args.offers) if args.offers else SKILL_DIR / "assets" / "sample_offers.json"
    if not args.offers and not args.sample:
        raise InputError("--offers FILE is required (or use --sample)")
    offers = load_offers(offers_file)
    result: dict[str, list[dict[str, Any]]] = {"new": [], "changed": [], "unchanged": [], "suppressed": []}
    saved = state["offers"]

    for offer in offers:
        fp = fingerprint(offer)
        record = saved.get(offer["id"])
        if record is None:
            bucket = "new"
        elif record.get("status") in SUPPRESSED_STATUSES:
            bucket = "suppressed"
        elif record.get("fingerprint") != fp:
            bucket = "changed"
        else:
            bucket = "unchanged"

        entry: dict[str, Any] = dict(offer)
        if bucket == "suppressed":
            entry = {"id": offer["id"], "provider": offer["provider"], "status": record["status"]}
        elif bucket == "unchanged":
            entry = {"id": offer["id"], "provider": offer["provider"]}
        result[bucket].append(entry)

        if args.record and bucket in ("new", "changed"):
            rec = saved.setdefault(offer["id"], {})
            rec.update(
                provider=offer["provider"],
                benefit=offer["benefit"],
                official_url=offer["official_url"],
                renewal_terms=offer["renewal_terms"],
                fingerprint=fp,
                last_shown=today(),
            )
            rec.setdefault("status", "shown")

    if args.record:
        save_state(path, state)
    summary = {k: len(v) for k, v in result.items()}
    return {"summary": summary, **result, "recorded": bool(args.record)}


def cmd_mark(args: argparse.Namespace, state: dict[str, Any], path: Path) -> dict[str, Any]:
    offer_id = clean_text(args.id, "id", 80).lower()
    rec = state["offers"].setdefault(offer_id, {})
    rec["status"] = args.status
    rec["status_updated"] = today()
    if args.activated:
        rec["activated"] = parse_date(args.activated)
    save_state(path, state)
    return {"id": offer_id, "record": rec, "saved": True}


def cmd_list(_args: argparse.Namespace, state: dict[str, Any], _path: Path) -> dict[str, Any]:
    return {"profile": state["profile"], "offers": state["offers"]}


def cmd_reset(args: argparse.Namespace, _state: dict[str, Any], path: Path) -> dict[str, Any]:
    if not args.yes:
        raise InputError("reset deletes all saved data; rerun with --yes to confirm")
    path.unlink(missing_ok=True)
    return {"reset": True}


# ---------- entry point ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="campus-perks state helper")
    parser.add_argument("--sample", action="store_true", help="use sample data and a separate sample state file")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("profile", help="show or save the student's profile")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", action="store_true")
    g.add_argument("--set", metavar="JSON")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("diff", help="compare found offers with saved state")
    p.add_argument("--offers", metavar="FILE")
    p.add_argument("--record", action="store_true", help="save new/changed offers as shown")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("mark", help="record the student's decision on an offer")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=STATUSES)
    p.add_argument("--activated", metavar="YYYY-MM-DD")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("list", help="print all saved records")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("reset", help="delete all saved state")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_reset)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = state_path(args.sample)
    try:
        state = load_state(path) if args.command != "reset" else empty_state()
        output = args.func(args, state, path)
    except InputError as exc:
        print(json.dumps({"error": str(exc)}))
        return EXIT_BAD_INPUT
    except StateError as exc:
        print(json.dumps({"error": str(exc)}))
        return EXIT_BAD_STATE
    output["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = json.dumps(output, indent=1)
    if len(text) > 8000:  # Cubbie reads at most 8,000 characters; keep the JSON valid
        text = json.dumps(output, separators=(",", ":"))
    if len(text) > 8000:
        print(json.dumps({"error": "output too long; check fewer sources per run"}))
        return EXIT_BAD_INPUT
    print(text)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
