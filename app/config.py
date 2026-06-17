import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Config:
    """Central configuration class for Water Quality App."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-water-quality")
    
    # Default SQLite database path, supports PostgreSQL override
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'water_quality.db')}")
    
    # Handle postgres:// connection URI scheme change for SQLAlchemy 1.4+
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    
    # Safe thresholds for water quality (matching WHO/EPA drinking water standards)
    THRESHOLDS = {
        "ph": (6.5, 8.5),
        "Solids": (0, 1000.0),
        "Chloramines": (0, 4.0),
        "Sulfate": (0, 250.0),
        "Turbidity": (0, 5.0)
    }

class TestingConfig(Config):
    """Configuration class for testing with an in-memory database."""
    TESTING = True
    DATABASE_URL = "sqlite:///:memory:"
