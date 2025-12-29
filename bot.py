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
    main_menu = State()
    choosing_action = State()
    waiting_for_doc = State()
    selecting_module = State()
    testing = State()
    waiting_for_bug_desc = State()


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


def get_back_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True
    )


def get_action_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Завантажити файл", callback_data="action_upload")],
        [InlineKeyboardButton(text="▶️ Продовжити тестування", callback_data="action_continue")]
    ])


def get_modules_keyboard(modules_list):
    builder = []
    # Спочатку список модулів
    for mod in modules_list:
        builder.append([InlineKeyboardButton(text=f"📦 {mod}", callback_data=f"module_{mod}")])

    # Додаємо кнопку завантаження ще одного файлу в кінець
    builder.append([InlineKeyboardButton(text="➕ Завантажити ще файл", callback_data="action_upload")])

    return InlineKeyboardMarkup(inline_keyboard=builder)


def get_test_keyboard(row_number):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Pass", callback_data=f"pass_{row_number}"),
            InlineKeyboardButton(text="❌ Failed", callback_data=f"fail_{row_number}")
        ]
    ])


# --- START ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Привіт! Я QAFlow Bot.", reply_markup=get_main_keyboard())


# --- КНОПКА "НАЗАД" ---
@router.message(F.text == "🔙 Назад")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Ти в головному меню.", reply_markup=get_main_keyboard())


