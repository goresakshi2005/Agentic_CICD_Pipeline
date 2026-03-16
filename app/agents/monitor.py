# app/agents/monitor.py
import asyncio
from app.github_client import list_workflow_runs
from app.database import SessionLocal, PipelineRun
from app.services import process_failed_run   # <-- import from services
import logging

logger = logging.getLogger(__name__)

async def monitor_recent_runs():
    while True:
        try:
            runs = await list_workflow_runs(status="completed", per_page=10)
            db = SessionLocal()
            for run in runs:
                run_id = run["id"]
                existing = db.query(PipelineRun).filter_by(run_id=run_id).first()
                if not existing and run["conclusion"] == "failure":
                    logger.info(f"Monitor found unprocessed failed run {run_id}")
                    asyncio.create_task(process_failed_run(run))
            db.close()
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        await asyncio.sleep(60)