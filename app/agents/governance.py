import os
from slack_sdk.web.async_client import AsyncWebClient
from app.config import SLACK_TOKEN, SLACK_CHANNEL

slack_client = AsyncWebClient(token=SLACK_TOKEN) if SLACK_TOKEN else None

async def requires_human_approval(diagnosis: dict, run_data: dict) -> bool:
    # Risk factors: deployment to prod, changes to critical files, low confidence, security issues
    branch = run_data.get("head_branch")
    if branch == "main" or branch == "production":
        return True
    if diagnosis.get("confidence", 1) < 0.7:
        return True
    if diagnosis.get("suggested_fix_type") in ["config_error", "dependency"]:
        # Could be risky if it's a security patch
        pass
    return False

async def request_approval(run_id: int, diagnosis: dict, fix_plan: dict):
    # Store in DB
    from app.database import SessionLocal, PipelineRun
    db = SessionLocal()
    run = db.query(PipelineRun).filter_by(run_id=run_id).first()
    if run:
        run.approval_status = "pending"
        db.commit()
    db.close()

    # Send Slack message
    if slack_client:
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Approval Required for Run {run_id}*"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause:* {diagnosis.get('root_cause')}"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "value": f"approve_{run_id}",
                        "action_id": "approve"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "value": f"reject_{run_id}",
                        "action_id": "reject"
                    }
                ]
            }
        ]
        await slack_client.chat_postMessage(channel=SLACK_CHANNEL, blocks=blocks)