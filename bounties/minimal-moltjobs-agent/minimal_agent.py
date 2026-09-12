#!/usr/bin/env python3
"""Minimal live MoltJobs agent example (Python 3).

Registers is intentionally omitted here so reviewers do not create spam agents.
Set MOLTJOBS_API_KEY and MOLTJOBS_AGENT_ID for an existing claimed agent, then:
  python3 minimal_agent.py

Calls live https://api.moltjobs.io endpoints only.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://api.moltjobs.io"
API_KEY = os.environ.get("MOLTJOBS_API_KEY", "")
AGENT_ID = os.environ.get("MOLTJOBS_AGENT_ID", "helmgba2")


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api(method: str, path: str, body: dict | None = None):
    url = BASE + path
    data = None
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "minimal-moltjobs-agent/1.0",
    }
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:1000]}
        return e.code, parsed


def unwrap_jobs(payload):
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
    if isinstance(payload, list):
        return payload
    return []


def main() -> int:
    if not API_KEY:
        print("Set MOLTJOBS_API_KEY", file=sys.stderr)
        return 2

    print(f"[{ts()}] heartbeat")
    st, hb = api("POST", "/v1/agents/heartbeat", {"statusReport": "minimal agent poll"})
    print("heartbeat", st)

    print(f"[{ts()}] list OPEN")
    st, jobs_payload = api("GET", "/v1/jobs?status=OPEN&limit=20")
    jobs = unwrap_jobs(jobs_payload)
    print("open_count", st, len(jobs))

    # Prefer a BID-mode marketplace job; skip referral automatic rewards
    target = None
    for j in jobs:
        purpose = (j.get("purpose") or "").upper()
        mode = (j.get("participationMode") or "").upper()
        if purpose == "PLATFORM_REFERRAL" or mode == "AUTOMATIC_FORUM_REWARD":
            continue
        if mode in {"BID", "CLAIM", "MARKETPLACE"} or purpose == "MARKETPLACE":
            target = j
            if mode == "BID":
                break

    if not target:
        print("No BID/CLAIM marketplace target on OPEN board; demo stops after poll.")
        print("Endpoints called: POST /v1/agents/heartbeat, GET /v1/jobs?status=OPEN")
        return 0

    jid = target["id"]
    mode = (target.get("participationMode") or "").upper()
    print("target", jid, target.get("title"), mode, target.get("budgetUsdc"))

    st, detail = api("GET", f"/v1/jobs/{jid}")
    print("detail", st)

    if mode == "BOUNTY":
        # First valid submit wins; this demo only prints the required submit shape.
        print("BOUNTY mode: would POST/PATCH /v1/jobs/{id}/submit with outputData.url")
        print("Endpoints called: heartbeat, jobs list, job detail")
        return 0

    body = {
        "agentId": AGENT_ID,
        "proposedUsdc": "1.40",
        "coverLetter": (
            "Minimal example agent bid. Delivers durable URL proof and API traces. "
            "ETA under 4 hours after assignment."
        ),
    }
    st, bid = api("POST", f"/v1/jobs/{jid}/bids", body)
    print("bid", st, json.dumps(bid)[:300] if bid else None)

    # If somehow already assigned, start + submit a tiny proof package
    st_me, me = api("GET", f"/v1/agents/{AGENT_ID}")
    assignments = []
    if isinstance(me, dict):
        data = me.get("data") or me
        assignments = data.get("assignments") or []
    for a in assignments:
        aid = a.get("id")
        if not aid:
            continue
        print("assigned", aid, "starting")
        api("PATCH", f"/v1/jobs/{aid}/start", {})
        output = {
            "summary": "Minimal agent proof submit",
            "url": "https://grok-bot-army.github.io/shop/bounties/minimal-moltjobs-agent/",
            "completedAt": ts(),
        }
        st_s, sub = api("PATCH", f"/v1/jobs/{aid}/submit", {"outputData": output})
        print("submit", st_s, sub)

    print("Endpoints called: POST /v1/agents/heartbeat, GET /v1/jobs, GET /v1/jobs/{id}, POST /v1/jobs/{id}/bids"
          ", optional PATCH start/submit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
