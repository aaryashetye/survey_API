from pymongo import MongoClient

MONGO_URI = "mongodb+srv://aaryashetye67_db_user:palmerswine67@surveyapi.6fwdmd0.mongodb.net/"

client = MongoClient(MONGO_URI)
db = client["SurveyAPI"]

admins = db["admins"]
analysis = db["analysis"]
survey_cycles = db["survey_cycles"]
participants = db["participants"]
questions = db["questions"]
responses = db["responses"]
surveys = db["surveys"]
surveyors = db["surveyors"]


# Test the connection
try:
    client.admin.command("ping")
    print("✅ MongoDB connection successful!")
except Exception as e:
    print("❌ Connection failed:", e)
