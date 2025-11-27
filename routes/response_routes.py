from flask import Blueprint, jsonify, request
from database import responses  # MongoDB collection
import uuid  # for GUIDs
from datetime import datetime

response_bp = Blueprint("response_bp", __name__)

#  CREATE response
@response_bp.route("/responses", methods=["POST"])
def create_response():
    data = request.get_json()

    new_response = {
        "_id": str(uuid.uuid4()),  # GUID
        "survey_id": data.get("survey_id"),
        "cycle_id": data.get("cycle_id", ""),
        "surveyor_id": data.get("surveyor_id"),
        "participant_id": data.get("participant_id"),
        "answers": data.get("answers", []),
        "location": data.get("location", {"latitude": 0.0, "longitude": 0.0}),
        "timestamp": data.get("timestamp", datetime.utcnow().isoformat())
    }

    responses.insert_one(new_response)

    return jsonify({
        "message": "✅ Response recorded successfully!",
        "data": new_response
    }), 201


#  GET all responses
@response_bp.route("/responses", methods=["GET"])
def get_all_responses():
    all_responses = list(responses.find())
    return jsonify(all_responses), 200


#  GET single response by GUID
@response_bp.route("/responses/<string:response_id>", methods=["GET"])
def get_response(response_id):
    r = responses.find_one({"_id": response_id})
    if r:
        return jsonify(r), 200
    return jsonify({"error": "Response not found"}), 404


#  UPDATE response
@response_bp.route("/responses/<string:response_id>", methods=["PUT"])
def update_response(response_id):
    data = request.get_json()
    result = responses.update_one(
        {"_id": response_id},
        {"$set": {
            "answers": data.get("answers"),
            "location": data.get("location"),
            "timestamp": data.get("timestamp", datetime.utcnow().isoformat())
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Response not found"}), 404

    updated_response = responses.find_one({"_id": response_id})
    return jsonify({
        "message": "✅ Response updated successfully!",
        "data": updated_response
    }), 200


#  DELETE response
@response_bp.route("/responses/<string:response_id>", methods=["DELETE"])
def delete_response(response_id):
    result = responses.delete_one({"_id": response_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Response not found"}), 404

    return jsonify({"message": "🗑️ Response deleted successfully!"}), 200
