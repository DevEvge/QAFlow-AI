import os
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

import ai_helper
import utils

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN: raise ValueError("Не знайдено BOT_TOKEN")

class TestSession(StatesGroup):
    main_menu = State()          # Головне меню
    choosing_action = State()    # Вибір: Завантажити чи Продовжити
    waiting_for_doc = State()    # Чекаємо файл
    selecting_module = State()   # Вибираємо модуль зі списку
    testing = State()            # Процес тестування
    waiting_for_bug_desc = State() # Опис бага

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- КЛАВІАТУРИ ---

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Почати тестування")]],
        resize_keyboard=True
    )

def get_action_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Завантажити новий файл", callback_data="action_upload")],
        [InlineKeyboardButton(text="▶️ Продовжити тестування", callback_data="action_continue")]
    ])

def get_modules_keyboard(modules_list):
    builder = []
    for mod in modules_list:
        builder.append([InlineKeyboardButton(text=f"📦 {mod}", callback_data=f"module_{mod}")])
    return InlineKeyboardMarkup(inline_keyboard=builder)

def get_test_keyboard(row_number):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Pass", callback_data=f"pass_{row_number}"),
            InlineKeyboardButton(text="❌ Failed", callback_data=f"fail_{row_number}")
        ]
    ])

# --- ГЛОБАЛЬНИЙ СКИДАННЯ (Крім введення бага) ---
@router.message(~StateFilter(TestSession.waiting_for_bug_desc), F.text != "🚀 Почати тестування")
async def global_reset(message: Message, state: FSMContext):
    # Цей хендлер ловить будь-який текст, якщо ми не пишемо баг-репорт і не тиснемо старт
    await state.clear()
    await message.answer(
        "🏠 **Головне меню**\nЯ скинув контекст. Тисни кнопку, щоб почати.",
        reply_markup=get_main_keyboard()
    )

# --- START ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Привіт! Я QAFlow Bot.", reply_markup=get_main_keyboard())

# --- ЛОГІКА "ПОЧАТИ ТЕСТУВАННЯ" ---
@router.message(F.text == "🚀 Почати тестування")
async def start_flow(message: Message, state: FSMContext):
    # 1. Скануємо таблицю
    pending_modules = utils.get_unique_pending_modules()
    
    if pending_modules:
        # Є незавершені модулі -> даємо вибір
        await message.answer(
            f"🔎 Знайдено незавершені модулі: {len(pending_modules)} шт.\nЩо робимо?",
            reply_markup=get_action_keyboard()
        )
        await state.set_state(TestSession.choosing_action)
    else:
        # Таблиця чиста -> зразу просимо файл
        await message.answer("✅ Активних тестів немає.\n📤 **Скинь файл** (.docx, .doc, .txt) для створення нового модуля.")
        await state.set_state(TestSession.waiting_for_doc)

