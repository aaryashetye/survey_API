from flask import Blueprint, Flask, jsonify
from flask_cors import CORS
from routes.admin_routes import admin_bp
from routes.participant_routes import participant_bp
from routes.surveyor_routes import surveyor_bp
from routes.survey_routes import survey_bp
from routes.response_routes import response_bp
from routes.analysis_routes import analysis_bp
from routes.cycle_routes import cycle_bp
from routes.question_routes import question_bp


app = Flask(__name__)

# Register blueprint
app.register_blueprint(admin_bp)
app.register_blueprint(participant_bp)
app.register_blueprint(surveyor_bp)
app.register_blueprint(survey_bp)
app.register_blueprint(response_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(cycle_bp)
app.register_blueprint(question_bp)


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Local Admin API running!"})

import os

if __name__ == "__main__":
    # Use the PORT env var when provided by hosting platforms (Render sets $PORT).
    # Default to 5000 for local development.
    port = int(os.environ.get("PORT", 5000))

    # Bind to 0.0.0.0 so the container accepts external requests (not just localhost).
    # Disable the reloader on Windows to avoid socket races.
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)

CORS(app, resources={r"/*": {"origins": ["*"]}})