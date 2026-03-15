async def requires_human_approval(diagnosis: dict, run_data: dict) -> bool:
    """Determine if the fix/deployment requires human approval."""
    # Example: if deployment to production or high-risk change
    # For simplicity, always require approval for now, but could use diagnosis confidence, etc.
    return True

# We'll handle approval via an API endpoint that stores pending approvals.
# For now, we'll have a simple in-memory store.
pending_approvals = {}  # run_id -> (diagnosis, fix_plan)

def store_pending_approval(run_id: int, diagnosis: dict, fix_plan: dict):
    pending_approvals[run_id] = (diagnosis, fix_plan)

def get_pending_approval(run_id: int):
    return pending_approvals.get(run_id)

def remove_pending_approval(run_id: int):
    pending_approvals.pop(run_id, None)