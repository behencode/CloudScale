#!/usr/bin/env python3
"""Create a repeatable, local-only CampusConnect dataset for a screen demo."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

DEMO_DB = BACKEND / "data" / "campusconnect-demo.db"

from app.security import hash_password  # noqa: E402
from app.sqlite_repo import SqliteRepository  # noqa: E402


DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "CampusDemo123!"
OWNER_NAME = "Demo Student"

LISTINGS = [
    {
        "title": "Blue water bottle left in the main library",
        "description": "A blue insulated bottle was left on a study table near the east windows. It has a small mountain sticker on the lid. Please message me with the brand to confirm it is yours.",
        "category": "lost-and-found",
        "intent": "lost",
        "location": "Main Library, second floor",
        "contact": DEMO_EMAIL,
    },
    {
        "title": "Found a navy umbrella by the engineering building",
        "description": "I picked up a folded navy umbrella after the afternoon lecture. It is safe with me and can be collected near the student center help desk.",
        "category": "lost-and-found",
        "intent": "found",
        "location": "Engineering Building entrance",
        "contact": DEMO_EMAIL,
    },
    {
        "title": "Campbell Biology textbook, 12th edition",
        "description": "Good condition with a few light pencil notes in the first chapters. I am happy to lend it for the semester or trade for an introductory chemistry text.",
        "category": "textbooks",
        "intent": "offer",
        "location": "Science Library lobby",
        "contact": DEMO_EMAIL,
    },
    {
        "title": "Looking for a study partner for Calculus I",
        "description": "I am reviewing limits and derivatives before the next quiz and would like to meet once or twice this week. We can work through practice problems together.",
        "category": "community",
        "intent": "request",
        "location": "Student Center, quiet lounge",
        "contact": DEMO_EMAIL,
    },
    {
        "title": "Room available in a shared apartment near campus",
        "description": "A furnished room is available for a student from the start of next month. The apartment has a shared kitchen, laundry, and a short bus ride to campus. Contact for the fictional demo details.",
        "category": "housing",
        "intent": "offer",
        "location": "North Campus district",
        "contact": DEMO_EMAIL,
    },
    {
        "title": "Robotics club project night this Thursday",
        "description": "Bring a small project or just come learn. We will have a short demo of the line-following robot, snacks, and time for new members to meet the team.",
        "category": "events",
        "intent": "offer",
        "location": "Engineering Lab 204",
        "contact": DEMO_EMAIL,
    },
    {
        "title": "Found a set of keys with a red tag",
        "description": "A small key ring with two keys and a red fabric tag was turned in. It can be collected from the campus help desk after describing the tag.",
        "category": "lost-and-found",
        "intent": "found",
        "location": "Campus help desk",
        "contact": DEMO_EMAIL,
        "status": "resolved",
    },
    {
        "title": "Peer note-sharing group for Intro to Programming",
        "description": "Looking to swap concise lecture notes and practice examples with a few classmates. We can meet after class or use a shared study room.",
        "category": "community",
        "intent": "request",
        "location": "Computer Science Building",
        "contact": DEMO_EMAIL,
    },
]


def main() -> None:
    repo = SqliteRepository(str(DEMO_DB))
    repo.prepare()
    user = repo.get_user_by_email(DEMO_EMAIL)
    if user is None:
        user = repo.create_user(
            email=DEMO_EMAIL,
            name=OWNER_NAME,
            password_hash=hash_password(DEMO_PASSWORD),
            campus="North Campus (fictional demo)",
            bio="Sample account and listings for a local screen recording.",
        )
    else:
        repo.update_user(
            user["id"],
            {
                "name": OWNER_NAME,
                "campus": "North Campus (fictional demo)",
                "bio": "Sample account and listings for a local screen recording.",
            },
        )

    for index in range(len(LISTINGS)):
        repo.delete_listing(f"demo-listing-{index + 1}")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    for index, item in enumerate(LISTINGS):
        created_at = (now - timedelta(hours=3 * index)).isoformat()
        repo.create_listing(
            {
                "id": f"demo-listing-{index + 1}",
                "owner_id": user["id"],
                "owner_name": OWNER_NAME,
                "title": item["title"],
                "description": item["description"],
                "category": item["category"],
                "intent": item["intent"],
                "location": item["location"],
                "contact": item["contact"],
                "image_key": None,
                "status": item.get("status", "open"),
                "description_source": "demo",
                "category_source": "demo",
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

    existing_messages = {
        notification["message"] for notification in repo.list_notifications(user["id"])
    }
    for message in (
        "Welcome to CampusConnect. Your demo board is ready.",
        "Sample reminder: follow up on your Calculus study group request.",
    ):
        if message not in existing_messages:
            repo.add_notification(user_id=user["id"], message=message, channel="demo")

    print(f"Seeded {len(LISTINGS)} fictional listings into {DEMO_DB}")
    print(f"Demo sign-in: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print("This script uses local SQLite and local adapters only; it does not call AWS.")


if __name__ == "__main__":
    main()
