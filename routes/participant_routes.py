from flask import Blueprint, jsonify, request
from database import participants  # MongoDB collection
import uuid
import re
from datetime import datetime, timezone
from bson import ObjectId

participant_bp = Blueprint("participant_bp", __name__)

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
    """Map DB fields -> API fields."""
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif k == "surveyId":
            out["surveyId"] = v
        else:
            out[k] = serialize_value(v)
    return out


def bad_request(msg, errors=None):
    payload = {"success": False, "message": msg}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), 400


# ----------------- CREATE Participant -----------------
@participant_bp.route("/participants", methods=["POST"])
def create_participant():
    """
    Expected body:
    {
      "id": "guid",
      "name": "Asha Patil",
      "age": 35,
      "gender": "female",
      "surveyId": "a1b2c3d4-e5f6-7a8b-9c0d-ef1234567890"
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    participant_id = data.get("id")
    name = data.get("name")
    age = data.get("age")
    gender = data.get("gender")
    survey_id = data.get("surveyId")

    errors = {}

    # id: required GUID
    if not participant_id or not validate_guid(participant_id):
        errors["id"] = "id is required and must be a valid GUID."

    # name
    if not name or not isinstance(name, str):
        errors["name"] = "name is required and must be a string."

    # age
    if age is not None:
        try:
            age = int(age)
            if age < 0 or age > 120:
                errors["age"] = "age must be a reasonable integer."
        except Exception:
            errors["age"] = "age must be an integer."

    # gender
    allowed_genders = {"male", "female", "other", "prefer_not_to_say"}
    if gender not in allowed_genders:
        errors["gender"] = "gender must be one of male/female/other/prefer_not_to_say."

    # surveyId: required GUID
    if not survey_id or not validate_guid(survey_id):
        errors["surveyId"] = "surveyId is required and must be a valid GUID."

    if errors:
        return bad_request("Validation failed", errors)

    doc = {
        "_id": participant_id,      # client-chosen GUID
        "name": name,
        "age": age,
        "gender": gender,
        "surveyId": survey_id,
        "created_at": iso_now()
    }

    participants.insert_one(doc)

    return jsonify({
        "success": True,
        "message": "Participant created successfully.",
        "participant_id": participant_id
    }), 201


# ----------------- GET ALL Participants -----------------
@participant_bp.route("/participants", methods=["GET"])
def get_all_participants():
    cursor = list(participants.find({}))
    serialized = [serialize_doc(d) for d in cursor]
    return jsonify(serialized), 200


# ----------------- GET single Participant -----------------
@participant_bp.route("/participants/<string:participant_id>", methods=["GET"])
def get_participant(participant_id):
    # participant_id is a GUID
    if not validate_guid(participant_id):
        return bad_request("Invalid participant_id (GUID expected).")

    p = participants.find_one({"_id": participant_id})
    if p:
        return jsonify(serialize_doc(p)), 200
    return jsonify({"success": False, "message": "Participant not found"}), 404


# ----------------- UPDATE Participant -----------------
@participant_bp.route("/participants/<string:participant_id>", methods=["PUT"])
def update_participant(participant_id):
    # id itself is not changed, only other fields
    if not validate_guid(participant_id):
        return bad_request("Invalid participant_id (GUID expected).")

    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    updates = {}
    errors = {}

    # name
    if "name" in data:
        if not isinstance(data.get("name"), str):
            errors["name"] = "name must be a string."
        else:
            updates["name"] = data.get("name")

    # age
    if "age" in data:
        try:
            a = int(data.get("age"))
            if a < 0 or a > 120:
                errors["age"] = "age must be a reasonable integer."
            else:
                updates["age"] = a
        except Exception:
            errors["age"] = "age must be an integer."

    # gender
    if "gender" in data:
        allowed_genders = {"male", "female", "other", "prefer_not_to_say"}
        if data.get("gender") not in allowed_genders:
            errors["gender"] = "invalid gender value."
        else:
            updates["gender"] = data.get("gender")

    # surveyId
    if "surveyId" in data:
        if not validate_guid(data.get("surveyId")):
            errors["surveyId"] = "surveyId must be a valid GUID."
        else:
            updates["surveyId"] = data.get("surveyId")

    if errors:
        return bad_request("Validation failed", errors)

    if not updates:
        return bad_request("No updatable fields provided")

    updates["updated_at"] = iso_now()

    result = participants.update_one({"_id": participant_id}, {"$set": updates})
    if result.matched_count == 0:
        return jsonify({"success": False, "message": "Participant not found"}), 404

    updated = participants.find_one({"_id": participant_id})
    return jsonify({
        "success": True,
        "message": "Participant updated",
        "data": serialize_doc(updated)
    }), 200


# ----------------- DELETE Participant -----------------
@participant_bp.route("/participants/<string:participant_id>", methods=["DELETE"])
def delete_participant(participant_id):
    if not validate_guid(participant_id):
        return bad_request("Invalid participant_id (GUID expected).")

    result = participants.delete_one({"_id": participant_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "message": "Participant not found"}), 404

    return jsonify({"success": True, "message": "Participant deleted successfully"}), 200
