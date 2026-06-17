import re
import requests
from app.config import Config

class GeminiService:
    """Service to communicate with Google's Gemini API for water recommendations."""
    
    @staticmethod
    def get_recommendations(ph: float, solids: float, chloramines: float, sulfate: float, turbidity: float, is_potable: bool) -> list:
        """
        Sends water quality metrics to Gemini to fetch highly descriptive treatment suggestions.
        
        Returns:
            list: List of parsed suggestion strings, or None if the API fails.
        """
        api_key = Config.GEMINI_API_KEY
        if not api_key:
            print("Gemini API Key is missing. Recommendations will fallback to rules-based heuristics.")
            return None
            
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
                    # Strip list prefixes like "1. ", "2) ", "- ", "* " safely using regex
                    clean_line = re.sub(r'^\s*(?:\d+[\b.)\]]|-|\*)\s*', '', line)
                    if clean_line:
                        items.append(clean_line)
                if items:
                    return items
        except Exception as e:
            print(f"Gemini recommendation query failed: {e}")
            
        return None
