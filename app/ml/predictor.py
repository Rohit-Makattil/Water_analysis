import os
import joblib
import pandas as pd
import numpy as np
import shap

# Path to the serialized model file
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(MODEL_DIR, "water_quality_model.pkl")

class WaterQualityPredictor:
    """Class to load XGBoost model and execute inference with preprocessing and SHAP explainability."""
    
    def __init__(self):
        self.model = None
        self.explainer = None
        self._load_model()
        
    def _load_model(self):
        try:
            if os.path.exists(MODEL_PATH):
                self.model = joblib.load(MODEL_PATH)
                print(f"ML Model loaded successfully from {MODEL_PATH}.")
                
                # Initialize SHAP TreeExplainer for fast tree-based explanations
                try:
                    self.explainer = shap.TreeExplainer(self.model)
                    print("SHAP TreeExplainer initialized successfully.")
                except Exception as e:
                    print(f"Failed to initialize SHAP explainer: {e}")
                    self.explainer = None
            else:
                print(f"ML Model file not found at: {MODEL_PATH}")
        except Exception as e:
            print(f"Error loading ML model from {MODEL_PATH}: {e}")
            self.model = None
            self.explainer = None
            
    def predict(self, ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float) -> tuple:
        """
        Preprocesses raw inputs, executes predictions, and calculates confidence score.
        
        Args:
            ph (float): Acidity level (0 - 14)
            solids (float): Total dissolved solids (ppm)
            chloramines (float): Chloramines content (ppm)
            sulfate (float): Sulfate concentration (mg/L)
            turbidity (float): Turbidity (NTU)
            
        Returns:
            tuple: (prediction_label: str ["Potable" or "Not Potable"], confidence_score: float)
        """
        if self.model is None:
            self._load_model()
            if self.model is None:
                # Safe fallback if model files are corrupted or missing
                print("Predictor model unavailable. Returning default baseline prediction.")
                return "Not Potable", 0.5
                
        # 1. Feature Engineering (match training preprocessing logic)
        ph_capped = min(max(ph, 5.0), 9.0)
        ph_normalized = (ph_capped - 5.0) / (9.0 - 5.0) * 0.1
        sulfate_capped = min(max(sulfate, 100.0), 300.0)
        
        # 2. Build pandas DataFrame matching training features
        feature_names = ["ph_normalized", "Solids", "Chloramines", "Sulfate", "Turbidity"]
        input_data = pd.DataFrame(
            [[ph_normalized, solids, chloramines, sulfate_capped, turbidity]],
            columns=feature_names
        )
        
        # 3. Predict class (1 = Potable, 0 = Not Potable)
        prediction_val = self.model.predict(input_data)[0]
        prediction_label = "Potable" if prediction_val == 1 else "Not Potable"
        
        # 4. Compute prediction confidence score using class probabilities
        try:
            probabilities = self.model.predict_proba(input_data)[0]
            confidence_score = float(probabilities[prediction_val])
        except Exception as e:
            print(f"Failed to fetch model prediction probability: {e}")
            confidence_score = 1.0
            
        return prediction_label, confidence_score

    def explain(self, ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float) -> dict:
        """
        Computes SHAP explanations for a single water assessment prediction.
        
        Returns:
            dict: SHAP explanations containing:
                - base_value (float): Base probability or log-odds of potability.
                - contributions (dict): Map of feature names to shap value changes.
                - top_factors (list): Ordered list of factors affecting prediction.
        """
        if self.model is None:
            self._load_model()
            
        if self.explainer is None:
            print("SHAP explainer is unavailable. Returning empty explanations.")
            return {
                "base_value": 0.5,
                "contributions": {
                    "pH Level": 0.0,
                    "Total Dissolved Solids (TDS)": 0.0,
                    "Chloramines": 0.0,
                    "Sulfate": 0.0,
                    "Turbidity": 0.0
                },
                "top_factors": []
            }
            
        # 1. Feature Engineering (match training preprocessing logic)
        ph_capped = min(max(ph, 5.0), 9.0)
        ph_normalized = (ph_capped - 5.0) / (9.0 - 5.0) * 0.1
        sulfate_capped = min(max(sulfate, 100.0), 300.0)
        
        feature_names = ["ph_normalized", "Solids", "Chloramines", "Sulfate", "Turbidity"]
        input_data = pd.DataFrame(
            [[ph_normalized, solids, chloramines, sulfate_capped, turbidity]],
            columns=feature_names
        )
        
        try:
            # Get shap values (raw log-odds output margins for trees)
            shap_values = self.explainer.shap_values(input_data)
            
            # Extract row values safely depending on shape (different versions of SHAP output differently)
            if isinstance(shap_values, list):
                row_vals = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
            elif hasattr(shap_values, "shape"):
                if len(shap_values.shape) == 3:  # (classes, samples, features)
                    row_vals = shap_values[1][0] if shap_values.shape[0] > 1 else shap_values[0][0]
                elif len(shap_values.shape) == 2:  # (samples, features)
                    row_vals = shap_values[0]
                else:
                    row_vals = shap_values
            else:
                row_vals = shap_values
                
            # Parse base value safely
            expected_val = self.explainer.expected_value
            if isinstance(expected_val, (list, np.ndarray)):
                base_value = float(expected_val[1]) if len(expected_val) > 1 else float(expected_val[0])
            else:
                base_value = float(expected_val)
                
            # Map parameters to user-friendly UI display labels
            friendly_names = {
                "ph_normalized": "pH Level",
                "Solids": "Total Dissolved Solids (TDS)",
                "Chloramines": "Chloramines",
                "Sulfate": "Sulfate",
                "Turbidity": "Turbidity"
            }
            
            contributions = {}
            for name, val in zip(feature_names, row_vals):
                contributions[friendly_names[name]] = float(val)
                
            # Sort factors by absolute impact size to identify top influences
            sorted_factors = sorted(
                contributions.items(),
                key=lambda item: abs(item[1]),
                reverse=True
            )
            
            top_factors = [{"feature": feature, "impact": float(impact)} for feature, impact in sorted_factors]
            
            return {
                "base_value": base_value,
                "contributions": contributions,
                "top_factors": top_factors
            }
        except Exception as e:
            print(f"SHAP explanation calculation failed: {e}")
            return {
                "base_value": 0.5,
                "contributions": {
                    "pH Level": 0.0,
                    "Total Dissolved Solids (TDS)": 0.0,
                    "Chloramines": 0.0,
                    "Sulfate": 0.0,
                    "Turbidity": 0.0
                },
                "top_factors": []
            }

# Singleton predictor instance for use across the application
predictor = WaterQualityPredictor()
