from flask import Flask, request, render_template, jsonify
import joblib
import pandas as pd
import numpy as np
import requests
import os

# Load .env file manually if it exists
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

app = Flask(__name__)

# Load the trained model
try:
    print("Loading model...")
    model = joblib.load("water_quality_model.pkl")
    print("Model loaded successfully.")
except Exception as e:
    print(f"Model load failed: {e}")
    model = None

# Define feature names
feature_names = ["ph_normalized", "Solids", "Chloramines", "Sulfate", "Turbidity"]

# Store submissions
submissions = []

# Safe thresholds for water quality (matching WHO/EPA drinking water standards)
THRESHOLDS = {
    "ph": (6.5, 8.5),
    "Solids": (0, 1000),
    "Chloramines": (0, 4),
    "Sulfate": (0, 250),
    "Turbidity": (0, 5)
}

def generate_suggestion(issue, parameter, value, threshold):
    suggestions_map = {
        "ph_low": (
            f"Add calcium hydroxide (lime) or sodium carbonate (soda ash) using a pH adjustment feed system to neutralize acidity. "
            f"Test regularly with a pH meter to calibrate and maintain levels within the 6.5–8.5 range."
        ),
        "ph_high": (
            f"Inject food-grade phosphoric acid or introduce a carbon dioxide infusion system to lower alkalinity. "
            f"Continuous monitoring with a glass-electrode pH sensor is recommended to maintain the target range of 6.5–8.5."
        ),
        "Solids_high": (
            f"Install a high-efficiency reverse osmosis (RO) system or a multi-stage deionization unit to reduce dissolved minerals. "
            f"Replace filters according to manufacturer guidelines and monitor conductivity with a TDS pen."
        ),
        "Chloramines_high": (
            f"Deploy catalytic carbon filters or high-capacity granular activated carbon (GAC) filtration to adsorb chloramines. "
            f"Routinely test water using DPD chlorine test kits to ensure proper contaminant removal."
        ),
        "Sulfate_high": (
            f"Implement reverse osmosis filtration or strong-base anion exchange (SBA) resins to lower sulfate concentrations. "
            f"Regenerate ion-exchange resins periodically and monitor sulfate levels via colorimetric testing."
        ),
        "Turbidity_high": (
            f"Add a coagulant (such as aluminum sulfate/alum) to aggregate suspended solids, followed by a sediment backwash filter (sand or multimedia). "
            f"Ensure clarification processes are working and verify turbidity with an optical turbidimeter."
        )
    }
    
    # Normalize parameter names to match map keys
    param_key = parameter
    if parameter.lower() == "ph":
        param_key = "ph"
    elif parameter.lower() == "solids":
        param_key = "Solids"
    elif parameter.lower() == "chloramines":
        param_key = "Chloramines"
    elif parameter.lower() == "sulfate":
        param_key = "Sulfate"
    elif parameter.lower() == "turbidity":
        param_key = "Turbidity"

    if "too low" in issue.lower() or "low" in issue.lower():
        key = f"{param_key}_low"
    else:
        key = f"{param_key}_high"
        
    return suggestions_map.get(key, f"Treat water using certified filtration methods to adjust {parameter} to standard safe levels.")


def get_gemini_recs(ph, solids, chloramines, sulfate, turbidity, is_potable):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    status_str = "POTABLE (Safe to drink)" if is_potable else "NOT POTABLE (Potential health risk)"
    prompt = (
        f"You are a Senior Water Treatment & Chemical Safety Engineer. A water sample has been assessed with the following parameters:\n"
        f"- Overall Potability: {status_str}\n"
        f"- pH Level: {ph} (safe range: 6.5–8.5)\n"
        f"- Dissolved Solids (TDS): {solids} ppm (safe limit: 1,000 ppm)\n"
        f"- Chloramines: {chloramines} ppm (safe limit: 4.0 ppm)\n"
        f"- Sulfate: {sulfate} mg/L (safe limit: 250 mg/L)\n"
        f"- Turbidity: {turbidity} NTU (safe limit: 5.0 NTU)\n\n"
        f"Provide 3-4 professional, highly actionable and scientific treatment or maintenance recommendations to optimize this water. "
        f"Output ONLY a clean, numbered list where each recommendation is a single paragraph. Do not include markdown bold formatting or headers or introductory remarks. Each item must start with the number (e.g. '1. ...')."
    )
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=6)
        if response.status_code == 200:
            res_data = response.json()
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            items = []
            for line in raw_text.split('\n'):
                line = line.strip()
                # Remove common list prefixes and clean up
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                    clean_line = line.lstrip('0123456789.-* \t')
                    if clean_line:
                        items.append(clean_line)
            if items:
                return items
    except Exception as e:
        print(f"Gemini API call failed: {e}")
    
    return None


