# app/agents/governance.py
import logging
from app.config import SLACK_TOKEN, SLACK_CHANNEL

logger = logging.getLogger(__name__)

# ... (keep requires_human_approval as before)

async def request_approval(run_id: int, diagnosis: dict, fix_plan: dict):
    from app.database import SessionLocal, PipelineRun
    db = SessionLocal()
    run = db.query(PipelineRun).filter_by(run_id=run_id).first()
    if run:
        run.approval_status = "pending"
        db.commit()
    db.close()

    if SLACK_TOKEN:
        try:
            from slack_sdk.web.async_client import AsyncWebClient
            slack_client = AsyncWebClient(token=SLACK_TOKEN)
            blocks = [ ... ]  # same as before
            await slack_client.chat_postMessage(channel=SLACK_CHANNEL, blocks=blocks)
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            # Fallback: just log
            logger.info(f"Approval required for run {run_id}. Use POST /approve with run_id={run_id}")
    else:
        logger.info(f"Approval required for run {run_id}. Use POST /approve with run_id={run_id}")