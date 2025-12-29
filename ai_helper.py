import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing gemini api key")

client = genai.Client(api_key=GEMINI_API_KEY)

# Використовуємо стабільну та швидку модель
MODEL_ID = 'gemini-2.0-flash'


def generate_test_cases(requirements_text):
    # Промпт рівня Senior QA: фокус на покритті та чіткості
    prompt = f"""
    Act as a Lead QA Engineer. 
    Analyze the provided requirements text to create a comprehensive Test Checklist.

    TASKS:
    1. Identify the main functional module described in the text. Generate a concise, professional Module Name (2-5 words, e.g., "Auth & Security", "Payment Gateway").
    2. Extract test cases covering:
       - Positive scenarios (Happy Path).
       - Critical negative scenarios (Edge cases, Validation).

    Requirements Text:
    {requirements_text}

    OUTPUT RULES:
    1. Return ONLY raw JSON. No markdown formatting (no ```json tags).
    2. JSON Structure:
    {{
        "module_name": "Module Name Here",
        "cases": [
            "Verify that user can login with valid credentials",
            "Verify validation error for invalid email format",
            ...
        ]
    }}
    3. Language of Test Cases: Ukrainian (use standard QA terminology in English where appropriate, e.g., 'Submit', 'Placeholder').
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        data = json.loads(response.text)

        module_name = data.get("module_name", "General Requirements")
        cases = data.get("cases", [])

        # Обробка випадку, якщо AI повернув просто список
        if not cases and isinstance(data, list):
            return "General Requirements", data

        return module_name, cases

    except Exception as e:
        print(f"❌ AI Error (Cases): {e}")
        return None, []


def generate_bug_report(case_text, user_description):
    # Промпт для ідеального баг-репорту
    prompt = f"""
    Act as a Senior QA Engineer.
    Based on the failed Test Case and the Tester's Observation, write a professional Bug Report in English.

    INPUT:
    - Test Case: "{case_text}"
    - Observation: "{user_description}"

    OUTPUT FORMAT (Strictly follow this structure):
    **Title:** [Concise, meaningful summary of the defect]
    **Description:** [Brief context]
    **Expected Result:** [What should happen according to requirements]
    **Actual Result:** [What actually happened based on observation]

    Return ONLY the text of the report. No intro/outro.
    """

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ AI Error (Bug Report): {e}")
        return f"Error generating report. Details: {user_description}"