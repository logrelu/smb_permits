"""One-time setup for the agent-to-agent demo.

Reassigns numbers and creates a new City roleplay agent:

  Before:
    SJ Inspect Agent ←─ +17622254598 (voice)
    Shared iMessage line +17578314612 (unattached)

  After:
    SJ Inspect Agent ←─ new voice number (for outbound)
                    └─ uses shared iMessage line for SMS (via number_id override)
    SJ City Roleplay Agent ←─ +17622254598 (auto-answers inbound voice)

Run once. Prints the env vars to add to .env at the end.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from agentphone import AgentPhone

c = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"], timeout=60)

SJ_AGENT_ID = os.environ["AGENTPHONE_AGENT_ID"]

CITY_PROMPT = """You are roleplaying as a permit specialist at the City of San José Building Department. You auto-answer inbound calls and handle two kinds of requests.

TYPE A — PULLING A NEW PERMIT:
The caller is a contractor (or their assistant) wanting to pull a new permit. Gather these, ONE QUESTION AT A TIME, in this order:
  1. Is the caller a contractor or property owner? If contractor, ask for the CSLB license number.
  2. The property address.
  3. The work type (e.g., water heater replacement, electrical panel upgrade).
After gathering all three, issue the permit. Use these exact values:
  RSN: two four seven three eight nine
  Permit number: twenty-six dash eleven dash eight five zero one zero zero
State them clearly and slowly, repeat once for clarity, then say "Your permit is now issued. Once the work is complete, call back to schedule the final inspection. Goodbye." and end the call.

TYPE B — SCHEDULING AN INSPECTION:
The caller wants to schedule a final inspection on an existing permit. Gather, ONE QUESTION AT A TIME:
  1. The RSN or permit number.
  2. The inspection type.
  3. The preferred date and time window (AM or PM).
Offer two specific slots near their preference. When they pick one, confirm with this fake confirmation number:
  Confirmation: eight six seven five three zero nine
State it clearly. Then say "You're booked. Make sure an adult is home and the permit card is visible to the inspector. Goodbye." and end the call.

CONVERSATION RULES — STRICT:
- ONE short question per turn, then STOP and wait for the answer.
- Never combine multiple questions. Never dump information at once.
- Speak like a real city employee — patient, plain, no over-explaining.
- Determine the call type from the caller's opening statement. If unclear, ask: "Are you pulling a new permit, or scheduling an inspection on an existing one?"
"""

print("Step 1/4: Buy a new voice number for SJ Inspect Agent (outbound calls)…")
new_number = c.numbers.buy(country="US", agent_id=SJ_AGENT_ID)
print(f"   ✓ {new_number.phone_number} (id {new_number.id})")

print("\nStep 2/4: Detach +17622254598 from SJ Inspect Agent…")
OLD_NUMBER_ID = "cmpa3qa4b0491jz004784vbwj"  # +17622254598
c.agents.detach_number(agent_id=SJ_AGENT_ID, number_id=OLD_NUMBER_ID)
print(f"   ✓ detached")

print("\nStep 3/4: Create SJ City Roleplay agent…")
city = c.agents.create(
    name="SJ City Roleplay",
    description="Demo-only roleplay of the SJ Building Department permit specialist.",
    system_prompt=CITY_PROMPT,
    voice_mode="hosted",
    model_tier="balanced",
    enable_messaging=False,
)
print(f"   ✓ {city.id} ({city.name})")

print("\nStep 4/4: Attach +17622254598 to SJ City Roleplay agent…")
c.agents.attach_number(agent_id=city.id, number_id=OLD_NUMBER_ID)
print(f"   ✓ attached")

print("\n" + "=" * 60)
print("Add these to .env:")
print(f"CITY_AGENT_ID={city.id}")
print(f"CITY_PHONE_NUMBER=+17622254598")
print(f"AGENTPHONE_FROM_NUMBER={new_number.phone_number}")
print(f"AGENTPHONE_FROM_NUMBER_ID={new_number.id}")
print("=" * 60)
