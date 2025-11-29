from flask import Blueprint, jsonify, request
from database import responses, questions  # MongoDB collections
import uuid
from datetime import datetime, timezone
import re
from bson import ObjectId

response_bp = Blueprint("response_bp", __name__)

GUID_RE = re.compile(r'^[0-9a-fA-F\-]{36}$')

ALLOWED_Q_TYPES = {"mcq", "yes_no", "text", "number", "dropdown", "multi_select"}

# ----------------- helpers -----------------
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
    return {k: serialize_value(v) for k, v in doc.items()}

def bad_request(msg, errors=None):
    payload = {"success": False, "message": msg}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), 400


# -------------------------------------------------------------------
# 🔵 CREATE response  (POST /responses)
# -------------------------------------------------------------------
@response_bp.route("/responses", methods=["POST"])
def create_response():
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    survey_id = data.get("survey_id")
    cycle_id = data.get("cycle_id")
    surveyor_id = data.get("surveyor_id")
    participant_id = data.get("participant_id")
    answers = data.get("answers", [])
    location = data.get("location")
    timestamp = data.get("timestamp") or iso_now()

    errors = {}

    # ----------------- basic field validation -----------------
    if not survey_id or not validate_guid(survey_id):
        errors["survey_id"] = "survey_id is required and must be a GUID."

    if participant_id and not validate_guid(participant_id):
        errors["participant_id"] = "participant_id must be a GUID."

    if surveyor_id and not validate_guid(surveyor_id):
        errors["surveyor_id"] = "surveyor_id must be a GUID."

    if cycle_id and not validate_guid(cycle_id):
        errors["cycle_id"] = "cycle_id must be a GUID."

    # ----------------- validate location -----------------
    if not location or not isinstance(location, dict):
        errors["location"] = "location object is required with lat/lng."
    else:
        if location.get("lat") is None or location.get("lng") is None:
            errors["location.lat/lng"] = "lat and lng are required."
        else:
            try:
                float(location["lat"])
                float(location["lng"])
            except:
                errors["location"] = "lat/lng must be numbers."

    # ----------------- validate answers -----------------
    if not isinstance(answers, list) or len(answers) == 0:
        errors["answers"] = "answers list is required."

    # ----------------- per-answer validation -----------------
    normalized_answers = []

    for i, ans in enumerate(answers):

        if not isinstance(ans, dict):
            errors[f"answers[{i}]"] = "Each answer must be an object."
            continue

        qid = ans.get("question_id")
        qtype = ans.get("question_type")
        value = ans.get("value")
        opt_id = ans.get("option_id")

        if not qid or not validate_guid(qid):
            errors[f"answers[{i}].question_id"] = "question_id (GUID) is required."

        if qtype not in ALLOWED_Q_TYPES:
            errors[f"answers[{i}].question_type"] = f"Invalid question_type. Must be one of {sorted(ALLOWED_Q_TYPES)}."

        if qtype in {"mcq", "dropdown", "multi_select", "yes_no"}:
            if not opt_id or not validate_guid(opt_id):
                errors[f"answers[{i}].option_id"] = "option_id is required for choice-based questions."

        # Build cleaned structure
        normalized_answers.append({
            "question_id": qid,
            "question_type": qtype,
            "option_id": opt_id,
            "value": value,
            "value_text": value if isinstance(value, str) else None,
            "value_number": float(value) if isinstance(value, (int, float)) else None
        })

    if errors:
        return bad_request("Validation failed", errors)

    # ----------------- create final response doc -----------------
    response_id = make_guid()

    new_doc = {
        "_id": response_id,
        "survey_id": survey_id,
        "cycle_id": cycle_id,
        "participant_id": participant_id,
        "surveyor_id": surveyor_id,
        "status": "submitted",
        "timestamp": timestamp,
        "location": {
            "lat": float(location["lat"]),
            "lng": float(location["lng"]),
            "accuracy_m": location.get("accuracy_m")
        },
        "answers": normalized_answers,
        "created_at": iso_now()
    }

    responses.insert_one(new_doc)

    return jsonify({
        "success": True,
        "message": "Response recorded successfully.",
        "response_id": response_id
    }), 201


# -------------------------------------------------------------------
# 🟡 GET all responses
# -------------------------------------------------------------------
@response_bp.route("/responses", methods=["GET"])
def get_all_responses():
    all_res = [serialize_doc(r) for r in responses.find()]
    return jsonify(all_res), 200


# -------------------------------------------------------------------
# 🟣 GET single response by ID
# -------------------------------------------------------------------
@response_bp.route("/responses/<string:response_id>", methods=["GET"])
def get_response(response_id):
    if not validate_guid(response_id):
        return bad_request("Invalid response_id")

    r = responses.find_one({"_id": response_id})
    if r:
        return jsonify(serialize_doc(r)), 200
    return jsonify({"error": "Response not found"}), 404


# -------------------------------------------------------------------
# 🟠 UPDATE response
# -------------------------------------------------------------------
@response_bp.route("/responses/<string:response_id>", methods=["PUT"])
def update_response(response_id):
    if not validate_guid(response_id):
        return bad_request("Invalid response_id")

    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    updates = {}

    if "answers" in data:
        updates["answers"] = data["answers"]

    if "location" in data:
        updates["location"] = data["location"]

    updates["timestamp"] = iso_now()

    result = responses.update_one({"_id": response_id}, {"$set": updates})

    if result.matched_count == 0:
        return jsonify({"error": "Response not found"}), 404

    updated = serialize_doc(responses.find_one({"_id": response_id}))

    return jsonify({"success": True, "message": "Response updated successfully!", "data": updated}), 200


# -------------------------------------------------------------------
# 🔴 DELETE response
# -------------------------------------------------------------------
@response_bp.route("/responses/<string:response_id>", methods=["DELETE"])
def delete_response(response_id):
    if not validate_guid(response_id):
        return bad_request("Invalid response_id")

    result = responses.delete_one({"_id": response_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Response not found"}), 404

    return jsonify({"success": True, "message": "Response deleted successfully!"}), 200
