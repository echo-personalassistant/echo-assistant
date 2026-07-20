import requests
from config import GITHUB_TOKEN

def _get_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

def gh_list_prs(repo: str, state: str = "open") -> str:
    """
    List pull requests in a GitHub repository.

    Args:
        repo: The repository in 'owner/repo' format (e.g. 'octocat/Hello-World').
        state: State of pull requests: 'open', 'closed', or 'all'. Defaults to 'open'.
    """
    if not GITHUB_TOKEN:
        return "Error: GITHUB_TOKEN is not configured in config.py"

    url = f"https://api.github.com/repos/{repo}/pulls?state={state}"
    try:
        response = requests.get(url, headers=_get_headers(), timeout=10)
        if response.status_code != 200:
            return f"Error: GitHub API returned status {response.status_code}: {response.text}"
        prs = response.json()
        if not prs:
            return f"No {state} pull requests found in {repo}."
        
        result_lines = [f"{state.capitalize()} PRs for {repo}:"]
        for pr in prs[:10]: # Limit to top 10
            result_lines.append(f"- #{pr['number']}: {pr['title']} by {pr['user']['login']} ({pr['html_url']})")
        return "\n".join(result_lines)
    except Exception as e:
        return f"Error connecting to GitHub: {e}"

def gh_create_issue(repo: str, title: str, body: str = "") -> str:
    """
    Create an issue in a GitHub repository.

    Args:
        repo: The repository in 'owner/repo' format.
        title: The title of the issue.
        body: The markdown body content of the issue (optional).
    """
    if not GITHUB_TOKEN:
        return "Error: GITHUB_TOKEN is not configured in config.py"

    url = f"https://api.github.com/repos/{repo}/issues"
    data = {"title": title}
    if body:
        data["body"] = body

    try:
        response = requests.post(url, headers=_get_headers(), json=data, timeout=10)
        if response.status_code != 201:
            return f"Error: GitHub API returned status {response.status_code}: {response.text}"
        issue = response.json()
        return f"Successfully created issue #{issue['number']}: {issue['title']}\nURL: {issue['html_url']}"
    except Exception as e:
        return f"Error connecting to GitHub: {e}"

def gh_list_repos(org: str = "") -> str:
    """
    List repositories. If org is specified, lists repositories for that organization.
    Otherwise lists repositories for the authenticated user.

    Args:
        org: Organization name (optional).
    """
    if not GITHUB_TOKEN:
        return "Error: GITHUB_TOKEN is not configured in config.py"

    if org:
        url = f"https://api.github.com/orgs/{org}/repos"
    else:
        url = "https://api.github.com/user/repos"

    try:
        response = requests.get(url, headers=_get_headers(), timeout=10)
        if response.status_code != 200:
            return f"Error: GitHub API returned status {response.status_code}: {response.text}"
        repos = response.json()
        if not repos:
            return "No repositories found."
        
        result_lines = ["Repositories:"]
        for repo in repos[:15]: # Limit to top 15
            result_lines.append(f"- {repo['full_name']} ({repo['html_url']})")
        return "\n".join(result_lines)
    except Exception as e:
        return f"Error connecting to GitHub: {e}"

TOOL_SCHEMAS_GITHUB = [
    {
        "type": "function",
        "function": {
            "name": "gh_list_prs",
            "description": "List pull requests in a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "The repository owner/name, e.g. 'facebook/react'"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "State of pull requests. Default is 'open'."}
                },
                "required": ["repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gh_create_issue",
            "description": "Create an issue in a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "The repository owner/name, e.g. 'facebook/react'"},
                    "title": {"type": "string", "description": "The issue title."},
                    "body": {"type": "string", "description": "Optional issue body content."}
                },
                "required": ["repo", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gh_list_repos",
            "description": "List GitHub repositories for the authenticated user or an organization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "org": {"type": "string", "description": "Optional organization name. If not provided, lists the authenticated user's repos."}
                }
            }
        }
    }
]
