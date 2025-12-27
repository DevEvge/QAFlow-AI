import os
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
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
    waiting_for_doc = State()
    waiting_for_bug_desc = State()  # Новий стан: чекаємо опису бага


bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📋 Почати/Продовжити")]], resize_keyboard=True)


def get_test_keyboard(row_number):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Pass", callback_data=f"pass_{row_number}"),
            InlineKeyboardButton(text="❌ Failed", callback_data=f"fail_{row_number}")
        ]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Привіт! Я готовий. Тисни кнопку.", reply_markup=get_main_keyboard())


@router.message(F.text == "📋 Почати/Продовжити")
async def start_testing(message: Message, state: FSMContext):
    next_case = utils.get_next_pending_case()
    if next_case:
        await send_case_message(message, next_case)
    else:
        await message.answer("✅ Таблиця пуста. Скинь файл (.docx, .doc, .txt).")
        await state.set_state(TestSession.waiting_for_doc)


@router.message(TestSession.waiting_for_doc, F.document)
async def handle_document(message: Message, state: FSMContext):
    wait_msg = await message.answer("⏳ Обробляю файл...")
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = f"temp_{message.document.file_name}"
    await bot.download_file(file.file_path, file_path)

    try:
        if file_path.endswith('.docx'):
            text = utils.read_docx(file_path)
        elif file_path.endswith('.doc'):
            text = utils.read_doc(file_path)
        else:
            text = utils.read_txt(file_path)

        await bot.edit_message_text("🤖 AI генерує кейси...", chat_id=message.chat.id, message_id=wait_msg.message_id)
        cases = ai_helper.generate_test_cases(text)

        if not cases:
            await message.answer("❌ AI не повернув кейсів.")
            return

        utils.add_cases_to_sheet(cases)
        await message.answer(f"✅ Додано {len(cases)} кейсів.")
        await state.clear()

        next_case = utils.get_next_pending_case()
        if next_case: await send_case_message(message, next_case)

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)


async def send_case_message(message: Message, case_data):
    text = f"🛠 **TEST CASE #{case_data['row'] - 1}**\n\n🔸 {case_data['text']}"
    await message.answer(text, reply_markup=get_test_keyboard(case_data['row']))


# --- ОБРОБКА КНОПКИ PASS ---
@router.callback_query(F.data.startswith("pass_"))
async def process_pass(callback: CallbackQuery):
    row_number = int(callback.data.split("_")[1])
    utils.update_case_status(row_number, "Pass")

    await callback.message.edit_text(f"~~{callback.message.text.split('🔸 ')[1]}~~\n\n✅ **Passed**", reply_markup=None)

    next_case = utils.get_next_pending_case()
    if next_case:
        await send_case_message(callback.message, next_case)
    else:
        await callback.message.answer("🎉 Всі тести пройдено!")


# --- ОБРОБКА КНОПКИ FAILED ---
@router.callback_query(F.data.startswith("fail_"))
async def process_fail_start(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])
    case_text = callback.message.text.split('🔸 ')[1]

    # Зберігаємо дані про кейс, який впав
    await state.update_data(failed_row=row_number, failed_case_text=case_text, msg_id=callback.message.message_id)

    # Просимо опис бага
    await callback.message.answer("✍️ **Опиши, що пішло не так?**\n(Наприклад: 'Кнопка не активна' або 'Помилка 500')")
    await state.set_state(TestSession.waiting_for_bug_desc)
    await callback.answer()  # Закриваємо годинничок завантаження на кнопці


# --- ОБРОБКА ОПИСУ БАГА ---
@router.message(TestSession.waiting_for_bug_desc)
async def process_bug_description(message: Message, state: FSMContext):
    user_desc = message.text
    data = await state.get_data()
    row_number = data['failed_row']
    case_text = data['failed_case_text']

    wait_msg = await message.answer("🐛 AI пише баг-репорт (англійською)...")

    # 1. Генеруємо баг-репорт
    bug_report = ai_helper.generate_bug_report(case_text, user_desc)

    # 2. Записуємо в таблицю
    utils.update_case_status(row_number, "Failed", bug_report)

    # 3. Показуємо результат юзеру
    await bot.edit_message_text(f"📝 **Bug Report Created:**\n\n{bug_report}", chat_id=message.chat.id,
                                message_id=wait_msg.message_id)

    # 4. Оновлюємо старе повідомлення з кейсом
    try:
        await bot.edit_message_text(f"~~{case_text}~~\n\n❌ **Failed**", chat_id=message.chat.id,
                                    message_id=data['msg_id'], reply_markup=None)
    except:
        pass

    await state.clear()

    # 5. Наступний кейс
    next_case = utils.get_next_pending_case()
    if next_case:
        await send_case_message(message, next_case)
    else:
        await message.answer("🎉 Всі тести пройдено!")


async def main():
    print("🚀 Бот з баг-репортами запущений...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())