# --- ОБРОБКА ВИБОРУ (Завантажити / Продовжити) ---
@router.callback_query(TestSession.choosing_action, F.data == "action_upload")
async def action_upload(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 **Скинь файл** (.docx, .doc, .txt). Назва файлу стане назвою модуля.")
    await state.set_state(TestSession.waiting_for_doc)

@router.callback_query(TestSession.choosing_action, F.data == "action_continue")
async def action_continue(callback: CallbackQuery, state: FSMContext):
    modules = utils.get_unique_pending_modules()
    await callback.message.edit_text("📂 **Обери модуль для тестування:**", reply_markup=get_modules_keyboard(modules))
    await state.set_state(TestSession.selecting_module)

# --- ЗАВАНТАЖЕННЯ ФАЙЛУ ---
@router.message(TestSession.waiting_for_doc, F.document)
async def handle_document(message: Message, state: FSMContext):
    # Визначаємо назву модуля з імені файлу (без розширення)
    file_name_with_ext = message.document.file_name
    module_name = os.path.splitext(file_name_with_ext)[0]
    
    wait_msg = await message.answer(f"⏳ Читаю файл для модуля: **{module_name}**...")
    
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = f"temp_{file_name_with_ext}"
    await bot.download_file(file.file_path, file_path)

    try:
        if file_path.endswith('.docx'): text = utils.read_docx(file_path)
        elif file_path.endswith('.doc'): text = utils.read_doc(file_path)
        else: text = utils.read_txt(file_path)

        await bot.edit_message_text("🤖 AI генерує кейси...", chat_id=message.chat.id, message_id=wait_msg.message_id)
        cases = ai_helper.generate_test_cases(text)
        
        if not cases:
            await message.answer("❌ AI не повернув кейсів.")
            return

        # Записуємо з назвою модуля
        utils.add_cases_to_sheet(cases, module_name)
        
        await message.answer(
            f"✅ Модуль **{module_name}** створено ({len(cases)} кейсів)!\n"
            "Перекидаю на вибір модуля...",
        )
        
        # Перекидаємо на вибір модуля
        modules = utils.get_unique_pending_modules()
        await message.answer("📂 **Обери модуль:**", reply_markup=get_modules_keyboard(modules))
        await state.set_state(TestSession.selecting_module)

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

# --- ВИБІР МОДУЛЯ ---
@router.callback_query(TestSession.selecting_module, F.data.startswith("module_"))
async def select_module(callback: CallbackQuery, state: FSMContext):
    module_name = callback.data.split("module_")[1]
    await state.update_data(current_module=module_name)
    
    await callback.message.edit_text(f"🚀 Запускаю модуль: **{module_name}**")
    await state.set_state(TestSession.testing)
    
    # Запускаємо перший кейс цього модуля
    await send_next_case(callback.message, module_name)

# --- ЛОГІКА ТЕСТУВАННЯ ---
async def send_next_case(message: Message, module_name):
    case_data = utils.get_next_pending_case_by_module(module_name)
    
    if case_data:
        text = (
            f"📦 **Module:** {module_name}\n"
            f"🛠 **Row #{case_data['row']}**\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🔸 {case_data['text']}"
        )
        await message.answer(text, reply_markup=get_test_keyboard(case_data['row']))
    else:
        # Кейси в модулі закінчились
        await message.answer(
            f"🎉 **Модуль '{module_name}' завершено!**\n"
            "Повертаю до головного меню.",
            reply_markup=get_main_keyboard()
        )
        # Скидаємо стан
        # Можна було б перекинути на вибір модулів, але за ТЗ - головне меню
        # await state.clear() (це вже станеться автоматично при переході в idle або натисканні кнопки)

# --- PASS ---
@router.callback_query(F.data.startswith("pass_"))
async def process_pass(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])
    utils.update_case_status(row_number, "Pass")
    
    # Редагуємо старе повідомлення
    try:
        text_lines = callback.message.text.split('\n')
        case_text = text_lines[-1] # Останній рядок - це текст кейсу
        await callback.message.edit_text(f"~~{case_text}~~\n\n✅ **Passed**", reply_markup=None)
    except:
        await callback.message.edit_reply_markup(reply_markup=None)

    # Отримуємо поточний модуль зі стану
    data = await state.get_data()
    module_name = data.get('current_module')
    
    if module_name:
        await send_next_case(callback.message, module_name)
    else:
        await callback.message.answer("⚠️ Втрачено контекст модуля. Почни спочатку.")

# --- FAILED ---
@router.callback_query(F.data.startswith("fail_"))
async def process_fail(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])
    
    # Витягуємо текст кейсу з повідомлення
    text_lines = callback.message.text.split('\n')
    # Шукаємо рядок з описом (він після роздільника)
    case_text = text_lines[-1].replace("🔸 ", "")

    await state.update_data(failed_row=row_number, failed_case_text=case_text, msg_id=callback.message.message_id)
    
    await callback.message.answer("✍️ **Опиши баг:**")
    await state.set_state(TestSession.waiting_for_bug_desc)
    await callback.answer()

# --- ОПИС БАГА ---
@router.message(TestSession.waiting_for_bug_desc)
async def process_bug_desc(message: Message, state: FSMContext):
    user_desc = message.text
    data = await state.get_data()
    
    wait_msg = await message.answer("🐛 AI пише репорт...")
    
    bug_report = ai_helper.generate_bug_report(data['failed_case_text'], user_desc)
    utils.update_case_status(data['failed_row'], "Failed", bug_report)
    
    await bot.edit_message_text(f"📝 **Bug Report:**\n{bug_report}", chat_id=message.chat.id, message_id=wait_msg.message_id)
    
    # Позначаємо старе повідомлення як Failed
    try:
        await bot.edit_message_text(f"~~{data['failed_case_text']}~~\n\n❌ **Failed**", chat_id=message.chat.id, message_id=data['msg_id'], reply_markup=None)
    except: pass
    
    # Повертаємось до тестування модуля
    module_name = data.get('current_module')
    await state.set_state(TestSession.testing) # Повертаємо стан
    
    if module_name:
        await send_next_case(message, module_name)

async def main():
    print("🚀 Бот (Module Flow) запущений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())