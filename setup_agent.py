"""One-time: create the AgentPhone agent for the SJ inspection workflow."""
import os
from dotenv import load_dotenv
load_dotenv(".env")

from agentphone import AgentPhone

c = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])

agent = c.agents.create(
    name="SJ Inspect Agent",
    description="Schedules San Jose building inspections by phone and SMS.",
    system_prompt=(
        "You are a polite assistant helping a homeowner schedule a final "
        "inspection with the City of San Jose Planning, Building and Code "
        "Enforcement Division. State your purpose clearly, give the permit "
        "number and address when asked, and confirm scheduled details by "
        "repeating them back. Speak in short, clear sentences. Never invent "
        "permit numbers or addresses."
    ),
    voice_mode="hosted",      # AgentPhone runs the AI — required for make_conversation
    model_tier="balanced",    # turbo | balanced | max
    enable_messaging=True,
)

print("✅ Created agent")
print(f"   id    : {agent.id}")
print(f"   name  : {agent.name}")
print(f"\nAdd this to .env:\nAGENTPHONE_AGENT_ID={agent.id}")
