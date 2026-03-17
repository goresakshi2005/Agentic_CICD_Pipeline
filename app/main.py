# app/main.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from app import github_client
from app.agents import monitor   # keep monitor import for startup
from app.services import process_failed_run   # new
from app.models import ApprovalRequest
from app.database import SessionLocal, PipelineRun
import logging
import asyncio

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

@app.post("/approve")
async def approve_action(req: ApprovalRequest):
    db = SessionLocal()
    run = db.query(PipelineRun).filter_by(run_id=req.run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")

    pr_url = None
    if req.approved:
        # Re-use repair.apply_fix with the stored fix_plan
        from app.agents.repair import apply_fix
        pr_url = await apply_fix(run.fix_plan)
        run.approval_status = "approved"
    else:
        run.approval_status = "rejected"
    db.commit()
    db.close()
    return {"status": "approved" if req.approved else "rejected", "pr_url": pr_url}

@app.get("/health")
async def health():
    return {"status": "ok"}