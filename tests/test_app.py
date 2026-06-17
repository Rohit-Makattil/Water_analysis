import json
import pytest
from app.services.water_service import WaterService
from app.models import WaterAssessment

def test_validate_inputs_success():
    """Test that valid inputs are parsed correctly."""
    ph, solids, chloramines, sulfate, turbidity = WaterService.validate_inputs(
        "7.2", "500", "2.1", "150", "2.5"
    )
    assert ph == 7.2
    assert solids == 500.0
    assert chloramines == 2.1
    assert sulfate == 150.0
    assert turbidity == 2.5

def test_validate_inputs_failures():
    """Test that invalid inputs trigger ValueError with specific messages."""
    # Out of range pH
    with pytest.raises(ValueError, match="pH must be a value between 0.0 and 14.0"):
        WaterService.validate_inputs("15.0", "500", "2.1", "150", "2.5")
        
    # Negative solids
    with pytest.raises(ValueError, match="Total Dissolved Solids"):
        WaterService.validate_inputs("7.0", "-10", "2.1", "150", "2.5")
        
    # Non-numeric
    with pytest.raises(ValueError, match="All parameters must be valid decimal numbers"):
        WaterService.validate_inputs("abc", "500", "2.1", "150", "2.5")

    # Empty value
    with pytest.raises(ValueError, match="is required and cannot be empty"):
        WaterService.validate_inputs("", "500", "2.1", "150", "2.5")

def test_calculate_safety_score():
    """Test that the safety score calculates correctly with penalties."""
    # Perfect score
    assert WaterService.calculate_safety_score(7.0, 500, 2.0, 150, 2.5) == 100
    
    # Acidic pH penalty (6.5 - 5.5 = 1.0 * 20 = 20 penalty -> 80 score)
    assert WaterService.calculate_safety_score(5.5, 500, 2.0, 150, 2.5) == 80

def test_water_safety_category_mapping():
    """Test that safety scores map correctly to safety category labels."""
    assessment = WaterAssessment(water_safety_score=15)
    assert assessment.water_safety_category == "Critical"
    
    assessment = WaterAssessment(water_safety_score=35)
    assert assessment.water_safety_category == "Poor"
    
    assessment = WaterAssessment(water_safety_score=50)
    assert assessment.water_safety_category == "Moderate"
    
    assessment = WaterAssessment(water_safety_score=75)
    assert assessment.water_safety_category == "Good"
    
    assessment = WaterAssessment(water_safety_score=95)
    assert assessment.water_safety_category == "Excellent"

def test_check_who_violations():
    """Test that WHO guidelines violations are correctly detected."""
    violations = WaterService.check_who_violations(5.0, 1500, 5.0, 300, 6.0)
    assert len(violations) == 5
    assert any("pH level is too low" in v for v in violations)
    assert any("Solids are too high" in v for v in violations)
    assert any("Chloramines are too high" in v for v in violations)
    assert any("Sulfate is too high" in v for v in violations)
    assert any("Turbidity is too high" in v for v in violations)

def test_get_route_renders_dashboard(client):
    """Test that GET / returns the dashboard HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"HydroSafe" in response.data or b"Water Safety" in response.data

def test_post_route_assessment_json_success(client, db):
    """Test that POST / with valid inputs returns JSON success response containing SHAP and safety category."""
    payload = {
        "ph": "7.2",
        "solids": "500",
        "chloramines": "2.5",
        "sulfate": "180",
        "turbidity": "2.0"
    }
    response = client.post(
        "/",
        data=payload,
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert "prediction" in data
    assert "water_safety_score" in data
    assert "water_safety_category" in data
    assert "shap_explanation" in data
    assert "base_value" in data["shap_explanation"]
    assert "contributions" in data["shap_explanation"]
    assert "top_factors" in data["shap_explanation"]
    assert "id" in data

def test_post_route_assessment_json_failure(client, db):
    """Test that POST / with invalid inputs returns 400 Bad Request and error list when Accept header is set."""
    payload = {
        "ph": "15.0",
        "solids": "500",
        "chloramines": "2.5",
        "sulfate": "180",
        "turbidity": "2.0"
    }
    response = client.post(
        "/",
        data=payload,
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["status"] == "error"
    assert "reasons" in data
    assert len(data["reasons"]) > 0

def test_get_history_api(client, db):
    """Test that GET /api/history returns historical database logs."""
    response = client.get("/api/history")
    assert response.status_code == 200
    logs = json.loads(response.data)
    assert isinstance(logs, list)

def test_performance_routes(client):
    """Test that GET /performance renders the performance template and GET /api/performance-data serves metrics json."""
    # Test performance page rendering
    res_page = client.get("/performance")
    assert res_page.status_code == 200
    
    # Test performance API
    res_api = client.get("/api/performance-data")
    assert res_api.status_code == 200
    data = json.loads(res_api.data)
    assert "metrics" in data
    assert "roc_curves" in data
    assert "xgboost_confusion_matrix" in data
    assert "xgboost_feature_importances" in data
    assert "XGBoost" in data["metrics"]

def test_get_report_pdf_success(client, db):
    """Test that GET /api/report/<id> returns a PDF byte stream."""
    payload = {
        "ph": "7.2",
        "solids": "500",
        "chloramines": "2.5",
        "sulfate": "180",
        "turbidity": "2.0"
    }
    # Create an assessment first
    post_res = client.post(
        "/",
        data=payload,
        headers={"Accept": "application/json"}
    )
    assert post_res.status_code == 200
    data = json.loads(post_res.data)
    assessment_id = data["id"]
    
    # Download the report
    res = client.get(f"/api/report/{assessment_id}")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert b"%PDF" in res.data  # PDF magic bytes

def test_get_report_pdf_not_found(client, db):
    """Test that GET /api/report/999 returns 404."""
    res = client.get("/api/report/999")
    assert res.status_code == 404

def test_get_location_analytics(client, db):
    """Test that GET /api/location-analytics returns aggregated geographical JSON data."""
    payload_a = {
        "ph": "7.2",
        "solids": "500",
        "chloramines": "2.5",
        "sulfate": "180",
        "turbidity": "2.0",
        "location": "IoT Sensor - Sector A"
    }
    # Payload B has specific combinations verified to predict Not Potable under XGBoost model
    payload_b = {
        "ph": "5.0",
        "solids": "100",
        "chloramines": "8.0",
        "sulfate": "200",
        "turbidity": "10.0",
        "location": "IoT Sensor - Sector B"
    }
    # Create them
    res_a = client.post("/", data=payload_a, headers={"Accept": "application/json"})
    assert res_a.status_code == 200
    res_b = client.post("/", data=payload_b, headers={"Accept": "application/json"})
    assert res_b.status_code == 200

    # Query location analytics
    res = client.get("/api/location-analytics")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert isinstance(data, list)
    assert len(data) >= 2
    
    # Find Sector A
    sector_a = next((item for item in data if item["location"] == "IoT Sensor - Sector A"), None)
    assert sector_a is not None
    assert sector_a["total_assessments"] == 1
    assert sector_a["avg_safety_score"] > 80
    assert sector_a["potability_rate"] == 100.0
    
    # Find Sector B
    sector_b = next((item for item in data if item["location"] == "IoT Sensor - Sector B"), None)
    assert sector_b is not None
    assert sector_b["total_assessments"] == 1
    assert sector_b["avg_safety_score"] < 50
    assert sector_b["potability_rate"] == 0.0
