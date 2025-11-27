from flask import Blueprint, jsonify, request
import uuid  # for generating GUIDs
from database import survey_cycles  # MongoDB collection
from models import SurveyCycle

cycle_bp = Blueprint("cycle_bp", __name__)

#  CREATE cycle
@cycle_bp.route("/cycles", methods=["POST"])
def create_cycle():
    data = request.get_json()

    new_cycle = SurveyCycle(
        _id=str(uuid.uuid4()),  # Generate GUID
        survey_id=data.get("survey_id"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date")
    )

    # Insert into MongoDB
    survey_cycles.insert_one(new_cycle.__dict__)

    return jsonify({
        "message": "✅ Survey cycle created successfully!",
        "data": new_cycle.__dict__
    }), 201


#  GET all cycles
@cycle_bp.route("/cycles", methods=["GET"])
def get_all_cycles():
    all_cycles = list(survey_cycles.find())
    for c in all_cycles:
        c["_id"] = str(c["_id"])  # ensure string for JSON
    return jsonify(all_cycles), 200


# 🔍 GET one cycle
@cycle_bp.route("/cycles/<string:cycle_id>", methods=["GET"])
def get_cycle(cycle_id):
    cycle = survey_cycles.find_one({"_id": cycle_id})
    if cycle:
        cycle["_id"] = str(cycle["_id"])
        return jsonify(cycle), 200
    return jsonify({"error": "Cycle not found"}), 404


#  UPDATE cycle
@cycle_bp.route("/cycles/<string:cycle_id>", methods=["PUT"])
def update_cycle(cycle_id):
    data = request.get_json()

    result = survey_cycles.update_one(
        {"_id": cycle_id},
        {"$set": {
            "survey_id": data.get("survey_id"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date")
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Cycle not found"}), 404

    updated_cycle = survey_cycles.find_one({"_id": cycle_id})
    updated_cycle["_id"] = str(updated_cycle["_id"])

    return jsonify({
        "message": "✅ Cycle updated successfully!",
        "data": updated_cycle
    }), 200


#  DELETE cycle
@cycle_bp.route("/cycles/<string:cycle_id>", methods=["DELETE"])
def delete_cycle(cycle_id):
    result = survey_cycles.delete_one({"_id": cycle_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Cycle not found"}), 404

    return jsonify({"message": "🗑️ Cycle deleted successfully!"}), 200
