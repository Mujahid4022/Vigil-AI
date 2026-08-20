"""
text_processor.py - Urdu text shaping and Gemini AI integration (OLD SDK).
"""

import arabic_reshaper
from bidi.algorithm import get_display
import google.generativeai as genai
from config.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

def reshape_urdu_text(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped)
    return bidi_text

def generate_urdu_poetry(prompt: str = None) -> str:
    if not prompt:
        prompt = "Write a short, original Urdu poem of 4-6 lines about love, nature, or hope. Only return the poem text, no explanations."
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return None