import random
import string
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from faker import Faker

import database.db as db
from config import OWNER_IDS
from functions.force_join import check_force_join, force_join_keyboard, FORCE_JOIN_MSG
from functions.emojis import EMOJI

router = Router()

LOCALES = {
    "us": "en_US", "usa": "en_US",
    "uk": "en_GB", "gb": "en_GB", "england": "en_GB",
    "ca": "en_CA", "canada": "en_CA",
    "in": "en_IN", "india": "en_IN",
    "au": "en_AU", "australia": "en_AU",
    "nz": "en_NZ",
    "fr": "fr_FR", "france": "fr_FR",
    "de": "de_DE", "germany": "de_DE",
    "it": "it_IT", "italy": "it_IT",
    "es": "es_ES", "spain": "es_ES",
    "mx": "es_MX", "mexico": "es_MX",
    "br": "pt_BR", "brazil": "pt_BR",
}

GEO_DATA = {
    "us": [
        {"city": "New York", "state": "New York", "zip": "10001", "country": "United States"},
        {"city": "Los Angeles", "state": "California", "zip": "90001", "country": "United States"},
        {"city": "Chicago", "state": "Illinois", "zip": "60601", "country": "United States"},
        {"city": "Houston", "state": "Texas", "zip": "77001", "country": "United States"},
        {"city": "Phoenix", "state": "Arizona", "zip": "85001", "country": "United States"},
        {"city": "Philadelphia", "state": "Pennsylvania", "zip": "19101", "country": "United States"},
        {"city": "San Antonio", "state": "Texas", "zip": "78201", "country": "United States"},
        {"city": "San Diego", "state": "California", "zip": "92101", "country": "United States"},
        {"city": "Dallas", "state": "Texas", "zip": "75201", "country": "United States"},
        {"city": "Austin", "state": "Texas", "zip": "78701", "country": "United States"},
        {"city": "Miami", "state": "Florida", "zip": "33101", "country": "United States"},
        {"city": "Atlanta", "state": "Georgia", "zip": "30301", "country": "United States"},
    ],
    "ca": [
        {"city": "Toronto", "state": "Ontario", "zip": "M5V 2T6", "country": "Canada"},
        {"city": "Montreal", "state": "Quebec", "zip": "H2Y 1Y8", "country": "Canada"},
        {"city": "Vancouver", "state": "British Columbia", "zip": "V6B 1Y1", "country": "Canada"},
        {"city": "Calgary", "state": "Alberta", "zip": "T2P 1J9", "country": "Canada"},
    ],
    "uk": [
        {"city": "London", "state": "England", "zip": "EC1A 1BB", "country": "United Kingdom"},
        {"city": "Birmingham", "state": "England", "zip": "B1 1TB", "country": "United Kingdom"},
        {"city": "Manchester", "state": "England", "zip": "M1 1AE", "country": "United Kingdom"},
        {"city": "Glasgow", "state": "Scotland", "zip": "G1 1QX", "country": "United Kingdom"},
    ],
    "in": [
        {"city": "Mumbai", "state": "Maharashtra", "zip": "400001", "country": "India"},
        {"city": "Delhi", "state": "Delhi", "zip": "110001", "country": "India"},
        {"city": "Bangalore", "state": "Karnataka", "zip": "560001", "country": "India"},
        {"city": "Hyderabad", "state": "Telangana", "zip": "500001", "country": "India"},
    ],
    "au": [
        {"city": "Sydney", "state": "New South Wales", "zip": "2000", "country": "Australia"},
        {"city": "Melbourne", "state": "Victoria", "zip": "3000", "country": "Australia"},
        {"city": "Brisbane", "state": "Queensland", "zip": "4000", "country": "Australia"},
        {"city": "Perth", "state": "Western Australia", "zip": "6000", "country": "Australia"},
    ]
}

def generate_random_password(length=10) -> str:
    chars = string.ascii_letters + string.digits + "$#@!%*?&"
    return "".join(random.choice(chars) for _ in range(length))

@router.message(Command("fake", "faker", "rand", prefix="/."))
async def cmd_fake(msg: Message, command: CommandObject, bot: Bot):
    uid = msg.from_user.id
    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)

    if await db.is_banned(uid):
        return

    if not await check_force_join(bot, uid):
        kb = await force_join_keyboard()
        await msg.answer(FORCE_JOIN_MSG, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    args = (command.args or "").strip().lower()
    locale = LOCALES.get(args, "en_US")

    try:
        fake = Faker(locale)
    except Exception:
        fake = Faker("en_US")

    try:
        gender = random.choice(["Male", "Female"])
        if gender == "Male":
            first_name = fake.first_name_male()
            last_name = fake.last_name()
        else:
            first_name = fake.first_name_female()
            last_name = fake.last_name()
    except AttributeError:
        first_name = fake.first_name()
        last_name = fake.last_name()

    full_name = f"{first_name} {last_name}"
    
    try:
        street = fake.street_address()
    except AttributeError:
        try:
            street = fake.address().replace("\n", ", ")
        except AttributeError:
            street = ""

    geo_key = "us"
    if args in ["ca", "canada"]: geo_key = "ca"
    elif args in ["uk", "gb", "england"]: geo_key = "uk"
    elif args in ["in", "india"]: geo_key = "in"
    elif args in ["au", "australia"]: geo_key = "au"

    geo = random.choice(GEO_DATA[geo_key])
    city = geo["city"]
    state = geo["state"]
    postcode = geo["zip"]
    country = geo["country"]

    try:
        phone = fake.phone_number()
    except AttributeError:
        phone = ""

    domain = random.choice(["gmail.com", "hotmail.com"])
    email = f"{first_name.lower()}{last_name.lower()}{random.randint(10, 999)}@{domain}"

    username = f"{first_name.lower()}{random.randint(10, 99)}"
    password = generate_random_password()

    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)
    is_admin = await db.is_admin(uid)
    plan = await db.get_user_plan(uid)

    if is_owner:
        plan_label = "OWNER"
    elif is_admin:
        plan_label = "ADMIN"
    elif plan["unlimited"]:
        plan_label = "PREMIUM"
    else:
        plan_label = "FREE"

    user_label = msg.from_user.first_name or "User"

    text = (
        f"Fake Info Created Successfully ✅\n"
        f"━━━━━━━━━━━━━━\n"
        f"🆔 Full Name: <code>{full_name}</code>\n"
        f"👤 Gender: <code>{gender}</code>\n"
        f"🏠 Street: <code>{street}</code>\n"
        f"🏙️ City: <code>{city}</code>\n"
        f"🌏 State/Province: <code>{state}</code>\n"
        f"📮 Postal Code: <code>{postcode}</code>\n"
        f"🌍 Country: <code>{country}</code>\n"
        f"📞 Phone Number: <code>{phone}</code>\n"
        f"📧 Email: <code>{email}</code>\n"
        f"👤 Username: <code>{username}</code>\n"
        f"🔑 Password: <code>{password}</code>\n"
        f"🗺️ Address Type: <code>Synthetic (geo)</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"Checked By: {user_label} [ <b>{plan_label}</b> ]\n"
        f"Bot by: @damxd89"
    )

    await msg.answer(text, parse_mode=ParseMode.HTML)
