# file: question_bp.py
from flask import Blueprint, jsonify, request
from database import questions  # MongoDB collection (assumed already configured)
import uuid
from datetime import datetime, timezone
import re
from bson import ObjectId

question_bp = Blueprint("question_bp", __name__)

GUID_RE = re.compile(r'^[0-9a-fA-F0-9\-]{36}$')
ALLOWED_Q_TYPES = {"mcq", "yes_no", "text", "number", "dropdown", "multi_select"}

# ---------- helpers ----------
def make_guid():
    return str(uuid.uuid4())

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()

def validate_guid(g):
    return isinstance(g, str) and GUID_RE.match(g)

def serialize_value(v):
    # convert ObjectId to string recursively for dict/list
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
    d = {}
    for k, v in doc.items():
        # convert top-level _id (could be string GUID or ObjectId) to string
        if k == "_id":
            d[k] = str(v)
        else:
            d[k] = serialize_value(v)
    return d

def bad_request(msg, errors=None):
    payload = {"success": False, "message": msg}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), 400

# ---------- CREATE survey questions ----------
@question_bp.route("/questions", methods=["POST"])
def create_questions():
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    survey_id = data.get("survey_id")
    incoming_questions = data.get("questions", [])

    errors = {}
    if not survey_id or not validate_guid(survey_id):
        errors["survey_id"] = "survey_id is required and must be a GUID."

    if not isinstance(incoming_questions, list) or len(incoming_questions) == 0:
        errors["questions"] = "questions must be a non-empty array."

    # validate each question minimally
    normalized_questions = []
    for i, q in enumerate(incoming_questions):
        if not isinstance(q, dict):
            errors[f"questions[{i}]"] = "Each question must be an object."
            continue

        q_text = q.get("question_text")
        q_type = q.get("question_type")
        q_options = q.get("options", [])

        if not q_text or not isinstance(q_text, str):
            errors[f"questions[{i}].question_text"] = "question_text is required and must be a string."
        if q_type not in ALLOWED_Q_TYPES:
            errors[f"questions[{i}].question_type"] = f"question_type is required and must be one of {sorted(ALLOWED_Q_TYPES)}."

        # For choice-type questions ensure options present
        if q_type in {"mcq", "dropdown", "multi_select", "yes_no"}:
            if not isinstance(q_options, list) or len(q_options) == 0:
                errors[f"questions[{i}].options"] = "options array is required for choice-type questions."
            else:
                for j, opt in enumerate(q_options):
                    if not isinstance(opt, dict):
                        errors[f"questions[{i}].options[{j}]"] = "Each option must be an object with at least a 'label'."
                    elif not opt.get("label"):
                        errors[f"questions[{i}].options[{j}].label"] = "label is required for each option."

        # If validation passed for this question, normalize it
        if not any(k.startswith(f"questions[{i}]") for k in errors.keys()):
            question_id = make_guid()
            normalized_opts = []
            for opt in q_options:
                normalized_opts.append({
                    "option_id": make_guid(),
                    "label": opt.get("label"),
                    "value": opt.get("value", opt.get("label"))
                })
            normalized_questions.append({
                "question_id": question_id,
                "question_text": q_text,
                "question_type": q_type,
                "options": normalized_opts,
                "required": bool(q.get("required", False)),
                "order": int(q.get("order", 0)),
                "metadata": q.get("metadata", {})
            })

    if errors:
        return bad_request("Validation failed", errors)

    doc = {
        "_id": make_guid(),  # top-level document id (survey_questions document)
        "survey_id": survey_id,
        "questions": normalized_questions,
        "created_at": iso_now()
    }

    questions.insert_one(doc)

    return jsonify({
        "success": True,
        "message": "Survey questions created successfully.",
        "survey_questions_id": doc["_id"],
        "survey_id": survey_id
    }), 201

