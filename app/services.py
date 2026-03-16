# app/services.py
import logging
from app import github_client
from app.agents import diagnosis, repair, governance, security
from app.database import SessionLocal, PipelineRun

logger = logging.getLogger(__name__)

async def process_failed_run(run_data: dict):
    run_id = run_data["id"]
    commit_sha = run_data.get("head_sha")
    if not commit_sha:
        logger.error("No commit SHA")
        return

    db = SessionLocal()
    try:
        db_run = PipelineRun(
            run_id=run_id,
            status=run_data["status"],
            conclusion=run_data["conclusion"],
            commit_sha=commit_sha,
            branch=run_data.get("head_branch")
        )
        db.add(db_run)
        db.commit()

        logs = await github_client.get_workflow_logs(run_id)
        if not logs:
            logger.error("No logs")
            return

        # Get test artifacts (if any)
        test_output = await github_client.get_test_results(run_id)

        diag = await diagnosis.diagnose_failure(run_id, commit_sha, logs, test_output)
        logger.info(f"Diagnosis: {diag}")

        # Security scan (async)
        sec_issues = await security.scan_for_secrets_async()
        if sec_issues and sec_issues.get("vulnerabilities"):
            diag["security_issues"] = sec_issues
            diag["requires_approval"] = True

        fix_plan = await repair.generate_fix(diag)
        logger.info(f"Fix plan: {fix_plan}")

        db_run.diagnosis = diag
        db_run.fix_plan = fix_plan
        db.commit()

        if await governance.requires_human_approval(diag, run_data):
            await governance.request_approval(run_id, diag, fix_plan)
        else:
            pr_url = await repair.apply_fix(fix_plan)
            if pr_url:
                logger.info(f"Created PR: {pr_url}")
                # Optionally add to knowledge base after PR merge (requires webhook)
    finally:
        db.close()