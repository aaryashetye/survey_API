from flask import Flask, jsonify
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

if __name__ == "__main__":
    # disable the reloader (avoids socket/thread races on Windows)
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)