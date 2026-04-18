from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from leadflow.config import get_settings
from leadflow.db.session import SessionLocal, configure_session
from leadflow.integrations.apify_client import ApifyClient
from leadflow.repositories import get_prompt
from leadflow.services.normalize import normalize_prompt_brief, normalize_prospect_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the configured Apify profile actor directly and inspect output.")
    parser.add_argument("--prompt-id", help="Existing prompt id to reuse canonical_brief_json from the database.")
    parser.add_argument("--brief-file", help="Path to a JSON file containing a canonical brief.")
    parser.add_argument("--roles", nargs="*", default=[], help="Override target roles.")
    parser.add_argument("--geographies", nargs="*", default=[], help="Override geographies.")
    parser.add_argument("--industries", nargs="*", default=[], help="Override industries.")
    parser.add_argument("--limit", type=int, default=5, help="Result limit for the actor test.")
    parser.add_argument("--raw-only", action="store_true", help="Print only raw actor output.")
    return parser.parse_args()


def load_brief(args: argparse.Namespace, db: Session) -> dict[str, Any]:
    if args.prompt_id:
        prompt = get_prompt(db, args.prompt_id)
        if not prompt:
            raise SystemExit(f"Prompt not found: {args.prompt_id}")
        if prompt.canonical_brief_json:
            brief = dict(prompt.canonical_brief_json)
        else:
            brief = {}
    elif args.brief_file:
        brief = json.loads(Path(args.brief_file).read_text())
    else:
        brief = {
            "target_roles": args.roles or ["Founder"],
            "industries": args.industries or [],
            "geographies": args.geographies or ["United States"],
            "seniority_hints": [],
            "exclusions": [],
            "outreach_angle": "",
            "result_limit": args.limit,
        }

    if args.roles:
        brief["target_roles"] = args.roles
    if args.geographies:
        brief["geographies"] = args.geographies
    if args.industries:
        brief["industries"] = args.industries
    brief["result_limit"] = args.limit
    return normalize_prompt_brief(brief, args.limit)


def main() -> None:
    args = parse_args()
    settings = get_settings()
    configure_session(settings.database_url)
    client = ApifyClient(settings)

    with SessionLocal() as db:
        brief = load_brief(args, db)

    actor_id, payload = client.build_discovery_payload(brief)
    print("=== Actor ===")
    print(actor_id)
    print()
    print("=== Brief ===")
    print(json.dumps(brief, indent=2, ensure_ascii=False))
    print()
    print("=== Payload ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()

    raw_items = client._run_actor(actor_id, payload)
    print(f"=== Raw Result Count ===\n{len(raw_items)}\n")
    print("=== Raw Sample ===")
    print(json.dumps(raw_items[:3], indent=2, ensure_ascii=False))
    print()

    if args.raw_only:
        return

    normalized = [
        item
        for item in (
            normalize_prospect_payload(raw_item, settings.apify_profile_actor_id)
            for raw_item in raw_items
        )
        if item
    ]
    print(f"=== Normalized Result Count ===\n{len(normalized)}\n")
    print("=== Normalized Sample ===")
    print(json.dumps(normalized[:5], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
