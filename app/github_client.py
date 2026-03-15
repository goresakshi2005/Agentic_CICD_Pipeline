import httpx
from typing import Optional, Dict, Any, List
from app.config import GITHUB_TOKEN, GITHUB_REPO

GITHUB_API_BASE = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

async def get_workflow_run(run_id: int) -> Optional[Dict[str, Any]]:
    """Get details of a workflow run."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs/{run_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
    return None

async def get_workflow_logs(run_id: int) -> Optional[str]:
    """Get logs of a workflow run (as text)."""
    # First, get the download URL for logs
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs/{run_id}/logs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    return None

async def get_commit_details(commit_sha: str) -> Optional[Dict[str, Any]]:
    """Get commit details including diff and message."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/commits/{commit_sha}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
    return None

async def create_pull_request(title: str, body: str, head: str, base: str = "main") -> Optional[Dict[str, Any]]:
    """Create a pull request."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/pulls"
    data = {
        "title": title,
        "body": body,
        "head": head,
        "base": base
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=HEADERS)
        if resp.status_code == 201:
            return resp.json()
    return None

async def get_file_content(path: str, ref: str = "main") -> Optional[str]:
    """Get content of a file from repo."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}?ref={ref}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            import base64
            return base64.b64decode(data["content"]).decode("utf-8")
    return None

async def create_branch(branch_name: str, from_branch: str = "main") -> bool:
    """Create a new branch from the base branch."""
    # Get the SHA of the base branch
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/git/ref/heads/{from_branch}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            return False
        sha = resp.json()["object"]["sha"]

    # Create new branch
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/git/refs"
    data = {
        "ref": f"refs/heads/{branch_name}",
        "sha": sha
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=HEADERS)
        return resp.status_code == 201

async def update_file(path: str, content: str, commit_message: str, branch: str) -> bool:
    """Update a file on a given branch (creates commit)."""
    # First, get the current file's SHA (if exists)
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}?ref={branch}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        sha = None
        if resp.status_code == 200:
            sha = resp.json()["sha"]

    import base64
    content_bytes = content.encode("utf-8")
    content_b64 = base64.b64encode(content_bytes).decode("utf-8")

    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.put(url, json=data, headers=HEADERS)
        return resp.status_code in (200, 201)