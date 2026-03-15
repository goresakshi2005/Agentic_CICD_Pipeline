import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # format: owner/repo
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")