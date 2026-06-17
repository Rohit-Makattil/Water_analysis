import os
import json
from flask import Blueprint, request, render_template, jsonify, send_file, current_app
from app.database import get_db
from app.services.water_service import WaterService
from app.models import WaterAssessment

main_bp = Blueprint("main", __name__)

@main_bp.route("/", methods=["GET", "POST"])
def predict():
    """Main route serving diagnostic page (GET) and executing assessment submissions (POST)."""
    form_data = {"ph": "", "solids": "", "chloramines": "", "sulfate": "", "turbidity": ""}

    if request.method == "POST":
        with get_db() as db:
            try:
                if request.is_json:
                    data = request.get_json() or {}
                    ph_val = data.get("ph")
                    solids_val = data.get("solids")
                    chloramines_val = data.get("chloramines")
                    sulfate_val = data.get("sulfate")
                    turbidity_val = data.get("turbidity")
                    location_val = data.get("location")
                else:
                    ph_val = request.form.get("ph")
                    solids_val = request.form.get("solids")
                    chloramines_val = request.form.get("chloramines")
                    sulfate_val = request.form.get("sulfate")
                    turbidity_val = request.form.get("turbidity")
                    location_val = request.form.get("location")

                ph, solids, chloramines, sulfate, turbidity = WaterService.validate_inputs(
                    ph_val, solids_val, chloramines_val, sulfate_val, turbidity_val
                )

                form_data = {
                    "ph": ph,
                    "solids": solids,
                    "chloramines": chloramines,
                    "sulfate": sulfate,
                    "turbidity": turbidity
                }

                # Resolve location: support manual override (e.g. from IoT simulation)
                headers = dict(request.headers)
                result = WaterService.process_assessment(
                    db=db,
                    ph=ph,
                    solids=solids,
                    chloramines=chloramines,
                    sulfate=sulfate,
                    turbidity=turbidity,
                    headers=headers
                )
                
                # If custom location was sent (e.g., from IoT Simulator Sector), override resolved location
                if location_val:
                    assessment_id = result["id"]
                    assessment = db.query(WaterAssessment).filter(WaterAssessment.id == assessment_id).first()
                    if assessment:
                        assessment.user_location = location_val
                        db.commit()
                        db.refresh(assessment)
                        result = assessment.to_dict()

                accept_header = request.headers.get('Accept', '')
                if 'application/json' in accept_header or request.is_json:
                    return jsonify({
                        "status": "success",
                        "prediction": result["prediction"],
                        "reasons": result["failed_who_parameters"],
                        "suggestions": result["recommendations"],
                        "confidence_score": result["confidence_score"],
                        "water_safety_score": result["water_safety_score"],
                        "water_safety_category": result["water_safety_category"],
                        "shap_explanation": result.get("shap_explanation"),
                        "id": result["id"]
                    })

                return render_template(
                    "index.html",
                    prediction=result["prediction"],
                    reasons=result["failed_who_parameters"],
                    suggestions=result["recommendations"],
                    water_safety_score=result["water_safety_score"],
                    water_safety_category=result["water_safety_category"],
                    shap_explanation=result.get("shap_explanation"),
                    form_data=form_data
                )

            except ValueError as ve:
                db.rollback()
                print(f"Validation Error: {ve}")
                accept_header = request.headers.get('Accept', '')
                if 'application/json' in accept_header or request.is_json:
                    return jsonify({
                        "status": "error",
                        "reasons": [str(ve)],
                        "suggestions": []
                    }), 400
                    
                return render_template(
                    "index.html",
                    prediction=None,
                    reasons=[str(ve)],
                    suggestions=[],
                    form_data=form_data
                )
                
            except Exception as e:
                db.rollback()
                print(f"Unhandled Server Exception: {e}")
                accept_header = request.headers.get('Accept', '')
                if 'application/json' in accept_header or request.is_json:
                    return jsonify({
                        "status": "error",
                        "reasons": [f"An unexpected internal error occurred: {e}"],
                        "suggestions": []
                    }), 500
                    
                return render_template(
                    "index.html",
                    prediction=None,
                    reasons=["An unexpected internal error occurred. Please try again."],
                    suggestions=[],
                    form_data=form_data
                )

    return render_template("index.html", prediction=None, reasons=[], suggestions=[], form_data=form_data)


