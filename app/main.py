from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from app import github_client
from app.agents import monitor, diagnosis, repair, governance, orchestrator, security
from app.models import ApprovalRequest
from app.database import SessionLocal, PipelineRun
import logging
import json

app = FastAPI()
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor.monitor_recent_runs())

@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")
    if event != "workflow_run":
        return {"status": "ignored"}

    run_data = payload.get("workflow_run")
    if not run_data:
        raise HTTPException(400, "Invalid payload")

    if run_data.get("status") == "completed" and run_data.get("conclusion") == "failure":
        background_tasks.add_task(process_failed_run, run_data)
        return {"status": "processing"}
    return {"status": "ignored"}

async def process_failed_run(run_data: dict):
    run_id = run_data["id"]
    commit_sha = run_data.get("head_sha")
    if not commit_sha:
        logger.error("No commit SHA")
        return

    # Save to DB
    db = SessionLocal()
    db_run = PipelineRun(run_id=run_id, status=run_data["status"], conclusion=run_data["conclusion"], commit_sha=commit_sha, branch=run_data.get("head_branch"))
    db.add(db_run)
    db.commit()

    logs = await github_client.get_workflow_logs(run_id)
    if not logs:
        logger.error("No logs")
        return

    diag = await diagnosis.diagnose_failure(run_id, commit_sha, logs)
    logger.info(f"Diagnosis: {diag}")

    # Optionally run security scan
    sec_issues = await security.scan_for_secrets()
    if sec_issues.get("vulnerabilities"):
        diag["security_issues"] = sec_issues
        diag["requires_approval"] = True

    fix_plan = await repair.generate_fix(diag)
    logger.info(f"Fix plan: {fix_plan}")

    # Update DB
    db_run.diagnosis = diag
    db_run.fix_plan = fix_plan
    db.commit()

    if await governance.requires_human_approval(diag, run_data):
        await governance.request_approval(run_id, diag, fix_plan)
    else:
        pr_url = await repair.apply_fix(fix_plan)
        if pr_url:
            logger.info(f"Created PR: {pr_url}")
            # Optionally trigger canary after PR merge (would need webhook for pull_request)
        db.close()

@app.post("/approve")
async def approve_action(req: ApprovalRequest):
    db = SessionLocal()
    run = db.query(PipelineRun).filter_by(run_id=req.run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")

    if req.approved:
        pr_url = await repair.apply_fix(run.fix_plan)
        run.approval_status = "approved"
        if pr_url:
            # Could also trigger deployment after PR merge
            pass
    else:
        run.approval_status = "rejected"
    db.commit()
    db.close()
    return {"status": "approved" if req.approved else "rejected", "pr_url": pr_url if req.approved else None}

@app.get("/health")
async def health():
    return {"status": "ok"}