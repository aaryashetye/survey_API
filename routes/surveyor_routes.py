from flask import Blueprint, jsonify, request
from database import surveyors  # MongoDB collection
import uuid  # for GUIDs

surveyor_bp = Blueprint("surveyor_bp", __name__)

#  CREATE Surveyor
@surveyor_bp.route("/surveyors", methods=["POST"])
def create_surveyor():
    data = request.get_json()

    # Optional: check if email already exists
    if surveyors.find_one({"email": data.get("email")}):
        return jsonify({"error": "Email already exists!"}), 400

    new_surveyor = {
        "_id": str(uuid.uuid4()),  # GUID
        "name": data.get("name"),
        "email": data.get("email"),
        "password": data.get("password")  # ideally hashed
    }

    surveyors.insert_one(new_surveyor)

    return jsonify({
        "message": "✅ Surveyor created successfully!",
        "data": new_surveyor
    }), 201


#  READ (GET ALL)
@surveyor_bp.route("/surveyors", methods=["GET"])
def get_all_surveyors():
    all_surveyors = list(surveyors.find())
    return jsonify(all_surveyors), 200


#  READ (ONE)
@surveyor_bp.route("/surveyors/<string:surveyor_id>", methods=["GET"])
def get_surveyor(surveyor_id):
    s = surveyors.find_one({"_id": surveyor_id})
    if s:
        return jsonify(s), 200
    return jsonify({"error": "Surveyor not found"}), 404


#  UPDATE
@surveyor_bp.route("/surveyors/<string:surveyor_id>", methods=["PUT"])
def update_surveyor(surveyor_id):
    data = request.get_json()
    result = surveyors.update_one(
        {"_id": surveyor_id},
        {"$set": {
            "name": data.get("name"),
            "email": data.get("email"),
            "password": data.get("password")
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Surveyor not found"}), 404

    updated_surveyor = surveyors.find_one({"_id": surveyor_id})
    return jsonify({
        "message": "✅ Surveyor updated successfully!",
        "data": updated_surveyor
    }), 200


#  DELETE
@surveyor_bp.route("/surveyors/<string:surveyor_id>", methods=["DELETE"])
def delete_surveyor(surveyor_id):
    result = surveyors.delete_one({"_id": surveyor_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Surveyor not found"}), 404

    return jsonify({"message": "🗑️ Surveyor deleted successfully!"}), 200
