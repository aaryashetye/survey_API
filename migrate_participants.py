from database import participants

def migrate_participants():
    result = participants.update_many(
        {"surveyor_id": {"$exists": False}},
        {"$set": {"surveyor_id": "default_user"}}
    )

    print(f"Updated {result.modified_count} participants")

if __name__ == "__main__":
    migrate_participants()