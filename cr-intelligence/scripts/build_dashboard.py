"""
CR Intelligence Dashboard Builder

Pulls PR review data from GitHub, analyzes review patterns,
classifies comments using Gemini, and generates an HTML dashboard
comparing AI vs Human review coverage.
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path

from github import Github
from jinja2 import Environment, FileSystemLoader
import google.generativeai as genai


REPO_NAME = os.environ.get("REPO_NAME", "redhat-community-ai-tools/UnifAI")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
LOOKBACK_DAYS = 60
OUTPUT_DIR = Path(__file__).parent.parent / "output"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
DATA_DIR = Path(__file__).parent.parent / "data"

AI_BOTS = {"coderabbitai", "coderabbitai[bot]", "github-actions[bot]", "gemini-cr-bot"}

CATEGORIES = [
    "ARCHITECTURE",
    "ERROR_HANDLING",
    "NAMING",
    "TESTING",
    "PERFORMANCE",
    "SECURITY",
    "STYLE",
    "LOGIC",
]


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
            is_ai = reviewer.lower() in AI_BOTS or "[bot]" in reviewer.lower()
            review_comments.append({
                "body": comment.body,
                "path": comment.path,
                "reviewer": reviewer,
                "is_ai": is_ai,
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


def classify_comments(comments):
    """Classify review comments into categories using Gemini 2.5 Flash."""
    if not GEMINI_API_KEY or not comments:
        return comments

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    batch_size = 20
    classified = []

    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        comments_text = "\n---\n".join(
            f"[{j}] File: {c['path']}\nComment: {c['body'][:300]}"
            for j, c in enumerate(batch)
        )

        prompt = f"""Classify each code review comment into exactly ONE category.

Categories:
- ARCHITECTURE: Layer violations, dependency direction, module boundaries, hexagonal architecture
- ERROR_HANDLING: Missing error cases, wrong error types, no retry logic, exception handling
- NAMING: Unclear names, convention violations, inconsistent naming
- TESTING: Missing tests, weak assertions, untested paths, test quality
- PERFORMANCE: Inefficient patterns, N+1 queries, unnecessary allocations, caching
- SECURITY: Input validation, auth checks, secrets exposure, injection risks
- STYLE: Formatting, imports, code organization, conventions, cosmetic issues
- LOGIC: Business logic bugs, edge cases, incorrect conditions, race conditions

For each comment (numbered [0], [1], etc.), return ONLY a JSON array of categories in the same order.
Example output: ["STYLE", "ARCHITECTURE", "LOGIC"]

Comments:
{comments_text}"""

        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            categories = json.loads(text)
            for j, comment in enumerate(batch):
                cat = categories[j] if j < len(categories) else "STYLE"
                comment["category"] = cat if cat in CATEGORIES else "STYLE"
                classified.append(comment)
        except Exception as e:
            print(f"  Warning: Classification batch failed ({e}), defaulting to STYLE")
            for comment in batch:
                comment["category"] = "STYLE"
                classified.append(comment)

        if i + batch_size < len(comments):
            time.sleep(1)

    return classified


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

    # File extension breakdown
    file_extensions = defaultdict(int)
    for comment in review_comments:
        ext = Path(comment["path"]).suffix or "other"
        file_extensions[ext] += 1

    # Weekly trend
    weekly_data = defaultdict(lambda: {"prs_opened": 0, "prs_merged": 0, "comments": 0, "ai_comments": 0, "human_comments": 0})
    for pr in prs_data:
        week = datetime.fromisoformat(pr["created_at"]).strftime("%Y-W%W")
        weekly_data[week]["prs_opened"] += 1
        if pr["merged_at"]:
            merge_week = datetime.fromisoformat(pr["merged_at"]).strftime("%Y-W%W")
            weekly_data[merge_week]["prs_merged"] += 1

    for comment in review_comments:
        week = datetime.fromisoformat(comment["created_at"]).strftime("%Y-W%W")
        weekly_data[week]["comments"] += 1
        if comment.get("is_ai"):
            weekly_data[week]["ai_comments"] += 1
        else:
            weekly_data[week]["human_comments"] += 1

    sorted_weeks = sorted(weekly_data.keys())[-8:]
    weekly_trend = [{"week": w, **weekly_data[w]} for w in sorted_weeks]

    # Top reviewers (humans only)
    human_reviewers = {k: v for k, v in reviewers_summary.items() if k.lower() not in AI_BOTS and "[bot]" not in k.lower()}
    top_reviewers = sorted(human_reviewers.items(), key=lambda x: x[1]["comments"], reverse=True)[:10]

    # AI vs Human analysis
    ai_comments = [c for c in review_comments if c.get("is_ai")]
    human_comments = [c for c in review_comments if not c.get("is_ai")]

    ai_files = set(c["path"] for c in ai_comments)
    human_files = set(c["path"] for c in human_comments)
    overlap_files = ai_files & human_files
    ai_only_files = ai_files - human_files
    human_only_files = human_files - ai_files

    ai_coverage_pct = round(len(overlap_files) / len(human_files) * 100, 1) if human_files else 0

    ai_prs = set(c["pr_number"] for c in ai_comments)
    human_prs = set(c["pr_number"] for c in human_comments)
    prs_with_both = ai_prs & human_prs

    # Category breakdown (AI vs Human)
    ai_categories = defaultdict(int)
    human_categories = defaultdict(int)
    for comment in review_comments:
        cat = comment.get("category", "STYLE")
        if comment.get("is_ai"):
            ai_categories[cat] += 1
        else:
            human_categories[cat] += 1

    category_comparison = []
    for cat in CATEGORIES:
        category_comparison.append({
            "category": cat,
            "ai_count": ai_categories.get(cat, 0),
            "human_count": human_categories.get(cat, 0),
        })

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
        # AI vs Human metrics
        "ai_total_comments": len(ai_comments),
        "human_total_comments": len(human_comments),
        "ai_coverage_pct": ai_coverage_pct,
        "overlap_files_count": len(overlap_files),
        "ai_only_files_count": len(ai_only_files),
        "human_only_files_count": len(human_only_files),
        "prs_with_both_count": len(prs_with_both),
        "category_comparison": category_comparison,
        "ai_categories": dict(ai_categories),
        "human_categories": dict(human_categories),
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

    ai_count = sum(1 for c in review_comments if c.get("is_ai"))
    human_count = len(review_comments) - ai_count
    print(f"  AI comments: {ai_count}, Human comments: {human_count}")

    if GEMINI_API_KEY:
        print("Classifying comments with Gemini 2.5 Flash...")
        review_comments = classify_comments(review_comments)
        print("  Classification complete")
    else:
        print("  Skipping classification (no GEMINI_API_KEY)")
        for c in review_comments:
            c["category"] = "STYLE"

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
