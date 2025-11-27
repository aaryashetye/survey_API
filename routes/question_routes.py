from flask import Blueprint, jsonify, request
from database import questions  # MongoDB collection
import uuid  # for GUIDs

question_bp = Blueprint("question_bp", __name__)

# 🟢 CREATE survey questions
@question_bp.route("/questions", methods=["POST"])
def create_questions():
    data = request.get_json()

    new_questions = {
        "_id": str(uuid.uuid4()),  # GUID
        "survey_id": data.get("survey_id"),
        "questions": data.get("questions", [])
    }

    questions.insert_one(new_questions)

    return jsonify({
        "message": "✅ Survey questions created successfully!",
        "data": new_questions
    }), 201


# 🔵 GET all questions
@question_bp.route("/questions", methods=["GET"])
def get_all_questions():
    all_questions = list(questions.find())
    return jsonify(all_questions), 200


# 🔍 GET questions for a single survey
@question_bp.route("/questions/<string:survey_id>", methods=["GET"])
def get_questions_by_survey(survey_id):
    q = questions.find_one({"survey_id": survey_id})
    if q:
        return jsonify(q), 200
    return jsonify({"error": "Questions not found for this survey"}), 404


# ✏️ UPDATE questions
@question_bp.route("/questions/<string:survey_id>", methods=["PUT"])
def update_questions(survey_id):
    data = request.get_json()
    result = questions.update_one(
        {"survey_id": survey_id},
        {"$set": {"questions": data.get("questions", [])}}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Questions not found for this survey"}), 404

    updated_questions = questions.find_one({"survey_id": survey_id})
    return jsonify({
        "message": "✅ Survey questions updated successfully!",
        "data": updated_questions
    }), 200


# ❌ DELETE questions
@question_bp.route("/questions/<string:survey_id>", methods=["DELETE"])
def delete_questions(survey_id):
    result = questions.delete_one({"survey_id": survey_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Questions not found for this survey"}), 404

    return jsonify({"message": "🗑️ Survey questions deleted successfully!"}), 200
