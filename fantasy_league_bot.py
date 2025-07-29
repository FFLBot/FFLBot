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
    # Salva l'ID del gruppo dove è stato lanciato il comando
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

@dp.callback_query(Form.league_type, F.data.startswith("type"))
async def league_type_step(cb: CallbackQuery, state: FSMContext):
    choice = cb.data.split(":")[1]
    await state.update_data(league_type=choice)
    await state.set_state(Form.platform)
    await cb.message.edit_text("Scegli la piattaforma:", reply_markup=kb("platform", ["Sleeper", "ESPN", "Fantrax", "Altro"], back=True))

@dp.callback_query(Form.platform, F.data.startswith("platform"))
async def platform_step(cb: CallbackQuery, state: FSMContext):
    choice = cb.data.split(":")[1]

    if choice in ["ESPN", "Fantrax", "Altro"]:
        await state.set_state(Form.other_info)
        await state.update_data(platform=choice, skip_remaining=True)
        await cb.message.edit_text("Inserisci eventuali altre informazioni sulla lega:")
    else:
        await state.update_data(platform=choice, other_info="")
        await ruleset_prompt(cb, state)

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
                InlineKeyboardButton(text="📅 Partecipa", callback_data="join"),
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

@dp.callback_query(Form.ruleset, F.data.startswith("rules"))
async def ruleset_step(cb: CallbackQuery, state: FSMContext):
    choice = cb.data.split(":")[1]
    if choice == "Altro":
        await state.set_state(Form.ruleset_custom)
        await cb.message.edit_text("Inserisci regolamento/gestione:")
    else:
        await state.update_data(ruleset=choice)
        await teams_prompt(cb, state)

@dp.message(Form.ruleset_custom)
async def ruleset_custom(message: Message, state: FSMContext):
    await state.update_data(ruleset=message.text)
    await teams_prompt(message, state)

async def teams_prompt(source, state: FSMContext):
    send = source.message.edit_text if isinstance(source, CallbackQuery) else source.answer
    await state.set_state(Form.teams)
    await send("Quante squadre partecipano?", reply_markup=kb("teams", ["10", "12", "16"], back=True))

@dp.callback_query(Form.teams, F.data.startswith("teams"))
async def teams_step(cb: CallbackQuery, state: FSMContext):
    teams = int(cb.data.split(":")[1])
    await state.update_data(teams=teams)
    await state.set_state(Form.idp_dst)
    await cb.message.edit_text("Che tipo di difesa vuoi usare?", reply_markup=kb("idp", ["IDP", "DST"], back=True))

@dp.callback_query(Form.idp_dst, F.data.startswith("idp"))
async def idp_step(cb: CallbackQuery, state: FSMContext):
    await state.update_data(idp_dst=cb.data.split(":")[1])
    data = await state.get_data()
    if data["teams"] in (10, 12):
        await state.set_state(Form.superflex)
        await cb.message.edit_text("C'è lo slot Superflex?", reply_markup=kb("sflex", ["Si", "No"], back=True))
    else:
        await bestball_prompt(cb, state)

@dp.callback_query(Form.superflex, F.data.startswith("sflex"))
async def sflex_step(cb: CallbackQuery, state: FSMContext):
    await state.update_data(superflex=cb.data.split(":")[1])
    await bestball_prompt(cb, state)

async def bestball_prompt(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Form.bestball)
    await cb.message.edit_text("Usi la formazione BestBall?", reply_markup=kb("bb", ["Si", "No"], back=True))

@dp.callback_query(Form.bestball, F.data.startswith("bb"))
async def bestball_step(cb: CallbackQuery, state: FSMContext):
    await state.update_data(bestball=cb.data.split(":")[1])
    await state.set_state(Form.draft)
    await cb.message.edit_text("Tipo di draft:", reply_markup=kb("draft", ["Slow", "Fast", "Auction"], back=True))

@dp.callback_query(Form.draft, F.data.startswith("draft"))
async def draft_step(cb: CallbackQuery, state: FSMContext):
    await state.update_data(draft=cb.data.split(":")[1])
    data = await state.get_data()

    summary = (
        f"🏈 **Aperte le iscrizioni a una nuova lega di fantasy football!**\n"
        f"Nome: {data['name']}\n"
        f"Tipo: {data['league_type']}\n"
        f"Piattaforma: {data['platform']}\n"
        f"Regolamento: {data['ruleset']}\n"
        f"Squadre: {data['teams']}\n"
        f"IDP/DST: {data['idp_dst']}\n"
        f"Superflex: {data.get('superflex', 'N/A')}\n"
        f"BestBall: {data['bestball']}\n"
        f"Draft: {data['draft']}\n\n"
        "Premi qui per partecipare:")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Partecipa", callback_data="join"),
            InlineKeyboardButton(text="❌ Annulla", callback_data="leave"),
            InlineKeyboardButton(text="🗑 Elimina lega", callback_data="delete_league")
        ]
    ])

    msg = await bot.send_message(GROUP_ID, summary, reply_markup=keyboard, parse_mode="Markdown")
    await bot.pin_chat_message(GROUP_ID, msg.message_id, disable_notification=False)
    leagues[msg.message_id] = {"data": data, "participants": [], "creator_id": cb.from_user.id}
    await cb.message.edit_text("Lega creata e pubblicata nel gruppo!")
    await state.clear()

