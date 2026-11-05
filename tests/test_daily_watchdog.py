"""The daily watchdog's decision (offline): when to open the failing-channel issue, when to leave it alone."""
import importlib.util
import os
from datetime import datetime, timedelta, timezone

spec = importlib.util.spec_from_file_location("daily_watchdog", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "daily_watchdog.py"))
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def run(hours_ago, conclusion, status="completed", rid=1):
    t = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"createdAt": t, "conclusion": conclusion, "status": status, "databaseId": rid}


def test_two_failures_in_a_row_is_failing():
    d = wd.decide([run(5, "failure", rid=3), run(12, "failure", rid=2), run(20, "success", rid=1)], NOW)
    assert d["state"] == "failing" and [r["databaseId"] for r in d["failed"]] == [3, 2]


def test_one_failure_is_not_enough_it_may_be_a_flake():
    assert wd.decide([run(5, "failure"), run(12, "success")], NOW)["state"] == "unknown"


def test_a_success_after_failures_is_ok_and_closes_the_issue():
    assert wd.decide([run(2, "success"), run(9, "failure"), run(14, "failure")], NOW)["state"] == "ok"


def test_runs_that_are_still_going_are_ignored():
    d = wd.decide([run(1, "", status="in_progress"), run(5, "failure"), run(12, "failure")], NOW)
    assert d["state"] == "failing"
    assert wd.decide([run(1, "", status="in_progress")], NOW)["state"] == "unknown"
    assert wd.decide([], NOW)["state"] == "unknown"


def test_a_success_that_is_very_old_means_the_schedule_went_quiet():
    assert wd.decide([run(40, "success")], NOW)["state"] == "stale"
    assert wd.decide([run(29, "success")], NOW)["state"] == "ok"


def test_issue_text_links_the_failed_runs_and_warns_not_to_dispatch_the_daily():
    d = wd.decide([run(5, "failure", rid=33), run(12, "failure", rid=22)], NOW)
    title, body = wd.issue_text(d, "owner/repo")
    assert "failing" in title and "actions/runs/33" in body and "actions/runs/22" in body and "Do not dispatch the daily workflow" in body
