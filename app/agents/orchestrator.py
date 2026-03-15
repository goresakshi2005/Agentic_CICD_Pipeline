from app.github_client import GITHUB_REPO, HEADERS
import httpx

async def trigger_deployment(environment: str = "production"):
    """Trigger a deployment workflow (assumes a workflow_dispatch event)."""
    # This depends on your setup; we'll assume there's a deploy.yml with workflow_dispatch
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/deploy.yml/dispatches"
    data = {
        "ref": "main",
        "inputs": {
            "environment": environment
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=HEADERS)
        return resp.status_code == 204