import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing gemini api key")

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_test_cases(requirements_text):
    print(f"🤖 Відправляю в AI текст довжиною {len(requirements_text)} символів...")

    prompt = f"""
    Act as a Senior QA Engineer. 
    Analyze the following requirements text and extract checklist-style test cases.

    Requirements:
    {requirements_text}

    OUTPUT FORMAT RULES:
    1. Return ONLY a raw JSON list of strings. No markdown, no "json" tags, no extra text.
    2. Example format: ["Verify that login button is disabled when fields are empty", "Verify error message on invalid email"]
    3. Language of test cases: Ukrainian (keep technical terms in English if needed).
    """
    try:
        # Використовуємо стабільну модель 1.5-flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )

        text_response = response.text.strip()
        # Чистимо відповідь від markdown
        clear_json = text_response.replace("```json", "").replace("```", "").strip()

        test_cases = json.loads(clear_json)
        print(f"✅ AI повернув {len(test_cases)} кейсів.")
        return test_cases

    except Exception as e:
        print(f"❌ Помилка AI: {e}")
        # Якщо помилка, спробуємо вивести, що саме повернув AI (якщо повернув)
        try:
            print(f"Сира відповідь: {response.text}")
        except:
            pass
        return []