
import os, argparse, uuid, re
from pymongo import MongoClient
from datetime import datetime, timezone
from copy import deepcopy

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "SurveyAPI")
COL = os.getenv("QUESTIONS_COL", "questions")  # collection name

GUID_RE = re.compile(r'^[0-9a-fA-F\-]{36}$')

def make_guid():
    return str(uuid.uuid4())

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()

def norm_str(s):
    return None if s is None else str(s).strip()

def detect_question_type(q):
    """Heuristic: if options present -> mcq, else text"""
    opts = q.get("options")
    if opts and isinstance(opts, list) and len(opts) > 0:
        # if options are explicitly yes/no style, could map to yes_no, but default mcq
        return "mcq"
    return "text"

def normalize_option(opt):
    """
    Accept many legacy shapes:
    {optionId: 1, option: "Yes"} or {"label":"Yes"} or "Yes"
    Return dict with option_id, label, value
    """
    if opt is None:
        return None
    if isinstance(opt, dict):
        label = opt.get("label") or opt.get("option") or opt.get("text") or opt.get("value")
        val = opt.get("value") or label
        # try keep existing option_id if it looks like GUID
        oid = opt.get("option_id") or opt.get("optionId") or opt.get("id")
        if isinstance(oid, str) and GUID_RE.match(oid):
            option_id = oid
        else:
            option_id = make_guid()
        return {"option_id": option_id, "label": norm_str(label), "value": norm_str(val)}
    # if option is a string
    if isinstance(opt, str):
        return {"option_id": make_guid(), "label": norm_str(opt), "value": norm_str(opt)}
    # if numeric option id (legacy) with separate option text, caller likely passes dict — handle conservatively
    return {"option_id": make_guid(), "label": str(opt), "value": str(opt)}

def migrate(dry_run=True, limit=None, survey_id=None):
    client = MongoClient(MONGO_URI)
    db = client.get_database() if DB_NAME is None else client[DB_NAME]
    col = db[COL]

    q = {}
    if survey_id:
        q["survey_id"] = survey_id

    if limit:
       cursor = col.find(q).limit(limit).batch_size(100)
    else:
       cursor = col.find(q).batch_size(100)

    stats = {"scanned":0, "modified":0, "skipped":0}
    try:
        for doc in cursor:
            stats["scanned"] += 1
            orig = deepcopy(doc)
            changed = False

            # ensure top-level _id is GUID; if not, generate new GUID and keep original id in metadata
            if not isinstance(orig.get("_id"), str) or not GUID_RE.match(str(orig.get("_id"))):
                new_id = make_guid()
                orig["_id"] = new_id
                changed = True

            # normalize survey_id key (accept surveyId or survey_id)
            survey_id_val = orig.get("survey_id") or orig.get("surveyId") or orig.get("survey")
            if survey_id_val and not (isinstance(survey_id_val, str) and GUID_RE.match(survey_id_val)):
                # if survey_id exists but not GUID, leave as-is (can't convert)
                pass
            if survey_id_val and (orig.get("survey_id") != survey_id_val):
                orig["survey_id"] = survey_id_val
                changed = True

            incoming_questions = orig.get("questions") or orig.get("question") or orig.get("qs") or []
            # if old structure used top-level array with numeric qno, transform
            normalized_questions = []
            order_counter = 1
            for qidx, qitem in enumerate(incoming_questions):
                # many legacy shapes: dict with keys qno,text,options(option list), or minimal strings
                if isinstance(qitem, dict):
                    qtext = qitem.get("question_text") or qitem.get("text") or qitem.get("label") or qitem.get("q")
                    qtype = qitem.get("question_type") or qitem.get("type") or detect_question_type(qitem)
                    options_raw = qitem.get("options") or qitem.get("choices") or qitem.get("opts") or []
                    required = qitem.get("required")
                    order = qitem.get("order") or qitem.get("qno") or (qitem.get("order") == 0 and 0) or order_counter
                else:
                    # if qitem is string, use string as question_text
                    qtext = str(qitem)
                    qtype = "text"
                    options_raw = []
                    required = False
                    order = order_counter

                # normalize options
                normalized_opts = []
                if isinstance(options_raw, list):
                    for opt in options_raw:
                        no = normalize_option(opt)
                        if no:
                            normalized_opts.append(no)

                # ensure question_id
                qid = qitem.get("question_id") if isinstance(qitem, dict) else None
                if not (isinstance(qid, str) and GUID_RE.match(qid)):
                    qid = make_guid()
                    changed = True

                normalized_questions.append({
                    "question_id": qid,
                    "question_text": norm_str(qtext),
                    "question_type": qtype if qtype in {"mcq","yes_no","text","number","dropdown","multi_select"} else detect_question_type(qitem if isinstance(qitem, dict) else {}),
                    "options": normalized_opts,
                    "required": bool(required),
                    "order": int(order) if order is not None else order_counter,
                    "metadata": qitem.get("metadata") if isinstance(qitem, dict) else {}
                })
                order_counter += 1

            # Write back: set normalized questions array and timestamps
            new_doc = {
                "_id": orig["_id"],
                "survey_id": orig.get("survey_id") or survey_id,
                "questions": normalized_questions,
                "created_at": orig.get("created_at") or iso_now(),
                "updated_at": iso_now()
            }

            # decide if update needed: compare shapes
            # simple check: if original doesn't have question_id/option_id or questions differ
            need_update = False
            orig_qs = orig.get("questions") or []
            # naive check: if any question in normalized_questions lacks same text in orig, update
            if not orig_qs or any("question_id" not in q for q in orig_qs) or any(any("option_id" not in o for o in q.get("options", [])) for q in normalized_questions):
                need_update = True

            print(f"[{'DRY' if dry_run else 'LIVE'}] Processing doc _id={orig['_id']} need_update={need_update}")
            if need_update:
                if not dry_run:
                    col.replace_one({"_id": orig["_id"]}, new_doc, upsert=True)
                stats["modified"] += 1
            else:
                stats["skipped"] += 1

    finally:
        try: cursor.close()
        except: pass

    print("\n--- migration summary ---")
    for k,v in stats.items():
        print(f"{k}: {v}")
    print("dry_run:", dry_run)
    print("done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--survey-id", type=str, default=None)
    args = parser.parse_args()
    print("Connecting to:", MONGO_URI)
    migrate(dry_run=args.dry_run, limit=args.limit, survey_id=args.survey_id)