# --- ЛОГІКА "ПОЧАТИ ТЕСТУВАННЯ" ---
@router.message(F.text == "🚀 Почати тестування")
async def start_flow(message: Message, state: FSMContext):
    # 1. Відправляємо статус з кнопкою Назад (щоб вона з'явилась у юзера)
    status_msg = await message.answer("⏳ Перевіряю таблицю...", reply_markup=get_back_keyboard())

    # Імітація роботи (можна прибрати, якщо хочеш миттєво)
    # await asyncio.sleep(0.5)

    pending_modules = utils.get_unique_pending_modules()

    # 2. ВИДАЛЯЄМО статус. Це критично для уникнення помилки "message can't be edited",
    # тому що ми переходимо з Reply клавіатури на Inline.
    await status_msg.delete()

    if pending_modules:
        # Відправляємо НОВЕ повідомлення з вибором дій
        await message.answer(
            f"🔎 Знайдено незавершені модулі: {len(pending_modules)} шт.\nЩо робимо?",
            reply_markup=get_action_keyboard()
        )
        await state.set_state(TestSession.choosing_action)
    else:
        # Відправляємо НОВЕ повідомлення з проханням файлу
        await message.answer(
            "✅ Активних тестів немає.\n📤 **Скинь файл** (.docx, .doc, .txt) для створення нового модуля.",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(TestSession.waiting_for_doc)


# --- ОБРОБКА ВИБОРУ ---
@router.callback_query(TestSession.choosing_action, F.data == "action_upload")
async def action_upload(callback: CallbackQuery, state: FSMContext):
    # Тут ми вже можемо редагувати, бо повідомлення має Inline кнопки (або не має Reply конфлікту)
    await callback.message.edit_text("📤 **Скинь файл** з вимогами.")
    await state.set_state(TestSession.waiting_for_doc)


@router.callback_query(TestSession.choosing_action, F.data == "action_continue")
async def action_continue(callback: CallbackQuery, state: FSMContext):
    modules = utils.get_unique_pending_modules()
    await callback.message.edit_text("📂 **Обери модуль:**", reply_markup=get_modules_keyboard(modules))
    await state.set_state(TestSession.selecting_module)


# --- ЗАВАНТАЖЕННЯ ФАЙЛУ (SMART FLOW - NO FLICKER) ---
@router.message(TestSession.waiting_for_doc, F.document)
async def handle_document(message: Message, state: FSMContext):
    # 1. Повідомлення про старт.
    # ВАЖЛИВО: reply_markup=None. Кнопка "Назад" і так є у юзера з попереднього кроку.
    # Відсутність ReplyMarkup дозволяє нам вільно редагувати це повідомлення далі без помилок.
    status_msg = await message.answer("⏳ **Отримую файл...**")

    file_id = message.document.file_id
    file_name = message.document.file_name
    file = await bot.get_file(file_id)
    file_path = f"temp_{file_name}"
    await bot.download_file(file.file_path, file_path)

    try:
        # 2. Оновлюємо статус: Читання (Smooth edit)
        await status_msg.edit_text("📖 **Читаю зміст...**")

        if file_path.endswith('.docx'):
            text = utils.read_docx(file_path)
        elif file_path.endswith('.doc'):
            text = utils.read_doc(file_path)
        else:
            text = utils.read_txt(file_path)

        # 3. Оновлюємо статус: AI аналіз (Smooth edit)
        await status_msg.edit_text("🧠 **AI аналізує вимоги та генерує назву модуля...**")

        module_name, cases = ai_helper.generate_test_cases(text)

        if not cases:
            await status_msg.edit_text("❌ AI не зміг виділити кейси. Спробуй інший файл.")
            return

        # 4. Оновлюємо статус: Запис (Smooth edit)
        await status_msg.edit_text(f"📝 **Записую в таблицю:**\n📦 Модуль: {module_name}\n🔢 Кейсів: {len(cases)}")

        utils.add_cases_to_sheet(cases, module_name)

        # 5. Фінал - показуємо меню вибору модулів
        # Тут ми додаємо Inline клавіатуру. Оскільки status_msg був "чистим", це дозволено!
        modules = utils.get_unique_pending_modules()

        await status_msg.edit_text(
            f"✅ **Готово!** Модуль '{module_name}' додано.\nОбери, що тестувати:",
            reply_markup=get_modules_keyboard(modules)
        )
        await state.set_state(TestSession.selecting_module)

    except Exception as e:
        await status_msg.edit_text(f"❌ Помилка: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)


# --- ОБРОБКА ДУРНИЦЬ ЗАМІСТЬ ФАЙЛУ ---
@router.message(TestSession.waiting_for_doc, F.text)
async def handle_text_instead(message: Message):
    if message.text == "🔙 Назад":
        await go_back(message, state)
        return
    await message.answer("⚠️ Я чекаю файл, а не текст.\nНатисни '🔙 Назад' для виходу.")


# --- ВІДПОВІДЬ НА КНОПКУ 'ЗАВАНТАЖИТИ ЩЕ' У СПИСКУ МОДУЛІВ ---
@router.callback_query(TestSession.selecting_module, F.data == "action_upload")
async def upload_more(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 **Скинь наступний файл.**")
    await state.set_state(TestSession.waiting_for_doc)


# --- ВИБІР МОДУЛЯ ---
@router.callback_query(TestSession.selecting_module, F.data.startswith("module_"))
async def select_module(callback: CallbackQuery, state: FSMContext):
    module_name = callback.data.split("module_")[1]
    await state.update_data(current_module=module_name)

    await callback.message.edit_text(f"🚀 Запускаю модуль: **{module_name}**")
    await state.set_state(TestSession.testing)
    await send_next_case(callback.message, module_name)


# --- ТЕСТУВАННЯ ---
async def send_next_case(message: Message, module_name):
    case_data = utils.get_next_pending_case_by_module(module_name)

    if case_data:
        text = (
            f"📦 **{module_name}**\n"
            f"🛠 **Case #{case_data['row']}**\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🔸 {case_data['text']}"
        )
        await message.answer(text, reply_markup=get_test_keyboard(case_data['row']))
    else:
        await message.answer(
            f"🎉 **Модуль '{module_name}' завершено!**",
            reply_markup=get_main_keyboard()
        )
        await state.clear()


# --- PASS ---
@router.callback_query(F.data.startswith("pass_"))
async def process_pass(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])

    try:
        text_lines = callback.message.text.split('\n')
        case_text = text_lines[-1]

        utils.update_case_status(row_number, "Pass")

        await callback.message.edit_text(f"~~{case_text}~~\n\n✅ **Passed**", reply_markup=None)
    except:
        await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    module_name = data.get('current_module')

    if module_name:
        await send_next_case(callback.message, module_name)


# --- FAILED ---
@router.callback_query(F.data.startswith("fail_"))
async def process_fail(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])

    text_lines = callback.message.text.split('\n')
    case_text = text_lines[-1].replace("🔸 ", "")

    await state.update_data(failed_row=row_number, failed_case_text=case_text, msg_id=callback.message.message_id)

    # Ховаємо клаву на час вводу
    await callback.message.answer("✍️ **Опиши баг:**",
                                  reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True))
    await state.set_state(TestSession.waiting_for_bug_desc)
    await callback.answer()


# --- ОПИС БАГА ---
@router.message(TestSession.waiting_for_bug_desc)
async def process_bug_desc(message: Message, state: FSMContext):
    user_desc = message.text
    data = await state.get_data()

    status_msg = await message.answer("⏳ **AI формує Bug Report (EN)...**")

    bug_report = ai_helper.generate_bug_report(data['failed_case_text'], user_desc)

    await status_msg.edit_text("📝 **Зберігаю в таблицю...**")
    utils.update_case_status(data['failed_row'], "Failed", bug_report)

    await status_msg.edit_text(f"🐛 **Bug Report Created:**\n{bug_report}")

    try:
        await bot.edit_message_text(f"~~{data['failed_case_text']}~~\n\n❌ **Failed**", chat_id=message.chat.id,
                                    message_id=data['msg_id'], reply_markup=None)
    except:
        pass

    module_name = data.get('current_module')
    await state.set_state(TestSession.testing)

    if module_name:
        await send_next_case(message, module_name)


# --- GLOBAL RESET ---
@router.message()
async def global_reset(message: Message, state: FSMContext):
    if await state.get_state() == TestSession.waiting_for_bug_desc: return
    await state.clear()
    await message.answer("🏠 Скинуто. Головне меню.", reply_markup=get_main_keyboard())


async def main():
    print("🚀 Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())