from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, Float, String, DateTime, Text
from app.database import Base

class WaterAssessment(Base):
    """ORM Model for Water Safety Assessments."""
    __tablename__ = "water_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user_location = Column(String(255), nullable=True)
    
    # Input parameters
    ph = Column(Float, nullable=False)
    solids = Column(Float, nullable=False)
    chloramines = Column(Float, nullable=False)
    sulfate = Column(Float, nullable=False)
    turbidity = Column(Float, nullable=False)
    
    # ML Outputs
    prediction = Column(String(50), nullable=False)
    confidence_score = Column(Float, nullable=False)
    
    # Calculated Index Score (0 - 100)
    water_safety_score = Column(Integer, nullable=False)
    
    # Failed guidelines & recommendations stored as serialized JSON strings
    failed_who_parameters_json = Column(Text, nullable=False)
    recommendations_json = Column(Text, nullable=False)
    
    @property
    def failed_who_parameters(self) -> list:
        """Parse failed WHO guidelines from database JSON string."""
        try:
            return json.loads(self.failed_who_parameters_json) if self.failed_who_parameters_json else []
        except Exception:
            return []
            
    @failed_who_parameters.setter
    def failed_who_parameters(self, value: list):
        """Serialize failed WHO guidelines list to JSON string."""
        self.failed_who_parameters_json = json.dumps(value)
        
    @property
    def recommendations(self) -> list:
        """Parse recommendations from database JSON string."""
        try:
            return json.loads(self.recommendations_json) if self.recommendations_json else []
        except Exception:
            return []
            
    @recommendations.setter
    def recommendations(self, value: list):
        """Serialize recommendations list to JSON string."""
        self.recommendations_json = json.dumps(value)

    @property
    def water_safety_category(self) -> str:
        """Categorize the water safety score (0-100)."""
        score = self.water_safety_score
        if score is None:
            return "Critical"
        if score <= 20:
            return "Critical"
        elif score <= 40:
            return "Poor"
        elif score <= 60:
            return "Moderate"
        elif score <= 80:
            return "Good"
        else:
            return "Excellent"

    def to_dict(self) -> dict:
        """Serialize ORM object to Python dict."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_location": self.user_location,
            "ph": self.ph,
            "solids": self.solids,
            "chloramines": self.chloramines,
            "sulfate": self.sulfate,
            "turbidity": self.turbidity,
            "prediction": self.prediction,
            "confidence_score": self.confidence_score,
            "water_safety_score": self.water_safety_score,
            "water_safety_category": self.water_safety_category,
            "failed_who_parameters": self.failed_who_parameters,
            "recommendations": self.recommendations
        }
