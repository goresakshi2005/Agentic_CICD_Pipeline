# app/github_client.py
import httpx
import base64
import io
import zipfile
from junitparser import JUnitXml
from typing import Optional, Dict, Any, List
from app.config import GITHUB_TOKEN, GITHUB_REPO

GITHUB_API_BASE = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# ---------- Existing functions (keep them) ----------
async def get_workflow_run(run_id: int) -> Optional[Dict[str, Any]]:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs/{run_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
    return None

async def get_workflow_logs(run_id: int) -> Optional[str]:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs/{run_id}/logs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    return None

async def get_commit_details(commit_sha: str) -> Optional[Dict[str, Any]]:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/commits/{commit_sha}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
    return None

async def create_pull_request(title: str, body: str, head: str, base: str = "main") -> Optional[Dict[str, Any]]:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/pulls"
    data = {"title": title, "body": body, "head": head, "base": base}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=HEADERS)
        if resp.status_code == 201:
            return resp.json()
    return None

async def get_file_content(path: str, ref: str = "main") -> Optional[str]:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}?ref={ref}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            return base64.b64decode(data["content"]).decode("utf-8")
    return None

async def create_branch(branch_name: str, from_branch: str = "main") -> bool:
    # Get SHA of base branch
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/git/ref/heads/{from_branch}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            return False
        sha = resp.json()["object"]["sha"]

    # Create new branch
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/git/refs"
    data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=HEADERS)
        return resp.status_code == 201

async def update_file(path: str, content: str, commit_message: str, branch: str) -> bool:
    # Get current file's SHA if exists
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}?ref={branch}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        sha = resp.json()["sha"] if resp.status_code == 200 else None

    content_bytes = content.encode("utf-8")
    content_b64 = base64.b64encode(content_bytes).decode("utf-8")
    data = {"message": commit_message, "content": content_b64, "branch": branch}
    if sha:
        data["sha"] = sha

    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.put(url, json=data, headers=HEADERS)
        return resp.status_code in (200, 201)

async def trigger_workflow_dispatch(workflow_id: str, ref: str = "main", inputs: dict = None):
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/workflows/{workflow_id}/dispatches"
    data = {"ref": ref}
    if inputs:
        data["inputs"] = inputs
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=HEADERS)
        return resp.status_code == 204

async def get_deployment_status(deployment_id: int) -> dict:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/deployments/{deployment_id}/statuses"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        return resp.json() if resp.status_code == 200 else {}

# ---------- NEW functions needed for monitoring and test artifacts ----------
async def list_workflow_runs(status: str = None, per_page: int = 30) -> List[Dict[str, Any]]:
    """List workflow runs, optionally filtered by status."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs"
    params = {"per_page": per_page}
    if status:
        params["status"] = status
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, params=params)
        if resp.status_code == 200:
            return resp.json()["workflow_runs"]
    return []

async def list_artifacts(run_id: int) -> List[Dict[str, Any]]:
    """List artifacts for a workflow run."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs/{run_id}/artifacts"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json().get("artifacts", [])
    return []

async def download_artifact(artifact_url: str) -> Optional[bytes]:
    """Download an artifact zip."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(artifact_url, headers=HEADERS, follow_redirects=True)
        if resp.status_code == 200:
            return resp.content
    return None

async def get_test_results(run_id: int) -> str:
    """Attempt to download and parse JUnit XML from artifacts."""
    artifacts = await list_artifacts(run_id)
    # Look for an artifact containing test results (common names)
    test_artifact = None
    for art in artifacts:
        name = art["name"].lower()
        if "test" in name or "junit" in name or "report" in name:
            test_artifact = art
            break
    if not test_artifact:
        return "No test artifact found."

    archive_url = test_artifact["archive_download_url"]
    data = await download_artifact(archive_url)
    if not data:
        return "Failed to download artifact."

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml_files = [f for f in z.namelist() if f.endswith(".xml")]
            if not xml_files:
                return "No XML file in artifact."
            with z.open(xml_files[0]) as f:
                content = f.read().decode("utf-8")
                # Parse with junitparser to extract failures
                xml = JUnitXml.fromstring(content)
                failures = []
                for suite in xml:
                    for case in suite:
                        if case.result and case.result.type == "failure":
                            failures.append(f"{case.name}: {case.result.message}")
                if failures:
                    return "Test failures:\n" + "\n".join(failures)
                else:
                    return "Test report found, but no failures."
    except Exception as e:
        return f"Error parsing test artifact: {e}"