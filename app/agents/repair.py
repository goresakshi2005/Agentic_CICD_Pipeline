from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage
from app.config import GEMINI_API_KEY
from app.github_client import get_file_content, create_branch, update_file, create_pull_request
import json

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=GEMINI_API_KEY, temperature=0.2)

repair_prompt = PromptTemplate(
    input_variables=["root_cause", "fix_type", "details", "repo_files"],
    template="""
Based on the diagnosis, generate a fix.

Root Cause: {root_cause}
Fix Type: {fix_type}
Details: {details}

Current repository files (relevant ones):
{repo_files}

You need to propose changes to fix the pipeline. Provide a JSON output with:
- "files_to_change": a list of objects, each with "path" and "new_content" (full file content after change)
- "commit_message": a descriptive commit message for the fix
- "pr_title": title for the pull request
- "pr_body": description of the fix

If no file changes are needed (e.g., just retry), set files_to_change empty.
"""
)

async def generate_fix(diagnosis: dict) -> dict:
    # Fetch relevant files (we might need to know which files to fetch; for simplicity, fetch common ones like requirements.txt, Dockerfile, etc.)
    common_files = ["requirements.txt", "setup.py", "Dockerfile", ".github/workflows/ci.yml"]
    repo_files_content = {}
    for file in common_files:
        content = await get_file_content(file)
        if content:
            repo_files_content[file] = content

    prompt = repair_prompt.format(
        root_cause=diagnosis["root_cause"],
        fix_type=diagnosis["suggested_fix_type"],
        details=diagnosis.get("details", ""),
        repo_files=json.dumps(repo_files_content, indent=2)
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        fix_plan = json.loads(response.content)
    except:
        fix_plan = {"files_to_change": [], "commit_message": "Auto-fix", "pr_title": "Auto-fix pipeline", "pr_body": response.content}
    return fix_plan

async def apply_fix(fix_plan: dict, base_branch: str = "main") -> Optional[str]:
    """Create a branch, apply changes, and create PR. Returns PR URL if created."""
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

    # Create PR
    pr = await create_pull_request(
        title=fix_plan["pr_title"],
        body=fix_plan["pr_body"],
        head=branch_name,
        base=base_branch
    )
    if pr:
        return pr["html_url"]
    return None