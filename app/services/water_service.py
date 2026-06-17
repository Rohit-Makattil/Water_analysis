from datetime import datetime, timezone
import json
from app.config import Config
from app.models import WaterAssessment
from app.ml.predictor import predictor
from app.services.gemini_service import GeminiService

class WaterService:
    """Service handling water diagnostics business logic and DB persistence."""
    
    @staticmethod
    def validate_inputs(ph_val, solids_val, chloramines_val, sulfate_val, turbidity_val) -> tuple:
        """
        Validates form or JSON input parameters and parses them to floats.
        
        Args:
            ph_val, solids_val, chloramines_val, sulfate_val, turbidity_val: Raw inputs.
            
        Returns:
            tuple: (ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float)
            
        Raises:
            ValueError: If any parameter is missing, invalid, out of bounds, or not a number.
        """
        # Validate that all arguments are provided and not empty strings
        for name, val in [("pH", ph_val), ("Solids", solids_val), 
                          ("Chloramines", chloramines_val), ("Sulfate", sulfate_val), 
                          ("Turbidity", turbidity_val)]:
            if val is None or (isinstance(val, str) and val.strip() == ""):
                raise ValueError(f"Water parameter '{name}' is required and cannot be empty.")
                
        try:
            ph = float(ph_val)
            solids = float(solids_val)
            chloramines = float(chloramines_val)
            sulfate = float(sulfate_val)
            turbidity = float(turbidity_val)
        except (ValueError, TypeError):
            raise ValueError("All parameters must be valid decimal numbers.")
            
        # Validate ranges
        if not (0.0 <= ph <= 14.0):
            raise ValueError("pH must be a value between 0.0 and 14.0.")
        if solids < 0:
            raise ValueError("Total Dissolved Solids (TDS) cannot be negative.")
        if chloramines < 0:
            raise ValueError("Chloramines content cannot be negative.")
        if sulfate < 0:
            raise ValueError("Sulfate concentration cannot be negative.")
        if turbidity < 0:
            raise ValueError("Turbidity cannot be negative.")
            
        return ph, solids, chloramines, sulfate, turbidity

    @staticmethod
    def calculate_safety_score(ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float) -> int:
        """
        Calculates mathematical client-side comparable safety score (0 - 100).
        Matches frontend logic.
        """
        penalty = 0.0
        
        # pH safe range: 6.5 - 8.5
        if ph < 6.5:
            penalty += (6.5 - ph) * 20
        elif ph > 8.5:
            penalty += (ph - 8.5) * 20

        # Solids (TDS) safe limit: 1000 ppm
        if solids > 1000:
            penalty += ((solids - 1000) / 1000) * 35

        # Chloramines safe limit: 4.0 ppm
        if chloramines > 4.0:
            penalty += ((chloramines - 4.0) / 4.0) * 35

        # Sulfate safe limit: 250 mg/L
        if sulfate > 250:
            penalty += ((sulfate - 250) / 250) * 35

        # Turbidity safe limit: 5.0 NTU
        if turbidity > 5.0:
            penalty += ((turbidity - 5.0) / 5.0) * 35

        return max(0, int(round(100 - penalty)))

    @staticmethod
    def check_who_violations(ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float) -> list:
        """Determines reasons for failures based on WHO guidelines."""
        reasons = []
        thresholds = Config.THRESHOLDS
        
        if ph < thresholds["ph"][0]:
            reasons.append(f"pH level is too low at {ph:.1f} (should be 6.5–8.5).")
        elif ph > thresholds["ph"][1]:
            reasons.append(f"pH level is too high at {ph:.1f} (should be 6.5–8.5).")
            
        if solids > thresholds["Solids"][1]:
            reasons.append(f"Solids are too high at {solids:.1f} ppm (should be below {int(thresholds['Solids'][1])} ppm).")
            
        if chloramines > thresholds["Chloramines"][1]:
            reasons.append(f"Chloramines are too high at {chloramines:.1f} ppm (should be below {thresholds['Chloramines'][1]} ppm).")
            
        if sulfate > thresholds["Sulfate"][1]:
            reasons.append(f"Sulfate is too high at {sulfate:.1f} mg/L (should be below {int(thresholds['Sulfate'][1])} mg/L).")
            
        if turbidity > thresholds["Turbidity"][1]:
            reasons.append(f"Turbidity is too high at {turbidity:.1f} NTU (should be below {thresholds['Turbidity'][1]} NTU).")
            
        return reasons

    @staticmethod
    def get_fallback_suggestions(ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float, is_potable: bool) -> list:
        """Rules-based fallback treatment guidelines matching baseline logic."""
        if is_potable:
            return ["All chemical parameters reside within standard safe guidelines. Maintain standard filtration monitoring."]
            
        suggestions = []
        thresholds = Config.THRESHOLDS
        
        if ph < thresholds["ph"][0]:
            suggestions.append(
                "Add calcium hydroxide (lime) or sodium carbonate (soda ash) using a pH adjustment feed system to neutralize acidity. "
                "Test regularly with a pH meter to calibrate and maintain levels within the 6.5–8.5 range."
            )
        elif ph > thresholds["ph"][1]:
            suggestions.append(
                "Inject food-grade phosphoric acid or introduce a carbon dioxide infusion system to lower alkalinity. "
                "Continuous monitoring with a glass-electrode pH sensor is recommended to maintain the target range of 6.5–8.5."
            )
            
        if solids > thresholds["Solids"][1]:
            suggestions.append(
                "Install a high-efficiency reverse osmosis (RO) system or a multi-stage deionization unit to reduce dissolved minerals. "
                "Replace filters according to manufacturer guidelines and monitor conductivity with a TDS pen."
            )
            
        if chloramines > thresholds["Chloramines"][1]:
            suggestions.append(
                "Deploy catalytic carbon filters or high-capacity granular activated carbon (GAC) filtration to adsorb chloramines. "
                "Routinely test water using DPD chlorine test kits to ensure proper contaminant removal."
            )
            
        if sulfate > thresholds["Sulfate"][1]:
            suggestions.append(
                "Implement reverse osmosis filtration or strong-base anion exchange (SBA) resins to lower sulfate concentrations. "
                "Regenerate ion-exchange resins periodically and monitor sulfate levels via colorimetric testing."
            )
            
        if turbidity > thresholds["Turbidity"][1]:
            suggestions.append(
                "Add a coagulant (such as aluminum sulfate/alum) to aggregate suspended solids, followed by a sediment backwash filter (sand or multimedia). "
                "Ensure clarification processes are working and verify turbidity with an optical turbidimeter."
            )
            
        return suggestions

    @staticmethod
    def resolve_location(headers: dict) -> str:
        """Heuristic location resolver using request headers."""
        # Check standard headers used by proxies/CDN (e.g. Cloudflare)
        cf_country = headers.get("CF-IPCountry")
        if cf_country:
            return f"Country Code: {cf_country}"
            
        x_forwarded = headers.get("X-Forwarded-For")
        if x_forwarded:
            ip = x_forwarded.split(',')[0].strip()
            return f"IP Address: {ip}"
            
        return "Unknown (Remote)"

    @classmethod
    def process_assessment(cls, db, ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float, headers: dict) -> dict:
        """
        Coordinates full assessment pipeline:
        Runs ML prediction, calculates safety index, checks WHO violations, fetches recommendations,
        generates SHAP explainability contributions, and saves assessment record in the database.
        """
        # 1. Prediction and Confidence
        prediction, confidence = predictor.predict(ph, solids, chloramines, sulfate, turbidity)
        is_potable = (prediction == "Potable")
        
        # 2. Safety score & WHO Violations
        safety_score = cls.calculate_safety_score(ph, solids, chloramines, sulfate, turbidity)
        violations = cls.check_who_violations(ph, solids, chloramines, sulfate, turbidity)
        
        # 3. Recommendations (Gemini with rules-based fallback)
        recs = GeminiService.get_recommendations(ph, solids, chloramines, sulfate, turbidity, is_potable)
        if not recs:
            recs = cls.get_fallback_suggestions(ph, solids, chloramines, sulfate, turbidity, is_potable)
            
        # 4. Resolve Location
        location = cls.resolve_location(headers)
        
        # 5. Save record to DB
        assessment = WaterAssessment(
            user_location=location,
            ph=ph,
            solids=solids,
            chloramines=chloramines,
            sulfate=sulfate,
            turbidity=turbidity,
            prediction=prediction,
            confidence_score=confidence,
            water_safety_score=safety_score
        )
        assessment.failed_who_parameters = violations
        assessment.recommendations = recs
        
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        
        # 6. Generate SHAP explanations dynamically and merge with response
        shap_explanation = predictor.explain(ph, solids, chloramines, sulfate, turbidity)
        
        res_dict = assessment.to_dict()
        res_dict["shap_explanation"] = shap_explanation
        
        return res_dict
