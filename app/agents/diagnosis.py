from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage
from app.config import GEMINI_API_KEY
from app.knowledge_base import search_similar_problems
import json

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=GEMINI_API_KEY, temperature=0)

diagnosis_prompt = PromptTemplate(
    input_variables=["logs", "commit_message", "diff", "similar_issues"],
    template="""
You are a DevOps expert. Analyze the CI/CD pipeline failure logs and the related commit to diagnose the root cause.

Commit Message:
{commit_message}

Commit Diff (files changed):
{diff}

Pipeline Logs (last 100 lines):
{logs}

Similar past issues and solutions:
{similar_issues}

Provide a JSON output with:
- "root_cause": a concise description of the problem
- "confidence": a number between 0 and 1
- "suggested_fix_type": one of ["dependency", "test_failure", "syntax_error", "config_error", "other"]
- "details": any extra details
"""
)

async def diagnose_failure(run_id: int, commit_sha: str, logs: str) -> dict:
    # Get commit details
    from app.github_client import get_commit_details
    commit_data = await get_commit_details(commit_sha)
    commit_message = commit_data.get("commit", {}).get("message", "")
    # Get diff (simplified: we can get files changed)
    files = commit_data.get("files", [])
    diff_text = "\n".join([f"{f['filename']}: {f['status']}" for f in files])

    # Search knowledge base for similar issues
    similar = search_similar_problems(logs[:500])  # use first 500 chars as query
    similar_text = "\n".join(similar) if similar else "No similar past issues."

    prompt = diagnosis_prompt.format(
        logs=logs[-2000:],  # last 2000 chars
        commit_message=commit_message,
        diff=diff_text,
        similar_issues=similar_text
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    # Expect JSON response
    try:
        result = json.loads(response.content)
    except:
        # Fallback
        result = {"root_cause": "Unknown", "confidence": 0.5, "suggested_fix_type": "other", "details": response.content}
    return result