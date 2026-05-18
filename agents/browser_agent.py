"""Browser Use agent — navigates the sjpermits.org Unregistered Permit Wizard.

This wizard is the city's "what permit do I need?" categorization tool. It does
not actually file the permit — that requires login. For the demo, we use it to
*identify* the permit category from minimal contractor input.

Uses ChatBrowserUse (so it runs on browser-use hackathon credits, not Anthropic).
"""
from browser_use import Agent, Browser, ChatBrowserUse


async def navigate_permit_wizard(license_num: str, work_type: str, address: str) -> str:
    """Walk the unregistered permit wizard to identify the permit category.

    Returns a string the orchestrator can log/parse. Does NOT submit.
    """
    task = f"""Navigate San José's online permit wizard to identify the correct permit category for a job. Do NOT log in. Do NOT submit anything.

JOB INPUTS:
  CSLB License: {license_num}
  Address: {address}
  Work: {work_type}

STEPS:
  1. Open this exact URL directly:
       https://portal.sanjoseca.gov/deployed/sfjsp?interviewID=ApplicationWiz&workspace=Lit_Ips_Frd&lang=en
  2. The wizard will ask which department. Pick "Building" and click any continue/next button.
  3. Pick "Residential Single-Family & Duplex (RS) = 1 & 2 Family Residential Projects (including a 2nd Unit, ADU, etc.)" and continue.
  4. For a water heater replacement, pick "Mechanical, Electrical and Plumbing Permits (water heater, furnace, electrical panel, property line cleanout, etc.)" and continue.
  5. When asked Single-Family or Duplex, pick "Single-Family" and continue.
  6. Click "View Permit Type".
  7. You should land on an "ADD NEW APPLICATION" page that shows four populated dropdowns: Application Group, Application Type, Application Sub Type, Application Work Type.
  8. STOP here. Do NOT click "Return to Login". Do NOT submit anything.

OUTPUT (final answer): extract the *visible human-readable label text* shown to the user in each dropdown (NOT internal value codes or IDs). For example the Application Group dropdown displays "Building" — that is the text you want, not "10". Return a single line:
  CATEGORIZED: group=<visible text> | type=<visible text> | sub=<visible text> | work=<visible text>

Expected for a water heater on a single-family home:
  CATEGORIZED: group=Building | type=1 & 2 Family Detached Dwellings (including ADU) | sub=Single-Family | work=Simple Mechanical/Plumbing/Electrical Permits (Water Heater, Furnace, etc.)

If you hit a blocker (CAPTCHA, page not loading, layout changed unexpectedly), return:
  FAILED: <one-sentence reason>
"""
    browser = Browser()
    agent = Agent(
        task=task,
        llm=ChatBrowserUse(),
        browser=browser,
        use_vision=False,
    )
    history = await agent.run()
    return history.final_result()
