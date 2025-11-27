from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

@dataclass
class Admin:
    _id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    email: str = ""
    password: str = ""

@dataclass
class Participant:
    _id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    age: int = 0
    gender: str = ""
    survey_id: str = ""

@dataclass
class Surveyor:
    _id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    email: str = ""
    password: str = ""

@dataclass
class Survey:
    _id: str = field(default_factory=lambda: f"svy_{str(uuid4())[:8]}")
    title: str = ""
    created_by: str = ""  # admin_id or surveyor_id
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

@dataclass
class SurveyResponse:
    _id: str = field(default_factory=lambda: f"resp_{str(uuid4())[:8]}")
    survey_id: str = ""
    cycle_id: str = ""
    surveyor_id: str = ""
    participant_id: str = ""
    answers: list = field(default_factory=list)
    location: dict = field(default_factory=lambda: {"latitude": 0.0, "longitude": 0.0})
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

@dataclass
class SurveyAnalysis:
    _id: str = field(default_factory=lambda: f"analysis_{str(uuid4())[:8]}")
    survey_id: str = ""
    cycle: int = 1
    map_pins: list = field(default_factory=list)
    summary: str = ""

@dataclass
class SurveyCycle:
    _id: str = field(default_factory=lambda: f"cycle_{str(uuid4())[:8]}")
    survey_id: str = ""
    start_date: str = ""
    end_date: str = ""

@dataclass
class SurveyQuestion:
    _id: str = field(default_factory=lambda: f"sq_{str(uuid4())[:8]}")
    survey_id: str = ""  # Link to the parent survey
    questions: list = field(default_factory=list)