@app.route("/", methods=["GET", "POST"])
def predict():
    prediction = None
    reasons = []
    suggestions = []
    form_data = {"ph": "", "solids": "", "chloramines": "", "sulfate": "", "turbidity": ""}

    if request.method == "POST":
        print("POST request received...")
        try:
            # Get input values
            ph = float(request.form["ph"])
            solids = float(request.form["solids"])
            chloramines = float(request.form["chloramines"])
            sulfate = float(request.form["sulfate"])
            turbidity = float(request.form["turbidity"])
            print(f"Input values: ph={ph}, solids={solids}, chloramines={chloramines}, sulfate={sulfate}, turbidity={turbidity}")

            # Store form data to pre-fill
            form_data = {
                "ph": ph,
                "solids": solids,
                "chloramines": chloramines,
                "sulfate": sulfate,
                "turbidity": turbidity
            }

            # Cap and normalize pH, clip Sulfate
            ph_capped = min(max(ph, 5), 9)
            ph_normalized = (ph_capped - 5) / (9 - 5) * 0.1
            sulfate_capped = min(max(sulfate, 100), 300)
            print(f"Normalized: ph_normalized={ph_normalized}, sulfate_capped={sulfate_capped}")

            # Prepare input data
            input_data = pd.DataFrame([[ph_normalized, solids, chloramines, sulfate_capped, turbidity]],
                                      columns=feature_names)
            print("Input data prepared.")

            # Predict
            if model is not None:
                print("Making prediction...")
                prediction = model.predict(input_data)[0]
                result = "Potable" if prediction == 1 else "Not Potable"
                print(f"Prediction: {result}")
            else:
                print("No model loaded, defaulting to 'Not Potable'.")
                result = "Not Potable"

            # Store submission
            submissions.append({
                "ph": ph_capped,
                "Solids": solids,
                "Chloramines": chloramines,
                "Sulfate": sulfate_capped,
                "Turbidity": turbidity,
                "Potability": result
            })
            print("Submission stored.")

            # Reasons for non-potable
            if result == "Not Potable":
                if ph < THRESHOLDS["ph"][0]:
                    reasons.append(f"pH is too low at {ph:.1f} (should be 6.5–8.5).")
                elif ph > THRESHOLDS["ph"][1]:
                    reasons.append(f"pH is too high at {ph:.1f} (should be 6.5–8.5).")
                if solids > THRESHOLDS["Solids"][1]:
                    reasons.append(f"Solids are too high at {solids:.1f} ppm (should be below {THRESHOLDS['Solids'][1]} ppm).")
                if chloramines > THRESHOLDS["Chloramines"][1]:
                    reasons.append(f"Chloramines are too high at {chloramines:.1f} ppm (should be below 4 ppm).")
                if sulfate > THRESHOLDS["Sulfate"][1]:
                    reasons.append(f"Sulfate is too high at {sulfate:.1f} mg/L (should be below 250 mg/L).")
                if turbidity > THRESHOLDS["Turbidity"][1]:
                    reasons.append(f"Turbidity is too high at {turbidity:.1f} NTU (should be below 5 NTU).")

            # Try to get suggestions from Gemini API first
            is_pot = (result == "Potable")
            gemini_recs = get_gemini_recs(ph, solids, chloramines, sulfate, turbidity, is_pot)
            if gemini_recs:
                suggestions = gemini_recs
                print("Generated recommendations successfully using Gemini API.")
            else:
                # Fallback to rules-based recommendations
                if result == "Not Potable":
                    if ph < THRESHOLDS["ph"][0]:
                        suggestions.append(generate_suggestion(f"pH is too low at {ph:.1f}", "pH", ph, "6.5–8.5"))
                    elif ph > THRESHOLDS["ph"][1]:
                        suggestions.append(generate_suggestion(f"pH is too high at {ph:.1f}", "pH", ph, "6.5–8.5"))
                    if solids > THRESHOLDS["Solids"][1]:
                        suggestions.append(generate_suggestion(f"Solids are too high at {solids:.1f} ppm", "Solids", solids, str(THRESHOLDS['Solids'][1])))
                    if chloramines > THRESHOLDS["Chloramines"][1]:
                        suggestions.append(generate_suggestion(f"Chloramines are too high at {chloramines:.1f} ppm", "Chloramines", chloramines, "4"))
                    if sulfate > THRESHOLDS["Sulfate"][1]:
                        suggestions.append(generate_suggestion(f"Sulfate is too high at {sulfate:.1f} mg/L", "Sulfate", sulfate, "250"))
                    if turbidity > THRESHOLDS["Turbidity"][1]:
                        suggestions.append(generate_suggestion(f"Turbidity is too high at {turbidity:.1f} NTU", "Turbidity", turbidity, "5"))
                else:
                    suggestions.append("All chemical parameters reside within standard safe guidelines. Maintain standard filtration monitoring.")
            
            print(f"Reasons: {reasons}, Suggestions: {suggestions}")

            accept_header = request.headers.get('Accept', '')
            if 'application/json' in accept_header:
                return jsonify({
                    "status": "success",
                    "prediction": result,
                    "reasons": reasons,
                    "suggestions": suggestions
                })

            return render_template(
                "index.html",
                prediction=result,
                reasons=reasons,
                suggestions=suggestions,
                form_data=form_data
            )

        except ValueError as ve:
            print(f"ValueError: {ve}")
            accept_header = request.headers.get('Accept', '')
            if 'application/json' in accept_header:
                return jsonify({
                    "status": "error",
                    "reasons": ["Invalid input. Please enter valid numbers."],
                    "suggestions": []
                }), 400
            return render_template(
                "index.html",
                prediction=None,
                reasons=["Invalid input. Please enter valid numbers."],
                suggestions=[],
                form_data=form_data
            )
        except Exception as e:
            print(f"Unexpected error: {e}")
            accept_header = request.headers.get('Accept', '')
            if 'application/json' in accept_header:
                return jsonify({
                    "status": "error",
                    "reasons": [f"An error occurred: {e}"],
                    "suggestions": []
                }), 500
            return render_template(
                "index.html",
                prediction=None,
                reasons=[f"An error occurred: {e}"],
                suggestions=[],
                form_data=form_data
            )

    return render_template("index.html", prediction=None, reasons=[], suggestions=[], form_data=form_data)

if __name__ == "__main__":
    app.run(debug=True)