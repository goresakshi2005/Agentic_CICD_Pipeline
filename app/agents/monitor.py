import asyncio
from app.github_client import get_workflow_run
from app.database import SessionLocal, PipelineRun
from app.agents.diagnosis import diagnose_failure
from app.main import process_failed_run  # careful with circular imports; better to move logic to a service
import logging

logger = logging.getLogger(__name__)

async def monitor_recent_runs():
    """Periodically check for recent failed runs not yet processed."""
    while True:
        try:
            # Use GitHub API to list recent runs (simplified: get last 10)
            # This requires a new github_client method; we'll add it.
            from app.github_client import list_workflow_runs
            runs = await list_workflow_runs(status="completed", per_page=10)
            db = SessionLocal()
            for run in runs:
                run_id = run["id"]
                existing = db.query(PipelineRun).filter_by(run_id=run_id).first()
                if not existing and run["conclusion"] == "failure":
                    # Process this run
                    logger.info(f"Monitor found unprocessed failed run {run_id}")
                    # Schedule processing (we can use asyncio.create_task)
                    asyncio.create_task(process_failed_run(run))
            db.close()
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        await asyncio.sleep(60)  # poll every minute