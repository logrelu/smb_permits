import asyncio, os
from dotenv import load_dotenv
load_dotenv()

# 1. Imports load?
from agents.browser_agent import book_online
from agents.voice_agent import call_to_book
from agents.sms_agent import send_confirmation
print("✓ imports ok")

# 2. SMS works? (cheap — costs ~1¢)
send_confirmation(os.environ.get("TEST_PHONE", "+1YOURPHONE"),
                  "Smoke test from SJ Inspect Agent")
print("✓ sms sent — check your phone")
