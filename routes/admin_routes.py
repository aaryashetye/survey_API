from flask import Blueprint, jsonify, request
import uuid
from database import admins

admin_bp = Blueprint("admin_bp", __name__)

# CREATE Admin
@admin_bp.route("/admins", methods=["POST"])
def create_admin():
    data = request.get_json()
    guid = str(uuid.uuid4())  # Generate GUID for _id
    data["_id"] = guid

    admins.insert_one(data)
    return jsonify({
        "message": "✅ Admin created successfully!",
        "id": guid
    }), 201


#  READ ALL
@admin_bp.route("/admins", methods=["GET"])
def get_all_admins():
    all_admins = list(admins.find())
    return jsonify(all_admins), 200


#  READ ONE
@admin_bp.route("/admins/<string:admin_id>", methods=["GET"])
def get_admin(admin_id):
    admin = admins.find_one({"_id": admin_id})
    if admin:
        return jsonify(admin), 200
    return jsonify({"error": "Admin not found"}), 404


#  UPDATE
@admin_bp.route("/admins/<string:admin_id>", methods=["PUT"])
def update_admin(admin_id):
    data = request.get_json()
    result = admins.update_one({"_id": admin_id}, {"$set": data})
    if result.matched_count == 0:
        return jsonify({"error": "Admin not found"}), 404

    updated_admin = admins.find_one({"_id": admin_id})
    return jsonify({
        "message": "✅ Admin updated successfully!",
        "data": updated_admin
    }), 200


#  DELETE
@admin_bp.route("/admins/<string:admin_id>", methods=["DELETE"])
def delete_admin(admin_id):
    result = admins.delete_one({"_id": admin_id})
    if result.deleted_count == 0:
        return jsonify({"error": "Admin not found"}), 404
    return jsonify({"message": "🗑️ Admin deleted successfully!"}), 200
