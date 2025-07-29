import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("La variabile BOT_TOKEN non è impostata.")

bot = Bot(TOKEN)
dp = Dispatcher()

GROUP_ID = -1002345368518

class Form(StatesGroup):
    name = State()
    league_type = State()
    platform = State()
    other_info = State()
    ruleset = State()
    ruleset_custom = State()
    teams = State()
    idp_dst = State()
    superflex = State()
    bestball = State()
    draft = State()

leagues: dict[int, dict] = {}

def kb(prefix: str, options: list[str], back: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=o, callback_data=f"{prefix}:{o}")] for o in options]
    if back:
        rows.append([InlineKeyboardButton(text="🔙 Indietro", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(Command("crealega"))
async def crealega(message: Message, state: FSMContext):
    if message.chat.type in ("group", "supergroup"):
        await state.update_data(group_id=message.chat.id)
        try:
            await bot.send_message(message.from_user.id, "Perfetto! Iniziamo a creare la tua lega.\n\nCome si chiama la lega?")
            await state.set_state(Form.name)
        except:
            await message.reply("Per favore apri la chat privata con me, premi /start e poi riprova /crealega.")
    else:
        await message.answer("Devi scrivere /crealega nel gruppo per creare una lega.")

@dp.message(Form.name)
async def name_step(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.league_type)
    await message.answer("Che tipo di lega è?", reply_markup=kb("type", ["Dynasty", "Redraft"], back=True))

@dp.callback_query(F.data.startswith("type"))
async def league_type_step(cb: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    if current != Form.league_type.state:
        return await cb.answer("Errore di stato. Riprova o ricomincia con /crealega", show_alert=True)

    choice = cb.data.split(":")[1]
    await state.update_data(league_type=choice)
    await state.set_state(Form.platform)
    await bot.send_message(cb.from_user.id, "Scegli la piattaforma:", reply_markup=kb("platform", ["Sleeper", "ESPN", "Fantrax", "Altro"], back=True))
    await cb.answer()

@dp.callback_query(F.data.startswith("platform"))
async def platform_step(cb: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    if current != Form.platform.state:
        return await cb.answer("Errore di stato, riprova da capo.", show_alert=True)

    choice = cb.data.split(":")[1]

    if choice in ["ESPN", "Fantrax", "Altro"]:
        await state.set_state(Form.other_info)
        await state.update_data(platform=choice, skip_remaining=True)
        await bot.send_message(cb.from_user.id, "Inserisci eventuali altre informazioni sulla lega:")
    else:
        await state.update_data(platform=choice, other_info="")
        await ruleset_prompt(cb, state)
    await cb.answer()

@dp.message(Form.other_info)
async def other_info_step(message: Message, state: FSMContext):
    await state.update_data(other_info=message.text)
    data = await state.get_data()

    if data.get("skip_remaining"):
        summary = (
            f"🏈 **Aperte le iscrizioni a una nuova lega di fantasy football!**\n"
            f"Tipo: {data['league_type']}\n"
            f"Piattaforma: {data['platform']}\n"
            f"Info: {data['other_info']}\n"
            "Premi qui per partecipare:"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗕 Partecipa", callback_data="join"),
                InlineKeyboardButton(text="❌ Annulla", callback_data="leave"),
                InlineKeyboardButton(text="🗑 Elimina lega", callback_data="delete_league")
            ]
        ])

        msg = await bot.send_message(data["group_id"], summary, reply_markup=keyboard, parse_mode="Markdown")
        await bot.pin_chat_message(data["group_id"], msg.message_id, disable_notification=False)
        leagues[msg.message_id] = {"data": data, "participants": [], "creator_id": message.from_user.id}
        await message.answer("Lega creata e pubblicata nel gruppo!")
        await state.clear()
    else:
        await ruleset_prompt(message, state)
