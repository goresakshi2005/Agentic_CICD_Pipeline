from app.config import GEMINI_API_KEY
from app.github_client import get_file_content, create_branch, update_file, create_pull_request
import json
import time
from typing import Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.knowledge_base import search_similar_problems, add_fix_to_knowledge

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GEMINI_API_KEY, temperature=0.2)

repair_prompt = PromptTemplate(
    input_variables=["root_cause", "fix_type", "details", "repo_files", "past_fixes"],
    template="""
Based on the diagnosis, generate a fix.

Root Cause: {root_cause}
Fix Type: {fix_type}
Details: {details}

Current relevant files:
{repo_files}

Similar past fixes:
{past_fixes}

Propose a fix. Output JSON:
- "files_to_change": list of {"path": str, "new_content": str}
- "commit_message": str
- "pr_title": str
- "pr_body": str
- "retry": boolean (if fix is just to rerun pipeline)
- "strategy": one of ["file_update", "retry", "rollback", "other"]
"""
)

async def generate_fix(diagnosis: dict) -> dict:
    common_files = ["requirements.txt", "setup.py", "Dockerfile", ".github/workflows/ci.yml"]
    repo_files_content = {}
    for file in common_files:
        content = await get_file_content(file)
        if content:
            repo_files_content[file] = content

    # Get similar past fixes from knowledge base (text)
    past = search_similar_problems(diagnosis["root_cause"])
    past_fixes = "\n".join(past) if past else "No past fixes."

    prompt = repair_prompt.format(
        root_cause=diagnosis["root_cause"],
        fix_type=diagnosis["suggested_fix_type"],
        details=diagnosis.get("details", ""),
        repo_files=json.dumps(repo_files_content, indent=2),
        past_fixes=past_fixes
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        fix_plan = json.loads(response.content)
    except:
        fix_plan = {"files_to_change": [], "commit_message": "Auto-fix", "pr_title": "Auto-fix pipeline", "pr_body": response.content, "retry": False, "strategy": "other"}
    return fix_plan

async def apply_fix(fix_plan: dict, base_branch: str = "main") -> Optional[str]:
    if fix_plan.get("retry"):
        # Just trigger a new run (maybe via workflow_dispatch)
        # We'll need to know the workflow ID; for simplicity, assume it's the same.
        from app.github_client import trigger_workflow_dispatch
        success = await trigger_workflow_dispatch("ci.yml", ref=base_branch)
        return "retry_triggered" if success else None

    if not fix_plan.get("files_to_change"):
        return None

    branch_name = f"auto-fix-{int(time.time())}"
    success = await create_branch(branch_name, base_branch)
    if not success:
        return None

    for file_change in fix_plan["files_to_change"]:
        path = file_change["path"]
        new_content = file_change["new_content"]
        await update_file(path, new_content, fix_plan["commit_message"], branch_name)

    pr = await create_pull_request(
        title=fix_plan["pr_title"],
        body=fix_plan["pr_body"],
        head=branch_name,
        base=base_branch
    )
    if pr:
        # Record in knowledge base (optional: you may want to wait until PR is merged)
        # For now, we'll add immediately assuming the fix is good.
        add_fix_to_knowledge(diagnosis["root_cause"], fix_plan.get("pr_body", ""), success=True)
        return pr["html_url"]
    return None