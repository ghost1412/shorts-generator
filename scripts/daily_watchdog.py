"""Daily channel watchdog: open ONE issue when the scheduled daily runs keep failing, close it when a run succeeds again.

Run by .github/workflows/daily_watchdog.yml (needs the `gh` CLI and GH_TOKEN). The decision is a pure function (`decide`) so it is
tested offline; `main` only fetches the runs and keeps a single issue labelled `daily-failing` up to date.

    python scripts/daily_watchdog.py [--dry-run]
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

WORKFLOW = "Daily Short Generator"
LABEL = "daily-failing"
FAILS_NEEDED = 2                      # this many failed runs in a row before anyone is bothered (one failure can be a flake)
STALE_AFTER = timedelta(hours=30)     # the schedule is every 4 h but GitHub often delays it; this long without any run is suspicious


def parse_time(text):
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def decide(runs, now=None):
    """runs: [{conclusion, status, createdAt, databaseId}] newest first. Returns {"state", "failed", "latest"}.

    state: "failing" (the last FAILS_NEEDED finished runs all failed), "ok" (the latest finished run succeeded),
           "stale" (no run at all for STALE_AFTER), "unknown" (not enough information, or a single failure)."""
    now = now or datetime.now(timezone.utc)
    done = [r for r in runs if r.get("status") == "completed"]
    if not done:
        return {"state": "unknown", "failed": [], "latest": None}
    latest = done[0]
    if now - parse_time(latest["createdAt"]) > STALE_AFTER and latest.get("conclusion") == "success":
        return {"state": "stale", "failed": [], "latest": latest}
    if latest.get("conclusion") == "success":
        return {"state": "ok", "failed": [], "latest": latest}
    recent = done[:FAILS_NEEDED]
    if len(recent) == FAILS_NEEDED and all(r.get("conclusion") in ("failure", "timed_out", "startup_failure") for r in recent):
        return {"state": "failing", "failed": recent, "latest": latest}
    return {"state": "unknown", "failed": [], "latest": latest}


def issue_text(decision, repo):
    runs = decision["failed"]
    links = "\n".join(f"- {r['createdAt']}: https://github.com/{repo}/actions/runs/{r['databaseId']}" for r in runs)
    return ("Daily channel failing: the last scheduled runs failed",
            f"The last {len(runs)} finished runs of **{WORKFLOW}** failed:\n\n{links}\n\n"
            "Read the log with `gh run view <id> --log-failed`. Reproduce a render problem without posting anything with "
            "`gh workflow run e2e.yml -f extra_args=\"<the daily job's flags>\"`. Do not dispatch the daily workflow itself: it posts publicly.\n\n"
            "This issue is opened and closed automatically by the daily watchdog (scripts/daily_watchdog.py).")


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print what would happen, change nothing")
    ap.add_argument("--repo", default="")
    a = ap.parse_args(argv)
    repo = a.repo or sh("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").stdout.strip()
    r = sh("gh", "run", "list", "--workflow", WORKFLOW, "--limit", "6", "--json", "conclusion,status,createdAt,databaseId")
    if r.returncode != 0:
        print(f"Could not list runs: {r.stderr.strip()[:200]}")
        return 1
    decision = decide(json.loads(r.stdout or "[]"))
    print(f"state: {decision['state']}; latest: {decision['latest']}")
    found = sh("gh", "issue", "list", "--label", LABEL, "--state", "open", "--json", "number", "-q", ".[0].number").stdout.strip()
    if decision["state"] == "failing" and not found:
        title, body = issue_text(decision, repo)
        print(f"-> would open issue: {title}" if a.dry_run else "-> opening an issue")
        if not a.dry_run:
            sh("gh", "label", "create", LABEL, "--color", "d73a4a", "--description", "The scheduled daily channel run is failing", "--force")
            out = sh("gh", "issue", "create", "--title", title, "--body", body, "--label", LABEL)
            print(out.stdout.strip() or out.stderr.strip())
    elif decision["state"] in ("ok",) and found:
        print(f"-> would close issue #{found}" if a.dry_run else f"-> closing issue #{found}")
        if not a.dry_run:
            sh("gh", "issue", "close", found, "--comment", "A scheduled daily run succeeded again. Closing automatically.")
    elif decision["state"] == "stale":
        print("-> no scheduled run for a long time (GitHub may be skipping the schedule); not opening an issue for that alone")
    else:
        print("-> nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
