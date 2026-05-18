"""
demo_login.py

Tiny smoke test for browser-use. Logs into a PUBLIC practice site with
PUBLIC test credentials, then verifies the success page. Browser runs
LOCALLY (headed) so you can watch every step.

Site:        https://practicetestautomation.com/practice-test-login/
Credentials: student / Password123   (these are public, site-provided)

Install
-------
    pip install -U browser-use python-dotenv
    uvx browser-use install      # one-time local Chromium

.env (same folder)
------------------
    BROWSER_USE_API_KEY=bu_...   # so ChatBrowserUse is on your hackathon credits

Run
---
    python demo_login.py
"""

import asyncio
import os
from dotenv import load_dotenv

from browser_use import Agent, Browser, ChatBrowserUse

load_dotenv()
os.environ["ANONYMIZED_TELEMETRY"] = "false"

# Same shielding pattern you'll use on sjpermits: real values stay local,
# the LLM only sees the placeholder names `demo_user` and `demo_pass`.
sensitive_data = {
    "https://practicetestautomation.com": {
        "demo_user": "student",
        "demo_pass": "Password123",
    }
}

TASK = """
Step 1. Open https://practicetestautomation.com/practice-test-login/
Step 2. Type `demo_user` into the Username field.
Step 3. Type `demo_pass` into the Password field.
Step 4. Click the Submit button.
Step 5. After the page reloads, confirm it shows the heading
        "Logged In Successfully" and report the exact heading text.

Final answer format:
    STATUS:  <SUCCESS | FAILURE>
    HEADING: <the exact heading text you saw>
"""


async def main():
    browser = Browser()              # local, headed Chromium
    agent = Agent(
        task=TASK,
        llm=ChatBrowserUse(),        # LLM service; covered by your credits
        browser=browser,
        sensitive_data=sensitive_data,
        use_vision=False,            # DOM-only; faster and cheaper
    )
    history = await agent.run()
    print("\n=== RESULT ===")
    print(history.final_result())


if __name__ == "__main__":
    asyncio.run(main())