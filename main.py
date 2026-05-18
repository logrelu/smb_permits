"""Entry point. Loads the permit, picks a target date, runs the workflow."""
import asyncio
import json
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

from orchestrator import book_inspection

load_dotenv()


def main():
    with open("permit.json") as f:
        permit = json.load(f)

    # SJ Building needs 24-48h notice. Target 3 business days out.
    desired_date = (date.today() + timedelta(days=3)).isoformat()

    print(f"📋 Booking inspection for permit {permit['rsn']} @ {permit['address']}")
    print(f"🗓  Target date: {desired_date}\n")

    try:
        confirmation = asyncio.run(book_inspection(permit, desired_date))
        print(f"\n✅ Inspection booked: {confirmation}")
    except Exception as e:
        print(f"\n❌ Booking failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
