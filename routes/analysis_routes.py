from flask import Blueprint, jsonify
from database import responses, participants

from utils.ai_engine import analyze_trends
from utils.ai_local import generate_local_analysis

analysis_bp = Blueprint("analysis_bp", __name__)


# ---------- HELPER ----------
def build_grouped_data(survey_responses):

    grouped = {}

    for r in survey_responses:
        pid = str(r["participant_id"])

        grouped.setdefault(pid, {
            "participant_id": pid,
            "cycles": []
        })

        grouped[pid]["cycles"].append({
            "cycle_id": r.get("cycle_id"),
            "timestamp": r.get("timestamp"),
            "answers": [
                {
                    "questionNo": str(a["question_id"]),
                    "rating": a.get("rating"),
                    "answer": a.get("value_text")
                }
                for a in r.get("answers", [])
            ]
        })

    return grouped


# ---------- ROUTE 1 (DETAILED ANALYSIS) ----------
@analysis_bp.route("/analysis/<string:surveyor_id>", methods=["GET"])
def get_ai_analysis(surveyor_id):

    res = list(responses.find({"surveyor_id": surveyor_id}))
    parts = list(participants.find({}))

    participant_map = {
        str(p["_id"]): p.get("name", "Unknown") for p in parts
    }

    grouped = {}

    for r in res:

        if not r.get("location"):
            continue

        pid = str(r.get("participant_id"))

        if pid not in grouped:
            grouped[pid] = {
                "name": participant_map.get(pid, "Unknown"),
                "cycles": []
            }

        grouped[pid]["cycles"].append({
            "timestamp": r.get("timestamp"),
            "lat": r["location"]["lat"],
            "lng": r["location"]["lng"],
            "answers": [
                {
                    "questionNo": str(a["question_id"]),
                    "rating": a.get("rating"),
                    "answer": a.get("value_text")
                }
                for a in r.get("answers", [])
            ]
        })

    # ✅ Apply AI
    result = analyze_trends(grouped)

    return jsonify(result), 200


# ---------- ROUTE 2 (FULL AI REPORT) ----------
@analysis_bp.route("/analysis/generate/<string:survey_id>", methods=["GET"])
def generate_analysis(survey_id):

    survey_responses = list(responses.find({"survey_id": survey_id}))

    if not survey_responses:
        return jsonify({"error": "No data found"}), 404

    # ✅ Trend AI
    grouped = build_grouped_data(survey_responses)
    trend_result = analyze_trends(grouped)

    # ✅ Issue AI
    all_text = []

    for r in survey_responses:
        for ans in r.get("answers", []):
            all_text.append(str(ans))

    issue_result = generate_local_analysis(all_text)

    return jsonify({
        "trend_analysis": trend_result,
        "issue_analysis": issue_result
    }), 200