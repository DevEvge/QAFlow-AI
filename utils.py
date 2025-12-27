import os
import gspread
import docx
from dotenv import load_dotenv

load_dotenv()
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")


def get_sheet():
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open(SPREADSHEET_NAME)
    return sh.sheet1


def read_docx(file_path):
    doc = docx.Document(file_path)
    full_text = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            full_text.append(paragraph.text)
    return "\n".join(full_text)


def read_doc(file_path):
    try:
        import textract
        text = textract.process(file_path).decode('utf-8')
        return text
    except ImportError:
        raise ImportError("Для читання .doc файлів потрібна бібліотека textract. Встановіть: pip install textract")
    except Exception as e:
        raise Exception(f"Помилка читання .doc файлу: {e}")


def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return text
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1251') as f:
            text = f.read()
        return text
    except Exception as e:
        raise Exception(f"Помилка читання .txt файлу: {e}")


def add_cases_to_sheet(cases_list):
    worksheet = get_sheet()
    existing_rows = len(worksheet.col_values(1))
    start_row = existing_rows + 1

    rows_to_insert = [[case, "PENDING"] for case in cases_list]
    worksheet.append_rows(rows_to_insert)

    result_data = []
    for i, case_text in enumerate(cases_list):
        result_data.append({
            "row": start_row + i,
            "text": case_text
        })

    return result_data


def update_case_status(row_num, status):
    worksheet = get_sheet()
    cell_address = f"B{row_num}"

    worksheet.update_acell(cell_address, status)

    if status == "Pass":
        color = {"red": 0.85, "green": 0.93, "blue": 0.83}
    else:
        color = {"red": 0.96, "green": 0.8, "blue": 0.8}

    worksheet.format(cell_address, {
        "backgroundColor": color,
        "textFormat": {"bold": True}
    })

    
