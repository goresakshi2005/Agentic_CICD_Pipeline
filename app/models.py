from pydantic import BaseModel
from typing import Optional, Dict, Any

class WebhookPayload(BaseModel):
    action: str
    workflow_run: Optional[Dict[str, Any]]
    repository: Optional[Dict[str, Any]]
    sender: Optional[Dict[str, Any]]

class ApprovalRequest(BaseModel):
    run_id: int
    approved: bool
    user: str