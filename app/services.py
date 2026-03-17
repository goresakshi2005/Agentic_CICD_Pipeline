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
        # 1. Check if a record already exists for this run_id
        db_run = db.query(PipelineRun).filter_by(run_id=run_id).first()

        if not db_run:
            # Create a new record
            db_run = PipelineRun(
                run_id=run_id,
                status=run_data["status"],
                conclusion=run_data["conclusion"],
                commit_sha=commit_sha,
                branch=run_data.get("head_branch"),
                approval_status="pending"  # default
            )
            db.add(db_run)
        else:
            # Update existing record's basic fields (in case they changed)
            db_run.status = run_data["status"]
            db_run.conclusion = run_data["conclusion"]
            db_run.commit_sha = commit_sha
            db_run.branch = run_data.get("head_branch")
            # Reset approval status to force fresh approval (if needed)
            db_run.approval_status = "pending"
            # Clear old analysis data – will be overwritten
            db_run.logs = None
            db_run.diagnosis = None
            db_run.fix_plan = None

        # 2. Fetch fresh data from GitHub
        logs = await github_client.get_workflow_logs(run_id)
        if not logs:
            logger.error("No logs")
            return

        test_output = await github_client.get_test_results(run_id)

        # 3. Run diagnosis
        diag = await diagnosis.diagnose_failure(run_id, commit_sha, logs, test_output)
        logger.info(f"Diagnosis: {diag}")

        # 4. Security scan (async)
        sec_issues = await security.scan_for_secrets_async()
        if sec_issues and sec_issues.get("vulnerabilities"):
            diag["security_issues"] = sec_issues
            diag["requires_approval"] = True

        # 5. Generate fix plan
        fix_plan = await repair.generate_fix(diag)
        logger.info(f"Fix plan: {fix_plan}")

        # 6. Update the record with new analysis
        db_run.logs = logs
        db_run.diagnosis = diag
        db_run.fix_plan = fix_plan
        db.commit()  # persist all changes

        # 7. Handle approval or auto-apply
        if await governance.requires_human_approval(diag, run_data):
            await governance.request_approval(run_id, diag, fix_plan)
        else:
            pr_url = await repair.apply_fix(fix_plan)
            if pr_url:
                logger.info(f"Created PR: {pr_url}")

    except Exception as e:
        logger.exception(f"Error processing failed run {run_id}")
        db.rollback()  # ensure transaction is rolled back on error
    finally:
        db.close()