@dp.callback_query(F.data == "join")
async def cb_join(cb: CallbackQuery):
    league = leagues.get(cb.message.message_id)
    if not league:
        return await cb.answer("Lega non trovata.", show_alert=True)

    if cb.from_user.id in [u.id for u in league["participants"]]:
        return await cb.answer("Hai già partecipato a questa lega!", show_alert=True)

    league["participants"].append(cb.from_user)
    await refresh_roster(cb.message, league)
    await bot.pin_chat_message(GROUP_ID, cb.message.message_id, disable_notification=False)
    await cb.answer("Sei stato aggiunto alla lega.")

@dp.callback_query(F.data == "leave")
async def cb_leave(cb: CallbackQuery):
    league = leagues.get(cb.message.message_id)
    if league:
        league["participants"] = [u for u in league["participants"] if u.id != cb.from_user.id]
        await refresh_roster(cb.message, league)
        await bot.pin_chat_message(GROUP_ID, cb.message.message_id, disable_notification=False)
    await cb.answer()

@dp.callback_query(F.data == "delete_league")
async def delete_league(cb: CallbackQuery):
    league = leagues.get(cb.message.message_id)
    if not league:
        return await cb.answer("Lega non trovata.", show_alert=True)
    if cb.from_user.id != league["creator_id"]:
        return await cb.answer("Solo il creatore può eliminarla.", show_alert=True)
    await cb.message.delete()
    del leagues[cb.message.message_id]
    await cb.answer("Lega eliminata.")

async def refresh_roster(msg: Message, league: dict):
    data = league["data"]
    max_teams = int(data.get("teams", 0))

    base = (
        f"🏈 **Aperte le iscrizioni a una nuova lega di fantasy football!**\n"
        f"Nome: {data.get('name', '-') }\n"
        f"Tipo: {data.get('league_type', '-') }\n"
        f"Piattaforma: {data.get('platform', '-') }\n"
    )
    if "ruleset" in data:
        base += (
            f"Regolamento: {data['ruleset']}\n"
            f"Squadre: {data['teams']}\n"
            f"IDP/DST: {data['idp_dst']}\n"
            f"Superflex: {data.get('superflex', 'N/A')}\n"
            f"BestBall: {data['bestball']}\n"
            f"Draft: {data['draft']}\n"
        )
    if "other_info" in data:
        base += f"Info: {data['other_info']}\n"

    roster = "\n**Partecipanti:**\n" + (
        "\n".join(f"{i+1}. {u.full_name} {'(Riserva)' if i >= max_teams else ''}" for i, u in enumerate(league["participants"]))
        or "_Nessun partecipante_"
    )

    await msg.edit_text(base + roster, reply_markup=msg.reply_markup, parse_mode="Markdown")

@dp.callback_query(F.data == "back")
async def handle_back(cb: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    data = await state.get_data()

    if current == Form.league_type.state:
        await state.set_state(Form.name)
        await cb.message.edit_text("Come si chiama la lega?")
    elif current == Form.platform.state:
        await state.set_state(Form.league_type)
        await cb.message.edit_text("Che tipo di lega è?", reply_markup=kb("type", ["Dynasty", "Redraft"], back=True))
    elif current == Form.ruleset.state:
        await state.set_state(Form.platform)
        await cb.message.edit_text("Scegli la piattaforma:", reply_markup=kb("platform", ["Sleeper", "ESPN", "Fantrax", "Altro"], back=True))
    elif current == Form.teams.state:
        await state.set_state(Form.ruleset)
        await cb.message.edit_text("Regolamento e gestione:", reply_markup=kb("rules", ["FF Lovers", "Altro"], back=True))
    elif current == Form.idp_dst.state:
        await state.set_state(Form.teams)
        await cb.message.edit_text("Quante squadre partecipano?", reply_markup=kb("teams", ["10", "12", "16"], back=True))
    elif current == Form.superflex.state:
        await state.set_state(Form.idp_dst)
        await cb.message.edit_text("Che tipo di difesa vuoi usare?", reply_markup=kb("idp", ["IDP", "DST"], back=True))
    elif current == Form.bestball.state:
        if data.get("teams") in (10, 12):
            await state.set_state(Form.superflex)
            await cb.message.edit_text("C'è lo slot Superflex?", reply_markup=kb("sflex", ["Si", "No"], back=True))
        else:
            await state.set_state(Form.idp_dst)
            await cb.message.edit_text("Che tipo di difesa vuoi usare?", reply_markup=kb("idp", ["IDP", "DST"], back=True))
    elif current == Form.draft.state:
        await state.set_state(Form.bestball)
        await cb.message.edit_text("Usi la formazione BestBall?", reply_markup=kb("bb", ["Si", "No"], back=True))

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