@main_bp.route("/api/history", methods=["GET"])
def get_history():
    """Retrieve historical ingestion logs from the SQLite/PostgreSQL database."""
    with get_db() as db:
        try:
            assessments = db.query(WaterAssessment).order_by(WaterAssessment.timestamp.desc()).all()
            return jsonify([item.to_dict() for item in assessments])
        except Exception as e:
            print(f"Error querying database history: {e}")
            return jsonify({"error": "Failed to retrieve history logs."}), 500


@main_bp.route("/performance", methods=["GET"])
def performance():
    """Render the Model Performance metrics dashboard page."""
    return render_template("index.html", active_tab="performance")


@main_bp.route("/api/performance-data", methods=["GET"])
def get_performance_data():
    """Serve the pre-calculated metrics comparison JSON for performance charts."""
    json_path = os.path.join(current_app.root_path, "static", "model_performance_data.json")
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({"error": "Performance statistics file not found. Run train_model.py first."}), 404
    except Exception as e:
        print(f"Error loading performance statistics: {e}")
        return jsonify({"error": f"Internal server error loading statistics: {e}"}), 500


@main_bp.route("/api/report/<int:assessment_id>", methods=["GET"])
def download_report(assessment_id):
    """Generate and stream a professional PDF report for a specific water assessment."""
    with get_db() as db:
        assessment = db.query(WaterAssessment).filter(WaterAssessment.id == assessment_id).first()
        if not assessment:
            return jsonify({"error": "Assessment record not found."}), 404
        
        try:
            from app.services.pdf_service import PDFService
            pdf_buffer = PDFService.generate_assessment_report(assessment)
            return send_file(
                pdf_buffer,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"hydrosafe_report_{assessment.id}.pdf"
            )
        except Exception as e:
            print(f"Failed to generate PDF report: {e}")
            return jsonify({"error": f"Failed to compile PDF report: {e}"}), 500


@main_bp.route("/api/location-analytics", methods=["GET"])
def get_location_analytics():
    """Calculate aggregated safety scores and potability statistics grouped by location."""
    with get_db() as db:
        try:
            assessments = db.query(WaterAssessment).all()
            if not assessments:
                return jsonify([])
                
            # Group rows by user location
            location_groups = {}
            for row in assessments:
                loc = row.user_location or "Unknown (Remote)"
                if loc not in location_groups:
                    location_groups[loc] = []
                location_groups[loc].append(row)
                
            analytics = []
            for loc, rows in location_groups.items():
                total = len(rows)
                avg_score = sum(r.water_safety_score for r in rows) / total
                potable_count = sum(1 for r in rows if r.prediction == "Potable")
                potability_rate = (potable_count / total) * 100
                
                # Count guideline violations
                failures = {"pH": 0, "Solids": 0, "Chloramines": 0, "Sulfate": 0, "Turbidity": 0}
                for r in rows:
                    if r.ph < 6.5 or r.ph > 8.5: failures["pH"] += 1
                    if r.solids > 1000: failures["Solids"] += 1
                    if r.chloramines > 4.0: failures["Chloramines"] += 1
                    if r.sulfate > 250: failures["Sulfate"] += 1
                    if r.turbidity > 5.0: failures["Turbidity"] += 1
                    
                # Identify main driving contaminant (highest failure count)
                primary_contaminant = "None"
                max_fails = 0
                for param, count in failures.items():
                    if count > max_fails:
                        max_fails = count
                        primary_contaminant = param
                        
                analytics.append({
                    "location": loc,
                    "total_assessments": total,
                    "avg_safety_score": float(round(avg_score, 1)),
                    "potability_rate": float(round(potability_rate, 1)),
                    "primary_contaminant": primary_contaminant
                })
                
            return jsonify(analytics)
        except Exception as e:
            print(f"Error calculating location analytics: {e}")
            return jsonify({"error": f"Failed to compute location analytics: {e}"}), 500
