from flask import Blueprint, jsonify, request
from database import participants  # MongoDB collection
import uuid  # for GUIDs

participant_bp = Blueprint("participant_bp", __name__)

#  CREATE Participant
@participant_bp.route("/participants", methods=["POST"])
def create_participant():
    data = request.get_json()

    new_participant = {
        "_id": str(uuid.uuid4()),  # GUID
        "name": data.get("name"),
        "age": data.get("age"),
        "gender": data.get("gender"),
        "survey_id": data.get("survey_id")
    }

    participants.insert_one(new_participant)

    return jsonify({
        "message": "✅ Participant added successfully!",
        "data": new_participant
    }), 201


#  READ (GET ALL)
@participant_bp.route("/participants", methods=["GET"])
def get_all_participants():
    all_participants = list(participants.find())
    return jsonify(all_participants), 200


#  READ (GET ONE)
@participant_bp.route("/participants/<string:participant_id>", methods=["GET"])
def get_participant(participant_id):
    p = participants.find_one({"_id": participant_id})
    if p:
        return jsonify(p), 200
    return jsonify({"error": "Participant not found"}), 404


#  UPDATE
@participant_bp.route("/participants/<string:participant_id>", methods=["PUT"])
def update_participant(participant_id):
    data = request.get_json()
    result = participants.update_one(
        {"_id": participant_id},
        {"$set": {
            "name": data.get("name"),
            "age": data.get("age"),
            "gender": data.get("gender"),
            "survey_id": data.get("survey_id")
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Participant not found"}), 404

    updated_participant = participants.find_one({"_id": participant_id})
    return jsonify({
        "message": "✅ Participant updated successfully!",
        "data": updated_participant
    }), 200


#  DELETE
@participant_bp.route("/participants/<string:participant_id>", methods=["DELETE"])
def delete_participant(participant_id):
    result = participants.delete_one({"_id": participant_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Participant not found"}), 404

    return jsonify({"message": "🗑️ Participant deleted successfully!"}), 200
