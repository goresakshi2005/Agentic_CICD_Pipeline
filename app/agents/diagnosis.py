from app.config import GEMINI_API_KEY
from app.knowledge_base import search_similar_problems
from app.github_client import get_commit_details, get_test_results
import json
import re

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GEMINI_API_KEY, temperature=0)

diagnosis_prompt = PromptTemplate(
    input_variables=["logs", "commit_message", "diff", "test_output", "similar_issues"],
    template="""
You are a DevOps expert. Analyze the CI/CD pipeline failure.

Commit Message: {commit_message}
Files changed: {diff}

Test output (if any): {test_output}

Pipeline logs (last 2000 chars): {logs}

Similar past issues: {similar_issues}

Provide a JSON output with:
- "root_cause": concise description
- "confidence": 0-1
- "suggested_fix_type": one of ["dependency", "test_failure", "syntax_error", "config_error", "flaky_test", "other"]
- "details": extra info (e.g., missing package name, test name)
- "requires_approval": boolean (true if high risk)
"""
)

# app/agents/diagnosis.py (modify diagnose_failure signature and usage)

async def diagnose_failure(run_id: int, commit_sha: str, logs: str, test_output: str = "") -> dict:
    commit_data = await get_commit_details(commit_sha)
    commit_message = commit_data.get("commit", {}).get("message", "")
    files = commit_data.get("files", [])
    diff_text = "\n".join([f"{f['filename']}: {f['status']}" for f in files])

    similar = search_similar_problems(logs[:500])
    similar_text = "\n".join(similar) if similar else "No similar past issues."

    prompt = diagnosis_prompt.format(
        logs=logs[-2000:],
        commit_message=commit_message,
        diff=diff_text,
        test_output=test_output,
        similar_issues=similar_text
    )
    response = llm.invoke([HumanMessage(content=prompt)])

async def extract_test_output(run_id: int, logs: str) -> str:
    # Simple extraction: look for lines between "test session starts" and a summary
    match = re.search(r"=+ test session starts =+(.*?)(=+ .*? in .*? =+)", logs, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "No structured test output found."