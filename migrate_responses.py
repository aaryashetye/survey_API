#!/usr/bin/env python3
"""
migrate_responses.py

Purpose:
  - Normalize responses.answers to include question_type, option_id (where applicable),
    value_text/value_number, and normalize location keys to {lat,lng,accuracy_m}.
  - Works with migrated questions that have question_id and options with option_id.
  - Supports dry-run and limit/survey-id filtering.

Usage:
  MONGO_URI="..." python migrate_responses.py --dry-run --limit 50
  MONGO_URI="..." python migrate_responses.py --survey-id <id>
  MONGO_URI="..." python migrate_responses.py
"""

import os, argparse
from pymongo import MongoClient
from copy import deepcopy
from datetime import datetime, timezone
import math, uuid, re

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "SurveyAPI")
RESP_COL = os.getenv("RESPONSES_COL", "responses")
QUEST_COL = os.getenv("QUESTIONS_COL", "questions")

GUID_RE = re.compile(r'^[0-9a-fA-F\-]{36}$')

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()

def norm_str(s):
    return None if s is None else str(s).strip().lower()

def is_number_like(v):
    try:
        float(v)
        return True
    except:
        return False

def to_float_or_none(v):
    try:
        return float(v)
    except:
        return None

def normalize_location(obj):
    if not obj or not isinstance(obj, dict):
        return None
    lat = None
    lng = None
    acc = None
    if "latitude" in obj and "longitude" in obj:
        lat = to_float_or_none(obj.get("latitude"))
        lng = to_float_or_none(obj.get("longitude"))
    if lat is None and ("lat" in obj and "lng" in obj):
        lat = to_float_or_none(obj.get("lat"))
        lng = to_float_or_none(obj.get("lng"))
    if lat is None:
        lat = to_float_or_none(obj.get("lat") or obj.get("latitude"))
    if lng is None:
        lng = to_float_or_none(obj.get("lng") or obj.get("longitude"))
    if "accuracy_m" in obj:
        acc = to_float_or_none(obj.get("accuracy_m"))
    elif "accuracy" in obj:
        acc = to_float_or_none(obj.get("accuracy"))
    if lat is None or lng is None:
        return None
    return {"lat": lat, "lng": lng, "accuracy_m": acc}

def load_question_cache(db, cache, qid):
    if qid in cache:
        return cache[qid]
    # find containing question by question_id in nested questions array
    qdoc = db[QUEST_COL].find_one({"questions.question_id": qid}, {"questions.$": 1})
    if qdoc and "questions" in qdoc and len(qdoc["questions"])>0:
        cache[qid] = qdoc["questions"][0]
        return cache[qid]
    cache[qid] = None
    return None

def match_option(question_obj, raw_value):
    if not question_obj:
        return None
    nv = norm_str(raw_value)
    for opt in question_obj.get("options", []) or []:
        if norm_str(opt.get("label")) == nv or norm_str(opt.get("value")) == nv:
            return opt
    # substring fallback
    for opt in question_obj.get("options", []) or []:
        ol = norm_str(opt.get("label"))
        if ol and nv and nv in ol:
            return opt
    return None

def migrate(dry_run=True, limit=None, survey_id=None):
    client = MongoClient(MONGO_URI)
    db = client.get_database() if DB_NAME is None else client[DB_NAME]
    resp_col = db[RESP_COL]
    qcache = {}

    query = {"answers": {"$exists": True, "$ne": []}}
    if survey_id:
        query["survey_id"] = survey_id

    if limit:
       cursor = resp_col.find(query).limit(limit).batch_size(100)
    else:
       cursor = resp_col.find(query).batch_size(100)

    stats = {"docs":0, "modified":0, "answers_scanned":0, "answers_fixed":0, "answers_legacy":0, "answers_skipped":0}
    try:
        for doc in cursor:
            stats["docs"] += 1
            doc_id = doc.get("_id")
            orig_answers = deepcopy(doc.get("answers", []))
            new_answers = deepcopy(orig_answers)
            changed = False

            # normalize location
            norm_loc = normalize_location(doc.get("location"))
            if norm_loc and norm_loc != doc.get("location"):
                changed = True

            for i, ans in enumerate(new_answers):
                stats["answers_scanned"] += 1
                # skip if already normalized (has question_type and either option_id/value_text/value_number)
                if ans.get("question_type") and (ans.get("option_id") or ans.get("value_text") or ans.get("value_number")):
                    stats["answers_skipped"] += 1
                    continue

                qid = ans.get("question_id")
                raw_value = ans.get("value") if "value" in ans else ans.get("answer") if "answer" in ans else None
                if not qid:
                    ans["legacy"] = True
                    stats["answers_legacy"] += 1
                    continue

                qobj = load_question_cache(db, qcache, qid)
                if not qobj:
                    ans["legacy"] = True
                    stats["answers_legacy"] += 1
                    continue

                # set question_type if missing
                if not ans.get("question_type"):
                    ans["question_type"] = qobj.get("question_type")

                qtype = ans.get("question_type")
                if qtype in {"mcq","dropdown","multi_select","yes_no"}:
                    if ans.get("option_id"):
                        # already has option_id — normalize values
                        if raw_value is not None:
                            if is_number_like(raw_value):
                                ans["value_number"] = float(raw_value)
                                ans["value_text"] = None
                            else:
                                ans["value_text"] = str(raw_value)
                                ans["value_number"] = None
                            stats["answers_fixed"] += 1
                            changed = True
                        else:
                            # nothing to do
                            pass
                    else:
                        matched = match_option(qobj, raw_value)
                        if matched:
                            ans["option_id"] = matched.get("option_id")
                            ans["value_text"] = str(raw_value) if raw_value is not None else None
                            ans["value_number"] = float(raw_value) if is_number_like(raw_value) else None
                            stats["answers_fixed"] += 1
                            changed = True
                        else:
                            ans["legacy"] = True
                            stats["answers_legacy"] += 1
                else:
                    # text/number: set text/number
                    if raw_value is not None:
                        if is_number_like(raw_value):
                            ans["value_number"] = float(raw_value)
                            ans["value_text"] = None
                        else:
                            ans["value_text"] = str(raw_value)
                            ans["value_number"] = None
                        stats["answers_fixed"] += 1
                        changed = True
                    else:
                        ans["legacy"] = True
                        stats["answers_legacy"] += 1

            if changed or norm_loc:
                update = {}
                if changed:
                    update["answers"] = new_answers
                if norm_loc:
                    update["location"] = norm_loc
                if not dry_run:
                    resp_col.update_one({"_id": doc_id}, {"$set": update})
                stats["modified"] += 1

            print(f"[{'DRY' if dry_run else 'LIVE'}] Doc {doc_id} changed={changed or bool(norm_loc)}")

    finally:
        try: cursor.close()
        except: pass

    print("\n--- summary ---")
    for k,v in stats.items():
        print(f"{k}: {v}")
    print("dry_run:", dry_run)
    print("done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--survey-id", type=str, default=None)
    args = parser.parse_args()
    print("Connecting to:", MONGO_URI)
    migrate(dry_run=args.dry_run, limit=args.limit, survey_id=args.survey_id)
