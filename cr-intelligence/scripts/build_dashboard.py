"""
CR Intelligence Dashboard Builder

Pulls PR review data from GitHub, analyzes review patterns,
and generates an HTML dashboard with metrics and charts.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path

from github import Github
from jinja2 import Environment, FileSystemLoader


REPO_NAME = os.environ.get("REPO_NAME", "redhat-community-ai-tools/UnifAI")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
LOOKBACK_DAYS = 60
OUTPUT_DIR = Path(__file__).parent.parent / "output"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
DATA_DIR = Path(__file__).parent.parent / "data"


def collect_pr_data(repo):
    """Pull review data from closed and open PRs."""
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    prs_data = []
    review_comments = []
    reviewers_activity = defaultdict(lambda: {"comments": 0, "prs_reviewed": set()})

    for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
        if pr.updated_at < since:
            break

        pr_info = {
            "number": pr.number,
            "title": pr.title,
            "author": pr.user.login,
            "state": pr.state,
            "created_at": pr.created_at.isoformat(),
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
            "comments_count": 0,
            "review_cycles": 0,
            "reviewers": [],
            "time_to_first_review_hours": None,
            "time_to_merge_hours": None,
        }

        comments = list(pr.get_review_comments())
        pr_info["comments_count"] = len(comments)

        reviews = list(pr.get_reviews())
        pr_info["review_cycles"] = len([r for r in reviews if r.state in ("CHANGES_REQUESTED", "APPROVED")])
        pr_info["reviewers"] = list(set(r.user.login for r in reviews if r.user))

        if reviews:
            first_review_time = min(r.submitted_at for r in reviews if r.submitted_at)
            delta = first_review_time - pr.created_at
            pr_info["time_to_first_review_hours"] = round(delta.total_seconds() / 3600, 1)

        if pr.merged_at:
            delta = pr.merged_at - pr.created_at
            pr_info["time_to_merge_hours"] = round(delta.total_seconds() / 3600, 1)

        for comment in comments:
            reviewer = comment.user.login if comment.user else "unknown"
            review_comments.append({
                "body": comment.body,
                "path": comment.path,
                "reviewer": reviewer,
                "pr_number": pr.number,
                "created_at": comment.created_at.isoformat(),
            })
            reviewers_activity[reviewer]["comments"] += 1
            reviewers_activity[reviewer]["prs_reviewed"].add(pr.number)

        prs_data.append(pr_info)

    reviewers_summary = {
        name: {
            "comments": data["comments"],
            "prs_reviewed": len(data["prs_reviewed"]),
        }
        for name, data in reviewers_activity.items()
    }

    return prs_data, review_comments, reviewers_summary


def compute_metrics(prs_data, review_comments, reviewers_summary):
    """Compute dashboard metrics from raw data."""
    merged_prs = [p for p in prs_data if p["merged_at"]]
    open_prs = [p for p in prs_data if p["state"] == "open"]

    ttfr_values = [p["time_to_first_review_hours"] for p in prs_data if p["time_to_first_review_hours"] is not None]
    ttm_values = [p["time_to_merge_hours"] for p in merged_prs if p["time_to_merge_hours"] is not None]
    cycle_values = [p["review_cycles"] for p in prs_data if p["review_cycles"] > 0]

    avg_time_to_first_review = round(sum(ttfr_values) / len(ttfr_values), 1) if ttfr_values else 0
    avg_time_to_merge = round(sum(ttm_values) / len(ttm_values), 1) if ttm_values else 0
    avg_review_cycles = round(sum(cycle_values) / len(cycle_values), 1) if cycle_values else 0

    comments_per_pr = round(len(review_comments) / len(prs_data), 1) if prs_data else 0

    file_extensions = defaultdict(int)
    for comment in review_comments:
        ext = Path(comment["path"]).suffix or "other"
        file_extensions[ext] += 1

    weekly_data = defaultdict(lambda: {"prs_opened": 0, "prs_merged": 0, "comments": 0})
    for pr in prs_data:
        week = datetime.fromisoformat(pr["created_at"]).strftime("%Y-W%W")
        weekly_data[week]["prs_opened"] += 1
        if pr["merged_at"]:
            merge_week = datetime.fromisoformat(pr["merged_at"]).strftime("%Y-W%W")
            weekly_data[merge_week]["prs_merged"] += 1

    for comment in review_comments:
        week = datetime.fromisoformat(comment["created_at"]).strftime("%Y-W%W")
        weekly_data[week]["comments"] += 1

    sorted_weeks = sorted(weekly_data.keys())[-8:]
    weekly_trend = [{"week": w, **weekly_data[w]} for w in sorted_weeks]

    top_reviewers = sorted(reviewers_summary.items(), key=lambda x: x[1]["comments"], reverse=True)[:10]

    return {
        "total_prs": len(prs_data),
        "open_prs": len(open_prs),
        "merged_prs": len(merged_prs),
        "total_comments": len(review_comments),
        "avg_time_to_first_review_hours": avg_time_to_first_review,
        "avg_time_to_merge_hours": avg_time_to_merge,
        "avg_review_cycles": avg_review_cycles,
        "comments_per_pr": comments_per_pr,
        "file_extensions": dict(file_extensions),
        "weekly_trend": weekly_trend,
        "top_reviewers": [{"name": name, **data} for name, data in top_reviewers],
        "lookback_days": LOOKBACK_DAYS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_dashboard(metrics):
    """Render HTML dashboard from metrics."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("dashboard.html")
    return template.render(metrics=metrics, metrics_json=json.dumps(metrics))


def main():
    print(f"Collecting PR data from {REPO_NAME} (last {LOOKBACK_DAYS} days)...")
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    prs_data, review_comments, reviewers_summary = collect_pr_data(repo)
    print(f"  Found {len(prs_data)} PRs, {len(review_comments)} review comments")

    print("Computing metrics...")
    metrics = compute_metrics(prs_data, review_comments, reviewers_summary)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_file = DATA_DIR / f"snapshot_{datetime.now().strftime('%Y%m%d')}.json"
    with open(snapshot_file, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Saved snapshot to {snapshot_file}")

    print("Building dashboard...")
    html = build_dashboard(metrics)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "index.html"
    with open(output_file, "w") as f:
        f.write(html)
    print(f"  Dashboard written to {output_file}")
    print("Done!")


if __name__ == "__main__":
    main()
