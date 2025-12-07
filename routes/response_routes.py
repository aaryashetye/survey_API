# response_bp.py
from flask import Blueprint, jsonify, request
from database import responses, questions   # MongoDB collections
import uuid
from datetime import datetime, timezone
import re
from bson import ObjectId

response_bp = Blueprint("response_bp", __name__)

GUID_RE = re.compile(r'^[0-9a-fA-F\-]{36}$')
ALLOWED_Q_TYPES = {"mcq", "yes_no", "text", "number", "dropdown", "multi_select"}

# ---------- helpers ----------
def make_guid():
    return str(uuid.uuid4())

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()

def is_guid(s):
    return isinstance(s, str) and GUID_RE.match(s)

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

# Resolve questionIndex/optionIndex to IDs if the client sent indexes
def map_indexes_to_ids(survey_id, answers):
    qdoc = questions.find_one({"survey_id": survey_id})
    if not qdoc:
        return answers, {"survey_id": "questions for survey not found to resolve indexes"}
    qlist = qdoc.get("questions", [])
    errors = {}
    out = []
    for i, a in enumerate(answers):
        if not isinstance(a, dict):
            errors[f"answers[{i}]"] = "Each answer must be an object."
            continue
        a_copy = dict(a)
        qi = pick(a, "questionIndex", "question_index")
        oi = pick(a, "optionIndex", "option_index")

        qobj = None
        if qi is not None:
            try:
                qi_int = int(qi)
                qobj = qlist[qi_int]
                # prefer integer qno if present, else use stored id
                qid = qobj.get("qno") if "qno" in qobj else qobj.get("question_id")
                if qid is None:
                    errors[f"answers[{i}]"] = "cannot resolve question id for index"
                else:
                    a_copy["questionId"] = qid
            except Exception:
                errors[f"answers[{i}]"] = "invalid questionIndex"

        if oi is not None:
            try:
                oi_int = int(oi)
                if qobj is None:
                    # try to locate question by given questionId in a_copy
                    qobj = next(
                        (
                            qq
                            for qq in qlist
                            if qq.get("qno") == a_copy.get("questionId")
                            or qq.get("question_id") == a_copy.get("questionId")
                        ),
                        None,
                    )
                if not qobj:
                    errors[f"answers[{i}]"] = "cannot resolve optionIndex without question present"
                else:
                    opts = qobj.get("options", [])
                    if oi_int < 0 or oi_int >= len(opts):
                        errors[f"answers[{i}]"] = "optionIndex out of range"
                    else:
                        opt = opts[oi_int]
                        a_copy["optionId"] = opt.get("option_id")
            except Exception:
                errors[f"answers[{i}]"] = "invalid optionIndex"

        out.append(a_copy)
    return out, (errors if errors else None)

