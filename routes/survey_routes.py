from flask import Blueprint, jsonify, request
from database import surveys  # MongoDB collection
import uuid  # for GUIDs
from datetime import datetime

survey_bp = Blueprint("survey_bp", __name__)

#  CREATE a new survey
@survey_bp.route("/surveys", methods=["POST"])
def create_survey():
    data = request.get_json()

    new_survey = {
        "_id": str(uuid.uuid4()),  # GUID
        "title": data.get("title"),
        "created_by": data.get("created_by"),
        "created_at": data.get("created_at", datetime.utcnow().isoformat())
    }

    surveys.insert_one(new_survey)

    return jsonify({
        "message": "✅ Survey created successfully!",
        "data": new_survey
    }), 201


# 🔵 READ (GET ALL surveys)
@survey_bp.route("/surveys", methods=["GET"])
def get_all_surveys():
    all_surveys = list(surveys.find())
    return jsonify(all_surveys), 200


# 🔍 READ (GET ONE survey)
@survey_bp.route("/surveys/<string:survey_id>", methods=["GET"])
def get_survey(survey_id):
    s = surveys.find_one({"_id": survey_id})
    if s:
        return jsonify(s), 200
    return jsonify({"error": "Survey not found"}), 404


# ✏️ UPDATE survey
@survey_bp.route("/surveys/<string:survey_id>", methods=["PUT"])
def update_survey(survey_id):
    data = request.get_json()
    result = surveys.update_one(
        {"_id": survey_id},
        {"$set": {
            "title": data.get("title"),
            "created_by": data.get("created_by")
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Survey not found"}), 404

    updated_survey = surveys.find_one({"_id": survey_id})
    return jsonify({
        "message": "✅ Survey updated successfully!",
        "data": updated_survey
    }), 200


# ❌ DELETE survey
@survey_bp.route("/surveys/<string:survey_id>", methods=["DELETE"])
def delete_survey(survey_id):
    result = surveys.delete_one({"_id": survey_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Survey not found"}), 404

    return jsonify({"message": "🗑️ Survey deleted successfully!"}), 200
