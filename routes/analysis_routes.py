from flask import Blueprint, jsonify, request
from database import analysis # your MongoDB collection
import uuid  # for GUID generation

analysis_bp = Blueprint("analysis_bp", __name__)

#  CREATE analysis record
@analysis_bp.route("/analysis", methods=["POST"])
def create_analysis():
    data = request.get_json()

    new_analysis = {
        "_id": str(uuid.uuid4()),  # GUID
        "survey_id": data.get("survey_id"),
        "cycle": data.get("cycle", 1),
        "map_pins": data.get("map_pins", []),
        "summary": data.get("summary", "")
    }

    analysis.insert_one(new_analysis)

    return jsonify({
        "message": "✅ Analysis created successfully!",
        "data": new_analysis
    }), 201


#  GET all analyses
@analysis_bp.route("/analysis", methods=["GET"])
def get_all_analysis():
    analyses = list(analysis.find({}, {"_id": 1, "survey_id": 1, "cycle": 1, "map_pins": 1, "summary": 1}))
    # No ObjectId conversion needed, GUID is already string
    return jsonify(analyses), 200


#  GET one analysis by GUID
@analysis_bp.route("/analysis/<string:analysis_id>", methods=["GET"])
def get_analysis(analysis_id):
    a = analysis.find_one({"_id": analysis_id})
    if a:
        return jsonify(a), 200
    return jsonify({"error": "Analysis not found"}), 404


#  UPDATE analysis
@analysis_bp.route("/analysis/<string:analysis_id>", methods=["PUT"])
def update_analysis(analysis_id):
    data = request.get_json()
    result = analysis.update_one(
        {"_id": analysis_id},
        {"$set": {
            "survey_id": data.get("survey_id"),
            "cycle": data.get("cycle"),
            "map_pins": data.get("map_pins"),
            "summary": data.get("summary")
        }}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Analysis not found"}), 404

    updated_analysis = analysis.find_one({"_id": analysis_id})
    return jsonify({"message": "✅ Analysis updated successfully!", "data": updated_analysis}), 200


#  DELETE analysis
@analysis_bp.route("/analysis/<string:analysis_id>", methods=["DELETE"])
def delete_analysis(analysis_id):
    result = analysis.delete_one({"_id": analysis_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Analysis not found"}), 404

    return jsonify({"message": "🗑️ Analysis deleted successfully!"}), 200