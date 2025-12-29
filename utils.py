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
        raise Exception(f"Помилка авторизації Google Sheets: {e}")


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
        if "antiword" in str(e):
            return "Помилка формату: Старий .doc файл. Будь ласка, збережіть його як .docx і спробуйте знову."
        raise e


def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        with open(file_path, 'r', encoding='cp1251') as f:
            return f.read()


def add_cases_to_sheet(cases_list, module_name):
    worksheet = get_sheet()
    rows = [[module_name, case, "PENDING", ""] for case in cases_list]
    worksheet.append_rows(rows)


def get_unique_pending_modules():
    """
    Повертає словник: { "Назва Модуля": номер_рядка_першого_кейсу }
    """
    worksheet = get_sheet()
    all_values = worksheet.get_all_values()

    pending_modules = {}

    for i, row in enumerate(all_values):
        if len(row) >= 3:
            status = row[2].strip().upper()
            if status == "PENDING":
                module_name = row[0].strip()
                if module_name and module_name not in pending_modules:
                    pending_modules[module_name] = i + 1

    return pending_modules


def get_module_name_by_row(row_num):
    worksheet = get_sheet()
    try:
        return worksheet.acell(f"A{row_num}").value
    except:
        return None


def get_next_pending_case_by_module(target_module):
    worksheet = get_sheet()
    all_values = worksheet.get_all_values()

    for i, row in enumerate(all_values):
        if len(row) >= 3:
            module = row[0].strip()
            status = row[2].strip().upper()

            if module == target_module and status == "PENDING":
                return {
                    "row": i + 1,
                    "text": row[1]
                }
    return None


def update_case_status(row_num, status, bug_report=None):
    worksheet = get_sheet()
    worksheet.update_acell(f"C{row_num}", status)

    if bug_report:
        worksheet.update_acell(f"D{row_num}", bug_report)

    if status == "Pass":
        color = {"red": 0.85, "green": 0.93, "blue": 0.83}
    else:
        color = {"red": 0.96, "green": 0.8, "blue": 0.8}

    worksheet.format(f"C{row_num}", {
        "backgroundColor": color,
        "textFormat": {"bold": True}
    })