# ---------- GET all questions ----------
@question_bp.route("/questions", methods=["GET"])
def get_all_questions():
    cursor = list(questions.find({}))
    serialized = [serialize_doc(d) for d in cursor]
    return jsonify(serialized), 200

# ---------- GET questions for a single survey ----------
@question_bp.route("/questions/<string:survey_id>", methods=["GET"])
def get_questions_by_survey(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")
    q = questions.find_one({"survey_id": survey_id})
    if q:
        return jsonify(serialize_doc(q)), 200
    return jsonify({"success": False, "message": "Questions not found for this survey"}), 404

# ---------- UPDATE questions ----------
@question_bp.route("/questions/<string:survey_id>", methods=["PUT"])
def update_questions(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")

    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    incoming_questions = data.get("questions", [])
    if not isinstance(incoming_questions, list):
        return bad_request("questions must be an array.")

    errors = {}
    normalized_questions = []
    for i, q in enumerate(incoming_questions):
        if not isinstance(q, dict):
            errors[f"questions[{i}]"] = "Each question must be an object."
            continue

        # allow client to pass existing question_id (to preserve identity)
        qid = q.get("question_id") if validate_guid(q.get("question_id")) else make_guid()
        q_text = q.get("question_text")
        q_type = q.get("question_type")
        q_options = q.get("options", [])

        if not q_text or not isinstance(q_text, str):
            errors[f"questions[{i}].question_text"] = "question_text is required and must be a string."
        if q_type not in ALLOWED_Q_TYPES:
            errors[f"questions[{i}].question_type"] = f"question_type is required and must be one of {sorted(ALLOWED_Q_TYPES)}."

        # normalize/validate options; allow option_id if provided else generate
        normalized_opts = []
        if q_type in {"mcq", "dropdown", "multi_select", "yes_no"}:
            if not isinstance(q_options, list) or len(q_options) == 0:
                errors[f"questions[{i}].options"] = "options array is required for choice-type questions."
            else:
                for j, opt in enumerate(q_options):
                    if not isinstance(opt, dict):
                        errors[f"questions[{i}].options[{j}]"] = "Each option must be an object with at least a 'label'."
                    elif not opt.get("label"):
                        errors[f"questions[{i}].options[{j}].label"] = "label is required for each option."
                    else:
                        oid = opt.get("option_id") if validate_guid(opt.get("option_id")) else make_guid()
                        normalized_opts.append({
                            "option_id": oid,
                            "label": opt.get("label"),
                            "value": opt.get("value", opt.get("label"))
                        })

        if not any(k.startswith(f"questions[{i}]") for k in errors.keys()):
            normalized_questions.append({
                "question_id": qid,
                "question_text": q_text,
                "question_type": q_type,
                "options": normalized_opts,
                "required": bool(q.get("required", False)),
                "order": int(q.get("order", 0)),
                "metadata": q.get("metadata", {})
            })

    if errors:
        return bad_request("Validation failed", errors)

    result = questions.update_one(
        {"survey_id": survey_id},
        {"$set": {"questions": normalized_questions, "updated_at": iso_now()}}
    )

    if result.matched_count == 0:
        return jsonify({"success": False, "message": "Questions not found for this survey"}), 404

    updated_questions = questions.find_one({"survey_id": survey_id})
    return jsonify({
        "success": True,
        "message": "Survey questions updated successfully!",
        "data": serialize_doc(updated_questions)
    }), 200

# ---------- DELETE questions ----------
@question_bp.route("/questions/<string:survey_id>", methods=["DELETE"])
def delete_questions(survey_id):
    if not validate_guid(survey_id):
        return bad_request("Invalid survey_id (GUID expected).")

    result = questions.delete_one({"survey_id": survey_id})

    if result.deleted_count == 0:
        return jsonify({"success": False, "message": "Questions not found for this survey"}), 404

    return jsonify({"success": True, "message": "Survey questions deleted successfully!"}), 200
