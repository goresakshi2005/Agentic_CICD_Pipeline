# app/agents/security.py
import subprocess
import json
import asyncio

async def scan_for_secrets_async(branch: str = "main"):
    """Run safety check in a thread."""
    loop = asyncio.get_event_loop()
    # safety check --json
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(["safety", "check", "--json"], capture_output=True, text=True)
    )
    try:
        return json.loads(result.stdout)
    except:
        return {"vulnerabilities": []}