# ---------- POST /responses ----------
@response_bp.route("/responses", methods=["POST"])
def create_response():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"success": False, "message": "Missing JSON body"}), 400

    # accept many key forms
    survey_id = pick(data, "surveyId", "survey_id", "SurveyId", "id")
    cycle_id = pick(data, "cycleId", "cycle_id", "CycleId")
    surveyor_id = pick(data, "surveyorId", "surveyor_id", "SurveyorId")
    participant_id = pick(data, "participantId", "participant_id", "ParticipantId")
    answers = pick(data, "Answers", "answers") or []
    location = pick(data, "Location", "location") or {}
    timestamp = pick(data, "Timestamp", "timestamp") or iso_now()

    errors = {}

    if not survey_id:
        errors["survey_id"] = "survey_id is required."

    # normalize location keys
    lat = pick(location, "lat", "latitude")
    lng = pick(location, "lng", "longitude")
    if lat is None or lng is None:
        errors["location"] = "location with latitude/longitude (or lat/lng) is required."
    else:
        try:
            lat = float(lat)
            lng = float(lng)
        except Exception:
            errors["location"] = "latitude/longitude must be numbers."

    if not isinstance(answers, list) or len(answers) == 0:
        errors["answers"] = "answers list is required."

    # if client used indexes, map them
    if any(
        (pick(a, "questionIndex", "question_index") is not None) or
        (pick(a, "optionIndex", "option_index") is not None)
        for a in answers if isinstance(a, dict)
    ):
        answers, map_err = map_indexes_to_ids(survey_id, answers)
        if map_err:
            errors.update(map_err)

    normalized_answers = []
    for i, a in enumerate(answers):
        if not isinstance(a, dict):
            errors[f"answers[{i}]"] = "Each answer must be an object."
            continue

        # accept many key names
        q_in = pick(a, "questionId", "QuestionId", "question_id", "questionId")
        o_in = pick(a, "optionId", "OptionId", "option_id", "optionId")
        qtype = pick(a, "questionType", "question_type", "QuestionType")
        val = pick(a, "option", "value", "Option", "Value")

        # normalize question id (int or guid or string)
        q_int = ensure_int(q_in)
        if q_int is not None:
            qid = q_int
        elif q_in and is_guid(q_in):
            qid = q_in
        elif q_in:
            qid = str(q_in)
        else:
            qid = None

        o_int = ensure_int(o_in)
        if o_int is not None:
            opt_id = o_int
        elif o_in and is_guid(o_in):
            opt_id = o_in
        elif o_in:
            opt_id = str(o_in)
        else:
            opt_id = None

        if not qid:
            errors[f"answers[{i}].question_id"] = "questionId/question_id is required (int or GUID)."

        if qtype and qtype not in ALLOWED_Q_TYPES:
            errors[f"answers[{i}].question_type"] = (
                f"Invalid question_type. Must be one of {sorted(ALLOWED_Q_TYPES)}."
            )

        normalized_answers.append({
            "question_id": qid,
            "question_type": qtype,
            "option_id": opt_id,
            "value": val,
            "value_text": val if isinstance(val, str) else None,
            "value_number": float(val) if isinstance(val, (int, float)) else None
        })

    # ---------- rating logic (based on option ratings from questions) ----------
    rating_sum = 0
    rating_count = 0

    qdoc = questions.find_one({"survey_id": survey_id})
    questions_list = qdoc.get("questions", []) if qdoc else []

    def find_option_rating(qid, opt_id):
        """
        qid: in your Model B this is usually an int (qno),
             but we also check question_id if you use GUIDs.
        opt_id: optionId (usually int).
        """
        for q in questions_list:
            if q.get("qno") == qid or q.get("question_id") == qid:
                for opt in q.get("options", []):
                    if opt.get("option_id") == opt_id:
                        return opt.get("rating", 0)
        return 0

    for ans in normalized_answers:
        qid = ans.get("question_id")
        opt_id = ans.get("option_id")
        if qid is None or opt_id is None:
            continue
        r = find_option_rating(qid, opt_id)
        ans["rating"] = r  # per-answer rating (1–4 or 0 if none)
        if isinstance(r, (int, float)) and r > 0:
            rating_sum += r
            rating_count += 1

    overall_rating = rating_sum / rating_count if rating_count > 0 else None

    # ---------- final validation check ----------
    if errors:
        return jsonify({"success": False, "message": "Validation failed", "errors": errors}), 400

    response_id = make_guid()
    doc = {
        "_id": response_id,
        "survey_id": survey_id,
        "cycle_id": cycle_id,
        "participant_id": participant_id,
        "surveyor_id": surveyor_id,
        "status": "submitted",
        "timestamp": timestamp,
        "location": {
            "lat": lat,
            "lng": lng,
            "accuracy_m": pick(location, "accuracy_m", None)
        },
        "answers": normalized_answers,
        "rating": overall_rating,   # overall average rating from 1–4
        "created_at": iso_now()
    }

    responses.insert_one(doc)

    return jsonify({
        "success": True,
        "message": "Response recorded successfully.",
        "response_id": response_id
    }), 201

# ---------- GET /responses (all) ----------
@response_bp.route("/responses", methods=["GET"])
def get_all_responses():
    all_res = [serialize_doc(r) for r in responses.find()]
    return jsonify(all_res), 200

# ---------- GET single ----------
@response_bp.route("/responses/<string:response_id>", methods=["GET"])
def get_response(response_id):
    r = responses.find_one({"_id": response_id})
    if r:
        return jsonify(serialize_doc(r)), 200
    return jsonify({"error": "Response not found"}), 404

# ---------- PUT /responses/<id> ----------
@response_bp.route("/responses/<string:response_id>", methods=["PUT"])
def update_response(response_id):
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"success": False, "message": "Missing JSON body"}), 400

    updates = {}
    if "answers" in data or "Answers" in data:
        updates["answers"] = pick(data, "answers", "Answers")
    if "location" in data or "Location" in data:
        loc = pick(data, "location", "Location")
        lat = pick(loc, "lat", "latitude")
        lng = pick(loc, "lng", "longitude")
        if lat is not None and lng is not None:
            try:
                updates["location"] = {
                    "lat": float(lat),
                    "lng": float(lng),
                    "accuracy_m": pick(loc, "accuracy_m", None)
                }
            except Exception:
                return jsonify({"success": False, "message": "Invalid location values"}), 400
    updates["timestamp"] = iso_now()

    res = responses.update_one({"_id": response_id}, {"$set": updates})
    if res.matched_count == 0:
        return jsonify({"error": "Response not found"}), 404
    updated = serialize_doc(responses.find_one({"_id": response_id}))
    return jsonify({
        "success": True,
        "message": "Response updated successfully!",
        "data": updated
    }), 200

# ---------- DELETE ----------
@response_bp.route("/responses/<string:response_id>", methods=["DELETE"])
def delete_response(response_id):
    res = responses.delete_one({"_id": response_id})
    if res.deleted_count == 0:
        return jsonify({"error": "Response not found"}), 404
    return jsonify({"success": True, "message": "Response deleted successfully!"}), 200
