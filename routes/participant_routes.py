# file: participant_bp.py
from flask import Blueprint, jsonify, request
from database import participants  # MongoDB collection
import uuid
import re
from datetime import datetime, timezone
from bson import ObjectId

participant_bp = Blueprint("participant_bp", __name__)

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

def is_valid_phone(p):
    if not p:
        return False
    # very basic international-ish phone pattern (allows digits, +, -, spaces)
    return bool(re.match(r'^[\+\d][\d\-\s]{5,20}$', str(p)))

def is_valid_email(e):
    if not e:
        return False
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", str(e)))

# ----------------- CREATE Participant -----------------
@participant_bp.route("/participants", methods=["POST"])
def create_participant():
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    name = data.get("name")
    age = data.get("age")
    gender = data.get("gender")
    survey_id = data.get("survey_id")
    phone = data.get("phone")
    email = data.get("email")
    location = data.get("location")  # optional: {lat, lng}

    errors = {}
    if not name or not isinstance(name, str):
        errors["name"] = "name is required and must be a string."
    if age is not None:
        try:
            age = int(age)
            if age < 0 or age > 120:
                errors["age"] = "age must be a reasonable integer."
        except Exception:
            errors["age"] = "age must be an integer."
    if gender is not None and gender not in {"male", "female", "other", "prefer_not_to_say"}:
        errors["gender"] = "gender must be one of male/female/other/prefer_not_to_say or omitted."

    if survey_id is not None and not validate_guid(survey_id):
        errors["survey_id"] = "survey_id must be a GUID if provided."

    if phone is not None and not is_valid_phone(phone):
        errors["phone"] = "invalid phone format."
    if email is not None and not is_valid_email(email):
        errors["email"] = "invalid email format."

    # normalize location if provided
    if location is not None:
        if not isinstance(location, dict) or location.get("lat") is None or location.get("lng") is None:
            errors["location"] = "location must be an object with lat and lng numbers."
        else:
            try:
                location = {"lat": float(location.get("lat")), "lng": float(location.get("lng")), "accuracy_m": location.get("accuracy_m")}
            except Exception:
                errors["location"] = "lat and lng must be numbers."

    if errors:
        return bad_request("Validation failed", errors)

    participant_id = make_guid()
    doc = {
        "_id": participant_id,
        "first_name": name,
        "age": age,
        "gender": gender,
        "survey_id": survey_id,
        "phone": phone,
        "email": email,
        "location": location,
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
    if not validate_guid(participant_id):
        return bad_request("Invalid participant_id (GUID expected).")
    p = participants.find_one({"_id": participant_id})
    if p:
        return jsonify(serialize_doc(p)), 200
    return jsonify({"success": False, "message": "Participant not found"}), 404

# ----------------- UPDATE Participant -----------------
@participant_bp.route("/participants/<string:participant_id>", methods=["PUT"])
def update_participant(participant_id):
    if not validate_guid(participant_id):
        return bad_request("Invalid participant_id (GUID expected).")
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    updates = {}
    errors = {}

    if "name" in data:
        if not isinstance(data.get("name"), str):
            errors["name"] = "name must be a string."
        else:
            updates["first_name"] = data.get("name")

    if "age" in data:
        try:
            a = int(data.get("age"))
            if a < 0 or a > 120:
                errors["age"] = "age must be a reasonable integer."
            else:
                updates["age"] = a
        except Exception:
            errors["age"] = "age must be an integer."

    if "gender" in data:
        if data.get("gender") not in {"male", "female", "other", "prefer_not_to_say"}:
            errors["gender"] = "invalid gender value."
        else:
            updates["gender"] = data.get("gender")

    if "survey_id" in data:
        if not validate_guid(data.get("survey_id")):
            errors["survey_id"] = "survey_id must be a GUID."
        else:
            updates["survey_id"] = data.get("survey_id")

    if "phone" in data:
        if not is_valid_phone(data.get("phone")):
            errors["phone"] = "invalid phone format."
        else:
            updates["phone"] = data.get("phone")

    if "email" in data:
        if not is_valid_email(data.get("email")):
            errors["email"] = "invalid email format."
        else:
            updates["email"] = data.get("email")

    if "location" in data:
        loc = data.get("location")
        if not isinstance(loc, dict) or loc.get("lat") is None or loc.get("lng") is None:
            errors["location"] = "location must be an object with lat and lng numbers."
        else:
            try:
                updates["location"] = {"lat": float(loc.get("lat")), "lng": float(loc.get("lng")), "accuracy_m": loc.get("accuracy_m")}
            except Exception:
                errors["location"] = "lat and lng must be numbers."

    if errors:
        return bad_request("Validation failed", errors)

    if not updates:
        return bad_request("No updatable fields provided")

    updates["updated_at"] = iso_now()

    result = participants.update_one({"_id": participant_id}, {"$set": updates})
    if result.matched_count == 0:
        return jsonify({"success": False, "message": "Participant not found"}), 404

    updated = participants.find_one({"_id": participant_id})
    return jsonify({"success": True, "message": "Participant updated", "data": serialize_doc(updated)}), 200

# ----------------- DELETE Participant -----------------
@participant_bp.route("/participants/<string:participant_id>", methods=["DELETE"])
def delete_participant(participant_id):
    if not validate_guid(participant_id):
        return bad_request("Invalid participant_id (GUID expected).")
    result = participants.delete_one({"_id": participant_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "message": "Participant not found"}), 404
    return jsonify({"success": True, "message": "Participant deleted successfully"}), 200
