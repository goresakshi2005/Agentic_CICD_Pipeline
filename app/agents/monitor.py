async def monitor_workflow(run_data: dict) -> bool:
    """Return True if workflow failed."""
    conclusion = run_data.get("conclusion")
    status = run_data.get("status")
    # If conclusion is 'failure' or status is 'completed' with conclusion 'failure'
    if status == "completed" and conclusion == "failure":
        return True
    return False