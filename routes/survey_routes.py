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

GUID_RE = re.compile(r'^[0-9a-fA-F\-]{36}$')


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
    """Map DB field names -> API field names."""
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif k == "title":
            out["title"] = v
        elif k == "created_by":
            out["createdBy"] = v
        elif k == "created_at":
            out["createdAt"] = v
        elif k == "current_participants":
            out["currentParticipants"] = v
        elif k == "target_participants":
            out["targetParticipants"] = v
        elif k == "is_completed":
            out["isCompleted"] = v
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

    # expected body:
    # {
    #   "id": "survey_001",
    #   "title": "Village Nutrition Survey 2025",
    #   "createdBy": "...GUID...",
    #   "createdAt": "2025-01-01T10:30:00Z",
    #   "currentParticipants": 0,
    #   "targetParticipants": 100,
    #   "isCompleted": false
    # }

    survey_id = data.get("id")
    title = data.get("title")
    created_by = data.get("createdBy")
    created_at = data.get("createdAt") or iso_now()
    current_participants = data.get("currentParticipants", 0)
    target_participants = data.get("targetParticipants", 0)
    is_completed = data.get("isCompleted", False)

    errors = {}

    # id required, but not forced to be GUID (you use "survey_001")
    if not survey_id or not isinstance(survey_id, str) or survey_id.strip() == "":
        errors["id"] = "id is required and must be a non-empty string."

    if not title or not isinstance(title, str) or title.strip() == "":
        errors["title"] = "title is required and must be a non-empty string."

    if created_by is not None and not validate_guid(created_by):
        errors["createdBy"] = "createdBy must be a GUID if provided."

    # numeric fields
    try:
        current_participants = int(current_participants)
    except Exception:
        errors["currentParticipants"] = "currentParticipants must be an integer."

    try:
        target_participants = int(target_participants)
    except Exception:
        errors["targetParticipants"] = "targetParticipants must be an integer."

    # boolean field
    if not isinstance(is_completed, bool):
        # allow "true"/"false" style strings if needed
        if isinstance(is_completed, str):
            is_completed = is_completed.lower() == "true"
        else:
            errors["isCompleted"] = "isCompleted must be a boolean."

    if errors:
        return bad_request("Validation failed", errors)

    now = iso_now()

    doc = {
        "_id": survey_id,  # use your "id" as primary key
        "title": title.strip(),
        "created_by": created_by,
        "created_at": created_at,
        "updated_at": now,
        "current_participants": current_participants,
        "target_participants": target_participants,
        "is_completed": is_completed,
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
    # no longer require GUID; just require non-empty string
    if not survey_id:
        return bad_request("Invalid survey_id.")
    doc = surveys.find_one({"_id": survey_id})
    if not doc:
        return jsonify({"success": False, "message": "Survey not found"}), 404
    return jsonify(serialize_doc(doc)), 200


# ----------------- UPDATE survey -----------------
@survey_bp.route("/surveys/<string:survey_id>", methods=["PUT"])
def update_survey(survey_id):
    if not survey_id:
        return bad_request("Invalid survey_id.")

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

    if "createdBy" in data:
        if data.get("createdBy") is not None and not validate_guid(data.get("createdBy")):
            errors["createdBy"] = "createdBy must be a GUID."
        else:
            updates["created_by"] = data.get("createdBy")

    if "createdAt" in data:
        updates["created_at"] = data.get("createdAt")

    if "currentParticipants" in data:
        try:
            updates["current_participants"] = int(data.get("currentParticipants"))
        except Exception:
            errors["currentParticipants"] = "currentParticipants must be an integer."

    if "targetParticipants" in data:
        try:
            updates["target_participants"] = int(data.get("targetParticipants"))
        except Exception:
            errors["targetParticipants"] = "targetParticipants must be an integer."

    if "isCompleted" in data:
        val = data.get("isCompleted")
        if isinstance(val, bool):
            updates["is_completed"] = val
        elif isinstance(val, str):
            updates["is_completed"] = val.lower() == "true"
        else:
            errors["isCompleted"] = "isCompleted must be a boolean."

    if errors:
        return bad_request("Validation failed", errors)
    if not updates:
        return bad_request("No updatable fields provided")

    updates["updated_at"] = iso_now()

    res = surveys.update_one({"_id": survey_id}, {"$set": updates})
    if res.matched_count == 0:
        return jsonify({"success": False, "message": "Survey not found"}), 404

    updated = surveys.find_one({"_id": survey_id})
    return jsonify({
        "success": True,
        "message": "Survey updated",
        "data": serialize_doc(updated)
    }), 200


# ----------------- DELETE survey -----------------
@survey_bp.route("/surveys/<string:survey_id>", methods=["DELETE"])
def delete_survey(survey_id):
    if not survey_id:
        return bad_request("Invalid survey_id.")
    res = surveys.delete_one({"_id": survey_id})
    if res.deleted_count == 0:
        return jsonify({"success": False, "message": "Survey not found"}), 404
    return jsonify({"success": True, "message": "Survey deleted successfully"}), 200


# ----------------- OPTIONAL: Recalculate counts from other collections -----------------
@survey_bp.route("/surveys/<string:survey_id>/recalculate_counts", methods=["POST"])
def recalculate_counts(survey_id):
    if not survey_id:
        return bad_request("Invalid survey_id.")

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
        # you can still store this if you want, or ignore
        new_counts["question_count"] = qcount

    if participants_col is not None:
        pcount = participants_col.count_documents({"survey_id": survey_id})
        new_counts["participant_count"] = pcount

    if not new_counts:
        return bad_request("No counts available to recalculate.")

    new_counts["updated_at"] = iso_now()
    surveys.update_one({"_id": survey_id}, {"$set": new_counts})
    updated = surveys.find_one({"_id": survey_id})
    return jsonify({
        "success": True,
        "message": "Counts recalculated",
        "data": serialize_doc(updated)
    }), 200
