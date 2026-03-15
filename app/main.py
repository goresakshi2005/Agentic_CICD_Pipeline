from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from app import github_client
from app.agents import monitor, diagnosis, repair, governance, orchestrator
from app.models import WebhookPayload, ApprovalRequest
import logging
import time

app = FastAPI()
logger = logging.getLogger(__name__)

@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive GitHub webhook for workflow_run events."""
    payload = await request.json()
    # Verify signature if secret set (optional, skipped for brevity)
    event = request.headers.get("X-GitHub-Event")
    if event != "workflow_run":
        return {"status": "ignored"}

    run_data = payload.get("workflow_run")
    if not run_data:
        raise HTTPException(400, "Invalid payload")

    # Only handle completed failures
    if run_data.get("status") != "completed" or run_data.get("conclusion") != "failure":
        return {"status": "ignored"}

    # Pass to background processing
    background_tasks.add_task(process_failed_run, run_data)
    return {"status": "processing"}

async def process_failed_run(run_data: dict):
    run_id = run_data["id"]
    head_commit = run_data.get("head_commit", {})
    commit_sha = head_commit.get("id") or run_data.get("head_sha")
    if not commit_sha:
        logger.error("No commit SHA found")
        return

    logger.info(f"Processing failed run {run_id}")

    # 1. Get logs
    logs = await github_client.get_workflow_logs(run_id)
    if not logs:
        logger.error("Could not fetch logs")
        return

    # 2. Diagnose
    diag = await diagnosis.diagnose_failure(run_id, commit_sha, logs)
    logger.info(f"Diagnosis: {diag}")

    # 3. Generate fix
    fix_plan = await repair.generate_fix(diag)
    logger.info(f"Fix plan: {fix_plan}")

    # 4. Check if human approval needed
    if await governance.requires_human_approval(diag, run_data):
        # Store for approval
        governance.store_pending_approval(run_id, diag, fix_plan)
        # Notify human (e.g., via webhook, email). We'll expose an endpoint for approval.
        logger.info(f"Waiting for approval for run {run_id}")
        # You could send Slack message here
    else:
        # Apply fix automatically
        pr_url = await repair.apply_fix(fix_plan)
        if pr_url:
            logger.info(f"Created PR: {pr_url}")
            # Optionally, after PR merge, auto-deploy? We'll keep simple.
        else:
            logger.info("No changes applied or fix failed.")

@app.post("/approve")
async def approve_action(req: ApprovalRequest):
    """Human approval endpoint."""
    run_id = req.run_id
    approved = req.approved
    pending = governance.get_pending_approval(run_id)
    if not pending:
        raise HTTPException(404, "No pending approval for this run")

    diag, fix_plan = pending
    if approved:
        # Apply fix
        pr_url = await repair.apply_fix(fix_plan)
        if pr_url:
            # Optionally, if this is a deployment, we could trigger after PR merge
            # For now, just return
            governance.remove_pending_approval(run_id)
            return {"status": "approved", "pr_url": pr_url}
        else:
            return {"status": "fix_failed"}
    else:
        governance.remove_pending_approval(run_id)
        return {"status": "rejected"}

@app.get("/health")
async def health():
    return {"status": "ok"}