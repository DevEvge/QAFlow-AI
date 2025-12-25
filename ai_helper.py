import os
import json 
import google.generativeai  as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing gemini api key")


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def generate_test_case(requirements_text) :
    print("Send message to AI")
    
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
    try :
        response = model.generate_content(prompt)
        text_response = response.text.strip()

        clear_json = text_response.replace("```json", "").replace("```", "").strip()
        
        test_cases = json.loads(clear_json)

        return test_cases
    except Exception as e: 
        print(f"❌ Помилка AI: {e}")
        return []
    
if __name__ == "__main__":
    # Тестовий текст (імітація шматка з docx)
    sample_text = """
    Функціонал "Відновлення паролю".
    Користувач вводить email. Якщо email існує - відправляємо код.
    Якщо поле пусте - показати помилку "Введіть email".
    Якщо формат невірний (без @) - показати помилку "Невірний формат".
    """
    
    result = generate_test_case(sample_text)
    
    print("\n✅ Результат від Gemini:")
    for i, case in enumerate(result, 1):
        print(f"{i}. {case}")