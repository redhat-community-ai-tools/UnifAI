# CR Intelligence Dashboard

Automated dashboard that tracks code review metrics for the UnifAI team.

## What it shows

- **Open PRs** awaiting review
- **Time to first review** — how long PRs wait before someone looks
- **Time to merge** — total lifecycle
- **Review cycles** — how many back-and-forth rounds per PR
- **Comments per PR** — review depth
- **Weekly trends** — activity over time
- **Top reviewers** — who's doing the most review work
- **File type breakdown** — where comments concentrate

## How it works

1. GitHub Action runs weekly (or on push to `cr-intelligence-dashboard` branch)
2. Python script pulls PR data via GitHub API
3. Generates a static HTML dashboard with Chart.js
4. Deploys to GitHub Pages

## Running locally

```bash
export GITHUB_TOKEN=ghp_your_token
export REPO_NAME=redhat-community-ai-tools/UnifAI
pip install -r requirements.txt
python scripts/build_dashboard.py
open output/index.html
```

## Dashboard URL

Once deployed: https://redhat-community-ai-tools.github.io/UnifAI/
