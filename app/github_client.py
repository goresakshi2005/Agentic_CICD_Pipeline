# ... (keep existing methods) ...

async def get_test_results(run_id: int) -> Optional[str]:
    """Download and parse test report (assuming JUnit XML is uploaded as artifact)."""
    # GitHub doesn't store test reports directly; we'd need to download from artifacts.
    # Simplified: assume logs contain test output.
    logs = await get_workflow_logs(run_id)
    return logs  # for now

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

async def list_workflow_runs(status: str = None, per_page: int = 30):
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/runs"
    params = {"per_page": per_page}
    if status:
        params["status"] = status
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, params=params)
        if resp.status_code == 200:
            return resp.json()["workflow_runs"]
    return []