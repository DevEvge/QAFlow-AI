import os
import gspread
import docx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import textract

load_dotenv()
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")

def get_sheet():
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(SPREADSHEET_NAME)
        return sh.sheet1
    except Exception as e:
        raise Exception(f"Помилка доступу до Гугл Таблиці: {e}")

def read_docx(file_path):
    doc = docx.Document(file_path)
    full_text = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            full_text.append(paragraph.text)
    return "\n".join(full_text)

def read_doc(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if "<html" in content or "MIME-Version" in content:
            soup = BeautifulSoup(content, 'html.parser')
            for script in soup(["script", "style", "meta", "link", "xml"]):
                script.decompose()
            text = soup.get_text(separator='\n')
            return "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        
        text = textract.process(file_path).decode('utf-8')
        return text
    except Exception as e:
        if "antiword" in str(e): return "Помилка: Старий .doc формат. Збережіть як .docx"
        raise e

def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()
    except:
        with open(file_path, 'r', encoding='cp1251') as f: return f.read()

def add_cases_to_sheet(cases_list, module_name):
    """
    Додає кейси з прив'язкою до Модуля (Колонка A).
    Структура: [Module, Case, Status, BugReport]
    """
    worksheet = get_sheet()
    # Колонка A - Module, B - Case, C - Status, D - Bug Report
    rows = [[module_name, case, "PENDING", ""] for case in cases_list]
    worksheet.append_rows(rows)

def get_unique_pending_modules():
    """
    Повертає список унікальних назв модулів, де є статус PENDING.
    """
    worksheet = get_sheet()
    all_values = worksheet.get_all_values()
    
    # Пропускаємо заголовок, якщо він є (можна додати логіку перевірки)
    # Припускаємо, що A=Module, C=Status. В python list це індекси 0 і 2.
    pending_modules = set()
    
    for row in all_values:
        if len(row) >= 3:
            # Перевіряємо статус (3-тя колонка, індекс 2)
            if row[2].strip().upper() == "PENDING":
                module_name = row[0].strip() # 1-ша колонка
                if module_name:
                    pending_modules.add(module_name)
                    
    return list(pending_modules)

def get_next_pending_case_by_module(target_module):
    """
    Шукає перший PENDING кейс для конкретного модуля.
    """
    worksheet = get_sheet()
    all_values = worksheet.get_all_values()
    
    for i, row in enumerate(all_values):
        if len(row) >= 3:
            module = row[0].strip()
            status = row[2].strip().upper()
            
            if module == target_module and status == "PENDING":
                # i + 1 тому що в gspread нумерація з 1
                return {
                    "row": i + 1,
                    "text": row[1] # Колонка B - текст кейсу
                }
    return None

def update_case_status(row_num, status, bug_report=None):
    """
    Оновлює статус (Колонка C) і баг-репорт (Колонка D).
    """
    worksheet = get_sheet()
    
    # Колонка C - це статус
    worksheet.update_acell(f"C{row_num}", status)
    
    # Колонка D - це баг-репорт
    if bug_report:
        worksheet.update_acell(f"D{row_num}", bug_report)
    
    # Фарбуємо клітинку статусу
    if status == "Pass":
        color = {"red": 0.85, "green": 0.93, "blue": 0.83}
    else:
        color = {"red": 0.96, "green": 0.8, "blue": 0.8}
        
    worksheet.format(f"C{row_num}", {
        "backgroundColor": color,
        "textFormat": {"bold": True}
    })