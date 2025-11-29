# file: survey_bp.py
from flask import Blueprint, jsonify, request
from database import surveys  # MongoDB collection
# optional imports for count recalculation; if your database module exposes these, uncomment above or ensure available
try:
    from database import questions as questions_col
except Exception:
    questions_col = None

try:
    from database import participants as participants_col
except Exception:
    participants_col = None

import uuid
import re
from datetime import datetime, timezone
from bson import ObjectId

survey_bp = Blueprint("survey_bp", __name__)

GUID_RE = re.compile(r'^[0-9a-fA-F0-9\-]{36}$')

def make_guid():
    return str(uuid.uuid4())

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()

def validate_guid(g):
    return isinstance(g, str) and GUID_RE.match(g)

def serialize_value(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: serialize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [serialize_value(x) for x in v]
    return v

def serialize_doc(doc):
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out[k] = str(v)
        else:
            out[k] = serialize_value(v)
    return out

def bad_request(msg, errors=None):
    payload = {"success": False, "message": msg}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), 400

# ----------------- CREATE survey -----------------
@survey_bp.route("/surveys", methods=["POST"])
def create_survey():
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    title = data.get("title")
    description = data.get("description")
    created_by = data.get("created_by")

    errors = {}
    if not title or not isinstance(title, str) or title.strip() == "":
        errors["title"] = "title is required and must be a non-empty string."
    if created_by is not None and not validate_guid(created_by):
        errors["created_by"] = "created_by must be a GUID if provided."

    if errors:
        return bad_request("Validation failed", errors)

    survey_id = make_guid()
    now = iso_now()

    doc = {
        "_id": survey_id,
        "title": title.strip(),
        "description": description or "",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "participant_count": int(data.get("participant_count", 0)),
        "question_count": int(data.get("question_count", 0))
    }

    surveys.insert_one(doc)

    return jsonify({
        "success": True,
        "message": "Survey created successfully.",
        "survey_id": survey_id
    }), 201

# ----------------- GET all surveys -----------------
@survey_bp.route("/surveys", methods=["GET"])
def get_all_surveys():
    docs = list(surveys.find({}))
    serialized = [serialize_doc(d) for d in docs]
    return jsonify(serialized), 200

# ----------------- GET survey by id -----------------
@survey_bp.route("/surveys/<string:survey_id>", methods=["GET"])
def get_survey(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")
    doc = surveys.find_one({"_id": survey_id})
    if not doc:
        return jsonify({"success": False, "message": "Survey not found"}), 404
    return jsonify(serialize_doc(doc)), 200

# ----------------- UPDATE survey -----------------
@survey_bp.route("/surveys/<string:survey_id>", methods=["PUT"])
def update_survey(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    updates = {}
    errors = {}

    if "title" in data:
        if not isinstance(data.get("title"), str) or data.get("title").strip() == "":
            errors["title"] = "title must be a non-empty string."
        else:
            updates["title"] = data.get("title").strip()

    if "description" in data:
        updates["description"] = data.get("description") or ""

    if "created_by" in data:
        if not validate_guid(data.get("created_by")):
            errors["created_by"] = "created_by must be a GUID."
        else:
            updates["created_by"] = data.get("created_by")

    # allow manual updates to counts (optional)
    if "participant_count" in data:
        try:
            updates["participant_count"] = int(data.get("participant_count"))
        except Exception:
            errors["participant_count"] = "participant_count must be an integer."
    if "question_count" in data:
        try:
            updates["question_count"] = int(data.get("question_count"))
        except Exception:
            errors["question_count"] = "question_count must be an integer."

    if errors:
        return bad_request("Validation failed", errors)
    if not updates:
        return bad_request("No updatable fields provided")

    updates["updated_at"] = iso_now()

    res = surveys.update_one({"_id": survey_id}, {"$set": updates})
    if res.matched_count == 0:
        return jsonify({"success": False, "message": "Survey not found"}), 404

    updated = surveys.find_one({"_id": survey_id})
    return jsonify({"success": True, "message": "Survey updated", "data": serialize_doc(updated)}), 200

# ----------------- DELETE survey -----------------
@survey_bp.route("/surveys/<string:survey_id>", methods=["DELETE"])
def delete_survey(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")
    res = surveys.delete_one({"_id": survey_id})
    if res.deleted_count == 0:
        return jsonify({"success": False, "message": "Survey not found"}), 404
    return jsonify({"success": True, "message": "Survey deleted successfully"}), 200

# ----------------- OPTIONAL: Recalculate counts from other collections -----------------
@survey_bp.route("/surveys/<string:survey_id>/recalculate_counts", methods=["POST"])
def recalculate_counts(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")

    # require the optional collections to be available
    if questions_col is None and participants_col is None:
        return bad_request("Recalculation not available: questions/participants collections not accessible on server.")

    new_counts = {}
    if questions_col is not None:
        # count number of questions for this survey
        # assumes questions collection stores docs with survey_id and nested questions array
        qdoc = questions_col.find_one({"survey_id": survey_id}, {"questions": 1})
        qcount = 0
        if qdoc and "questions" in qdoc:
            qcount = len(qdoc["questions"])
        new_counts["question_count"] = qcount

    if participants_col is not None:
        pcount = participants_col.count_documents({"survey_id": survey_id})
        new_counts["participant_count"] = pcount

    if not new_counts:
        return bad_request("No counts available to recalculate.")

    new_counts["updated_at"] = iso_now()
    surveys.update_one({"_id": survey_id}, {"$set": new_counts})
    updated = surveys.find_one({"_id": survey_id})
    return jsonify({"success": True, "message": "Counts recalculated", "data": serialize_doc(updated)}), 200
