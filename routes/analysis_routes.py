from flask import Blueprint, jsonify
from database import responses, participants, questions
from utils.ai_engine import compare_question    

analysis_bp = Blueprint("analysis_bp", __name__)


# ---------- AI CLASSIFICATION ----------
def classify_change(change):
    if change >= 2:
        return "Significant Improvement"
    elif change == 1:
        return "Slight Improvement"
    elif change == 0:
        return "No Change"
    elif change == -1:
        return "Slight Decline"
    else:
        return "Significant Decline"


# ---------- AI ANALYSIS ROUTE ----------
@analysis_bp.route("/analysis/<string:surveyor_id>", methods=["GET"])
def get_ai_analysis(surveyor_id):

    # Load raw responses
    res = list(responses.find({"surveyor_id": surveyor_id}))
    parts = list(participants.find({}))
    qs = list(questions.find({}))

    # Map participant names
    participant_map = {str(p["_id"]): p.get("name","Unknown") for p in parts}

    grouped = {}

    # Group responses by participant
    for r in res:

        if not r.get("location"):
            continue

        pid = str(r.get("participant_id"))

        if pid not in grouped:
            grouped[pid] = {
                "name": participant_map.get(pid,"Unknown"),
                "cycles":[]
            }

        grouped[pid]["cycles"].append({
            "timestamp": r.get("timestamp"),
            "lat": r["location"]["lat"],
            "lng": r["location"]["lng"],
            "answers":[
                {
                    "questionNo": str(a["question_id"]),
                    "rating": a.get("rating"),
                    "answer": a.get("value_text")
                } for a in r.get("answers",[])
            ]
        })

    # ---------- AI PART ----------
    for pid,data in grouped.items():

        data["cycles"].sort(key=lambda x: x["timestamp"])

        for i in range(len(data["cycles"])):

            if i == 0:
                data["cycles"][i]["status"] = "No Previous Data"
                continue

            prev = data["cycles"][i-1]["answers"]
            curr = data["cycles"][i]["answers"]

            change = 0

            for p in prev:
                match = next((c for c in curr if c["questionNo"] == p["questionNo"]),None)
                if match:
                    change += p["rating"] - match["rating"]

            data["cycles"][i]["status"] = classify_change(change)

    return jsonify(grouped)