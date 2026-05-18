"""One-shot setup: confirm SDK shape, find or create an agent, print its ID."""
import inspect, os
from dotenv import load_dotenv
load_dotenv(".env")

from agentphone import AgentPhone
c = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])

print("─── signatures ───")
print("agents.create           :", inspect.signature(c.agents.create))
print("calls.make_conversation :", inspect.signature(c.calls.make_conversation))
print("messages.send           :", inspect.signature(c.messages.send))

print("\n─── AgentList shape ───")
resp = c.agents.list()
print("type :", type(resp).__name__)
print("attrs:", [a for a in dir(resp) if not a.startswith("_")])

rows = None
for attr in ("data", "items", "agents", "results"):
    if hasattr(resp, attr):
        rows = getattr(resp, attr)
        print(f"rows under .{attr}")
        break
if rows is None and hasattr(resp, "model_dump"):
    print("dump:", resp.model_dump())

print("\n─── existing agents ───")
for a in (rows or []):
    print(" ", a)

if rows:
    first = rows[0]
    agent_id = first.id if hasattr(first, "id") else first["id"]
    print(f"\n➡  Add to .env:\nAGENTPHONE_AGENT_ID={agent_id}")
else:
    print("\nNo agents yet — paste the create signature output above and I'll write the create call.")
