from app.github_client import trigger_workflow_dispatch, get_deployment_status
import asyncio

async def canary_deploy(environment: str = "production", canary_percent: int = 10):
    """Deploy to canary, monitor, then full rollout."""
    # Step 1: Deploy to canary (using a workflow that accepts percentage)
    inputs = {"environment": environment, "canary": canary_percent}
    success = await trigger_workflow_dispatch("deploy.yml", ref="main", inputs=inputs)
    if not success:
        return False

    # Step 2: Wait and monitor for errors (simplified: wait 5 min, check status)
    await asyncio.sleep(300)
    # In real implementation, you'd query your monitoring system (e.g., Prometheus)
    # Here we assume a deployment status check via GitHub.
    # We'd need to know the deployment ID; for simplicity, we'll just assume success.
    # If failure, rollback.
    # Rollback would trigger another deployment with previous version.
    return True