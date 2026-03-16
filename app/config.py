import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_REPO = os.getenv("GITHUB_REPO")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# New
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#deploy-approvals")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))  # seconds