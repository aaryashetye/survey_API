
# question_bp.py
from flask import Blueprint, jsonify, request
from database import questions  # MongoDB collection
import uuid
from datetime import datetime, timezone
from bson import ObjectId

question_bp = Blueprint("question_bp", __name__)

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()

def serialize_value(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: serialize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [serialize_value(x) for x in v]
    return v

def serialize_to_pascal(doc):
    if not doc:
        return doc
    out = {}
    out["Id"] = str(doc.get("_id"))
    out["SurveyId"] = doc.get("survey_id")
    questions_out = []
    for q in doc.get("questions", []):
        q_out = {
            "Qno": q.get("qno"),
            "Text": q.get("text"),
            "Options": [
                {"OptionId": o.get("option_id"), "Option": o.get("option")}
                for o in q.get("options", [])
            ]
        }
        questions_out.append(q_out)
    out["Questions"] = questions_out
    out["CreatedAt"] = doc.get("created_at")
    out["UpdatedAt"] = doc.get("updated_at")
    return out

def bad_request(msg, errors=None):
    payload = {"success": False, "message": msg}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), 400

def pick(dct, *keys, default=None):
    for k in keys:
        if isinstance(dct, dict) and k in dct:
            return dct[k]
    return default

def ensure_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except Exception:
        return None

def next_qno(survey_id):
    doc = questions.find_one({"survey_id": survey_id}, {"questions.qno": 1})
    max_q = 0
    if doc and "questions" in doc:
        for q in doc["questions"]:
            qno = ensure_int(q.get("qno"))
            if qno and qno > max_q:
                max_q = qno
    return max_q + 1

def next_option_id_for_q(survey_id, qno):
    doc = questions.find_one({"survey_id": survey_id}, {"questions": 1})
    if not doc:
        return 1
    for q in doc.get("questions", []):
        if ensure_int(q.get("qno")) == qno:
            max_o = 0
            for o in q.get("options", []):
                oid = ensure_int(o.get("option_id"))
                if oid and oid > max_o:
                    max_o = oid
            return max_o + 1
    return 1

# ----------------- CREATE / REPLACE questions (Model B) -----------------
@question_bp.route("/questions", methods=["POST"])
def create_questions():
    data = request.get_json(force=True, silent=True)
    if not data:
        return bad_request("Missing JSON body")

    # accept surveyId, survey_id or id
    survey_id = pick(data, "surveyId", "survey_id", "id") or str(uuid.uuid4())
    incoming = pick(data, "Questions", "questions")
    if not isinstance(incoming, list) or len(incoming) == 0:
        return bad_request("Validation failed", {"questions": "questions must be a non-empty array."})

    errors = {}
    normalized_questions = []
    # compute next qno lazily
    next_qno_cache = None

    for i, q in enumerate(incoming):
        if not isinstance(q, dict):
            errors[f"questions[{i}]"] = "Each question must be an object."
            continue

        # accept Qno / qno
        qno_in = pick(q, "Qno", "qno")
        qno = ensure_int(qno_in)
        if qno is None:
            if next_qno_cache is None:
                next_qno_cache = next_qno(survey_id)
            qno = next_qno_cache
            next_qno_cache += 1

        # accept Text / text
        text = pick(q, "Text", "text")
        if not text or not isinstance(text, str) or text.strip() == "":
            errors[f"questions[{i}].text"] = "text is required and must be a non-empty string."
            continue
        text = text.strip()

        # Options: accept Options / options
        opts_in = pick(q, "Options", "options") or []
        if not isinstance(opts_in, list):
            errors[f"questions[{i}].options"] = "options must be an array (can be empty)."
            continue

        normalized_opts = []
        next_opt_cache = None
        for j, opt in enumerate(opts_in):
            if not isinstance(opt, dict):
                errors[f"questions[{i}].options[{j}]"] = "Each option must be an object."
                continue
            label = pick(opt, "Option", "option")
            if not label or not isinstance(label, str):
                errors[f"questions[{i}].options[{j}].option"] = "Option text is required."
                continue
            oid_in = pick(opt, "OptionId", "optionId", "option_id")
            oid = ensure_int(oid_in)
            if oid is None:
                if next_opt_cache is None:
                    next_opt_cache = next_option_id_for_q(survey_id, qno)
                oid = next_opt_cache
                next_opt_cache += 1
            normalized_opts.append({
                "option_id": oid,
                "option": label.strip()
            })

        normalized_questions.append({
            "qno": qno,
            "text": text,
            "options": normalized_opts
        })

    if errors:
        return bad_request("Validation failed", errors)

    # Upsert / replace questions doc for this survey
    existing = questions.find_one({"survey_id": survey_id})
    now = iso_now()
    if existing:
        questions.update_one({"survey_id": survey_id}, {"$set": {"questions": normalized_questions, "updated_at": now}})
        doc_id = existing["_id"]
    else:
        doc = {
            "_id": str(uuid.uuid4()),
            "survey_id": survey_id,
            "questions": normalized_questions,
            "created_at": now,
            "updated_at": now
        }
        questions.insert_one(doc)
        doc_id = doc["_id"]

    return jsonify({
        "success": True,
        "message": "Survey questions created/updated successfully.",
        "surveyQuestionsId": str(doc_id),
        "surveyId": survey_id
    }), 201

# ----------------- GET by surveyId -----------------
@question_bp.route("/questions/<string:survey_id>", methods=["GET"])
def get_questions_by_survey(survey_id):
    doc = questions.find_one({"survey_id": survey_id})
    if not doc:
        return jsonify({"success": False, "message": "Questions not found for this survey"}), 404
    return jsonify(serialize_to_pascal(doc)), 200

# ----------------- GET all questions -----------------
@question_bp.route("/questions", methods=["GET"])
def get_all_questions():
    # return all survey question-sets serialized to PascalCase
    docs = list(questions.find({}))
    return jsonify([serialize_to_pascal(d) for d in docs]), 200

# ----------------- DELETE -----------------
@question_bp.route("/questions/<string:survey_id>", methods=["DELETE"])
def delete_questions(survey_id):
    res = questions.delete_one({"survey_id": survey_id})
    if res.deleted_count == 0:
        return jsonify({"success": False, "message": "Questions not found for this survey"}), 404
    return jsonify({"success": True, "message": "Survey questions deleted successfully!"}), 200
