from flask import Flask
from app.config import Config
from app.database import init_db
from app.routes import main_bp
from app.ml.predictor import predictor

def create_app(config_class=Config) -> Flask:
    """
    Application Factory pattern to initialize the Flask application,
    load configurations, warm up resources, and register route Blueprints.
    """
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)

    # Initialize database schemas
    try:
        print("Initializing database schemas...")
        init_db(app.config.get("DATABASE_URL"))
        print("Database schemas initialized successfully.")
    except Exception as e:
        print(f"Database schema initialization failed: {e}")

    # Warm up / Load XGBoost model at application startup
    try:
        if predictor.model is not None:
            print("ML predictive classifier verified and loaded.")
        else:
            print("Warning: ML model failed to load. Operating in baseline recommendation mode.")
    except Exception as e:
        print(f"Model warm-up error: {e}")

    # Register Blueprint routes
    app.register_blueprint(main_bp)

    return app
