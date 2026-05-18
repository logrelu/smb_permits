"""AgentPhone iMessage / SMS sender."""
import os
from agentphone import AgentPhone


def send_message(to_number: str, body: str) -> None:
    """Send an iMessage/SMS via AgentPhone. The body is sent verbatim."""
    client = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])
    client.messages.send(
        agent_id=os.environ["AGENTPHONE_AGENT_ID"],
        to_number=to_number,
        body=body,
        number_id=os.environ.get("AGENTPHONE_NUMBER_ID") or None,
    )


def send_confirmation(to_number: str, summary: str) -> None:
    """Back-compat alias for send_message — sends body verbatim, no decoration."""
    send_message(to_number, summary)
