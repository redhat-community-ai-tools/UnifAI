import os

def load_context(changed_files=None):
    """
    Loads architecture and convention docs for code review.
    Only loads docs for domains that have changes (saves tokens/cost).
    
    Args:
        changed_files: List of changed file paths. If None, loads all.
    """
    
    # Domain definitions: files to load and path patterns to match
    domains = {
        "UI": {
            "files": ["ui/ARCHITECTURE.md", "ui/README.md"],
            "paths": ["ui/"]
        },
        "CI/CD": {
            "files": ["ci/ARCHITECTURE.md", "ci/README.md"],
            "paths": ["ci/"]
        },
        "HELM": {
            "files": ["helm/ARCHITECTURE.md", "helm/README.md"],
            "paths": ["helm/"]
        },
    }
    
    # Detect which domains to load
    if not changed_files:
        domains_to_load = set(domains.keys())
    else:
        domains_to_load = set()
        for file_path in changed_files:
            # Skip review system files (don't review the reviewer!)
            if file_path.startswith("scripts/"):
                continue
                
            for domain, config in domains.items():
                if any(file_path.startswith(path) for path in config["paths"]):
                    domains_to_load.add(domain)
        
        # Safety: if nothing detected, load all
        if not domains_to_load:
            domains_to_load = set(domains.keys())
    
    # Load files for selected domains
    content = []
    for domain in sorted(domains_to_load):
        content.append(f"\n{'='*80}\nDOMAIN: {domain}\n{'='*80}\n")
        
        for file_path in domains[domain]["files"]:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content.append(f"\n--- FILE: {file_path} ---\n")
                    content.append(f.read())
    
    return "\n".join(content), domains_to_load
