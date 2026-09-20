# -*- coding: utf-8 -*-
"""
RADAR 3 (@radar_3bot) — ربات بازی استراتژیک جنگی برای پیام‌رسان بله
=================================================================
نصب:   pip install requests
اجرا:   python radar3.py
دیتا:  radar3_data.json (خودکار ساخته می‌شود — همه خریدها و کشورها ذخیره می‌شوند)

تغییر مهم این نسخه:
  • تقریباً همه منوها → دکمه اصلی ربات (ReplyKeyboardMarkup)
  • فقط دکمه‌های تأیید / لغو و موارد مشابه → دکمه شیشه‌ای (InlineKeyboard)
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

# ───────────────────────────── تنظیمات (از متغیر محیطی) ─────────────────────────────
# در Railway / لوکال این‌ها را ست کنید — داخل گیت‌هاب نگذارید
TOKEN = (os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("BOT_TOKEN تنظیم نشده — در Railway Variables مقدار بدهید")

_admin_raw = (os.environ.get("ADMIN_IDS") or "").strip()
if _admin_raw:
    ADMIN_IDS = {int(x.strip()) for x in _admin_raw.replace(";", ",").split(",") if x.strip().isdigit()}
else:
    ADMIN_IDS = set()

_admin_main = (os.environ.get("ADMIN_ID") or "").strip()
ADMIN_ID = int(_admin_main) if _admin_main.isdigit() else (next(iter(ADMIN_IDS)) if ADMIN_IDS else 0)

_un = (os.environ.get("UN_OWNER_ID") or "").strip()
UN_OWNER_ID = int(_un) if _un.isdigit() else ADMIN_ID

API_BASE  = "https://tapi.bale.ai/bot" + TOKEN
DATA_FILE = os.environ.get("DATA_FILE", "radar3_data.json")

START_COINS       = 600_000_000
BASE_COUNTRY_POWER = 1_000_000
HACK_DURATION_SEC  = 3600  # ۱ ساعت قفل هک
OIL_PER_FIELD     = 300
OIL_COST_PER_UNIT = 100  # نفت لازم برای هر واحد تجهیز تهاجمی در حمله
CHANNEL_USERNAME  = os.environ.get("CHANNEL_USERNAME", "@radaregang")
FORCE_CHANNELS = [
    {"user": "@radaregang", "btn": "کانال اصلی", "url": "https://ble.ir/radaregang"},
    {"user": "@radargabeliat", "btn": "کانال قابلیت ها", "url": "https://ble.ir/radargabeliat"},
    {"user": "@radare", "btn": "کانال اختراعات", "url": "https://ble.ir/radare"},
]

NOTIFY_PROFIT    = True
TEHRAN_TZ        = timezone(timedelta(hours=3, minutes=30))

PRINTER_INCOME = {1: 8_000_000_000, 2: 15_000_000_000, 3: 20_000_000_000}
LVL_FA = {1: "۱", 2: "۲", 3: "۳"}

# ───────────────────────────── ابزار اعداد فارسی ─────────────────────────────
_FA     = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_FA_SEP = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬")

def fad(n):
    return str(n).translate(_FA)

def fnum(n):
    return f"{n:,}".translate(_FA_SEP)

def coins_fa(n):
    if n == 0:
        return "۰ سکه"
    if n >= 1_000_000_000:
        if n % 1_000_000_000 == 0:
            return fad(n // 1_000_000_000) + " میلیارد سکه"
        return fad(n // 1_000_000_000) + " میلیارد و " + fad((n % 1_000_000_000) // 1_000_000) + " میلیون سکه"
    if n % 1_000_000 == 0:
        return fad(n // 1_000_000) + " میلیون سکه"
    return fnum(n) + " سکه"

def mil_fa(pm):
    if pm < 1000:
        return fad(pm) + " میلیون سکه"
    if pm % 1000 == 0:
        return fad(pm // 1000) + " میلیارد سکه"
    if pm % 500 == 0:
        return fad(pm / 1000) + " میلیارد سکه"
    return fad(pm // 1000) + " میلیارد و " + fad(pm % 1000) + " میلیون سکه"

# ───────────────────────────── کشورها ─────────────────────────────
COUNTRIES = [
    ("🇺🇳", "UN",           "سازمان ملل",          False),
    ("🇺🇸", "USA",          "ایالات متحده آمریکا", True),
    ("🇨🇳", "China",        "چین",                 True),
    ("🇷🇺", "Russia",       "روسیه",               True),
    ("🇮🇳", "India",        "هند",                 True),
    ("🇬🇧", "UK",           "بریتانیا",            True),
    ("🇫🇷", "France",       "فرانسه",              False),
    ("🇩🇪", "Germany",      "آلمان",               False),
    ("🇰🇵", "NorthKorea",   "کره شمالی",           False),
    ("🇯🇵", "Japan",        "ژاپن",                False),
    ("🇰🇷", "SouthKorea",   "کره جنوبی",           False),
    ("🇹🇷", "Turkey",       "ترکیه",               False),
    ("🇮🇹", "Italy",        "ایتالیا",             False),
    ("🇧🇷", "Brazil",       "برزیل",               False),
    ("🇨🇦", "Canada",       "کانادا",              False),
    ("🇦🇺", "Australia",    "استرلیا",             False),
    ("🇮🇱", "Israel",       "اسرائیل",             False),
    ("🇪🇸", "Spain",        "اسپانیا",             False),
    ("🇸🇦", "SaudiArabia",  "عربستان سعودی",       False),
    ("🇮🇷", "Iran",         "ایران",               False),
    ("🇵🇰", "Pakistan",     "پاکستان",             False),
    ("🇮🇩", "Indonesia",    "اندونزی",             False),
    ("🇲🇽", "Mexico",       "مکزیک",               False),
    ("🇳🇱", "Netherlands",  "هلند",                False),
    ("🇵🇱", "Poland",       "لهستان",              False),
    ("🇸🇪", "Sweden",       "سوئد",                False),
    ("🇳🇴", "Norway",       "نروژ",                False),
    ("🇿🇦", "SouthAfrica",  "آفریقای جنوبی",       False),
    ("🇪🇬", "Egypt",        "مصر",                 False),
    ("🇦🇪", "UAE",          "امارات متحده عربی",   False),
    ("🇸🇬", "Singapore",    "سنگاپور",             False),
    ("🇨🇭", "Switzerland",  "سوئیس",               False),
    ("🇺🇦", "Ukraine",      "اوکراین",             False),
    ("🇻🇳", "Vietnam",      "ویتنام",              False),
    ("🇹🇭", "Thailand",     "تایلند",              False),
    ("🇦🇷", "Argentina",    "آرژانتین",            False),
    ("🇲🇾", "Malaysia",     "مالزی",               False),
    ("🇾🇪", "Yemen",        "یمن",                 False),
]

# ───────────────────────────── متن‌های ثابت ─────────────────────────────
WELCOME = (
"آیا برای فرماندهی آماده‌ای؟ 🎖️\n\n"
"دنیا در آستانه فروپاشی است و تنها یک نفر می‌تواند ورق را برگرداند!\n\n"
"در @RADAR_3BOT، استراتژی شماست که سرنوشت جنگ را تعیین می‌کند. نیروها را سازماندهی کن، نقشه دشمن را نقش بر آب کن و به قدرت بلامنازع میدان نبرد تبدیل شو!\n\n"
"⚠️ فقط برای شجاعان:\n\n"
"⚔️ نبردهای نفس‌گیر\n\n"
"🛡️ مدیریت منابع و ارتش\n\n"
"🏆 جایگاهت را در رنکینگ جهانی تثبیت کن\n\n"
"همین حالا وارد میدان شو:\n\n"
"👉 @RADAR_3BOT"
)

COUNTRY_TEXT = (
"🇺🇳 سازمان ملل\n"
"⚔️ 🇺🇸 USA — United States — ایالات متحده آمریکاVIP\n"
"⚔️ 🇨🇳 China — چینVIP\n"
"⚔️ 🇷🇺 Russia — روسیهVIP\n"
"⚔️ 🇮🇳 India — هندVIP\n"
"⚔️ 🇬🇧 United Kingdom — بریتانیاVIP\n"
"\n"
"🇫🇷 France — فرانسه\n"
"🇩🇪 Germany — آلمان\n"
"🪖 🇰🇵 North Korea — کره شمالی\n"
"🪖 🇯🇵 Japan — ژاپن\n"
"🪖 🇰🇷 South Korea — کره جنوبی\n"
"🪖 🇹🇷 Turkey — ترکیه\n"
"\n"
"⚔️ 🇮🇹 Italy — ایتالیا\n"
"⚔️ 🇧🇷 Brazil — برزیل\n"
"⚔️ 🇨🇦 Canada — کانادا\n"
"⚔️ 🇦🇺 Australia — استرلیا\n"
"⚔️ 🇮🇱 Israel — اسرائیل\n"
"\n"
"🪖 🇪🇸 Spain — اسپانیا\n"
"🪖 🇸🇦 Saudi Arabia — عربستان سعودی\n"
"🪖 🇮🇷 Iran — ایران\n"
"🪖 🇵🇰 Pakistan — پاکستان\n"
"🪖 🇮🇩 Indonesia — اندونزی\n"
"\n"
"⚔️ 🇲🇽 Mexico — مکزیک\n"
"⚔️ 🇳🇱 Netherlands — هلند\n"
"⚔️ 🇵🇱 Poland — لهستان\n"
"⚔️ 🇸🇪 Sweden — سوئد\n"
"⚔️ 🇳🇴 Norway — نروژ\n"
"\n"
"🪖 🇿🇦 South Africa — آفریقای جنوبی\n"
"🪖 🇪🇬 Egypt — مصر\n"
"🪖 🇦🇪 United Arab Emirates — امارات متحده عربی\n"
"🪖 🇸🇬 Singapore — سنگاپور\n"
"🪖 🇨🇭 Switzerland — سوئیس\n"
"\n"
"⚔️ 🇺🇦 Ukraine — اوکراین\n"
"⚔️ 🇻🇳 Vietnam — ویتنام\n"
"⚔️ 🇹🇭 Thailand — تایلند\n"
"⚔️ 🇦🇷 Argentina — آرژانتین\n"
"🇲🇾 Malaysia — مالزی\n"
"🇾🇪 Yemen — یمن\n"
"\n"
"*VIP:5,000تومان\n"
"برای دریافت کشور های VIP به آیدی زیر مراجعه کنید!*\n"
"- @gymrooo"
)

WAR_TEXT = (
"*کاربر گرامی⚠️*\n\n"
"تجهیزات جنگی مورد نظر خود را از طریق این بخش خریداری کنید!✔️\n\n"
"*بخش اول 🎁:\n"
"https://ble.ir/radaregang/-2210119590173004338/1789143597094*\n\n"
"*بخش دوم 🎁:\n"
"https://ble.ir/radaregang/-7952668283615478139/1789143595970*\n\n"
"*بخش سوم 🎁:\n"
"https://ble.ir/radaregang/5393851020529936013/1789143594659*\n\n"
"*بخش چهارم 🎁:\n"
"https://ble.ir/radaregang/-8711512955285589941/1789143593348*\n\n"
"جهت خرید تجهیزات از منوی زیر استفاده کنید!📌"
)

COUNTRY_FULL_TEXT = "*کاربر گرامی⚠️*\n\nاین کشور پر شده است!✔️\n\nلطفا کشور دیگری را انتخاب نمایید!📌"
VIP_TEXT          = ("*کاربر گرامی⚠️*\n\nاین کشور VIP است و توانایی دریافت آن را ندارید!✔️\n\n"
                     "برای خرید این کشور به آیدی زیر مراجعه نمایید!📌\n\n- @gymrooo")
HAD_COUNTRY_TEXT  = "*کاربر گرامی⚠️*\n\nشما قبلا کشور داشته اید!✔️\n\nنمی توانید مالک کشوری شوید!📌"
CANCEL_TEXT       = "*کاربر گرامی⚠️*\n\nعملیات لغو با موفقیت انجام شد!✔️\n\nممنون از شما!📌"
BUY_OK_TEXT       = "*کاربر گرامی⚠️*\n\nتجهیزات مورد نظر با موفقیت خریداری شد!✔️\n\nمسیر خود را قدرتمند ادامه دهید!📌"
NEED_COUNTRY_TEXT = "*کاربر گرامی⚠️*\n\nابتدا کشور گیری کنید!✔️\n\nسپس می توانید خرید کنید!📌"
SHOP_TEXT         = "*کاربر گرامی⚠️*\n\nاز این بخش می توانید تجهیزات مورد نظر خود را خریداری کنید!✔️\n\nاز منوی زیر استفاده کنید!📌"
DEF_MENU_TEXT     = "*کاربر گرامی⚠️*\n\nاز این بخش می توانید تجهیزات دفاعی خریداری کنید!✔️\n\nاز منوی زیر استفاده کنید!📌"
UNKNOWN_TEXT      = "*کاربر گرامی⚠️*\n\nلطفا فقط از دکمه‌های ربات استفاده کنید!✔️\n\nاز منوی زیر استفاده کنید!📌"
NUKE_CARD_TEXT    = "*« 🛡 پدافند ضد بمب اتم »*\n\nقیمت : ۲۰ هزار تومان\n\nجهت خرید به آیدی زیر مراجعه نمایید!✔️\n\n- @gymrooo"

ADMIN_PANEL_TEXT  = "*ادمین گرامی⚠️*\n\nشما می توانید از طریق این بخش ربات خود را مدیریت کنید!✔️\n\nاز منوی زیر استفاده کنید!📌"
GIFT_SELECT_TEXT  = "*ادمین گرامی⚠️*\n\nکشور مورد نظر را برای اهدا انتخاب کنید!✔️\n\nاز منوی زیر استفاده کنید!📌"
GIFT_TAKEN_TEXT   = "*ادمین گرامی⚠️*\n\nاین کشور مدیر دارد!✔️\n\nامکان اهدا این کشور وجود ندارد!📌"
GIFT_OK_TEXT      = "*ادمین گرامی⚠️*\n\nکشور به کاربر مورد نظر اهدا شد!✔️\n\nاز شما متشکریم!📌"
GIFT_HAS_COUNTRY_TEXT = "*ادمین گرامی⚠️*\n\nاین کاربر از قبل مالک یک کشور است!✔️\n\nامکان اهدا کشور به این کاربر وجود ندارد!📌"
RM_SELECT_TEXT    = "*ادمین گرامی⚠️*\n\nکشور مورد نظر را انتخاب کنید!✔️\n\nاز منوی زیر استفاده کنید!📌"
RM_NO_MGR_TEXT    = "*ادمین گرامی⚠️*\n\nاین کشور مدیر ندارد!✔️\n\nنیازی به حذف مدیر نیست!📌"
ASK_UID_ADMIN     = "*ادمین گرامی⚠️*\n\nآیدی عددی فرد مورد نظر را ارسال نمایید!✔️\n\n*مثال : ۱۲۳۴۵۶۷۸۹ 📌*"
ASK_UID_GIFT      = "*ادمین گرامی⚠️*\n\nآیدی عددی کاربر مورد نظر را ارسال نمایید!✔️\n\n*مثال : ۱۲۳۴۵۶۷۸۹ 📌*"
INVALID_UID_TEXT  = "*ادمین گرامی⚠️*\n\nلطفا فقط آیدی عددی معتبر ارسال کنید!✔️\n\n*مثال : ۱۲۳۴۵۶۷۸۹ 📌*"
NOT_STARTED_TEXT  = "*ادمین گرامی⚠️*\n\nاین کاربر ربات را استارت نکرده است!✔️\n\nلطفا ابتدا از کاربر بخواهید ربات را استارت کند!📌"
PRINTER_LEVEL_ASK = "*ادمین گرامی⚠️*\n\nسطح دستگاه چاپ‌پول را انتخاب نمایید!✔️\n\nاز منوی زیر استفاده کنید!📌"
PRINTER_OFF_TEXT  = "*ادمین گرامی⚠️*\n\nدستگاه چاپ پول برای این کاربر غیرفعال است!✔️\n\nنیازی به تغییر نیست!📌"
PRINTER_REMOVED_TEXT = "*ادمین گرامی⚠️*\n\nدستگاه چاپ پول با موفقیت از تجهیزات کاربر حذف شد!✔️\n\nاز تلاش شما سپاسگزاریم!📌"

# ───────────────────────────── تجهیزات اقتصادی ─────────────────────────────
ECO_ITEMS = [
    {"id": "eco1", "btn": "💎 معدن الماس", "title": "۱ 💎 معدن الماس",
     "price": 350_000_000, "price_t": "قیمت: ۳۵۰ میلیون سکه",
     "profit": 300_000_000, "profit_t": "سود: ۳۰۰ میلیون سکه"},
    {"id": "eco2", "btn": "🥇 معدن طلا", "title": "۲ 🥇 معدن طلا",
     "price": 400_000_000, "price_t": "قیمت: ۴۰۰ میلیون سکه",
     "profit": 350_000_000, "profit_t": "سود: ۳۵۰ میلیون سکه"},
    {"id": "eco3", "btn": "⚙️ معدن آهن", "title": "۳ ⚙️ معدن آهن",
     "price": 300_000_000, "price_t": "قیمت: ۳۰۰ میلیون سکه",
     "profit": 250_000_000, "profit_t": "سود: ۲۵۰ میلیون سکه"},
    {"id": "eco4", "btn": "🟠 معدن مس", "title": "۴ 🟠 معدن مس",
     "price": 200_000_000, "price_t": "قیمت: ۲۰۰ میلیون سکه",
     "profit": 100_000_000, "profit_t": "سود: ۱۰۰ میلیون سکه"},
    {"id": "eco5", "btn": "🔥 میدان گاز طبیعی", "title": "۵ 🔥 میدان گاز طبیعی",
     "price": 800_000_000, "price_t": "قیمت: ۸۰۰ میلیون سکه",
     "profit": 600_000_000, "profit_t": "سود: ۶۰۰ میلیون سکه"},
    {"id": "eco6", "btn": "🛢️ میدان نفتی", "title": "۶ 🛢️ میدان نفتی",
     "price": 1_000_000_000, "price_t": "قیمت: ۱ میلیارد سکه",
     "profit": 800_000_000, "profit_t": "سود: ۸۰۰ میلیون سکه",
     "oil_t": "درآمد نفتی:\nهر ۲۴ ساعت ۳۰۰ بشکه نفت"},
]
ECO_MAP = {it["id"]: it for it in ECO_ITEMS}

# ───────────────────────────── تجهیزات دفاعی ─────────────────────────────
DEF_ITEMS = [
    {"id": "def1", "btn": "🛡️ ۴۰ سامانه Iron Dome — گنبد آهنین", "price": 300_000_000, "pt": "۳۰۰ میلیون سکه", "power": 180},
    {"id": "def2", "btn": "🛡️ ۴۰ سامانه Patriot PAC-3 — پاتریوت",  "price": 450_000_000, "pt": "۴۵۰ میلیون سکه", "power": 280},
    {"id": "def3", "btn": "🛡️ ۴۰ سامانه THAAD — تاد",              "price": 700_000_000, "pt": "۷۰۰ میلیون سکه", "power": 380},
    {"id": "def4", "btn": "🛡️ ۴۰ سامانه S-300 — اس-۳۰۰",            "price": 400_000_000, "pt": "۴۰۰ میلیون سکه", "power": 480},
    {"id": "def5", "btn": "🛡️ ۴۰ سامانه S-400 — اس-۴۰۰",            "price": 550_000_000, "pt": "۵۵۰ میلیون سکه", "power": 580},
    {"id": "def6", "btn": "🛡️ ۴۰ سامانه S-500 — اس-۵۰۰",            "price": 900_000_000, "pt": "۹۰۰ میلیون سکه", "power": 680},
    {"id": "def7", "btn": "🛡️ ۴۰ سامانه HQ-9 — اچ‌کیو-۹",           "price": 500_000_000, "pt": "۵۰۰ میلیون سکه", "power": 780},
]


PRINTERS = {
    1: ("دستگاه چاپ پول سطح ۱ 🎁", "۱۰ هزار تومان", "۸ میلیارد سکه"),
    2: ("دستگاه چاپ پول سطح ۲ 🎁", "۱۸ هزار تومان", "۱۵ میلیارد سکه"),
    3: ("دستگاه چاپ پول سطح ۳ 🎁", "۲۰ هزار تومان", "۲۰ میلیارد سکه"),
}

# ── تجهیزات هکری ──
HACK_EQ_ITEMS = [
    {"id": "hq", "btn": "🏢 مقر هکری", "pack": 10, "price": 100_000_000, "dia": 0,
     "card": "*🏢  10 مقر هکری*\n\n💰 قیمت هر 10 مقر هکری : 100 میلیون سکه\n\n👥 نیاز برای 50 هکر یا ضدهکر : 5 پک 10 تایی مقر"},
    {"id": "pc", "btn": "💻 کامپیوتر پیشرفته", "pack": 10, "price": 280_000_000, "dia": 0,
     "card": "*💻 10 کامپیوتر پیشرفته*\n\n💰 قیمت هر 10 کامپیوتر : 280 میلیون سکه\n\n👥 نیاز‌برای 50 هکر یا ضدهکر: 5 پک 10تایی کامپیوتر"},
    {"id": "comm", "btn": "📡 مرکز ارتباطات", "pack": 10, "price": 500_000_000, "dia": 10,
     "card": "*📡 10 مرکز ارتباطات*\n\n💰 قیمت هر 10 مرکز : 500 میلیون سکه + 💎 10 الماس\n\n👥 نیاز برای هر مقر : 5 پک 10 تایی"},
    {"id": "sat", "btn": "🛰 ماهواره اختصاصی", "pack": 10, "price": 800_000_000, "dia": 10,
     "card": "*🛰 10 ماهواره اختصاصی*\n\n💰 قیمت هر 10 ماهواره : 800 میلیون سکه + 💎 10 الماس\n\n👥 نیاز برای هر مقر : 5 پک 10 تایی"},
]
HACK_EQ_MAP = {it["id"]: it for it in HACK_EQ_ITEMS}

ANTI_HACK_GROUPS = [
    {"id": "ah1", "btn": "🟢 گروهک ضد‌هکری ضعیف", "power": 50, "price": 500_000_000, "dia": 10,
     "card": "*🟢 گروهک ضد‌هکری ضعیف*\n\n👥 ۵۰ ضد‌هکر\n🛡️ قدرت دفاع: ۵۰\n💰 ۵۰۰ میلیون + 💎 ۱۰ الماس"},
    {"id": "ah2", "btn": "🔵 گروهک ضد‌هکری متوسط", "power": 100, "price": 1_000_000_000, "dia": 20,
     "card": "*🔵 گروهک ضد‌هکری متوسط*\n\n👥 ۵۰ ضد‌هکر\n🛡️ قدرت دفاع: ۱۰۰\n💰 ۱ میلیارد + 💎 ۲۰ الماس"},
    {"id": "ah3", "btn": "🟠 گروهک ضد‌هکری قوی", "power": 150, "price": 1_500_000_000, "dia": 30,
     "card": "*🟠 گروهک ضد‌هکری قوی*\n\n👥 ۵۰ ضد‌هکر\n🛡️ قدرت دفاع: ۱۵۰\n💰 ۱.۵ میلیارد + 💎 ۳۰ الماس"},
    {"id": "ah4", "btn": "🔴 گروهک ضد‌هکری فوق‌قوی", "power": 200, "price": 2_000_000_000, "dia": 40,
     "card": "*🔴 گروهک ضد‌هکری فوق‌قوی*\n\n👥 ۵۰ ضد‌هکر\n🛡️ قدرت دفاع: ۲۰۰\n💰 ۲ میلیارد + 💎 ۴۰ الماس"},
    {"id": "ah5", "btn": "🟣 گروهک ضد‌هکری اسطوره‌ای", "power": 250, "price": 2_500_000_000, "dia": 50,
     "card": "*🟣 گروهک ضد‌هکری اسطوره‌ای*\n\n👥 ۵۰ ضد‌هکر\n🛡️ قدرت دفاع: ۲۵۰\n💰 ۲.۵ میلیارد + 💎 ۵۰ الماس"},
]
ANTI_HACK_MAP = {it["id"]: it for it in ANTI_HACK_GROUPS}

HACK_GROUPS = [
    {"id": "hk1", "btn": "🟢 گروهک هکری ضعیف", "power": 100, "price": 1_000_000_000, "dia": 30,
     "card": "*🟢 گروهک هکری ضعیف*\n\n👥 ۵۰ هکر\n⚡ نفوذ: ۱۰۰\n💰 ۱ میلیارد + 💎 ۳۰ الماس"},
    {"id": "hk2", "btn": "🔵 گروهک هکری متوسط", "power": 150, "price": 1_500_000_000, "dia": 60,
     "card": "*🔵 گروهک هکری متوسط*\n\n👥 ۵۰ هکر\n⚡ نفوذ: ۱۵۰\n💰 ۱.۵ میلیارد + 💎 ۶۰ الماس"},
    {"id": "hk3", "btn": "🟠 گروهک هکری قوی", "power": 200, "price": 2_000_000_000, "dia": 90,
     "card": "*🟠 گروهک هکری قوی*\n\n👥 ۵۰ هکر\n⚡ نفوذ: ۲۰۰\n💰 ۲ میلیارد + 💎 ۹۰ الماس"},
    {"id": "hk4", "btn": "🔴 گروهک هکری فوق‌قوی", "power": 250, "price": 2_500_000_000, "dia": 120,
     "card": "*🔴 گروهک هکری فوق‌قوی*\n\n👥 ۵۰ هکر\n⚡ نفوذ: ۲۵۰\n💰 ۲.۵ میلیارد + 💎 ۱۲۰ الماس"},
    {"id": "hk5", "btn": "🟣 گروهک هکری ابر‌قوی", "power": 300, "price": 3_000_000_000, "dia": 150,
     "card": "*🟣 گروهک هکری ابر‌قوی*\n\n👥 ۵۰ هکر\n⚡ نفوذ: ۳۰۰\n💰 ۳ میلیارد + 💎 ۱۵۰ الماس"},
    {"id": "hk6", "btn": "🟡👑 گروهک هکری اسطوره‌ای", "power": 350, "price": 3_500_000_000, "dia": 180,
     "card": "*🟡👑 گروهک هکری اسطوره‌ای*\n\n👥 ۵۰ هکر\n⚡ نفوذ: ۳۵۰\n💰 ۳.۵ میلیارد + 💎 ۱۸۰ الماس"},
]
HACK_GROUP_MAP = {it["id"]: it for it in HACK_GROUPS}

WORKER_RENT = [
    {"btn": "🔸 ۱ کارگر | ۱ روزه", "n": 1, "days": 1, "price": 30_000_000, "food": 100},
    {"btn": "🔸 ۱ کارگر | ۲ روزه", "n": 1, "days": 2, "price": 60_000_000, "food": 200},
    {"btn": "🔸 ۱ کارگر | ۳ روزه", "n": 1, "days": 3, "price": 90_000_000, "food": 300},
    {"btn": "🔸 ۲ کارگر | ۱ روزه", "n": 2, "days": 1, "price": 60_000_000, "food": 200},
    {"btn": "🔸 ۲ کارگر | ۲ روزه", "n": 2, "days": 2, "price": 90_000_000, "food": 400},
    {"btn": "🔸 ۲ کارگر | ۳ روزه", "n": 2, "days": 3, "price": 120_000_000, "food": 600},
    {"btn": "🔸 ۳ کارگر | ۱ روزه", "n": 3, "days": 1, "price": 130_000_000, "food": 300},
    {"btn": "🔸 ۳ کارگر | ۲ روزه", "n": 3, "days": 2, "price": 160_000_000, "food": 600},
    {"btn": "🔸 ۳ کارگر | ۳ روزه", "n": 3, "days": 3, "price": 190_000_000, "food": 900},
    {"btn": "🔸 ۴ کارگر | ۱ روزه", "n": 4, "days": 1, "price": 250_000_000, "food": 400},
    {"btn": "🔸 ۴ کارگر | ۲ روزه", "n": 4, "days": 2, "price": 280_000_000, "food": 800},
    {"btn": "🔸 ۴ کارگر | ۳ روزه", "n": 4, "days": 3, "price": 310_000_000, "food": 1200},
    {"btn": "🔸 ۵ کارگر | ۱ روزه", "n": 5, "days": 1, "price": 310_000_000, "food": 500},
    {"btn": "🔸 ۵ کارگر | ۲ روزه", "n": 5, "days": 2, "price": 340_000_000, "food": 1000},
    {"btn": "🔸 ۵ کارگر | ۳ روزه", "n": 5, "days": 3, "price": 370_000_000, "food": 1500},
]
WORKER_BUY_PRICE = 150_000_000
WORKER_FOOD_PER_DAY = 100
FOOD_PACK_PRICE = 90_000_000

HOUSE_ITEMS = [
    {"id": "h1", "btn": "🏕 کلبه کوچک درختی", "price": 50_000_000, "workers": 3, "sat": 3,
     "card": "*🏕 کلبه کوچک درختی*\n\n💰 قیمت: ۵۰ میلیون سکه\n😊 رضایت: ۳٪\n👷‍♂️ کارگران: ۳"},
    {"id": "h2", "btn": "⛺ کلبه بزرگ‌تر و معمولی", "price": 65_000_000, "workers": 5, "sat": 5,
     "card": "*⛺ کلبه بزرگ‌تر و معمولی*\n\n💰 قیمت: ۶۵ میلیون سکه\n😊 رضایت: ۵٪\n👷‍♂️ کارگران: ۵"},
    {"id": "h3", "btn": "🛖 خانه کلنگی", "price": 80_000_000, "workers": 8, "sat": 9,
     "card": "*🛖 خانه کلنگی*\n\n💰 قیمت: ۸۰ میلیون سکه\n😊 رضایت: ۹٪\n👷‍♂️ کارگران: ۸"},
    {"id": "h4", "btn": "🏚 خانه قدیمی زیر بنای محکم", "price": 100_000_000, "workers": 12, "sat": 15,
     "card": "*🏚 خانه قدیمی زیر بنای محکم*\n\n💰 قیمت: ۱۰۰ میلیون سکه\n😊 رضایت: ۱۵٪\n👷‍♂️ کارگران: ۱۲"},
    {"id": "h5", "btn": "🏡 خانه نو زیر بنای محکم", "price": 140_000_000, "workers": 16, "sat": 20,
     "card": "*🏡 خانه نو زیر بنای محکم*\n\n💰 قیمت: ۱۴۰ میلیون سکه\n😊 رضایت: ۲۰٪\n👷‍♂️ کارگران: ۱۶"},
    {"id": "h6", "btn": "🏠 خانه حیاط کوچک نو", "price": 200_000_000, "workers": 20, "sat": 30,
     "card": "*🏠 خانه حیاط کوچک نو*\n\n💰 قیمت: ۲۰۰ میلیون سکه\n😊 رضایت: ۳۰٪\n👷‍♂️ کارگران: ۲۰"},
    {"id": "h7", "btn": "🏠 خانه حیاط بزرگ نو", "price": 290_000_000, "workers": 25, "sat": 40,
     "card": "*🏠 خانه حیاط بزرگ نو*\n\n💰 قیمت: ۲۹۰ میلیون سکه\n😊 رضایت: ۴۰٪\n👷‍♂️ کارگران: ۲۵"},
    {"id": "h8", "btn": "🏡 خانه باغ کوچک تازه", "price": 350_000_000, "workers": 30, "sat": 45,
     "card": "*🏡 خانه باغ کوچک تازه*\n\n💰 قیمت: ۳۵۰ میلیون سکه\n😊 رضایت: ۴۵٪\n👷‍♂️ کارگران: ۳۰"},
    {"id": "h9", "btn": "🏡 خانه باغ بزرگ تازه", "price": 490_000_000, "workers": 40, "sat": 50,
     "card": "*🏡 خانه باغ بزرگ تازه*\n\n💰 قیمت: ۴۹۰ میلیون سکه\n😊 رضایت: ۵۰٪\n👷‍♂️ کارگران: ۴۰"},
    {"id": "h10", "btn": "🏛🏠 ویلا حیاط متوسط", "price": 600_000_000, "workers": 60, "sat": 70,
     "card": "*🏛🏠 ویلا حیاط متوسط*\n\n💰 قیمت: ۶۰۰ میلیون سکه\n😊 رضایت: ۷۰٪\n👷‍♂️ کارگران: ۶۰"},
    {"id": "h11", "btn": "🏠🏡 ویلا حیاط بزرگ", "price": 800_000_000, "workers": 70, "sat": 90,
     "card": "*🏠🏡 ویلا حیاط بزرگ*\n\n💰 قیمت: ۸۰۰ میلیون سکه\n😊 رضایت: ۹۰٪\n👷‍♂️ کارگران: ۷۰"},
    {"id": "h12", "btn": "🏠🏡🏛 ویلا باغ کوچک", "price": 1_300_000_000, "workers": 90, "sat": 120,
     "card": "*🏠🏡🏛 ویلا باغ کوچک*\n\n💰 قیمت: ۱ میلیارد و ۳۰۰ میلیون سکه\n😊 رضایت: ۱۲۰٪\n👷‍♂️ کارگران: ۹۰"},
    {"id": "h13", "btn": "🏠🏡🏛 ویلا باغ بزرگ", "price": 2_000_000_000, "workers": 120, "sat": 190,
     "card": "*🏠🏡🏛 ویلا باغ بزرگ*\n\n💰 قیمت: ۲ میلیارد سکه\n😊 رضایت: ۱۹۰٪\n👷‍♂️ کارگران: ۱۲۰"},
]

NEED_BASE50_TEXT = "*کاربر گرامی⚠️*\n\nابتدا باید ۵۰ عدد مقر هکری تهیه کنید!✔️\n\nهکر ها ابتدا نیاز به مقر دارند!📌"
NEED_PC50_TEXT = "*کاربر گرامی⚠️*\n\nهکر ها نیاز به ۵۰ کامپیوتر پیشرفته دارند!✔️\n\nابتدا کامپیوتر پیشرفته تهیه کنید!📌"
NEED_COMM50_TEXT = "*کاربر گرامی⚠️*\n\nابتدا باید ۵۰ عدد مرکز ارتباطات خریداری کنید!✔️\n\nسپس می توانید کامپیوتر خریداری کنید!📌"
NEED_BASE_FOR_PC = "*کاربر گرامی⚠️*\n\nابتدا باید ۵۰ عدد مقر هکری تهیه کنید!✔️\n\nکامپیوتر ها ابتدا باید در مقر قرار بگیرند!📌"
NO_COIN_TEXT = "*کاربر گرامی⚠️*\n\nسکه شما کافی نیست!✔️\n\nلطفا از فروشگاه خرید کنید!📌"
NO_DIA_TEXT = "*کاربر گرامی⚠️*\n\nالماس شما کافی نیست!✔️\n\nلطفا از فروشگاه خرید کنید!📌"
NO_BOTH_TEXT = "*کاربر گرامی⚠️*\n\nسکه و الماس شما کافی نیست!✔️\n\nلطفا از فروشگاه خرید کنید!📌"
NO_WORKER_TEXT = "*کاربر گرامی⚠️*\n\nشما کارگر مورد نیاز برای انجام این کار را ندارید!✔️\n\nابتدا کارگر خریداری کنید!📌"
NO_FOOD_TEXT = "*کاربر گرامی⚠️*\n\nشما برای خرید این کارگر غذای کافی ندارید!✖️\n\nشما باید از قبل غذای مورد نیاز کارگر را داشته باشید!📌"
HACKED_TEXT = "*کاربر گرامی⚠️*\n\nشما هک شده اید نمی توانید کاری انجام دهید!✔️\n\nپایان هک شدن شما ۱ ساعت طول خواهد کشید!📌"
COUNTRY_DESTROYED_TEXT = "*کاربر گرامی⚠️*\n\nاین کشور نابود شده است!✖️\n\nشما نمی توانید این کشور را مدیریت کنید!📌"
HACK_MENU_TEXT = "*کاربر گرامی⚠️*\n\nشما می توانید از طریق این بخش تیم هکری قدرتمندی بسازید!✔️\n\nجهت خرید هکر، از منوی زیر استفاده کنید!📌"
BUILD_INTRO = "*کاربر گرامی⚠️*\n\nشما می توانید از طریق این بخش، کشور خود را پیشرفت دهید و رضایت مردم خود را جلب کنید!✔️\n\nاگر مردم کشور شما از امکانات کشور راضی نباشند، دست به شورش می زنند و شما نابود خواهید شد!📌"
ASK_DIA_AMOUNT = "*ادمین گرامی⚠️*\n\nتعداد الماس مورد نیاز برای اهدا را وارد نمایید!✔️\n\nتنها عدد ارسال کنید!📌"
ASK_DIA_DEDUCT = "*ادمین گرامی⚠️*\n\nتعداد الماس مورد نیاز برای کسر را وارد نمایید!✔️\n\nتنها عدد ارسال کنید!📌"
ASK_COIN_AMOUNT = "*ادمین گرامی⚠️*\n\nجهت افزایش سکه باید با فرمت زیر میزان سکه را وارد کنید!✔️\n\n*مثال : ۵۰۰ میلیون📌*"
ASK_COIN_DEDUCT = "*ادمین گرامی⚠️*\n\nجهت کسر سکه باید با فرمت زیر میزان سکه را وارد کنید!✔️\n\n*مثال : ۵۰۰ میلیون📌*"


# ───────────────────────────── تجهیزات جنگی ─────────────────────────────
def _w(name, pm, pw, dia=0, pt=None):
    return {"name": name, "price": pm * 1_000_000, "power": pw, "dia": dia,
            "price_t": pt or mil_fa(pm)}

WAR_CATS = [
    {"key": "tank", "btn": "🛡 تانک ها", "phrase": "تانک مورد نظر خود را انتخاب نمایید", "items": [
        _w("🛡️ ۱ دستگاه M1A2 SEPv3 Abrams — ام۱آ۲ اس‌ای‌پی وی۳ آبرامز", 150, 130),
        _w("🛡️ ۱ دستگاه Leopard 2A7V — لئوپارد ۲آ۷وی", 160, 140),
        _w("🛡️ ۱ دستگاه Challenger 2 (TES) — چلنجر ۲", 170, 160),
        _w("🛡️ ۱ دستگاه Merkava Mk.4 Barak — مرکاوا مارک ۴ باراک", 180, 170),
        _w("🛡️ ۱ دستگاه Type 99A — تایپ ۹۹آ", 190, 180),
        _w("🛡️ ۱ دستگاه K2 Black Panther — کی۲ پلنگ سیاه", 200, 190),
        _w("🛡️ ۱ دستگاه Leclerc XLR — لکلرک ایکس‌ال‌آر", 210, 200),
        _w("🛡️ ۱ دستگاه Type 10 — تایپ ۱۰", 220, 210),
        _w("🛡️ ۱ دستگاه Altay — آلتای", 230, 220),
        _w("🛡️ ۱ دستگاه T-84 Oplot-M — تی-۸۴ اوپلوت-ام", 240, 230),
        _w("🛡️ ۱ دستگاه T-90MS — تی-۹۰ام‌اس", 250, 240),
        _w("🛡️ ۱ دستگاه Arjun Mk.1A — آرجون مارک ۱آ", 260, 250),
        _w("🛡️ ۱ دستگاه Al-Khalid I — الخالد ۱", 280, 265),
        _w("🛡️ ۱ دستگاه Zulfiqar-3 — ذوالفقار ۳", 310, 290),
        _w("🛡️ ۱ دستگاه T-14 Armata — تی-۱۴ آرماتا", 340, 320),
    ]},
    {"key": "ground", "btn": "🪖 نیروهای زمینی", "phrase": "نیروی زمینی مورد نظر خود را انتخاب نمایید", "items": [
        _w("🪖 ۱۰۰ نفر Delta Force — دلتا فورس", 150, 100),
        _w("🪖 ۱۰۰ نفر Navy SEALs — نیروی دریایی (سیلز)", 160, 110),
        _w("🪖 ۱۰۰ نفر SAS (Special Air Service) — اس‌ای‌اس (نیروی هوایی ویژه)", 170, 150),
        _w("🪖 ۱۰۰ نفر Spetsnaz GRU — اسپتسناز گرو", 180, 160),
        _w("🪖 ۱۰۰ نفر Sayeret Matkal — سایرت ماتکال", 190, 170),
        _w("🪖 ۱۰۰ نفر GIGN — ژیگن (ژاندارمری ویژه)", 200, 190),
        _w("🪖 ۱۰۰ نفر KSK (Kommando Spezialkräfte) — کی‌اس‌کی (نیروی ویژه آلمان)", 220, 200),
        _w("🪖 ۱۰۰ نفر GIS (Gruppo di Intervento Speciale) — جی‌آی‌اس (نیروی ویژه ایتالیا)", 240, 230),
        _w("🪖 ۱۰۰ نفر SOF (Special Operations Forces) — نیروی ویژه چین", 260, 250),
        _w("🪖 ۱۰۰ نفر صابرین — یگان ویژه نیروی زمینی", 280, 270),
    ]},
    {"key": "surface", "btn": "🚢 ناوهای جنگی سطحی", "phrase": "ناو جنگی مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚢 ۱ فروند Sa'ar 6 Corvette — کوروت ساعر ۶", 180, 150),
        _w("🚢 ۱ فروند Buyan-M Corvette — کوروت بویان-ام", 200, 200),
        _w("🚢 ۱ فروند FREMM Frigate — ناوچه فرم", 300, 250),
        _w("🚢 ۱ فروند Type 23 Frigate — ناوچه تایپ ۲۳", 320, 300),
        _w("🚢 ۱ فروند Arleigh Burke Destroyer — ناوشکن آرلی برک", 600, 500),
        _w("🚢 ۱ فروند Type 45 Destroyer — ناوشکن تایپ ۴۵", 650, 600),
        _w("🚢 ۱ فروند Zumwalt Destroyer — ناوشکن زاموالت", 800, 750),
        _w("🚢 ۱ فروند Ticonderoga Cruiser — رزم‌ناو تیکاندروگا", 900, 850),
        _w("🚢 ۱ فروند Kirov Cruiser — رزم‌ناو کیروف", 1000, 950),
    ]},
    {"key": "carrier", "btn": "✈️ ناو های هواپیمابر", "phrase": "ناو هواپیمابر مورد نظر خود را انتخاب نمایید", "items": [
        _w("✈️ ۱ فروند Cavour — کاوور", 2500, 2000),
        _w("✈️ ۱ فروند Charles de Gaulle — شارل دوگل", 3000, 2500),
        _w("✈️ ۱ فروند Queen Elizabeth — کوئین الیزابت", 3200, 3000, 0, "۳.۲ میلیارد سکه"),
        _w("✈️ ۱ فروند Nimitz-class — نیمیتز", 3500, 3300),
        _w("✈️ ۱ فروند Gerald R. Ford — جرالد فورد", 4000, 3500),
    ]},
    {"key": "patrol", "btn": "🛥 قایق‌های گشتی", "phrase": "قایق گشتی مورد نظر خود را انتخاب نمایید", "items": [
        _w("🛥️ ۴۰ فروند Sentinel-class — سنتینل", 20, 10),
        _w("🛥️ ۴۰ فروند Type 037 Hainan — تایپ ۰۳۷ هاینان", 20, 10),
        _w("🛥️ ۴۰ فروند Project 22460 Okhotnik — اوخوتنیک", 20, 10),
        _w("🛥️ ۴۰ فروند Moudge-class — موج", 20, 10),
        _w("🛥️ ۴۰ فروند L'Adroit Gowind — لادروا", 20, 10),
        _w("🛥️ ۴۰ فروند Comandanti-class — کوماندانتی", 20, 10),
        _w("🛥️ ۴۰ فروند Hayabusa-class — هایابوسا", 20, 10),
        _w("🛥️ ۴۰ فروند Armidale-class — آرمیدال", 20, 10),
        _w("🛥️ ۴۰ فروند Tuzla-class — توزلا", 20, 10),
        _w("🛥️ ۴۰ فروند Island-class — آیلند", 20, 10),
        _w("🛥️ ۴۰ فروند River-class — ریور", 20, 10),
        _w("🛥️ ۴۰ فروند Kingston-class — کینگستون", 20, 10),
        _w("🛥️ ۴۰ فروند Nornen-class — نورنن", 20, 10),
        _w("🛥️ ۴۰ فروند Stockholm-class — استکهلم", 20, 10),
    ]},
    {"key": "speed", "btn": "🚤 قایق های تندرو", "phrase": "قایق تندرو مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚤 ۴۰ فروند MK V Special Ops — ام‌کی ۵ ویژه", 30, 20),
        _w("🚤 ۴۰ فروند CB90 — سی‌بی ۹۰", 30, 20),
        _w("🚤 ۴۰ فروند Skjold-class — اسکیولد", 30, 20),
        _w("🚤 ۴۰ فروند Tondar-class — توندار", 30, 20),
        _w("🚤 ۴۰ فروند Cigarette 46' Shadow — سیگارت شادو", 30, 20),
        _w("🚤 ۴۰ فروند Project 12150 Mangust — مانگوست", 30, 20),
        _w("🚤 ۴۰ فروند S-100-class — اس-۱۰۰", 30, 20),
        _w("🚤 ۴۰ فروند Super Dvora Mk III — سوپر دوورا", 30, 20),
        _w("🚤 ۴۰ فروند Type 722 — تایپ ۷۲۲", 30, 20),
        _w("🚤 ۴۰ فروند Cutlass-class — کاتلاس", 30, 20),
        _w("🚤 ۴۰ فروند Cyclone-class — سیکلون", 30, 20),
        _w("🚤 ۴۰ فروند Project 14310 — پروژه ۱۴۳۱۰", 30, 20),
    ]},
    {"key": "mboat", "btn": "🚀 قایق‌های موشک‌انداز", "phrase": "قایق موشک‌انداز مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚀 ۴۰ فروند Type 022 Houbei — تایپ ۰۲۲ هوبی", 50, 40),
        _w("🚀 ۴۰ فروند Project 1241 Tarantul — تارانتول", 50, 40),
        _w("🚀 ۴۰ فروند Peykaap-class — پیکاپ", 50, 40),
        _w("🚀 ۴۰ فروند Combattante BR70 — کمبتانته", 50, 40),
        _w("🚀 ۴۰ فروند Gepard-class — گپارد", 50, 40),
        _w("🚀 ۴۰ فروند PKG Yoon Youngha — یون یونگ‌ها", 50, 40),
        _w("🚀 ۴۰ فروند Kılıç-class — کیلیچ", 50, 40),
        _w("🚀 ۴۰ فروند Ambassador Mk III — آمباسادور", 50, 40),
        _w("🚀 ۴۰ فروند Sa'ar 4.5 — ساعر ۴.۵", 50, 40),
        _w("🚀 ۴۰ فروند Molniya-class — مولنیا", 50, 40),
        _w("🚀 ۴۰ فروند Pegasus-class — پگاسوس", 50, 40),
        _w("🚀 ۴۰ فروند Project 206MR — پروژه ۲۰۶ام‌آر", 50, 40),
        _w("🚀 ۴۰ فروند Type 021 — تایپ ۰۲۱", 50, 40),
    ]},
    {"key": "sub", "btn": "🚢 زیر‌دریایی‌ها", "phrase": "زیردریایی مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚢 ۱ فروند Type 209 — تایپ ۲۰۹", 700, 700),
        _w("🚢 ۱ فروند Kilo-class — کیلو", 850, 1000),
        _w("🚢 ۱ فروند Yasen-class — یاسن", 1200, 1300),
        _w("🚢 ۱ فروند Virginia-class — ویرجینیا", 1400, 1500),
        _w("🚢 ۱ فروند Ohio-class — اوهایو", 1700, 2000),
    ]},
    {"key": "drone", "btn": "🛩 پهپادهای رزمی", "phrase": "پهپاد رزمی مورد نظر خود را انتخاب نمایید", "items": [
        _w("🛩️ ۲۰ فروند Shahed-136 — شاهد-۱۳۶", 20, 10),
        _w("🛩️ ۲۰ فروند Bayraktar TB2 — بایراکتار تی‌بی۲", 60, 50),
        _w("🛩️ ۲۰ فروند Bayraktar Akıncı — آقینجی", 90, 100),
        _w("🛩️ ۲۰ فروند MQ-9 Reaper — ام‌کیو-۹ ریپر", 120, 120),
        _w("🛩️ ۲۰ فروند RQ-4 Global Hawk — گلوبال هاوک", 140, 150),
        _w("🛩️ ۲۰ فروند RQ-170 Sentinel — آرکیو-۱۷۰", 300, 180),
        _w("🛩️ ۲۰ فروند MQ-25 Stingray — ام‌کیو-۲۵", 450, 300),
    ]},
    {"key": "heli", "btn": "🚁 بالگردهای نظامی", "phrase": "بالگرد نظامی مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚁 ۲۵ فروند Mil Mi-8 — میل-۸", 40, 20),
        _w("🚁 ۲۵ فروند UH-60 Black Hawk — بلک هاوک", 50, 40),
        _w("🚁 ۲۵ فروند CH-47 Chinook — شینوک", 80, 80),
        _w("🚁 ۲۵ فروند Mil Mi-24 Hind — میل-۲۴", 90, 100),
        _w("🚁 ۳۰ فروند AH-64 Apache — آپاچی", 120, 120),
        _w("🚁 ۲۵ فروند Ka-52 Alligator — کاموف-۵۲", 140, 180),
    ]},
    {"key": "bomber", "btn": "💣 بمب افکن ها", "phrase": "بمب‌افکن مورد نظر خود را انتخاب نمایید", "items": [
        _w("💣 ۳ بمب‌افکن B-52 Stratofortress — بی-۵۲ استراتوفورترس", 500, 900),
        _w("💣 ۳ بمب‌افکن Tu-95 Bear — توپولوف-۹۵", 650, 1000),
        _w("💣 ۳ بمب‌افکن B-1B Lancer — بی-۱بی لنسر", 700, 1100),
        _w("💣 ۳ بمب‌افکن Tu-160 White Swan — توپولوف-۱۶۰", 900, 1200),
        _w("💣 ۳ بمب‌افکن B-2 Spirit — بی-۲ اسپیریت", 3200, 3000),
    ]},
    {"key": "fighter", "btn": "✈️ جنگنده ها", "phrase": "جنگنده مورد نظر خود را انتخاب نمایید", "items": [
        _w("✈️ ۱۵ جنگنده F-16 Fighting Falcon — اف-۱۶ فالکن", 80, 50),
        _w("✈️ ۱۵ جنگنده F/A-18 Hornet — اف-۱۸ هورنت", 90, 100),
        _w("✈️ ۱۵ جنگنده Mirage 2000 — میراژ ۲۰۰۰", 100, 150),
        _w("✈️ ۱۵ جنگنده MiG-29 Fulcrum — میگ-۲۹", 120, 200),
        _w("✈️ ۱۵ جنگنده F-15 Eagle — اف-۱۵ ایگل", 130, 250),
        _w("✈️ ۱۵ جنگنده Su-27 Flanker — سوخو-۲۷", 150, 300),
        _w("✈️ ۱۵ جنگنده Eurofighter Typhoon — یوروفایتر تایفون", 170, 350),
        _w("✈️ ۱۵ جنگنده Dassault Rafale — رافال", 180, 400),
        _w("✈️ ۱۵ جنگنده Su-30 — سوخو-۳۰", 190, 450),
        _w("✈️ ۱۵ جنگنده Su-35 — سوخو-۳۵", 220, 500),
        _w("✈️ ۱۵ جنگنده F-35 Lightning II — اف-۳۵ لایتنینگ ۲", 300, 550),
        _w("✈️ ۱۵ جنگنده Su-57 Felon — سوخو-۵۷", 350, 600),
        _w("✈️ ۱۵ جنگنده J-20 Mighty Dragon — جی-۲۰", 400, 650),
        _w("✈️ ۱۵ جنگنده F-22 Raptor — اف-۲۲ رپتور", 450, 700),
    ]},
    {"key": "cruise", "btn": "🚀 موشک‌های کروز", "phrase": "موشک کروز مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚀 ۱۰ فروند Tomahawk Block V — توماهاوک بلوک ۵", 200, 500),
        _w("🚀 ۱۰ فروند Kalibr-M — کالیبر-ام", 210, 550),
        _w("🚀 ۱۰ فروند Storm Shadow / SCALP — استورم شدو / اسکالپ", 220, 600),
        _w("🚀 ۱۰ فروند CJ-10 (DH-10) — سی‌جی-۱۰", 230, 650),
        _w("🚀 ۱۰ فروند AGM-158C LRASM — ای‌جی‌ام-۱۵۸سی ال‌آر‌ای‌اس‌ام", 240, 700),
        _w("🚀 ۱۰ فروند Soumar — سومار", 250, 750),
        _w("🚀 ۱۰ فروند Hyunmoo-3 — هیونمو-۳", 260, 800),
        _w("🚀 ۱۰ فروند Type 12 (SSM) — تایپ ۱۲", 270, 850),
        _w("🚀 ۱۰ فروند BrahMos — برهموس", 280, 900),
        _w("🚀 ۱۰ فروند SOM — سوم", 300, 950),
    ]},
    {"key": "ballistic", "btn": "🚀 موشک‌های بالستیک", "phrase": "موشک بالستیک مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚀 ۱۰ فروند Iskander-M — اسکندر-ام", 310, 1000),
        _w("🚀 ۱۰ فروند Khorramshahr — خرمشهر", 320, 1050),
        _w("🚀 ۱۰ فروند DF-21D — دی‌اف-۲۱دی", 330, 1100),
        _w("🚀 ۱۰ فروند PrSM — پی‌آر‌اس‌ام", 340, 1150),
        _w("🚀 ۱۰ فروند Topol-M — توپول-ام", 350, 1200),
        _w("🚀 ۱۰ فروند DF-26 — دی‌اف-۲۶", 360, 1250),
        _w("🚀 ۱۰ فروند Minuteman III — مینیوتمن ۳", 370, 1300),
        _w("🚀 ۱۰ فروند Agni-V — آگنی-۵", 380, 1350),
        _w("🚀 ۱۰ فروند Hwasong-17 — هواسونگ-۱۷", 390, 1400),
        _w("🚀 ۱۰ فروند Sejjil — سجیل", 400, 1450),
    ]},
    {"key": "hyper", "btn": "🚀 موشک‌های هایپرسونیک", "phrase": "موشک هایپرسونیک مورد نظر خود را انتخاب نمایید", "items": [
        _w("🚀 ۱۰ فروند 3M22 Zircon — ۳ام-۲۲ زیرکون", 450, 1500, 20000),
        _w("🚀 ۱۰ فروند DF-17 — دی‌اف-۱۷", 460, 1550, 25000),
        _w("🚀 ۱۰ فروند AGM-183A ARRW — ای‌جی‌ام-۱۸۳ای آر‌آر‌دبلیو", 470, 1600, 30000),
        _w("🚀 ۱۰ فروند Kh-47M2 Kinzhal — خا-۴۷ام۲ کینژال", 480, 1650, 35000),
        _w("🚀 ۱۰ فروند DF-100 — دی‌اف-۱۰۰", 500, 1700, 40000),
        _w("🚀 ۱۰ فروند Fattah-1 — فتاح-۱", 520, 1750, 45000),
        _w("🚀 ۱۰ فروند Avangard — آوانگارد", 580, 1850, 55000),
        _w("🚀 ۱۰ فروند DF-41 — دی‌اف-۴۱", 600, 2000, 60000),
    ]},
]
WAR_CAT_MAP = {c["key"]: c for c in WAR_CATS}

FLAG_URLS = {'UN': 'https://uploadkon.ir/uploads/e9e220_261280px-Flag-of-the-United-Nations-svg.png', 'USA': 'https://uploadkon.ir/uploads/a9e716_26usaflag-222.png', 'China': 'https://uploadkon.ir/uploads/19e416_2629d375a6-ebe1-496b-bb81-277c7de18f7f.jpg', 'Russia': 'https://uploadkon.ir/uploads/926016_26nody-عکس-پرچم-چین-1634413767.jpg', 'India': 'https://uploadkon.ir/uploads/93b716_2610402854-409.jpg', 'UK': 'https://uploadkon.ir/uploads/f4fd16_26bc61e3b1-4084-4e94-b48c-64524ca80311.jpg', 'France': 'https://uploadkon.ir/uploads/ea4e16_26پرچم-فرانسه.jpg', 'Germany': 'https://uploadkon.ir/uploads/6c8b16_26nody-عکس-پرچم-آلمان-خفن-1739127311.jpg', 'NorthKorea': 'https://uploadkon.ir/uploads/8ed716_26کره-شمالی.jpg', 'Japan': 'https://uploadkon.ir/uploads/365916_26Shfg1000373www-tiktarh-com-.jpg', 'SouthKorea': 'https://uploadkon.ir/uploads/c25a16_26کره-جنوبی.jpg', 'Turkey': 'https://uploadkon.ir/uploads/bdf216_261033919-اهتزاز-پرچم-ترکیه.jpg', 'Italy': 'https://uploadkon.ir/uploads/50cb16_26Shfg1000369www-tiktarh-com-.jpg', 'Brazil': 'https://uploadkon.ir/uploads/e9e416_26New-Project-2024-07-29T133705-741.jpg', 'Canada': 'https://uploadkon.ir/uploads/e90216_26Screenshot-20260916-161612-Google.jpg', 'Australia': 'https://uploadkon.ir/uploads/3d8c16_26Screenshot-20260916-161859-Google.jpg', 'Israel': 'https://uploadkon.ir/uploads/8d5116_26پرچم-اسرائیل.jpg', 'Spain': 'https://uploadkon.ir/uploads/f24a16_26Screenshot-20260916-162129-Google.jpg', 'SaudiArabia': 'https://uploadkon.ir/uploads/9aca16_26Screenshot-20260916-162258-Google.jpg', 'Iran': 'https://uploadkon.ir/uploads/393d16_26157214837.jpg', 'Pakistan': 'https://uploadkon.ir/uploads/db6216_26پرچم-پاکستان.jpg', 'Indonesia': 'https://uploadkon.ir/uploads/b5c416_26139211301101184342163924.jpg', 'Mexico': 'https://uploadkon.ir/uploads/504216_26Mexican-Flag.jpg', 'Netherlands': 'https://uploadkon.ir/uploads/c60216_26The-meaning-of-the-color-of-the-Dutch-flag.jpg', 'Poland': 'https://uploadkon.ir/uploads/055016_261130264-پرچم-لهستان.jpg', 'Sweden': 'https://uploadkon.ir/uploads/a38c16_26nody-ولوسوئدی-کد-شاپور-سنگین-1739138706.jpg', 'Norway': 'https://uploadkon.ir/uploads/9e5416_26Shfg1000393www-tiktarh-com-.jpg', 'SouthAfrica': 'https://uploadkon.ir/uploads/69f916_26south-african-2001-500x333.jpg', 'Egypt': 'https://uploadkon.ir/uploads/449a16_26nody-کشور-مصر-1634835570.jpg', 'UAE': 'https://uploadkon.ir/uploads/82a416_26dubai-flag-differences.jpg', 'Singapore': 'https://uploadkon.ir/uploads/5b4c16_26IMG18411323.jpg', 'Switzerland': 'https://uploadkon.ir/uploads/db1316_26nody-مهاجرت-به-سوئیس-1634422410.jpg', 'Ukraine': 'https://uploadkon.ir/uploads/a25916_26Shfg1000316www-tiktarh-com-.jpg', 'Malaysia': 'https://uploadkon.ir/uploads/4aba16_2667785.jpg', 'Yemen': 'https://uploadkon.ir/uploads/704f16_26nody-پرچم-کشورجهان،معنی-نام-کشورها،پایتخت-کشورها-پارسه-پرچم-1739150052.png', 'Argentina': 'https://uploadkon.ir/uploads/e15316_26Shfg1000214www-tiktarh-com-.jpg', 'Thailand': 'https://uploadkon.ir/uploads/f04316_26nody-دانلود-عکس-پرچم-کشور-تایلند-1652040012.jpg', 'Vietnam': 'https://uploadkon.ir/uploads/ae9016_26nody-علت-جنگ-ویتنام-1634892030.jpg'}


# ───────────────────────────── ذخیره‌سازی ─────────────────────────────
LOCK = threading.RLock()
DATA = {"users": {}, "countries": {}, "destroyed": {}}
PENDING = {}
SPAM_HITS = {}  # uid -> [timestamps]
   # آیدی کاربر -> وضعیت موقت (ادمین یا انتخاب کشور/خرید)

def load_data():
    global DATA
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                DATA = json.load(f)
        except Exception as e:
            print("[DATA] خطا در خواندن فایل:", e)
    DATA.setdefault("users", {})
    DATA.setdefault("countries", {})
    DATA.setdefault("destroyed", {})
    DATA.setdefault("custom_buttons", [])  # [{"id","name","text"}]
    DATA.setdefault("bot_on", True)
    DATA.setdefault("deleted_button_names", [])
    # سازمان ملل همیشه متعلق به ادمین دوم
    un = DATA["countries"].get("UN")
    if not isinstance(un, dict):
        DATA["countries"]["UN"] = {
            "owner": UN_OWNER_ID, "power": BASE_COUNTRY_POWER,
            "hacked_until": None, "start_ts": time.time(),
        }
    else:
        DATA["countries"]["UN"]["owner"] = UN_OWNER_ID
    ou = DATA["users"].get(str(UN_OWNER_ID))
    if ou is not None:
        ou["country"] = "UN"
    # مهاجرت ساختار قدیمی countries[en]=uid → dict
    for en, val in list(DATA["countries"].items()):
        if not isinstance(val, dict):
            owner = val
            DATA["countries"][en] = {
                "owner": owner,
                "power": BASE_COUNTRY_POWER,
                "hacked_until": None,
                "start_ts": time.time(),
            }
            ou = DATA["users"].get(str(owner))
            if ou is not None and not ou.get("country_start"):
                ou["country_start"] = time.time()

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=1)

def get_user(uid):
    uid = str(uid)
    u = DATA["users"].get(uid)
    if u is None:
        u = {"coins": START_COINS, "diamonds": 0, "oil": 0, "food": 0, "country": None,
             "banned": False, "equipment": {}, "printer": 0, "nuke_def": False,
             "hq": 0, "pc": 0, "comm": 0, "sat": 0,
             "hackers": {}, "antihackers": {},
             "workers_perm": 0, "workers_temp": [], "houses": {},
             "satisfaction": 0, "hack_until": None, "country_start": None, "def_hp": {}, "warnings": 0, "blocked": False}
        DATA["users"][uid] = u
        save_data()
    else:
        for k, v in {"coins": START_COINS, "diamonds": 0, "oil": 0, "food": 0,
                     "country": None, "banned": False, "equipment": {},
                     "printer": 0, "nuke_def": False, "hq": 0, "pc": 0, "comm": 0, "sat": 0,
                     "hackers": {}, "antihackers": {}, "workers_perm": 0,
                     "workers_temp": [], "houses": {}, "satisfaction": 0,
                     "hack_until": None, "country_start": None, "def_hp": {}, "warnings": 0, "blocked": False}.items():
            u.setdefault(k, v)
    return u

# ───────────────────────────── ارتباط با API بله ─────────────────────────────
SESSION = requests.Session()

def api(method, **params):
    for _ in range(2):
        try:
            r = SESSION.post(API_BASE + "/" + method, json=params, timeout=40)
            return r.json()
        except Exception as e:
            print(f"[API] {method} خطا: {e}")
            time.sleep(1)
    return {"ok": False, "description": "network error"}

def IK(rows):
    """InlineKeyboard (شیشه‌ای) — فقط برای تأیید/لغو"""
    return [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]

def RK(rows, resize=True, one_time=False):
    """ReplyKeyboardMarkup (دکمه اصلی ربات)"""
    keyboard = [[{"text": t} for t in row] for row in rows]
    return {
        "keyboard": keyboard,
        "resize_keyboard": resize,
        "one_time_keyboard": one_time,
    }

def send_message(chat_id, text, reply_markup=None, md=True):
    payload = {"chat_id": chat_id, "text": text[:4000]}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if md:
        payload["parse_mode"] = "Markdown"
    res = api("sendMessage", **payload)
    if not res.get("ok") and md:
        payload["text"] = text.replace("*", "")[:4000]
        payload.pop("parse_mode", None)
        res = api("sendMessage", **payload)
    return res

def edit_message(chat_id, message_id, text, keyboard=None):
    """فقط برای پیام‌های شیشه‌ای (تأیید/لغو)"""
    payload = {"chat_id": chat_id, "message_id": message_id,
               "text": text[:4000], "parse_mode": "Markdown"}
    if keyboard is not None:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    res = api("editMessageText", **payload)
    if res.get("ok"):
        return res
    if "not modified" in str(res.get("description", "")).lower():
        return res
    payload.pop("parse_mode", None)
    payload["text"] = text.replace("*", "")[:4000]
    res = api("editMessageText", **payload)
    if not res.get("ok") and "not modified" not in str(res.get("description", "")).lower():
        send_message(chat_id, text, {"inline_keyboard": keyboard} if keyboard else None)
    return res

# ───────────────────────────── کیبوردهای اصلی (Reply) ─────────────────────────────

def war_eq_info(eq_id):
    """eq_id مثل tank_1 -> (cat_key, idx, item_dict) یا None"""
    if "_" not in str(eq_id):
        return None
    key, num = str(eq_id).rsplit("_", 1)
    if not num.isdigit():
        return None
    cat = WAR_CAT_MAP.get(key)
    if not cat:
        return None
    idx = int(num) - 1
    if idx < 0 or idx >= len(cat["items"]):
        return None
    return key, idx, cat["items"][idx]

def war_eq_short_name(eq_id):
    info = war_eq_info(eq_id)
    if not info:
        return str(eq_id)
    name = info[2]["name"]
    # کوتاه: بعد از اولین — یا کل
    if " — " in name:
        return name.split(" — ", 1)[-1][:40]
    return name[:40]

def user_war_equipment(u):
    """لیست (eq_id, count, item) از تجهیزات جنگی کاربر"""
    out = []
    eq = u.get("equipment") or {}
    for eid, cnt in list(eq.items()):
        try:
            c = int(cnt or 0)
        except (TypeError, ValueError):
            continue
        if c <= 0:
            continue
        info = war_eq_info(str(eid))
        if info:
            out.append((str(eid), c, info[2]))
    return out

def ensure_def_hp(u):
    """اگر def_hp برای تجهیز دفاعی موجود نباشد، از روی تعداد × قدرت پر می‌شود."""
    hp = u.setdefault("def_hp", {})
    eq = u.setdefault("equipment", {})
    for it in DEF_ITEMS:
        eid = it["id"]
        cnt = int(eq.get(eid, 0) or 0)
        full = it["power"] * cnt
        if cnt <= 0:
            hp[eid] = 0
            continue
        cur = int(hp.get(eid, 0) or 0)
        # اگر هنوز مقدار ندارد یا صفر است ولی واحد داریم → پر کن
        if eid not in hp or cur <= 0:
            hp[eid] = full
        # اگر واحد اضافه خریده شده و HP کمتر از حداکثر است، فقط به اندازه واحد جدید اضافه کن
        elif cur < full:
            # افزایش فقط وقتی count بالا رفته (نه وقتی آسیب خورده)
            # اگر cur مضربی از power نیست یعنی آسیب دیده — دست نزن مگر count بیشتر شده
            max_from_hp = (cur + it["power"] - 1) // it["power"] if it["power"] else 0
            if cnt > max_from_hp:
                hp[eid] = cur + it["power"] * (cnt - max_from_hp)
        elif cur > full:
            hp[eid] = full
    return hp


def total_def_power(u):
    ensure_def_hp(u)
    return sum(int(v or 0) for v in (u.get("def_hp") or {}).values())

def apply_defense(u, atk_power):
    """دفاع از قوی‌ترین. (آسیب_باقی‌مانده_به_کشور, لیست_استفاده)"""
    ensure_def_hp(u)
    hp = u.setdefault("def_hp", {})
    eq = u.setdefault("equipment", {})
    remaining_atk = int(atk_power)
    used_log = []
    order = sorted(DEF_ITEMS, key=lambda x: -x["power"])
    for it in order:
        if remaining_atk <= 0:
            break
        eid = it["id"]
        cur = int(hp.get(eid, 0) or 0)
        if cur <= 0:
            continue
        absorbed = min(cur, remaining_atk)
        new_hp = cur - absorbed
        hp[eid] = new_hp
        remaining_atk -= absorbed
        # همگام‌سازی تعداد واحد با HP باقی‌مانده
        if new_hp <= 0:
            eq[eid] = 0
            hp[eid] = 0
        else:
            # واحدهای کامل باقی + اگر کسری HP باشد یک واحد جزئی
            eq[eid] = max(1, (new_hp + it["power"] - 1) // it["power"])
        used_log.append({
            "name": it["btn"],
            "absorbed": absorbed,
            "left": new_hp,
        })
    # پاک کردن صفرها
    for eid in list(eq.keys()):
        if int(eq.get(eid, 0) or 0) <= 0 and str(eid).startswith("def"):
            eq.pop(eid, None)
            hp[eid] = 0
    return remaining_atk, used_log


def send_photo(chat_id, photo_url, caption, md=True):
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": (caption or "")[:1024]}
    if md:
        payload["parse_mode"] = "Markdown"
    res = api("sendPhoto", **payload)
    if not res.get("ok") and md:
        payload.pop("parse_mode", None)
        payload["caption"] = (caption or "").replace("*", "")[:1024]
        res = api("sendPhoto", **payload)
    return res

def post_attack_log(atk_name, def_name, damage, destroyed=False, destroyed_name=None):
    nl = "\n"
    text = (
        "حمله بزرگ انجام شد!🚀" + nl + nl +
        f"کشور حمله کننده : {atk_name}" + nl +
        f"کشور دفاع کننده : {def_name}" + nl +
        f"میزان تخریب : {fad(damage)} قدرت 💣"
    )
    try:
        send_message(CHANNEL_USERNAME, text, md=False)
    except Exception as e:
        print("[CHANNEL]", e)
    if destroyed and destroyed_name:
        t2 = (
            f"کشور {destroyed_name} توسط حمله {atk_name} به صورت کامل تخریب شد!🚀" + nl + nl +
            f"{destroyed_name} از روی کره زمین محو شد و دیگر کشوری به نام {destroyed_name} وجود نخواهد داشت! 💣" + nl + nl +
            f"خداحافظ {destroyed_name} !"
        )
        try:
            send_message(CHANNEL_USERNAME, t2, md=False)
        except Exception as e:
            print("[CHANNEL]", e)


def owned_countries_kb(exclude_en=None):
    rows, row = [], []
    for flag, en, name, vip in COUNTRIES:
        if DATA.get("destroyed", {}).get(en):
            continue
        c = DATA["countries"].get(en)
        if not c or not isinstance(c, dict) or not c.get("owner"):
            continue
        if exclude_en and en == exclude_en:
            continue
        row.append(f"⚔ {flag} {name}")
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if not rows:
        rows.append(["— کشوری برای حمله نیست —"])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def attack_force_btn_label(eid, cnt=None):
    """متن دکمه نیرو برای حمله — ایموجی + نام اصلی آیتم، بدون ×"""
    info = war_eq_info(eid)
    if not info:
        return str(eid)
    name = (info[2].get("name") or "").strip()
    # همان متن اصلی (شامل ایموجی اول)
    return _war_btn_label(name, max_len=64)

def attack_force_kb(u, force):
    """دکمه‌های تجهیزات جنگی کاربر + حمله اگر force غیرخالی"""
    rows = []
    items = user_war_equipment(u)
    if not items:
        rows.append(["— نیروی جنگی ندارید —"])
    for eid, cnt, it in items:
        rows.append([attack_force_btn_label(eid)])
    if force:
        rows.append(["حمله🚀"])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def do_military_attack(atk_uid, target_en, force):
    """force: {eq_id: count}"""
    au = get_user(atk_uid)
    if is_hacked(au):
        return False, HACKED_TEXT
    if not au.get("country"):
        return False, NEED_COUNTRY_TEXT
    if not force:
        return False, "*کاربر گرامی⚠️*\n\nابتدا نیرو انتخاب کنید!✔️"

    with LOCK:
        c = DATA["countries"].get(target_en)
        if not c or not isinstance(c, dict) or not c.get("owner"):
            return False, "*کاربر گرامی⚠️*\n\nاین کشور مدیر ندارد!✔️"
        if DATA.get("destroyed", {}).get(target_en):
            return False, COUNTRY_DESTROYED_TEXT
        if target_en == au.get("country"):
            return False, "*کاربر گرامی⚠️*\n\nبه کشور خودتان نمی‌توانید حمله کنید!✔️"

        total_units = 0
        atk_power = 0
        for eid, cnt in list(force.items()):
            cnt = int(cnt or 0)
            if cnt <= 0:
                continue
            info = war_eq_info(eid)
            if not info:
                continue
            have = int((au.get("equipment") or {}).get(eid, 0) or 0)
            if cnt > have:
                return False, (
                    f"*کاربر گرامی⚠️*\n\nنیرو های شما کمتر از {fad(cnt)} است!✔️\n\n"
                    f"شما نیروی کافی برای حمله با این تعداد نیرو ندارید!📌"
                )
            total_units += cnt
            # قدرت هر واحد × تعداد ارسالی
            atk_power += int(info[2]["power"]) * cnt

        if total_units <= 0 or atk_power <= 0:
            return False, "*کاربر گرامی⚠️*\n\nابتدا نیرو انتخاب کنید!✔️"

        oil_need = total_units * OIL_COST_PER_UNIT
        oil_have = int(au.get("oil") or 0)
        if oil_have < oil_need:
            return False, (
                f"*کاربر گرامی⚠️*\n\nجهت حمله با این تعداد نیرو باید {fad(oil_need)} بشکه نفت داشته باشید!✔️\n\n"
                f"شما تنها {fad(oil_have)} بشکه نفت دارید! بشکه نفت شما برای حمله با این مقدار نیرو کافی نیست!📌"
            )

        def_uid = c["owner"]
        du = get_user(def_uid)
        atk_name = country_name_fa(au.get("country"))
        def_name = country_name_fa(target_en)
        had_def = total_def_power(du) > 0

        if is_hacked(du):
            damage = atk_power
            used_log = []
        else:
            damage, used_log = apply_defense(du, atk_power)

        # کسر نیرو و نفت مهاجم
        for eid, cnt in force.items():
            cnt = int(cnt or 0)
            if cnt <= 0:
                continue
            cur = int((au.get("equipment") or {}).get(eid, 0) or 0)
            left = cur - cnt
            if left <= 0:
                au.setdefault("equipment", {}).pop(eid, None)
            else:
                au.setdefault("equipment", {})[eid] = left
        au["oil"] = oil_have - oil_need

        # قدرت کشور = پایه + دفاع؛ با مصرف دفاع و آسیب مستقیم کم می‌شود
        def_consumed = sum(int(ul.get("absorbed") or 0) for ul in used_log)
        country_hit = max(0, int(damage))  # آنچه از دفاع رد شد
        total_loss = def_consumed + country_hit
        old_power = int(c.get("power") or BASE_COUNTRY_POWER)
        overkill = total_loss > old_power
        actual_damage = min(total_loss, old_power)  # کاهش واقعی قدرت کشور
        new_power = max(0, old_power - actual_damage)
        c["power"] = new_power
        destroyed = new_power <= 0

        if destroyed:
            DATA.setdefault("destroyed", {})[target_en] = True
            DATA["countries"].pop(target_en, None)
            du["country"] = None
            du["banned"] = True
            # دفاع کامل از بین می‌رود
            for it in DEF_ITEMS:
                du.setdefault("equipment", {}).pop(it["id"], None)
                du.setdefault("def_hp", {})[it["id"]] = 0

        # اگر دفاع داشت و بعد از حمله صفر شد
        def_wiped = had_def and total_def_power(du) <= 0 and not destroyed
        if def_wiped:
            for it in DEF_ITEMS:
                du.setdefault("equipment", {}).pop(it["id"], None)
                du.setdefault("def_hp", {})[it["id"]] = 0

        save_data()

    # پیام‌ها (خارج از لاک)
    if damage <= 0:
        atk_msg = (
            f"*کاربر گرامی⚠️*\n\nحمله شما به کشور {def_name} موفقیت آمیز نبود!✖️\n\n"
            f"نیرو های شما از بین رفتند!📌"
        )
        lines = [
            f"*کاربر گرامی⚠️*\n\nشما توسط کشور {atk_name} مورد حمله قرار گرفتید!✔️\n\n"
            f"دفاع شما تمام نیرو های دشمن را از بین برد!📌\n\nنیرو های دفاعی مورد استفاده شما :\n"
        ]
        for ul in used_log:
            lines.append(f"{ul['name']} (جذب: {fad(ul['absorbed'])} | باقی: {fad(ul['left'])})")
        try:
            send_message(int(def_uid), "\n".join(lines))
        except Exception:
            pass
        post_attack_log(atk_name, def_name, 0, False)
        return True, atk_msg

    if destroyed:
        if overkill:
            atk_msg = (
                f"*کاربر گرامی⚠️*\n\nکشور {def_name} توسط شما ۱۰۰ درصد نابود شد!✔️\n\n"
                f"شما نیروی بیش از حد به کشور دشمن فرستادید و برخی از نیرو های شما نیز در همان جا از بین رفت!📌"
            )
        else:
            atk_msg = (
                f"*کاربر گرامی⚠️*\n\nکشور {def_name} توسط شما ۱۰۰ درصد نابود شد!✔️\n\n"
                f"حمله شما فوق العاده بود!📌"
            )
        def_msg = (
            f"*کاربر گرامی⚠️*\n\nکشور شما توسط کشور {atk_name} مورد حمله قرار گرفت!✔️\n\n"
            f"کشور شما به طور کامل نابود شد!📌"
        )
        try:
            send_message(int(def_uid), def_msg)
        except Exception:
            pass
        post_attack_log(atk_name, def_name, actual_damage, True, def_name)
        return True, atk_msg

    # آسیب جزئی
    atk_msg = (
        f"*کاربر گرامی⚠️*\n\nنیرو های شما به کشور {def_name} آسیب زد!✔️\n\n"
        f"شما توانستید {fad(actual_damage)} عدد از قدرت کشور دشمن را با خاک یکسان کنید!📌"
    )
    if def_wiped:
        def_msg = (
            f"*کاربر گرامی⚠️*\n\nکشور شما توسط کشور {atk_name} مورد حمله قرار گرفت!✔️\n\n"
            f"{fad(actual_damage)} عدد از قدرت کشور شما با خاک یکسان شد!📌\n\n"
            f"قدرت کشور پس از حمله دشمن : {fad(new_power)} 🚀\n\n"
            f"نیرو های دفاعی شما کاملا از بین رفتند! 💣"
        )
    else:
        def_msg = (
            f"*کاربر گرامی⚠️*\n\nکشور شما توسط کشور {atk_name} مورد حمله قرار گرفت!✔️\n\n"
            f"{fad(actual_damage)} عدد از قدرت کشور شما با خاک یکسان شد!📌\n\n"
            f"قدرت کشور پس از حمله دشمن : {fad(new_power)} 🚀"
        )
    try:
        send_message(int(def_uid), def_msg)
    except Exception:
        pass
    post_attack_log(atk_name, def_name, actual_damage, False)
    return True, atk_msg




def equipment_status_text(uid):
    """گزارش مرتب و فشرده موجودی کاربر"""
    u = get_user(uid)
    en = u.get("country")
    lines = ["*📊 وضعیت تجهیزات*", ""]

    # کشور و قدرت
    if en:
        cname = country_name_fa(en)
        c = DATA["countries"].get(en)
        power = int(c.get("power") or BASE_COUNTRY_POWER) if isinstance(c, dict) else BASE_COUNTRY_POWER
        lines.append(f"🏳 کشور: {cname}")
        lines.append(f"⚡ قدرت کشور: {fad(power)}")
    else:
        lines.append("🏳 کشور: —")
        lines.append("⚡ قدرت کشور: —")

    if is_hacked(u):
        lines.append("🔓 وضعیت: هک‌شده (قفل موقت)")

    lines.append("")
    lines.append(f"💰 سکه: {coins_fa(int(u.get('coins') or 0))}")
    lines.append(f"💎 الماس: {fad(int(u.get('diamonds') or 0))}")
    lines.append(f"🛢 نفت: {fad(int(u.get('oil') or 0))}")
    lines.append(f"🍞 غذا: {fad(int(u.get('food') or 0))}")

    pr = int(u.get("printer") or 0)
    if pr:
        lines.append(f"🖨 چاپ پول: سطح {LVL_FA.get(pr, pr)}")

    # اقتصادی
    eq = u.get("equipment") or {}
    eco_lines = []
    for it in ECO_ITEMS:
        n = int(eq.get(it["id"], 0) or 0)
        if n > 0:
            eco_lines.append(f"• {it['btn']}: {fad(n)}")
    lines.append("")
    lines.append("*⛏ معادن و اقتصاد*")
    if eco_lines:
        lines.extend(eco_lines)
    else:
        lines.append("• —")

    # دفاعی
    ensure_def_hp(u)
    hp = u.get("def_hp") or {}
    def_lines = []
    for it in DEF_ITEMS:
        n = int(eq.get(it["id"], 0) or 0)
        left = int(hp.get(it["id"], 0) or 0)
        if n > 0 or left > 0:
            def_lines.append(f"• {it['btn']}")
            def_lines.append(f"  تعداد: {fad(n)} | باقی‌قدرت: {fad(left)}")
    lines.append("")
    lines.append("*🛡 دفاعی*")
    if def_lines:
        lines.extend(def_lines)
        lines.append(f"Σ قدرت دفاع: {fad(total_def_power(u))}")
    else:
        lines.append("• —")

    if u.get("nuke_def"):
        lines.append("• 🛡 پدافند ضد بمب اتم: فعال")

    # جنگی
    war_lines = []
    for eid, cnt, it in user_war_equipment(u):
        name = it.get("name") or eid
        war_lines.append(f"• {name}")
        war_lines.append(f"  تعداد: {fad(cnt)} | قدرت‌واحد: {fad(it.get('power') or 0)}")
    lines.append("")
    lines.append("*⚔️ نیروهای جنگی*")
    if war_lines:
        lines.extend(war_lines)
    else:
        lines.append("• —")

    # هکری
    hq = int(u.get("hq") or 0)
    pc = int(u.get("pc") or 0)
    comm = int(u.get("comm") or 0)
    sat = int(u.get("sat") or 0)
    lines.append("")
    lines.append("*👨🏻‍💻 هکری*")
    lines.append(f"• مقر: {fad(hq)} | کامپیوتر: {fad(pc)}")
    lines.append(f"• ارتباطات: {fad(comm)} | ماهواره: {fad(sat)}")

    ah = u.get("antihackers") or {}
    hk = u.get("hackers") or {}
    if any(int(v or 0) > 0 for v in ah.values()):
        lines.append("ضد‌هکر:")
        for gid, n in ah.items():
            if int(n or 0) <= 0:
                continue
            it = ANTI_HACK_MAP.get(gid) or {}
            lines.append(f"• {it.get('btn', gid)}: {fad(n)}")
    if any(int(v or 0) > 0 for v in hk.values()):
        lines.append("گروهک هکری:")
        for gid, n in hk.items():
            if int(n or 0) <= 0:
                continue
            it = HACK_GROUP_MAP.get(gid) or {}
            lines.append(f"• {it.get('btn', gid)}: {fad(n)}")

    # ساخت و ساز
    houses = u.get("houses") or {}
    sat_v = int(u.get("satisfaction") or 0)
    wperm = int(u.get("workers_perm") or 0)
    lines.append("")
    lines.append("*🏗 ساخت‌وساز*")
    lines.append(f"• رضایت: {fad(sat_v)}٪ | کارگر دائم: {fad(wperm)}")
    if houses:
        for hid, n in houses.items():
            if int(n or 0) <= 0:
                continue
            # find house name
            hname = hid
            for h in HOUSE_ITEMS:
                if h["id"] == hid:
                    hname = h.get("btn") or hid
                    break
            lines.append(f"• {hname}: {fad(n)}")
    else:
        lines.append("• خانه: —")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3890] + "\n…"
    return text



def notify_admins(text, kb=None, md=True):
    for aid in ADMIN_IDS:
        try:
            send_message(aid, text, kb, md=md)
        except Exception as e:
            print("[NOTIFY]", aid, e)


def support_caption(uid, msg):
    u = get_user(uid)
    cname = country_name_fa(u.get("country")) if u.get("country") else "بدون کشور"
    body = (msg.get("text") or msg.get("caption") or "").strip()
    if not body:
        if msg.get("photo"):
            body = "📷 عکس"
        elif msg.get("video"):
            body = "🎬 ویدیو"
        elif msg.get("voice"):
            body = "🎤 ویس"
        elif msg.get("audio"):
            body = "🎵 موزیک"
        elif msg.get("document"):
            body = "📎 فایل"
        elif msg.get("animation"):
            body = "🎞 گیف"
        else:
            body = "—"
    # کپشن تلگرام حداکثر حدود ۱۰۲۴
    cap = (
        "📬 درخواست پشتیبانی\n"
        "────────────\n"
        f"👤 آیدی: {uid}\n"
        f"🏳 کشور: {cname}\n"
        "────────────\n"
        f"💬 پیام:\n{body}"
    )
    return cap[:1024]

def deliver_support_to_admins(uid, chat_id, msg):
    """یک پیام مرتب + دکمه شیشه‌ای برای هر ادمین"""
    cap = support_caption(uid, msg)
    kb = {"inline_keyboard": IK([[("✅️ تأیید گفت و گو", f"sup:{uid}")]])}
    for aid in ADMIN_IDS:
        try:
            if msg.get("photo"):
                api("sendPhoto", chat_id=aid, photo=msg["photo"][-1]["file_id"],
                    caption=cap, reply_markup=kb)
            elif msg.get("video"):
                api("sendVideo", chat_id=aid, video=msg["video"]["file_id"],
                    caption=cap, reply_markup=kb)
            elif msg.get("animation"):
                api("sendAnimation", chat_id=aid, animation=msg["animation"]["file_id"],
                    caption=cap, reply_markup=kb)
            elif msg.get("document"):
                api("sendDocument", chat_id=aid, document=msg["document"]["file_id"],
                    caption=cap, reply_markup=kb)
            elif msg.get("voice"):
                # ویس کپشن محدود دارد — یک پیام متنی با دکمه
                send_message(aid, cap, kb, md=False)
                api("sendVoice", chat_id=aid, voice=msg["voice"]["file_id"])
            elif msg.get("audio"):
                api("sendAudio", chat_id=aid, audio=msg["audio"]["file_id"],
                    caption=cap, reply_markup=kb)
            else:
                send_message(aid, cap, kb, md=False)
        except Exception as e:
            print("[SUPPORT]", aid, e)
            try:
                send_message(aid, cap, kb, md=False)
            except Exception:
                pass


def check_channel_member(uid, channel):
    """True اگر عضو یا ادمین کانال باشد"""
    try:
        res = api("getChatMember", chat_id=channel, user_id=uid)
        if not res.get("ok"):
            return False
        st = (res.get("result") or {}).get("status") or ""
        return st in ("creator", "administrator", "member", "restricted")
    except Exception as e:
        print("[JOIN CHECK]", channel, e)
        return False

def missing_force_channels(uid):
    if is_admin(uid):
        return []
    miss = []
    for ch in FORCE_CHANNELS:
        if not check_channel_member(uid, ch["user"]):
            miss.append(ch)
    return miss

def force_join_kb():
    rows = []
    for ch in FORCE_CHANNELS:
        rows.append([{"text": ch["btn"], "url": ch["url"]}])
    rows.append([{"text": "✅️ عضو شدم", "callback_data": "fjok"}])
    return {"inline_keyboard": rows}

FORCE_JOIN_TEXT = (
    "*کاربر گرامی⚠️*\n\n"
    "به ربات رادارِ جهانی خوش آمدید!✔️\n\n"
    "ابتدا در کانال های زیر عضو شوید!📌"
)

def require_force_join(uid, chat_id):
    miss = missing_force_channels(uid)
    if not miss:
        return False
    send_message(chat_id, FORCE_JOIN_TEXT, force_join_kb())
    return True

def is_admin(uid):
    try:
        return int(uid) in ADMIN_IDS
    except Exception:
        return False

def is_bot_on():
    return bool(DATA.get("bot_on", True))

def is_user_blocked(uid):
    if is_admin(uid):
        return False
    u = DATA["users"].get(str(uid)) or {}
    return bool(u.get("blocked"))

def check_spam(uid):
    """۷ کلیک در ۵ ثانیه = اسپم. ادمین معاف. True اگر اسپم باشد."""
    if is_admin(uid):
        return False
    now = time.time()
    hits = SPAM_HITS.setdefault(uid, [])
    hits.append(now)
    # فقط ۵ ثانیه اخیر
    SPAM_HITS[uid] = [t for t in hits if now - t <= 5]
    return len(SPAM_HITS[uid]) >= 7

def custom_buttons_kb():
    customs = DATA.get("custom_buttons") or []
    rows = [[b["name"]] for b in customs]
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def shop_user_kb():
    return RK([
        ["💰 خرید سکه", "💎 خرید الماس"],
        ["🔙 بازگشت"],
    ])

def find_custom_button(name):
    for b in (DATA.get("custom_buttons") or []):
        if b.get("name") == name:
            return b
    return None


def main_menu_kb(uid):
    rows = []
    if is_admin(uid):
        rows.append(["⚙️ پنل ادمین"])
    rows.append(["کشورگیری🏳🏴", "خرید تجهیزات🔫💣"])
    rows.append(["ارسال بیانیه📝", "نبرد⚔🛡🔥"])
    rows.append(["تجهیزات🚀", "فروشگاه🏬"])
    # پشتیبانی + دکمه‌های سفارشی (اولی کنار پشتیبانی، بقیه دو به دو)
    customs = list(DATA.get("custom_buttons") or [])
    if customs:
        first = customs[0]["name"]
        rows.append(["🆘️ پشتیبانی", first])
        row = []
        for b in customs[1:]:
            row.append(b["name"])
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    else:
        rows.append(["🆘️ پشتیبانی"])
    return RK(rows)

def admin_panel_kb(uid=None):
    rows = [
        ["➕️ اهدا کشور", "➖️ حذف مدیر کشور"],
        ["➕️ افزودن دستگاه چاپ پول", "➖️ حذف دستگاه چاپ پول"],
        ["💎 اهدا الماس", "💎 کسر الماس"],
        ["💰 اهدا سکه", "💰 کسر سکه"],
        ["➕️ اهدا نیرو", "➕️ اهدا بشکه نفت"],
        ["⚠️ اخطار", "⚠️ رفع اخطار"],
        ["🚫 مسدود کردن کاربر", "🚫 رفع مسدودی"],
        ["🧑‍🔧 ساخت دکمه", "✏️ ویرایش دکمه"],
        ["❌️ حذف دکمه", "🔎 جست و جوی کاربر"],
        ["✅ روشن کردن ربات", "❌ خاموش کردن ربات"],
    ]
    # فقط ادمین اصلی
    if uid is not None and int(uid) == int(ADMIN_ID):
        rows.append(["📱 اطلاعات"])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def shop_kb():
    return RK([
        ["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
        ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"],
        ["🔙 بازگشت"],
    ])

def _country_label(flag, en, name, vip):
    label = f"{flag} {name}"
    # نابود شده → ضربدر
    if DATA.get("destroyed", {}).get(en):
        return "❌️ " + label
    c = DATA["countries"].get(en)
    taken = False
    if en == "UN":
        # سازمان ملل (اگر نابود نباشد) همیشه پر + تیک
        taken = True
        if not isinstance(c, dict) or not c.get("owner"):
            DATA.setdefault("countries", {})["UN"] = {
                "owner": UN_OWNER_ID, "power": BASE_COUNTRY_POWER,
                "hacked_until": None, "start_ts": time.time(),
            }
    elif isinstance(c, dict) and c.get("owner"):
        taken = True
    elif c is not None and not isinstance(c, dict):
        taken = True
    if taken:
        label = "✅️ " + label
    elif vip:
        label += " 🌟"
    return label

def country_kb():
    rows, row = [], []
    for flag, en, name, vip in COUNTRIES:
        label = _country_label(flag, en, name, vip)
        row.append(label)
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def war_kb():
    rows, row = [], []
    for c in WAR_CATS:
        row.append(c["btn"])
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def eco_kb():
    rows, row = [], []
    for it in ECO_ITEMS:
        row.append(it["btn"])
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    for lvl in (1, 2, 3):
        rows.append([f"دستگاه چاپ پول سطح {LVL_FA[lvl]} 🎁"])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def def_kb():
    """تجهیزات دفاعی: هر دکمه در یک ردیف جدا"""
    rows = [[it["btn"]] for it in DEF_ITEMS]
    rows.append(["🛡پدافند ضد بمب اتم"])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def _war_btn_label(name, max_len=64):
    """متن دکمه آیتم جنگی — همان متن اصلی آیتم"""
    name = (name or "").strip()
    if len(name) <= max_len:
        return name
    return name[: max_len - 1]

def war_items_kb(key):
    """آیتم‌های داخل هر دسته: هر دکمه در یک ردیف"""
    cat = WAR_CAT_MAP.get(key)
    if not cat:
        return RK([["🔙 بازگشت"]])
    rows = [[_war_btn_label(it["name"])] for it in cat["items"]]
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def hack_target_kb(attacker_uid):
    """کشورهای دارای مدیر (غیر از خودی) برای حمله هکری — ۳ تا در هر ردیف"""
    rows, row = [], []
    au = get_user(attacker_uid)
    my = au.get("country")
    for flag, en, name, vip in COUNTRIES:
        c = DATA["countries"].get(en)
        if not c or not isinstance(c, dict):
            continue
        if not c.get("owner"):
            continue
        if en == my:
            continue
        if DATA.get("destroyed", {}).get(en):
            continue
        row.append(f"🎯 {flag} {name}")
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if not rows:
        rows.append(["— کشوری برای هک نیست —"])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def hack_menu_kb():
    return RK([
        ["👨🏻‍💻 تجهیزات هکری"],
        ["🛡️⚔️ گروهک‌های ضد‌هکری"],
        ["💻⚡ گروهک‌های هکری"],
        ["⚡ حمله هکری"],
        ["🔙 بازگشت"],
    ])

def hack_eq_kb():
    return RK([[it["btn"]] for it in HACK_EQ_ITEMS] + [["🔙 بازگشت"]])

def anti_hack_kb():
    return RK([[it["btn"]] for it in ANTI_HACK_GROUPS] + [["🔙 بازگشت"]])

def hack_group_kb():
    return RK([[it["btn"]] for it in HACK_GROUPS] + [["🔙 بازگشت"]])

def build_kb():
    return RK([["🏡 خانه"], ["👨‍🔧 کارگر"], ["🍕 غذا"], ["🔙 بازگشت"]])

def house_kb():
    return RK([[it["btn"]] for it in HOUSE_ITEMS] + [["🔙 بازگشت"]])

def worker_kb():
    rows = [["💰 خرید کارگر دائمی"]]
    for w in WORKER_RENT:
        rows.append([w["btn"]])
    rows.append(["🔙 بازگشت"])
    return RK(rows)

def insufficient_msg(need_c, need_d, have_c, have_d):
    if have_c < need_c and have_d < need_d:
        return NO_BOTH_TEXT
    if have_c < need_c:
        return NO_COIN_TEXT
    if have_d < need_d:
        return NO_DIA_TEXT
    return NO_COIN_TEXT

def is_hacked(u):
    until = u.get("hack_until")
    if not until:
        return False
    if time.time() < float(until):
        return True
    u["hack_until"] = None
    return False

def active_workers(u):
    now = time.time()
    n = int(u.get("workers_perm") or 0)
    alive = []
    for w in u.get("workers_temp") or []:
        if float(w.get("until", 0)) > now:
            n += int(w.get("n", 0))
            alive.append(w)
    u["workers_temp"] = alive
    return n

_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

def destroy_country(en, reason="power"):
    c = DATA["countries"].get(en)
    if not c:
        return
    owner = c.get("owner") if isinstance(c, dict) else c
    DATA.setdefault("destroyed", {})[en] = True
    DATA["countries"].pop(en, None)
    if owner:
        ou = DATA["users"].get(str(owner))
        if ou:
            ou["country"] = None
            ou["banned"] = True
            try:
                if reason == "revolt":
                    send_message(int(owner),
                        "*کاربر گرامی⚠️*\n\nکشور شما توسط شورش مردم از بین رفت!✖️\n\n"
                        "شما نتوانستید رضایت مردم را جلب کنید!📌")
                else:
                    send_message(int(owner),
                        "*کاربر گرامی⚠️*\n\nقدرت کشور شما به صفر رسید و نابود شد!✖️\n\n"
                        "کشور از اداره شما خارج شد!📌")
            except Exception:
                pass
    save_data()
    print(f"[DESTROY] {en} reason={reason}")

def can_hack_ops(u):
    return (int(u.get("hq") or 0) >= 50 and int(u.get("pc") or 0) >= 50
            and int(u.get("comm") or 0) >= 50 and int(u.get("sat") or 0) >= 50)

def hack_eq_missing_text(u):
    """متن کمبود تجهیزات هکری برای خرید هکر/ضد‌هکر"""
    lines = ["*کاربر گرامی⚠️*", "", "ابتدا تمام تجهیزات هکری مورد نیاز را تهیه کنید!✔️", ""]
    need = [
        ("🏢 مقر هکری", int(u.get("hq") or 0), 50),
        ("💻 کامپیوتر پیشرفته", int(u.get("pc") or 0), 50),
        ("📡 مرکز ارتباطات", int(u.get("comm") or 0), 50),
        ("🛰 ماهواره اختصاصی", int(u.get("sat") or 0), 50),
    ]
    for name, have, req in need:
        mark = "✅" if have >= req else "❌"
        lines.append(f"{mark} {name}: {fad(have)} / {fad(req)}")
    lines.append("")
    lines.append("بدون تأمین همه موارد بالا نمی‌توانید هکر یا ضد‌هکر بخرید!📌")
    return "\n".join(lines)

def consume_hack_stack(u, amount=50):
    for k in ("hq", "pc", "comm", "sat"):
        u[k] = max(0, int(u.get(k) or 0) - amount)

def total_hacker_power(u):
    total = 0
    for gid, cnt in (u.get("hackers") or {}).items():
        it = HACK_GROUP_MAP.get(gid)
        if it and cnt:
            total += it["power"] * int(cnt)
    return total

def total_antihack_power(u):
    total = 0
    for gid, cnt in (u.get("antihackers") or {}).items():
        it = ANTI_HACK_MAP.get(gid)
        if it and cnt:
            total += it["power"] * int(cnt)
    return total

def country_name_fa(en):
    for flag, code, name, vip in COUNTRIES:
        if code == en:
            return f"{flag} {name}"
    return en

def do_hack_attack(attacker_uid, target_en):
    """اجرای حمله هکری. برمی‌گرداند: (ok, message_for_attacker)"""
    au = get_user(attacker_uid)
    if is_hacked(au):
        return False, HACKED_TEXT
    if not au.get("country"):
        return False, NEED_COUNTRY_TEXT
    if not can_hack_ops(au):
        return False, ("*کاربر گرامی⚠️*\n\nبرای حمله هکری باید حداقل ۵۰ عدد از هر تجهیز "
                       "(مقر، کامپیوتر، مرکز ارتباطات، ماهواره) داشته باشید!✔️")
    if total_hacker_power(au) <= 0:
        return False, ("*کاربر گرامی⚠️*\n\nابتدا حداقل یک گروهک هکری خریداری کنید!✔️")
    if target_en == au.get("country"):
        return False, "*کاربر گرامی⚠️*\n\nنمی‌توانید کشور خودتان را هک کنید!✔️"
    if DATA.get("destroyed", {}).get(target_en):
        return False, COUNTRY_DESTROYED_TEXT
    c = DATA["countries"].get(target_en)
    if not c or not isinstance(c, dict) or not c.get("owner"):
        return False, "*کاربر گرامی⚠️*\n\nاین کشور مدیر ندارد!✔️"
    # already hacked?
    target_owner = c["owner"]
    tu = get_user(target_owner)
    if is_hacked(tu):
        return False, ("*کاربر گرامی⚠️*\n\nاین کشور هک شده است!✔️\n\n"
                       "هنوز تیم این کشور نتوانسته اند از دست هک شدن فرار کنند و نیازی به هک کردن مجدد نیست!📌")
    atk_power = total_hacker_power(au)
    def_power = total_antihack_power(tu)
    atk_name = country_name_fa(au.get("country") or "?")
    def_name = country_name_fa(target_en)

    with LOCK:
        # همیشه تجهیزات حمله کننده مصرف می‌شود
        consume_hack_stack(au, 50)
        # یک گروهک هکر از قوی‌ترین کم کن
        hk = au.get("hackers") or {}
        if hk:
            # remove one group from highest power available
            best = None
            best_pw = -1
            for gid, cnt in list(hk.items()):
                it = HACK_GROUP_MAP.get(gid)
                if it and cnt > 0 and it["power"] > best_pw:
                    best, best_pw = gid, it["power"]
            if best:
                hk[best] = hk.get(best, 1) - 1
                if hk[best] <= 0:
                    hk.pop(best, None)
                au["hackers"] = hk

        if atk_power > def_power:
            # موفقیت هک
            # مصرف ضد‌هکرهای مدافع
            ah = tu.get("antihackers") or {}
            for gid in list(ah.keys()):
                ah[gid] = 0
            tu["antihackers"] = {}
            consume_hack_stack(tu, min(50, int(tu.get("hq") or 0)))  # بخشی از تجهیزات مدافع
            tu["hack_until"] = time.time() + HACK_DURATION_SEC
            c["hacked_until"] = tu["hack_until"]
            save_data()
            try:
                send_message(int(target_owner),
                    f"*کاربر گرامی⚠️*\n\nکشور شما توسط هکر های کشور {atk_name} فتح شد!✔️\n\n"
                    f"شما نمی توانید کاری را به مدت ۱ ساعت انجام دهید!📌")
            except Exception:
                pass
            return True, (f"*کاربر گرامی⚠️*\n\nحمله هکری موفق بود!✔️\n\n"
                          f"کشور {def_name} به مدت ۱ ساعت هک شد.\n"
                          f"قدرت نفوذ: {fad(atk_power)} | دفاع: {fad(def_power)}📌")
        else:
            # دفاع موفق
            ah = tu.get("antihackers") or {}
            if ah:
                best = None
                best_pw = -1
                for gid, cnt in list(ah.items()):
                    it = ANTI_HACK_MAP.get(gid)
                    if it and cnt > 0 and it["power"] > best_pw:
                        best, best_pw = gid, it["power"]
                if best:
                    ah[best] = ah.get(best, 1) - 1
                    if ah[best] <= 0:
                        ah.pop(best, None)
                    tu["antihackers"] = ah
            consume_hack_stack(tu, min(50, int(tu.get("hq") or 0)))
            save_data()
            try:
                send_message(int(target_owner),
                    f"*کاربر گرامی⚠️*\n\nضد هکر های شما مانع از هک شدن شما شدند!✔️\n\n"
                    f"کشور {atk_name} سعی بر هک کردن شما داشت!📌")
            except Exception:
                pass
            return True, (f"*کاربر گرامی⚠️*\n\nضد هکر های کشور {def_name} هکر های شما را نابود کردند!✔️\n\n"
                          f"مراقب باشید!📌\nقدرت نفوذ: {fad(atk_power)} | دفاع: {fad(def_power)}")

def check_satisfaction():
    now = time.time()
    with LOCK:
        for uid, u in list(DATA["users"].items()):
            en = u.get("country")
            if not en:
                continue
            start = float(u.get("country_start") or 0)
            if not start:
                continue
            days = (now - start) / 86400.0
            week = int(days // 7)
            if week < 1:
                continue
            last_check = int(u.get("sat_week_check") or 0)
            if week <= last_check:
                continue
            sat = int(u.get("satisfaction") or 0)
            warned = u.get("sat_warned")
            if sat <= 20:
                if not warned:
                    u["sat_warned"] = True
                    save_data()
                    try:
                        send_message(int(uid),
                            "*کاربر گرامی⚠️*\n\nمردم شما قصد دارند دست به شورش بزنند!✖️\n\n"
                            "تا فردا مهلت دارید خانه بسازید تا از این شورش جلوگیری شود!📌")
                    except Exception:
                        pass
                else:
                    u["sat_warned"] = False
                    u["sat_week_check"] = week
                    save_data()
                    destroy_country(en, reason="revolt")
            else:
                u["sat_warned"] = False
                u["sat_week_check"] = week
                save_data()


def to_en_digits(s):
    return str(s).translate(_EN)

def parse_coin_amount(text):
    t = to_en_digits(text.strip().replace(",", "").replace("٬", "").replace("،", ""))
    t = t.replace("سکه", "").strip()
    m = re.match(r"^([\d.]+)\s*(میلیارد|میلیون|هزار)?$", t)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2) or ""
    if unit == "میلیارد":
        return int(num * 1_000_000_000)
    if unit == "میلیون":
        return int(num * 1_000_000)
    if unit == "هزار":
        return int(num * 1_000)
    return int(num)


# ───────────────────────────── کمک‌کننده‌های وضعیت ─────────────────────────────
def set_pending(uid, step, **extra):
    PENDING[uid] = {"step": step, **extra}

def clear_pending(uid):
    PENDING.pop(uid, None)

def get_pending(uid):
    return PENDING.get(uid)

# ───────────────────────────── کشورگیری ─────────────────────────────
def find_country_by_label(label):
    """بر اساس متن دکمه کشور را پیدا می‌کند"""
    clean = (label or "")
    for p in ("✅️ ", "✅ ", "❌️ ", "❌ ", "🌟", "VIP"):
        clean = clean.replace(p, "")
    clean = " ".join(clean.split()).strip()
    for i, (flag, en, name, vip) in enumerate(COUNTRIES):
        target = f"{flag} {name}"
        if clean == target or clean.startswith(target):
            return i, flag, en, name, vip
        # فقط نام فارسی
        if clean == name or clean.endswith(name):
            return i, flag, en, name, vip
    return None

def handle_country_select(uid, chat_id, label):
    found = find_country_by_label(label)
    if not found:
        send_message(chat_id, UNKNOWN_TEXT, main_menu_kb(uid))
        return
    i, flag, en, name, vip = found
    u = get_user(uid)

    if DATA.get("destroyed", {}).get(en):
        send_message(chat_id, COUNTRY_DESTROYED_TEXT, country_kb())
        return
    if DATA["countries"].get(en):
        send_message(chat_id, COUNTRY_FULL_TEXT, country_kb())
        return
    if vip:
        send_message(chat_id, VIP_TEXT, country_kb())
        return
    if u.get("country") or u.get("banned"):
        send_message(chat_id, HAD_COUNTRY_TEXT, country_kb())
        return

    # فقط اینجا شیشه‌ای: تأیید / لغو
    set_pending(uid, "confirm_country", idx=i)
    text = (f"*کاربر گرامی⚠️*\n\n"
            f"از انتخاب کشور {flag} {name} اطمینان دارید؟\n\n"
            f"در صورت تمایل به اداره این کشور، بر روی دکمه تایید کلیک کنید، و در غیر این صورت، گزینه لغو را انتخاب کنید!📌")
    send_message(chat_id, text, {"inline_keyboard": IK([[("تأیید✔️", f"cy{i}"), ("لغو✖️", "cx")]])})

def on_country_confirm(uid, chat_id, mid, i):
    flag, en, name, vip = COUNTRIES[i]
    u = get_user(uid)
    status = None
    with LOCK:
        if DATA.get("destroyed", {}).get(en):
            status = "destroyed"
        elif DATA["countries"].get(en):
            status = "full"
        elif u.get("country") or u.get("banned"):
            status = "had"
        else:
            DATA["countries"][en] = {"owner": uid, "power": BASE_COUNTRY_POWER, "hacked_until": None, "start_ts": time.time()}
            u["country"] = en
            u["country_start"] = time.time()
            u["satisfaction"] = 0
            u["banned"] = False
            save_data()
            status = "ok"
    clear_pending(uid)
    if status == "destroyed":
        edit_message(chat_id, mid, COUNTRY_DESTROYED_TEXT)
        send_message(chat_id, "لطفا کشور دیگری انتخاب کنید.", country_kb())
    elif status == "full":
        edit_message(chat_id, mid, COUNTRY_FULL_TEXT)
        send_message(chat_id, "لطفا کشور دیگری انتخاب کنید.", country_kb())
    elif status == "had":
        edit_message(chat_id, mid, HAD_COUNTRY_TEXT)
        send_message(chat_id, "به منوی کشورها بازگشتید.", country_kb())
    else:
        print(f"[COUNTRY] {en} -> {uid}")
        edit_message(chat_id, mid,
                     f"*کاربر گرامی⚠️*\n\nاداره کشور {flag} {name} از امروز در دست شماست!✔️\n\n{flag} {name} را بسازید و پیشرفت دهید!📌")
        send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid))

# ───────────────────────────── پنل ادمین ─────────────────────────────
def handle_admin_gift_country(uid, chat_id, label):
    found = find_country_by_label(label)
    if not found:
        send_message(chat_id, UNKNOWN_TEXT, admin_panel_kb())
        return
    i, flag, en, name, vip = found
    if DATA["countries"].get(en):
        send_message(chat_id, GIFT_TAKEN_TEXT, country_kb())  # همان کیبورد کشورها برای انتخاب مجدد
        return
    set_pending(uid, "ag", idx=i)
    send_message(chat_id, ASK_UID_GIFT, RK([["🔙 بازگشت"]]))

def handle_admin_remove_manager(uid, chat_id, label):
    found = find_country_by_label(label)
    if not found:
        send_message(chat_id, UNKNOWN_TEXT, admin_panel_kb())
        return
    i, flag, en, name, vip = found
    owner = None
    with LOCK:
        c = DATA["countries"].pop(en, None)
        if c is not None:
            owner = c.get("owner") if isinstance(c, dict) else c
            if owner is not None:
                ou = DATA["users"].get(str(owner))
                if ou is not None:
                    ou["country"] = None
                    ou["banned"] = True
            save_data()
    if owner is None:
        send_message(chat_id, RM_NO_MGR_TEXT, country_kb())
        return
    if owner:
        try:
            send_message(int(owner),
                         f"*کاربر گرامی⚠️*\n\nاداره کشور {flag} {name} از دست شما خارج شد!✔️\n\nاز زحمات شما متشکریم!📌")
        except Exception:
            pass
    print(f"[RM-MGR] {en} خالی شد (کاربر {owner})")
    send_message(chat_id,
                 f"*ادمین گرامی⚠️*\n\nاداره کشور {flag} {name} از دست کاربر خارج شد!✔️\n\nاز زحمات شما متشکریم!📌",
                 admin_panel_kb())


def printer_level_kb():
    return RK([
        ["سطح ۱ 🎁", "سطح ۲ 🎁", "سطح ۳ 🎁"],
        ["🔙 بازگشت"],
    ])

def on_set_printer(lvl, target):
    tu = get_user(target)
    with LOCK:
        tu["printer"] = lvl
        save_data()
    print(f"[PRINTER] سطح {lvl} برای {target} فعال شد")
    notify_admins(
                 f"*ادمین گرامی⚠️*\n\nدستگاه چاپ پول سطح {LVL_FA[lvl]} با موفقیت به تجهیزات کاربر اضافه شد!✔️\n\nاز زحمات شما سپاسگزاریم!📌",
                 admin_panel_kb())
    send_message(target,
                 f"*کاربر گرامی⚠️*\n\nدستگاه چاپ پول سطح {LVL_FA[lvl]} به تجهیزات شما اضافه شد!✔️\n\nبسازید و پیشرفت کنید!📌")

def admin_text_input(uid, chat_id, text):
    pend = get_pending(uid)
    if not pend:
        return
    if text == "🔙 بازگشت":
        clear_pending(uid)
        send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb())
        return
    step = pend.get("step")

    # مرحله آیدی برای الماس/سکه
    if step in ("gift_dia_uid", "deduct_dia_uid", "gift_coin_uid", "deduct_coin_uid"):
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d{3,15}", t):
            send_message(chat_id, INVALID_UID_TEXT)
            return
        target = int(t)
        if str(target) not in DATA["users"]:
            send_message(chat_id, NOT_STARTED_TEXT)
            return
        if step == "gift_dia_uid":
            set_pending(uid, "gift_dia_amt", target=target)
            send_message(chat_id, ASK_DIA_AMOUNT, RK([["🔙 بازگشت"]]))
        elif step == "deduct_dia_uid":
            set_pending(uid, "deduct_dia_amt", target=target)
            send_message(chat_id, ASK_DIA_DEDUCT, RK([["🔙 بازگشت"]]))
        elif step == "gift_coin_uid":
            set_pending(uid, "gift_coin_amt", target=target)
            send_message(chat_id, ASK_COIN_AMOUNT, RK([["🔙 بازگشت"]]))
        else:
            set_pending(uid, "deduct_coin_amt", target=target)
            send_message(chat_id, ASK_COIN_DEDUCT, RK([["🔙 بازگشت"]]))
        return

    if step in ("gift_dia_amt", "deduct_dia_amt"):
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"-?\d+", t):
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nلطفا فقط عدد ارسال کنید!✔️")
            return
        amount = int(t)
        target = pend["target"]
        tu = get_user(target)
        with LOCK:
            if step == "gift_dia_amt":
                tu["diamonds"] = int(tu.get("diamonds") or 0) + amount
            else:
                tu["diamonds"] = int(tu.get("diamonds") or 0) - amount
            save_data()
        clear_pending(uid)
        if step == "gift_dia_amt":
            send_message(chat_id,
                f"*ادمین گرامی⚠️*\n\n{fad(amount)} الماس به کاربر واریز شد!✔️",
                admin_panel_kb())
            if int(target) != int(uid):
                send_message(target,
                    f"*کاربر گرامی⚠️*\n\n{fad(amount)} الماس به حساب شما واریز شد!✔️\n\n"
                    f"کشور خود را بسازید و پیشرفت دهید!📌")
        else:
            send_message(chat_id,
                f"*ادمین گرامی⚠️*\n\n{fad(amount)} الماس از کاربر کسر شد!✔️",
                admin_panel_kb())
        return

    if step in ("gift_coin_amt", "deduct_coin_amt"):
        amount = parse_coin_amount(text)
        if amount is None:
            send_message(chat_id, ASK_COIN_AMOUNT if step == "gift_coin_amt" else ASK_COIN_DEDUCT)
            return
        target = pend["target"]
        tu = get_user(target)
        with LOCK:
            if step == "gift_coin_amt":
                tu["coins"] = int(tu.get("coins") or 0) + amount
            else:
                tu["coins"] = int(tu.get("coins") or 0) - amount
            save_data()
        clear_pending(uid)
        if step == "gift_coin_amt":
            send_message(chat_id,
                f"*ادمین گرامی⚠️*\n\n{coins_fa(amount)} به کاربر واریز شد!✔️",
                admin_panel_kb())
            if int(target) != int(uid):
                send_message(target,
                    f"*کاربر گرامی⚠️*\n\n{coins_fa(amount)} به حساب شما واریز شد!✔️")
        else:
            send_message(chat_id,
                f"*ادمین گرامی⚠️*\n\n{coins_fa(amount)} از کاربر کسر شد!✔️",
                admin_panel_kb())
        return


    # اهدا نفت
    if step == "gift_oil_uid":
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d{3,15}", t):
            send_message(chat_id, INVALID_UID_TEXT); return
        target = int(t)
        if str(target) not in DATA["users"]:
            send_message(chat_id, NOT_STARTED_TEXT); return
        set_pending(uid, "gift_oil_amt", target=target)
        send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد بشکه نفت مورد نظر را ارسال نمایید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]]))
        return
    if step == "gift_oil_amt":
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d+", t) or int(t) <= 0:
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nلطفا فقط عدد مثبت ارسال کنید!✔️\n\n*مثال : ۱۰📌*"); return
        amount = int(t)
        target = pend["target"]
        tu = get_user(target)
        with LOCK:
            tu["oil"] = int(tu.get("oil") or 0) + amount
            save_data()
        clear_pending(uid)
        send_message(chat_id, f"*ادمین گرامی⚠️*\n\n{fad(amount)} بشکه نفت به کاربر اضافه شد!✔️\n\nعملیات موفقیت آمیز بود!📌", admin_panel_kb())
        if int(target) != int(uid):
            send_message(target, f"*کاربر گرامی⚠️*\n\n{fad(amount)} بشکه نفت به حساب شما اضافه شد!✔️")
        return


    # اهدا نیرو — بعد از آیدی: ۵ بخش فروشگاه
    if step == "gift_force_uid":
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d{3,15}", t):
            send_message(chat_id, INVALID_UID_TEXT); return
        target = int(t)
        if str(target) not in DATA["users"]:
            send_message(chat_id, NOT_STARTED_TEXT); return
        set_pending(uid, "gift_force_section", target=target)
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nبخش مورد نظر را برای اهدا نیرو انتخاب کنید!✔️\n\nاز منوی زیر استفاده کنید!📌",
            RK([
                ["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
                ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"],
                ["🔙 بازگشت"],
            ]))
        return

    if step == "gift_force_section":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            clear_pending(uid); send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
        if text == "خرید تجهیزات اقتصادی💰💵💵💰":
            set_pending(uid, "gift_force_eco", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nتجهیز اقتصادی را انتخاب کنید!✔️", eco_kb()); return
        if text == "خرید تجهیزات دفاعی🛡":
            set_pending(uid, "gift_force_def", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nتجهیز دفاعی را انتخاب کنید!✔️", def_kb()); return
        if text == "خرید تجهیزات جنگی🧨💣":
            set_pending(uid, "gift_force_cat", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nدسته جنگی را انتخاب کنید!✔️", war_kb()); return
        if text == "گروهک های هکری👨‍💻":
            set_pending(uid, "gift_force_hack_menu", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش هکری را انتخاب کنید!✔️", hack_menu_kb()); return
        if text == "ساخت و ساز⚙🛠":
            set_pending(uid, "gift_force_qty", target=target, kind="food")
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد واحد غذا برای اهدا را بفرستید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]])); return
        send_message(chat_id, UNKNOWN_TEXT); return

    if step == "gift_force_eco":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_section", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش را انتخاب کنید!✔️",
                RK([["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
                    ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"], ["🔙 بازگشت"]])); return
        for it in ECO_ITEMS:
            if text == it["btn"]:
                set_pending(uid, "gift_force_qty", target=target, kind="eco", eq_id=it["id"])
                send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد مورد نظر را ارسال نمایید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]])); return
        send_message(chat_id, UNKNOWN_TEXT, eco_kb()); return

    if step == "gift_force_def":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_section", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش را انتخاب کنید!✔️",
                RK([["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
                    ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"], ["🔙 بازگشت"]])); return
        for it in DEF_ITEMS:
            if text == it["btn"]:
                set_pending(uid, "gift_force_qty", target=target, kind="def", eq_id=it["id"], power=it["power"])
                send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد مورد نظر را ارسال نمایید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]])); return
        send_message(chat_id, UNKNOWN_TEXT, def_kb()); return

    if step == "gift_force_hack_menu":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_section", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش را انتخاب کنید!✔️",
                RK([["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
                    ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"], ["🔙 بازگشت"]])); return
        if "تجهیزات هکری" in text or text.startswith("👨🏻‍💻"):
            set_pending(uid, "gift_force_hack_eq", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nتجهیز هکری را انتخاب کنید!✔️", hack_eq_kb()); return
        if "ضد" in text:
            set_pending(uid, "gift_force_hack_anti", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nگروهک ضد‌هکر را انتخاب کنید!✔️", anti_hack_kb()); return
        if "گروهک‌های هکری" in text or "💻⚡" in text:
            set_pending(uid, "gift_force_hack_grp", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nگروهک هکری را انتخاب کنید!✔️", hack_group_kb()); return
        send_message(chat_id, UNKNOWN_TEXT, hack_menu_kb()); return

    if step == "gift_force_hack_eq":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_hack_menu", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش هکری را انتخاب کنید!✔️", hack_menu_kb()); return
        for it in HACK_EQ_ITEMS:
            if text == it["btn"]:
                set_pending(uid, "gift_force_qty", target=target, kind="hack_eq", eq_id=it["id"], pack=it.get("pack", 1))
                send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد پک مورد نظر را بفرستید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]])); return
        send_message(chat_id, UNKNOWN_TEXT, hack_eq_kb()); return

    if step == "gift_force_hack_anti":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_hack_menu", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش هکری را انتخاب کنید!✔️", hack_menu_kb()); return
        for it in ANTI_HACK_GROUPS:
            if text == it["btn"]:
                set_pending(uid, "gift_force_qty", target=target, kind="hack_anti", eq_id=it["id"])
                send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد مورد نظر را بفرستید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]])); return
        send_message(chat_id, UNKNOWN_TEXT, anti_hack_kb()); return

    if step == "gift_force_hack_grp":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_hack_menu", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش هکری را انتخاب کنید!✔️", hack_menu_kb()); return
        for it in HACK_GROUPS:
            if text == it["btn"]:
                set_pending(uid, "gift_force_qty", target=target, kind="hack_grp", eq_id=it["id"])
                send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد مورد نظر را بفرستید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]])); return
        send_message(chat_id, UNKNOWN_TEXT, hack_group_kb()); return

    if step == "gift_force_cat":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_section", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش را انتخاب کنید!✔️",
                RK([["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
                    ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"], ["🔙 بازگشت"]])); return
        for c in WAR_CATS:
            if text == c["btn"]:
                set_pending(uid, "gift_force_item", target=target, key=c["key"])
                send_message(chat_id, f"*ادمین گرامی⚠️*\n\n{c['phrase']}!✔️", war_items_kb(c["key"]))
                return
        send_message(chat_id, UNKNOWN_TEXT, war_kb()); return

    if step == "gift_force_item":
        target = pend.get("target")
        key = pend.get("key")
        if text == "🔙 بازگشت":
            set_pending(uid, "gift_force_cat", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nدسته را انتخاب کنید!✔️", war_kb()); return
        cat = WAR_CAT_MAP.get(key)
        if cat:
            for idx, it in enumerate(cat["items"]):
                label = _war_btn_label(it["name"])
                if text == label or text == it["name"]:
                    set_pending(uid, "gift_force_qty", target=target, kind="war", key=key, idx=idx)
                    send_message(chat_id, "*ادمین گرامی⚠️*\n\nتعداد نیرو مورد نظر را ارسال نمایید!✔️\n\n*مثال : ۱۰📌*", RK([["🔙 بازگشت"]]))
                    return
        send_message(chat_id, UNKNOWN_TEXT, war_items_kb(key)); return

    if step == "gift_force_qty":
        target = pend.get("target")
        kind = pend.get("kind") or "war"
        if text == "🔙 بازگشت":
            clear_pending(uid)
            set_pending(uid, "gift_force_section", target=target)
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nبخش را انتخاب کنید!✔️",
                RK([["خرید تجهیزات اقتصادی💰💵💵💰", "خرید تجهیزات دفاعی🛡", "خرید تجهیزات جنگی🧨💣"],
                    ["گروهک های هکری👨‍💻", "ساخت و ساز⚙🛠"], ["🔙 بازگشت"]])); return
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d+", t) or int(t) <= 0:
            send_message(chat_id, "*ادمین گرامی⚠️*\n\nلطفا فقط عدد مثبت ارسال کنید!✔️\n\n*مثال : ۱۰📌*"); return
        amount = int(t)
        tu = get_user(target)
        with LOCK:
            if kind == "war":
                key, idx = pend.get("key"), pend.get("idx")
                eq_id = f"{key}_{idx + 1}"
                eq = tu.setdefault("equipment", {})
                eq[str(eq_id)] = int(eq.get(str(eq_id), 0) or 0) + amount
            elif kind == "eco":
                eq_id = pend.get("eq_id")
                eq = tu.setdefault("equipment", {})
                eq[eq_id] = int(eq.get(eq_id, 0) or 0) + amount
            elif kind == "def":
                eq_id = pend.get("eq_id")
                pw = int(pend.get("power") or 0)
                eq = tu.setdefault("equipment", {})
                eq[eq_id] = int(eq.get(eq_id, 0) or 0) + amount
                tu.setdefault("def_hp", {})[eq_id] = int(tu.get("def_hp", {}).get(eq_id, 0) or 0) + pw * amount
                en = tu.get("country")
                c = DATA["countries"].get(en) if en else None
                if isinstance(c, dict):
                    c["power"] = int(c.get("power") or BASE_COUNTRY_POWER) + pw * amount
            elif kind == "hack_eq":
                eq_id = pend.get("eq_id")
                pack = int(pend.get("pack") or 1)
                tu[eq_id] = int(tu.get(eq_id) or 0) + amount * pack
            elif kind == "hack_anti":
                gid = pend.get("eq_id")
                ah = tu.setdefault("antihackers", {})
                ah[gid] = int(ah.get(gid, 0) or 0) + amount
            elif kind == "hack_grp":
                gid = pend.get("eq_id")
                hk = tu.setdefault("hackers", {})
                hk[gid] = int(hk.get(gid, 0) or 0) + amount
            elif kind == "food":
                tu["food"] = int(tu.get("food") or 0) + amount
            save_data()
        clear_pending(uid)
        send_message(chat_id,
            f"*ادمین گرامی⚠️*\n\n{fad(amount)} واحد با موفقیت به کاربر اضافه شد!✔️\n\nعملیات موفقیت آمیز بود!📌",
            admin_panel_kb())
        if int(target) != int(uid):
            send_message(target,
                "*کاربر گرامی⚠️*\n\nچند عدد تجهیزات به شما اضافه شد!✔️\n\nاز بخش تجهیزات🚀 می توانید تجهیزات خود را مشاهده کنید!📌")
        return



    # اخطار / مسدود / جستجو
    if step in ("warn_uid", "unwarn_uid", "block_uid", "unblock_uid", "search_uid"):
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d{3,15}", t):
            send_message(chat_id, INVALID_UID_TEXT); return
        target = int(t)
        if str(target) not in DATA["users"] and step != "search_uid":
            # برای سرچ هم اگر نبود بساز نکن
            send_message(chat_id, NOT_STARTED_TEXT); return
        if step == "search_uid":
            if str(target) not in DATA["users"]:
                send_message(chat_id, NOT_STARTED_TEXT, admin_panel_kb()); clear_pending(uid); return
            clear_pending(uid)
            send_message(chat_id, equipment_status_text(target), admin_panel_kb())
            return
        tu = get_user(target)
        if step == "warn_uid":
            with LOCK:
                tu["warnings"] = int(tu.get("warnings") or 0) + 1
                w = tu["warnings"]
                if w >= 3:
                    tu["blocked"] = True
                save_data()
            clear_pending(uid)
            send_message(chat_id,
                f"*ادمین گرامی⚠️*\n\nکاربر مورد نظر اخطار دریافت کرد!✔️\n\nاخطار کاربر مورد نظر برابر با {fad(w)}/۳ شد📌",
                admin_panel_kb())
            try:
                if w >= 3:
                    send_message(target, "*کاربر گرامی⚠️*\n\nشما از ربات مسدود شدید!✖️\n\nشما تخلف کردید!📌")
                else:
                    send_message(target,
                        f"*کاربر گرامی⚠️*\n\nشما از طرف ربات اخطار دریافت کردید!✖️\n\nاخطار شما برابر با {w}/۳ می باشد!📌")
            except Exception:
                pass
            return
        if step == "unwarn_uid":
            w = int(tu.get("warnings") or 0)
            if w <= 0:
                clear_pending(uid)
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nاین کاربر اخطاری ندارد!✔️\n\nنیازی به رفع اخطار نیست!📌",
                    admin_panel_kb()); return
            with LOCK:
                tu["warnings"] = w - 1
                w = tu["warnings"]
                if w < 3:
                    tu["blocked"] = False
                save_data()
            clear_pending(uid)
            send_message(chat_id,
                f"*ادمین گرامی⚠️*\n\n1 اخطار کاربر رفع شد!✔️\n\nاخطار کاربر برابر با {w}/۳ شد!📌",
                admin_panel_kb())
            try:
                send_message(target,
                    f"*کاربر گرامی⚠️*\n\n1 اخطار شما توسط ربات رفع شد!✔️\n\nاخطار شما برابر با {w}/۳ می باشد!📌")
            except Exception:
                pass
            return
        if step == "block_uid":
            if tu.get("blocked"):
                clear_pending(uid)
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nکاربر مورد از پیش مسدود بوده است!✔️\n\nنیازی به مسدود کردن کاربر نیست!📌",
                    admin_panel_kb()); return
            with LOCK:
                tu["blocked"] = True
                save_data()
            clear_pending(uid)
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nکاربر مورد نظر از ربات مسدود شد!✔️\n\nعملیات مسدودی با موفقیت انجام شد!📌",
                admin_panel_kb())
            try:
                send_message(target,
                    "*کاربر گرامی⚠️*\n\nشما توسط ربات مسدود شدید!✔️\n\nشما تخلف کردید!📌")
            except Exception:
                pass
            return
        if step == "unblock_uid":
            if not tu.get("blocked"):
                clear_pending(uid)
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nکاربر مورد از پیش مسدود نبوده است!✖️\n\nنیازی به رفع مسدودی کاربر نیست!📌",
                    admin_panel_kb()); return
            with LOCK:
                tu["blocked"] = False
                save_data()
            clear_pending(uid)
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nکاربر مورد نظر از مسدودی خارج شد!✔️\n\nسپاس از توجه شما!📌",
                admin_panel_kb())
            try:
                send_message(target,
                    "*کاربر گرامی⚠️*\n\nشما توسط ربات از مسدودی خارج شدید!✔️\n\nحال می توانید از ربات استفاده کنید!📌")
            except Exception:
                pass
            return

    # ساخت / ویرایش دکمه
    if step == "btn_create_name":
        name = text.strip()
        if not name or name == "🔙 بازگشت":
            clear_pending(uid); send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
        set_pending(uid, "btn_create_text", name=name)
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nمتن این دکمه را وارد نمایید!✔️\n\nمتن دارای طول مناسب باشد و تنها در یک پیام ارسال گردد!📌",
            RK([["🔙 بازگشت"]])); return
    if step == "btn_create_text":
        if text == "🔙 بازگشت":
            clear_pending(uid); send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
        name = pend.get("name")
        bid = f"cb{int(time.time())}"
        with LOCK:
            DATA.setdefault("custom_buttons", []).append({"id": bid, "name": name, "text": text})
            # از لیست حذف‌شده‌ها دربیاور اگر دوباره ساخته شد
            dn = DATA.get("deleted_button_names") or []
            if name in dn:
                dn.remove(name)
                DATA["deleted_button_names"] = dn
            save_data()
        clear_pending(uid)
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nدکمه جدید با موفقیت ساخته شد!✔️\n\nعملیات ساخت دکمه موفقیت آمیز بود!📌",
            admin_panel_kb()); return
    if step == "btn_edit_text":
        if text == "🔙 بازگشت":
            clear_pending(uid); send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
        bid = pend.get("bid")
        with LOCK:
            for b in DATA.get("custom_buttons") or []:
                if b.get("id") == bid:
                    b["text"] = text
                    break
            save_data()
        clear_pending(uid)
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nدکمه مورد نظر با موفقیت ویرایش شد!✔️\n\nاز شما متشکریم!📌",
            admin_panel_kb()); return


    # ap / dp / ag — آیدی عددی
    t = to_en_digits(text).strip()
    if not re.fullmatch(r"\d{3,15}", t):
        send_message(chat_id, INVALID_UID_TEXT)
        return
    target = int(t)
    if str(target) not in DATA["users"]:
        send_message(chat_id, NOT_STARTED_TEXT)
        return

    if step == "ap":
        set_pending(uid, "ap_level", target=target)
        send_message(chat_id, PRINTER_LEVEL_ASK, printer_level_kb())
    elif step == "dp":
        tu = DATA["users"][str(target)]
        with LOCK:
            if tu.get("printer"):
                tu["printer"] = 0
                save_data()
                msg_text = PRINTER_REMOVED_TEXT
            else:
                msg_text = PRINTER_OFF_TEXT
        clear_pending(uid)
        send_message(chat_id, msg_text, admin_panel_kb())
    elif step == "ag":
        i = pend.get("idx", 0)
        flag, en, name, vip = COUNTRIES[i]
        tu = DATA["users"][str(target)]
        if tu.get("country"):
            send_message(chat_id, GIFT_HAS_COUNTRY_TEXT)
            return
        with LOCK:
            DATA.setdefault("destroyed", {}).pop(en, None)
            DATA["countries"][en] = {
                "owner": target, "power": BASE_COUNTRY_POWER,
                "hacked_until": None, "start_ts": time.time(),
            }
            tu["country"] = en
            tu["banned"] = False
            tu["country_start"] = time.time()
            tu["satisfaction"] = 0
            tu["houses"] = {}
            tu["hq"] = tu["pc"] = tu["comm"] = tu["sat"] = 0
            tu["hackers"] = {}
            tu["antihackers"] = {}
            tu["workers_perm"] = 0
            tu["workers_temp"] = []
            tu["food"] = 0
            tu["coins"] = START_COINS
            tu["equipment"] = {}
            tu["hack_until"] = None
            save_data()
        clear_pending(uid)
        print(f"[GIFT] {en} -> {target}")
        send_message(chat_id, GIFT_OK_TEXT, admin_panel_kb())
        send_message(target,
            f"*کاربر گرامی⚠️*\n\nکشور {flag} {name} به شما اهدا شد!✔️\n\n"
            f"از صفر شروع کنید — موجودی: {coins_fa(START_COINS)}📌")


# ───────────────────────────── فروشگاه اقتصادی ─────────────────────────────
def handle_eco_select(uid, chat_id, text):
    for n, it in enumerate(ECO_ITEMS, 1):
        if text == it["btn"]:
            # نمایش کارت + تأیید/لغو شیشه‌ای
            card = f"{it['title']}\n{it['price_t']}\n{it['profit_t']}"
            if it.get("oil_t"):
                card += "\n" + it["oil_t"]
            set_pending(uid, "eco_buy", n=n)
            send_message(chat_id, card, {"inline_keyboard": IK([[("خرید✔️", f"eb{n}"), ("لغو✖️", "se")]])})
            return
    for lvl in (1, 2, 3):
        if text == f"دستگاه چاپ پول سطح {LVL_FA[lvl]} 🎁":
            name, price, income = PRINTERS[lvl]
            card = (f"*« {name} »*\n\n"
                    f"قیمت : {price}\n"
                    f"درآمد : {income}\n\n"
                    f"برای خرید به آیدی زیر مراجعه نمایید!✔️\n\n"
                    f"- @gymrooo")
            send_message(chat_id, card, eco_kb())
            return
    if text == "🔙 بازگشت":
        send_message(chat_id, SHOP_TEXT, shop_kb())
        return
    send_message(chat_id, UNKNOWN_TEXT, eco_kb())

def on_eco_buy(uid, chat_id, mid, n):
    if not (1 <= n <= len(ECO_ITEMS)):
        return
    it = ECO_ITEMS[n - 1]
    u = get_user(uid)
    if not u.get("country"):
        clear_pending(uid)
        edit_message(chat_id, mid, NEED_COUNTRY_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", main_menu_kb(uid))
        return
    ok, bal = True, 0
    with LOCK:
        if u["coins"] < it["price"]:
            ok, bal = False, u["coins"]
        else:
            u["coins"] -= it["price"]
            u["equipment"][it["id"]] = u["equipment"].get(it["id"], 0) + 1
            save_data()
    clear_pending(uid)
    if ok:
        print(f"[BUY] {uid} -> {it['id']}")
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", eco_kb())
    else:
        edit_message(chat_id, mid,
                     f"*کاربر گرامی⚠️*\n\nدارایی شما {coins_fa(bal)} است!✔️\n\nتوان خرید این تجهیزات را ندارید!📌")
        send_message(chat_id, "از منوی زیر استفاده کنید.", eco_kb())

# ───────────────────────────── فروشگاه دفاعی ─────────────────────────────
def handle_def_select(uid, chat_id, text):
    for n, it in enumerate(DEF_ITEMS, 1):
        if text == it["btn"]:
            card = f"{it['btn']}\nقیمت کل: {it['pt']} 💸\nقدرت تخریب: {fad(it['power'])}"
            set_pending(uid, "def_buy", n=n)
            send_message(chat_id, card, {"inline_keyboard": IK([[("خرید✔️", f"db{n}"), ("لغو✖️", "sd")]])})
            return
    if text == "🛡پدافند ضد بمب اتم":
        send_message(chat_id, NUKE_CARD_TEXT, def_kb())
        return
    if text == "🔙 بازگشت":
        send_message(chat_id, SHOP_TEXT, shop_kb())
        return
    send_message(chat_id, UNKNOWN_TEXT, def_kb())

def on_def_buy(uid, chat_id, mid, n):
    if not (1 <= n <= len(DEF_ITEMS)):
        return
    it = DEF_ITEMS[n - 1]
    u = get_user(uid)
    if not u.get("country"):
        clear_pending(uid)
        edit_message(chat_id, mid, NEED_COUNTRY_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", main_menu_kb(uid))
        return
    ok, bal = True, 0
    with LOCK:
        if u["coins"] < it["price"]:
            ok, bal = False, u["coins"]
        else:
            u["coins"] -= it["price"]
            u["equipment"][it["id"]] = u["equipment"].get(it["id"], 0) + 1
            u.setdefault("def_hp", {})[it["id"]] = int(u.get("def_hp", {}).get(it["id"], 0) or 0) + it["power"]
            
            en = u.get("country")
            c = DATA["countries"].get(en)
            if isinstance(c, dict):
                c["power"] = int(c.get("power") or BASE_COUNTRY_POWER) + it["power"]
            elif en:
                DATA["countries"][en] = {"owner": uid, "power": BASE_COUNTRY_POWER + it["power"], "hacked_until": None, "start_ts": time.time()}
            save_data()
    clear_pending(uid)
    if ok:
        print(f"[BUY] {uid} -> {it['id']}")
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", def_kb())
    else:
        edit_message(chat_id, mid,
                     f"*کاربر گرامی⚠️*\n\nدارایی شما {coins_fa(bal)} است!✔️\n\nتوان خرید این تجهیزات را ندارید!📌")
        send_message(chat_id, "از منوی زیر استفاده کنید.", def_kb())

# ───────────────────────────── فروشگاه جنگی ─────────────────────────────
def handle_war_cat_select(uid, chat_id, text):
    for c in WAR_CATS:
        if text == c["btn"]:
            set_pending(uid, "war_cat", key=c["key"])
            msg = f"*کاربر گرامی⚠️*\n\n{c['phrase']}!✔️\n\nاز منوی زیر استفاده کنید!📌"
            send_message(chat_id, msg, war_items_kb(c["key"]))
            return
    if text == "🔙 بازگشت":
        send_message(chat_id, SHOP_TEXT, shop_kb())
        return
    send_message(chat_id, UNKNOWN_TEXT, war_kb())

def handle_war_item_select(uid, chat_id, text, key):
    cat = WAR_CAT_MAP.get(key)
    if not cat:
        send_message(chat_id, WAR_TEXT, war_kb())
        return
    if text == "🔙 بازگشت":
        clear_pending(uid)
        send_message(chat_id, WAR_TEXT, war_kb())
        return
    for idx, it in enumerate(cat["items"]):
        label = _war_btn_label(it["name"])
        if text == label or text == it["name"]:
            price_line = f"💸 قیمت کل: {it['price_t']}"
            if it["dia"]:
                price_line += f" + {fnum(it['dia'])} الماس"
            card = f"{it['name']}\n{price_line}\nقدرت تخریب: {fad(it['power'])}"
            set_pending(uid, "war_buy", key=key, idx=idx)
            send_message(chat_id, card, {"inline_keyboard": IK([[("خرید✔️", f"wb:{key}:{idx}"), ("لغو✖️", f"wc{key}")]])})
            return
    send_message(chat_id, UNKNOWN_TEXT, war_items_kb(key))

def on_war_buy(uid, chat_id, mid, key, idx):
    cat = WAR_CAT_MAP.get(key)
    if not cat or idx >= len(cat["items"]):
        return
    it = cat["items"][idx]
    u = get_user(uid)
    if not u.get("country"):
        clear_pending(uid)
        edit_message(chat_id, mid, NEED_COUNTRY_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", main_menu_kb(uid))
        return
    eq_id = f"{key}_{idx + 1}"
    ok = True
    coins = u["coins"]
    dia = u["diamonds"]
    with LOCK:
        if u["coins"] < it["price"] or u["diamonds"] < it["dia"]:
            ok = False
        else:
            u["coins"] -= it["price"]
            u["diamonds"] -= it["dia"]
            u["equipment"][eq_id] = u["equipment"].get(eq_id, 0) + 1
            save_data()
    set_pending(uid, "war_cat", key=key)
    if ok:
        print(f"[BUY] {uid} -> {eq_id}")
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", war_items_kb(key))
    else:
        if it["dia"]:
            bal = f"دارایی شما {coins_fa(coins)} و {fnum(dia)} الماس است!✔️"
        else:
            bal = f"دارایی شما {coins_fa(coins)} است!✔️"
        edit_message(chat_id, mid,
                     f"*کاربر گرامی⚠️*\n\n{bal}\n\nتوان خرید این تجهیزات را ندارید!📌")
        send_message(chat_id, "از منوی زیر استفاده کنید.", war_items_kb(key))

# ───────────────────────────── سود نیمه‌شب ─────────────────────────────
def calc_user_daily_income(u):
    """محاسبه سود روزانه یک کاربر از تجهیزات اقتصادی + چاپ‌پول + نفت"""
    income = 0
    for iid, cnt in u.get("equipment", {}).items():
        eco = ECO_MAP.get(iid)
        if eco and cnt:
            income += eco["profit"] * int(cnt)
    oil_gain = int(u.get("equipment", {}).get("eco6", 0) or 0) * OIL_PER_FIELD
    lvl = int(u.get("printer") or 0)
    if lvl in PRINTER_INCOME:
        income += PRINTER_INCOME[lvl]
    return income, oil_gain

def distribute_profits():
    """پرداخت سود روزانه — فقط تجهیزات اقتصادی و دستگاه چاپ پول سود می‌دهند
    (تجهیزات دفاعی و جنگی فقط قدرت تخریب دارند و سود روزانه ندارند)"""
    payouts = []
    with LOCK:
        for uid, u in list(DATA["users"].items()):
            income, oil_gain = calc_user_daily_income(u)
            if income or oil_gain:
                u["coins"] = int(u.get("coins", 0)) + income
                u["oil"] = int(u.get("oil", 0)) + oil_gain
                payouts.append((uid, income, oil_gain))
                pass  # quiet
        DATA["last_payout"] = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
        save_data()
    pass  # quiet
    if NOTIFY_PROFIT:
        for uid, income, oil in payouts:
            try:
                text = f"*کاربر گرامی⚠️*\n\nسود روزانه تجهیزات شما به مبلغ {coins_fa(income)} پرداخت شد!✔️"
                if oil:
                    text += f"\n\n{fad(oil)} بشکه نفت نیز به موجودی شما اضافه شد!📌"
                send_message(int(uid), text)
            except Exception as e:
                print(f"[PROFIT] ارسال پیام به {uid} ناموفق: {e}")
            time.sleep(0.05)

def catchup_payout():
    """اگر ربات موقع نیمه‌شب خاموش بوده، هنگام روشن شدن پرداخت معوقه انجام می‌شود"""
    now = datetime.now(TEHRAN_TZ)
    today = now.strftime("%Y-%m-%d")
    last = DATA.get("last_payout")
    if last is None:
        DATA["last_payout"] = today
        save_data()
        pass  # quiet
        return
    # اگر آخرین پرداخت مربوط به امروز نبود و از ساعت ۰۰:۰۰:۰۱ گذشته → پرداخت
    if last < today:
        pass  # quiet
        distribute_profits()
    else:
        pass  # quiet

def profit_worker():
    with LOCK:
        catchup_payout()
    while True:
        now = datetime.now(TEHRAN_TZ)
        target = now.replace(hour=0, minute=0, second=1, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - datetime.now(TEHRAN_TZ)).total_seconds()
        pass  # quiet
        time.sleep(max(1, wait))
        try:
            # جلوگیری از پرداخت دوباره در همان روز
            today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
            if DATA.get("last_payout") == today:
                pass  # quiet
            else:
                distribute_profits()
        except Exception as e:
            print("[PROFIT] خطا:", e)
        try:
            check_satisfaction()
        except Exception:
            pass
        time.sleep(5)


def on_hack_eq_buy(uid, chat_id, mid, eq_id):
    it = HACK_EQ_MAP.get(eq_id)
    if not it:
        return
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    if not u.get("country"):
        clear_pending(uid); edit_message(chat_id, mid, NEED_COUNTRY_TEXT); return
    if eq_id == "pc":
        if int(u.get("hq") or 0) < 50:
            clear_pending(uid); edit_message(chat_id, mid, NEED_BASE_FOR_PC)
            send_message(chat_id, "از منوی زیر استفاده کنید.", hack_eq_kb()); return
        if int(u.get("comm") or 0) < 50:
            clear_pending(uid); edit_message(chat_id, mid, NEED_COMM50_TEXT)
            send_message(chat_id, "از منوی زیر استفاده کنید.", hack_eq_kb()); return
    if eq_id in ("comm", "sat") and int(u.get("hq") or 0) < 10:
        clear_pending(uid); edit_message(chat_id, mid, NEED_BASE50_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_eq_kb()); return
    coins, dia = int(u["coins"]), int(u["diamonds"])
    ok = True
    with LOCK:
        if coins < it["price"] or dia < it["dia"]:
            ok = False
        else:
            u["coins"] -= it["price"]; u["diamonds"] -= it["dia"]
            u[eq_id] = int(u.get(eq_id) or 0) + it["pack"]
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, f"موجودی {it['btn']}: {fad(u[eq_id])}", hack_eq_kb())
    else:
        edit_message(chat_id, mid, insufficient_msg(it["price"], it["dia"], coins, dia))
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_eq_kb())

def on_anti_hack_buy(uid, chat_id, mid, gid):
    it = ANTI_HACK_MAP.get(gid)
    if not it: return
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    if not u.get("country"):
        clear_pending(uid); edit_message(chat_id, mid, NEED_COUNTRY_TEXT); return
    if not can_hack_ops(u):
        clear_pending(uid)
        edit_message(chat_id, mid, hack_eq_missing_text(u))
        send_message(chat_id, "از منوی زیر استفاده کنید.", anti_hack_kb()); return
    coins, dia = int(u["coins"]), int(u["diamonds"])
    ok = True
    with LOCK:
        if coins < it["price"] or dia < it["dia"]:
            ok = False
        else:
            u["coins"] -= it["price"]; u["diamonds"] -= it["dia"]
            ah = u.setdefault("antihackers", {}); ah[gid] = ah.get(gid, 0) + 1
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", anti_hack_kb())
    else:
        edit_message(chat_id, mid, insufficient_msg(it["price"], it["dia"], coins, dia))
        send_message(chat_id, "از منوی زیر استفاده کنید.", anti_hack_kb())

def on_hack_group_buy(uid, chat_id, mid, gid):
    it = HACK_GROUP_MAP.get(gid)
    if not it: return
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    if not u.get("country"):
        clear_pending(uid); edit_message(chat_id, mid, NEED_COUNTRY_TEXT); return
    if not can_hack_ops(u):
        clear_pending(uid)
        edit_message(chat_id, mid, hack_eq_missing_text(u))
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_group_kb()); return
    coins, dia = int(u["coins"]), int(u["diamonds"])
    ok = True
    with LOCK:
        if coins < it["price"] or dia < it["dia"]:
            ok = False
        else:
            u["coins"] -= it["price"]; u["diamonds"] -= it["dia"]
            hk = u.setdefault("hackers", {}); hk[gid] = hk.get(gid, 0) + 1
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_group_kb())
    else:
        edit_message(chat_id, mid, insufficient_msg(it["price"], it["dia"], coins, dia))
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_group_kb())

def on_worker_rent_buy(uid, chat_id, mid, idx):
    if idx < 0 or idx >= len(WORKER_RENT): return
    w = WORKER_RENT[idx]
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    if not u.get("country"):
        clear_pending(uid); edit_message(chat_id, mid, NEED_COUNTRY_TEXT); return
    if int(u.get("food") or 0) < w["food"]:
        clear_pending(uid); edit_message(chat_id, mid, NO_FOOD_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", worker_kb()); return
    coins = int(u["coins"]); ok = True
    with LOCK:
        if coins < w["price"]:
            ok = False
        else:
            u["coins"] -= w["price"]
            u["food"] = int(u.get("food") or 0) - w["food"]
            u.setdefault("workers_temp", []).append({"n": w["n"], "until": time.time() + w["days"] * 86400})
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, f"کارگران فعال: {fad(active_workers(u))}", worker_kb())
    else:
        edit_message(chat_id, mid, NO_COIN_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", worker_kb())

def on_worker_perm_buy(uid, chat_id, mid):
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    if not u.get("country"):
        clear_pending(uid); edit_message(chat_id, mid, NEED_COUNTRY_TEXT); return
    if int(u.get("food") or 0) < WORKER_FOOD_PER_DAY:
        clear_pending(uid); edit_message(chat_id, mid, NO_FOOD_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", worker_kb()); return
    coins = int(u["coins"]); ok = True
    with LOCK:
        if coins < WORKER_BUY_PRICE:
            ok = False
        else:
            u["coins"] -= WORKER_BUY_PRICE
            u["food"] = int(u.get("food") or 0) - WORKER_FOOD_PER_DAY
            u["workers_perm"] = int(u.get("workers_perm") or 0) + 1
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, f"کارگران فعال: {fad(active_workers(u))}", worker_kb())
    else:
        edit_message(chat_id, mid, NO_COIN_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", worker_kb())

def on_house_buy(uid, chat_id, mid, hid):
    it = next((h for h in HOUSE_ITEMS if h["id"] == hid), None)
    if not it: return
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    if not u.get("country"):
        clear_pending(uid); edit_message(chat_id, mid, NEED_COUNTRY_TEXT); return
    if active_workers(u) < it["workers"]:
        clear_pending(uid); edit_message(chat_id, mid, NO_WORKER_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", house_kb()); return
    coins = int(u["coins"]); ok = True
    with LOCK:
        if coins < it["price"]:
            ok = False
        else:
            u["coins"] -= it["price"]
            hs = u.setdefault("houses", {}); hs[hid] = hs.get(hid, 0) + 1
            u["satisfaction"] = int(u.get("satisfaction") or 0) + it["sat"]
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, f"رضایت مردم: {fad(u['satisfaction'])}٪", house_kb())
    else:
        edit_message(chat_id, mid, NO_COIN_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", house_kb())

def on_food_buy(uid, chat_id, mid, packs):
    u = get_user(uid)
    if is_hacked(u):
        clear_pending(uid); edit_message(chat_id, mid, HACKED_TEXT); return
    cost = packs * FOOD_PACK_PRICE
    coins = int(u["coins"]); ok = True
    with LOCK:
        if coins < cost:
            ok = False
        else:
            u["coins"] -= cost
            u["food"] = int(u.get("food") or 0) + packs * 100
            save_data()
    clear_pending(uid)
    if ok:
        edit_message(chat_id, mid, BUY_OK_TEXT)
        send_message(chat_id, f"موجودی غذا: {fad(u['food'])}", build_kb())
    else:
        edit_message(chat_id, mid, NO_COIN_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", build_kb())


# ───────────────────────────── مسیریابی Callback (فقط تأیید/لغو) ─────────────────────────────
def route_callback(uid, chat_id, mid, data):
    if data.startswith("cy"):  # تأیید کشور
        on_country_confirm(uid, chat_id, mid, int(data[2:]))
    elif data == "cx":  # لغو کشور
        clear_pending(uid)
        edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "به لیست کشورها بازگشتید.", country_kb())
    elif data.startswith("eb"):  # خرید اقتصادی
        on_eco_buy(uid, chat_id, mid, int(data[2:]))
    elif data == "se":  # لغو اقتصادی
        clear_pending(uid)
        edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", eco_kb())
    elif data.startswith("db"):  # خرید دفاعی
        on_def_buy(uid, chat_id, mid, int(data[2:]))
    elif data == "sd":  # لغو دفاعی
        clear_pending(uid)
        edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", def_kb())
    elif data.startswith("wb:"):  # خرید جنگی
        _, key, idx = data.split(":")
        on_war_buy(uid, chat_id, mid, key, int(idx))
    elif data.startswith("wc"):  # لغو جنگی
        key = data[2:]
        clear_pending(uid)
        set_pending(uid, "war_cat", key=key)
        edit_message(chat_id, mid, CANCEL_TEXT)
        cat = WAR_CAT_MAP.get(key)
        phrase = cat["phrase"] if cat else "تجهیزات"
        send_message(chat_id, f"*کاربر گرامی⚠️*\n\n{phrase}!✔️\n\nاز منوی زیر استفاده کنید!📌", war_items_kb(key))
    elif data == "fjok":
        if missing_force_channels(uid):
            edit_message(chat_id, mid, FORCE_JOIN_TEXT)
            send_message(chat_id, FORCE_JOIN_TEXT, force_join_kb())
        else:
            clear_pending(uid)
            try:
                edit_message(chat_id, mid, "*کاربر گرامی⚠️*\n\nعضویت شما تأیید شد!✔️")
            except Exception:
                pass
            send_message(chat_id, WELCOME, main_menu_kb(uid))
    elif data.startswith("sup:"):
        target = int(data[4:])
        clear_pending(uid)
        set_pending(uid, "admin_reply", target=target)
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nپیام خود را برای کاربر ارسال نمایید!✔️\n\nمنتظر پاسخ گویی شما هستیم!📌",
            RK([["🔙 بازگشت"]]))
    elif data.startswith("ha:"):
        target_en = data[3:]
        clear_pending(uid)
        ok, msg = do_hack_attack(uid, target_en)
        edit_message(chat_id, mid, msg)
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_menu_kb())
    elif data == "hac":
        clear_pending(uid)
        edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_menu_kb())
    elif data.startswith("he:"):
        on_hack_eq_buy(uid, chat_id, mid, data[3:])
    elif data == "hec":
        clear_pending(uid); edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_eq_kb())
    elif data.startswith("ah:"):
        on_anti_hack_buy(uid, chat_id, mid, data[3:])
    elif data == "ahc":
        clear_pending(uid); edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", anti_hack_kb())
    elif data.startswith("hk:"):
        on_hack_group_buy(uid, chat_id, mid, data[3:])
    elif data == "hkc":
        clear_pending(uid); edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", hack_group_kb())
    elif data.startswith("wr:"):
        on_worker_rent_buy(uid, chat_id, mid, int(data[3:]))
    elif data == "wp":
        on_worker_perm_buy(uid, chat_id, mid)
    elif data == "wrc":
        clear_pending(uid); edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", worker_kb())
    elif data.startswith("hb:"):
        on_house_buy(uid, chat_id, mid, data[3:])
    elif data == "hbc":
        clear_pending(uid); edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", house_kb())
    elif data.startswith("fd:"):
        on_food_buy(uid, chat_id, mid, int(data[3:]))
    elif data == "fdc":
        clear_pending(uid); edit_message(chat_id, mid, CANCEL_TEXT)
        send_message(chat_id, "از منوی زیر استفاده کنید.", build_kb())


def on_callback(cb):
    frm = cb.get("from") or {}
    uid = frm.get("id")
    msg = cb.get("message") or {}
    chat = msg.get("chat") or {}
    # فقط چت خصوصی — کانال و گروه نادیده گرفته می‌شوند
    if chat.get("type") and chat.get("type") != "private":
        if cb.get("id"):
            api("answerCallbackQuery", callback_query_id=cb["id"])
        return
    chat_id = chat.get("id")
    mid = msg.get("message_id")
    data = cb.get("data") or ""
    if cb.get("id"):
        api("answerCallbackQuery", callback_query_id=cb["id"])
    if uid is None or chat_id is None or mid is None:
        return
    # مسدود / خاموش — کال‌بک هم جواب نده (ادمین مستثنی)
    if is_user_blocked(uid) and not is_admin(uid):
        return
    if not is_bot_on() and not is_admin(uid):
        return
    try:
        route_callback(uid, chat_id, mid, data)
    except Exception as e:
        print("[CB ERROR]", data, e)

# ───────────────────────────── مسیریابی پیام‌های متنی (دکمه اصلی) ─────────────────────────────
def on_message(msg):
    chat = msg.get("chat") or {}
    # فقط پیام‌های خصوصی — کانال / گروه / سوپرگروه کاملاً نادیده
    if chat.get("type") != "private":
        return
    frm = msg.get("from") or {}
    uid = frm.get("id")
    if uid is None:
        return
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    get_user(uid)

    # مسدود کامل — هیچ جوابی
    if is_user_blocked(uid) and not is_admin(uid):
        return

    # ربات خاموش — فقط ادمین
    if not is_bot_on() and not is_admin(uid):
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nربات در حال حاضر خاموش است!✖️\n\nلطفا منتظر بمانید!📌")
        return

    # اسپم: ۷ کلیک در ۵ ثانیه — نادیده (ادمین معاف)
    if text and check_spam(uid):
        return

    if text.startswith("/start"):
        clear_pending(uid)
        if require_force_join(uid, chat_id):
            return
        send_message(chat_id, WELCOME, main_menu_kb(uid))
        return

    # عضویت اجباری (غیر ادمین)
    if not is_admin(uid) and missing_force_channels(uid):
        if text != "🔙 بازگشت":
            require_force_join(uid, chat_id)
            return

    # روشن/خاموش — اولویت بالا (فقط ادمین)
    if is_admin(uid) and text:
        _tn = text.replace("\ufe0f", "").replace("\u200c", "").strip()
        if "روشن کردن ربات" in text or "روشن کردن ربات" in _tn:
            if is_bot_on():
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات در حال حاضر روشن است!✔️\n\nنیازی به روشن کردن مجدد ربات نیست!📌",
                    admin_panel_kb(uid))
            else:
                DATA["bot_on"] = True
                save_data()
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات با موفقیت روشن شد!✔️\n\nممنون از شما!📌",
                    admin_panel_kb(uid))
            return
        if "خاموش کردن ربات" in text or "خاموش کردن ربات" in _tn:
            if not is_bot_on():
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات در حال حاضر خاموش است!✔️\n\nنیازی به خاموش کردن مجدد ربات نیست!📌",
                    admin_panel_kb(uid))
            else:
                DATA["bot_on"] = False
                save_data()
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات با موفقیت خاموش شد!✔️\n\nممنون از شما!📌",
                    admin_panel_kb(uid))
            return

    # ورودی متنی ادمین (آیدی عددی)
    if is_admin(uid) and uid in PENDING:
        pend = get_pending(uid)
        if pend and pend.get("step") in (
            "ap", "dp", "ag",
            "gift_dia_uid", "deduct_dia_uid", "gift_dia_amt", "deduct_dia_amt",
            "gift_coin_uid", "deduct_coin_uid", "gift_coin_amt", "deduct_coin_amt",
            "gift_oil_uid", "gift_oil_amt",
            "gift_force_uid", "gift_force_section",
            "gift_force_cat", "gift_force_item", "gift_force_qty",
            "gift_force_eco", "gift_force_def",
            "gift_force_hack_menu", "gift_force_hack_eq", "gift_force_hack_anti", "gift_force_hack_grp",
            "warn_uid", "unwarn_uid", "block_uid", "unblock_uid", "search_uid",
            "btn_create_name", "btn_create_text", "btn_edit_text",
        ):
            admin_text_input(uid, chat_id, text)
            return
        if pend and pend.get("step") == "ap_level":
            target = pend.get("target")
            if text in ("سطح ۱ 🎁", "سطح ۱", "1"):
                on_set_printer(1, target)
                clear_pending(uid)
                return
            if text in ("سطح ۲ 🎁", "سطح ۲", "2"):
                on_set_printer(2, target)
                clear_pending(uid)
                return
            if text in ("سطح ۳ 🎁", "سطح ۳", "3"):
                on_set_printer(3, target)
                clear_pending(uid)
                return
            if text == "🔙 بازگشت":
                clear_pending(uid)
                send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb())
                return

    pend = get_pending(uid)

    # پشتیبانی / پاسخ ادمین — حتی پیام بدون متن (عکس/ویس/...)
    if pend and pend.get("step") == "support_wait":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        deliver_support_to_admins(uid, chat_id, msg)
        clear_pending(uid)
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nپیام شما برای پشتیبانی ارسال گشت!✔️\n\nپشتیبانی به زودی جواب شما را خواهد داد!📌",
            main_menu_kb(uid))
        return
    if is_admin(uid) and pend and pend.get("step") == "admin_reply":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
        try:
            if msg.get("text"):
                send_message(target, msg.get("text"), md=False)
            elif msg.get("photo"):
                api("sendPhoto", chat_id=target, photo=msg["photo"][-1]["file_id"], caption=msg.get("caption") or "")
            elif msg.get("video"):
                api("sendVideo", chat_id=target, video=msg["video"]["file_id"], caption=msg.get("caption") or "")
            elif msg.get("voice"):
                api("sendVoice", chat_id=target, voice=msg["voice"]["file_id"])
            elif msg.get("audio"):
                api("sendAudio", chat_id=target, audio=msg["audio"]["file_id"])
            elif msg.get("document"):
                api("sendDocument", chat_id=target, document=msg["document"]["file_id"], caption=msg.get("caption") or "")
            elif msg.get("animation"):
                api("sendAnimation", chat_id=target, animation=msg["animation"]["file_id"])
            else:
                api("forwardMessage", chat_id=target, from_chat_id=chat_id, message_id=msg.get("message_id"))
            clear_pending(uid)
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nپیام شما با موفقیت برای کاربر ارسال شد!✔️\n\nاز زحمات شما سپاسگزاریم!📌",
                admin_panel_kb())
        except Exception as e:
            print("[ADMIN REPLY]", e)
            send_message(chat_id, "ارسال ناموفق بود.", admin_panel_kb())
        return

    # ── منوی اصلی ──
    if text == "کشورگیری🏳🏴":
        clear_pending(uid)
        send_message(chat_id, COUNTRY_TEXT, country_kb())
        return
    if text == "تجهیزات🚀":
        clear_pending(uid)
        send_message(chat_id, equipment_status_text(uid), main_menu_kb(uid))
        return
    if text == "خرید تجهیزات🔫💣":
        clear_pending(uid)
        send_message(chat_id, SHOP_TEXT, shop_kb())
        return
    if text == "⚙️ پنل ادمین" and is_admin(uid):
        clear_pending(uid)
        send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb(uid))
        return
    if text == "🔙 بازگشت":
        # بسته به وضعیت فعلی
        if pend:
            step = pend.get("step")
            if step in ("confirm_country",):
                clear_pending(uid)
                send_message(chat_id, COUNTRY_TEXT, country_kb())
                return
            if step == "war_cat":
                clear_pending(uid)
                send_message(chat_id, WAR_TEXT, war_kb())
                return
            if step in ("eco_buy", "def_buy", "war_buy"):
                # لغو از طریق دکمه شیشه‌ای انجام می‌شود؛ اینجا فقط بازگشت کلی
                clear_pending(uid)
        send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid))
        return

    # ── پنل ادمین ──
    if is_admin(uid):
        if text == "➕️ اهدا کشور":
            set_pending(uid, "admin_gift_select")
            send_message(chat_id, GIFT_SELECT_TEXT, country_kb())
            return
        if text == "➖️ حذف مدیر کشور":
            set_pending(uid, "admin_rm_select")
            send_message(chat_id, RM_SELECT_TEXT, country_kb())
            return
        if text == "➕️ افزودن دستگاه چاپ پول":
            set_pending(uid, "ap")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]]))
            return
        if text == "➖️ حذف دستگاه چاپ پول":
            set_pending(uid, "dp")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]]))
            return

        if pend and pend.get("step") == "admin_gift_select":
            handle_admin_gift_country(uid, chat_id, text)
            return
        if pend and pend.get("step") == "admin_rm_select":
            handle_admin_remove_manager(uid, chat_id, text)
            return

    # ── کشورگیری (انتخاب کشور با دکمه اصلی) ──
    if text.startswith("🇺🇳") or text.startswith("🇺🇸") or text.startswith("🇨🇳") or text.startswith("🇷🇺") or text.startswith("🇮🇳") or \
       text.startswith("🇬🇧") or text.startswith("🇫🇷") or text.startswith("🇩🇪") or text.startswith("🇰🇵") or \
       text.startswith("🇯🇵") or text.startswith("🇰🇷") or text.startswith("🇹🇷") or text.startswith("🇮🇹") or \
       text.startswith("🇧🇷") or text.startswith("🇨🇦") or text.startswith("🇦🇺") or text.startswith("🇮🇱") or \
       text.startswith("🇪🇸") or text.startswith("🇸🇦") or text.startswith("🇮🇷") or text.startswith("🇵🇰") or \
       text.startswith("🇮🇩") or text.startswith("🇲🇽") or text.startswith("🇳🇱") or text.startswith("🇵🇱") or \
       text.startswith("🇸🇪") or text.startswith("🇳🇴") or text.startswith("🇿🇦") or text.startswith("🇪🇬") or \
       text.startswith("🇦🇪") or text.startswith("🇸🇬") or text.startswith("🇨🇭") or text.startswith("🇺🇦") or \
       text.startswith("🇻🇳") or text.startswith("🇹🇭") or text.startswith("🇦🇷") or text.startswith("🇲🇾") or \
       text.startswith("🇾🇪") or text.startswith("✅️"):
        # اگر در حالت انتخاب برای اهدا/حذف ادمین هستیم، قبلاً هندل شده
        if not (pend and pend.get("step") in ("admin_gift_select", "admin_rm_select")):
            handle_country_select(uid, chat_id, text)
            return

    # ── فروشگاه ──
    if text == "خرید تجهیزات اقتصادی💰💵💵💰":
        clear_pending(uid)
        u = get_user(uid)
        msg = (f"*کاربر گرامی⚠️*\n\n"
               f"دارایی شما {coins_fa(u['coins'])} است!✔️\n\n"
               f"از میان تجهیزات اقتصادی، تجهیزات مورد نظر را انتخاب نمایید!📌")
        send_message(chat_id, msg, eco_kb())
        return
    if text == "خرید تجهیزات دفاعی🛡":
        clear_pending(uid)
        send_message(chat_id, DEF_MENU_TEXT, def_kb())
        return
    if text == "خرید تجهیزات جنگی🧨💣":
        clear_pending(uid)
        send_message(chat_id, WAR_TEXT, war_kb())
        return

    # اقتصادی
    if any(text == it["btn"] for it in ECO_ITEMS) or text.startswith("دستگاه چاپ پول سطح"):
        handle_eco_select(uid, chat_id, text)
        return

    # دفاعی
    if any(text == it["btn"] for it in DEF_ITEMS) or text == "🛡پدافند ضد بمب اتم":
        handle_def_select(uid, chat_id, text)
        return

    # دسته‌های جنگی
    if any(text == c["btn"] for c in WAR_CATS):
        handle_war_cat_select(uid, chat_id, text)
        return

    # نبرد در اولویت مطلق نسبت به خرید
    if pend and pend.get("step") == "battle_target":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        if text.startswith("⚔ "):
            label = text[2:].strip()
            target_en = None
            for flag, en, name, vip in COUNTRIES:
                if label == f"{flag} {name}":
                    target_en = en
                    break
            if not target_en:
                send_message(chat_id, UNKNOWN_TEXT, owned_countries_kb(get_user(uid).get("country"))); return
            set_pending(uid, "battle_force", target=target_en, force={})
            u = get_user(uid)
            send_message(chat_id,
                "*کاربر گرامی⚠️*\n\nنیرو های شما به شرح زیر است!✔️\n\nنیرو های مورد نظر برای حمله انتخاب نمایید!📌",
                attack_force_kb(u, {}))
            return
    if pend and pend.get("step") == "battle_force":
        target_en = pend.get("target")
        force = dict(pend.get("force") or {})
        u = get_user(uid)
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        if text == "حمله🚀":
            if not force:
                send_message(chat_id, "*کاربر گرامی⚠️*\n\nابتدا نیرو انتخاب کنید!✔️", attack_force_kb(u, force)); return
            ok, msg = do_military_attack(uid, target_en, force)
            clear_pending(uid)
            send_message(chat_id, msg, main_menu_kb(uid))
            return
        matched = None
        for eid, cnt, it in user_war_equipment(u):
            label = attack_force_btn_label(eid)
            short = war_eq_short_name(eid)
            full = (it.get("name") or "").strip()
            if text == label or text == short or text == full or text == _war_btn_label(full):
                matched = (eid, cnt, it)
                break
        if matched:
            eid, cnt, it = matched
            if force.get(eid):
                send_message(chat_id,
                    f"*کاربر گرامی⚠️*\n\nشما {fad(force[eid])} عدد از این تجهیزات را آماده حمله کردید!✔️\n\n"
                    f"اگر می خواهید با تعداد بیشتری از این نیرو حمله کنید، ابتدا حمله خود را انجام داده و سپس دوباره حمله کنید!📌",
                    attack_force_kb(u, force))
                return
            set_pending(uid, "battle_qty", target=target_en, force=force, eq=eid)
            pw = int(it["power"])
            send_message(chat_id,
                f"*کاربر گرامی⚠️*\n\n"
                f"شما {fad(cnt)} عدد از این تجهیزات دارید!\n"
                f"چند عدد را به کشور دشمن ارسال می‌کنید؟✔️\n\n"
                f"⚡ قدرت هر ۱ واحد: {fad(pw)}\n"
                f"⚡ مجموع اگر همه {fad(cnt)} تا را بفرستید: {fad(pw * cnt)}\n\n"
                f"مجموع تخریب = قدرت هر واحد × تعداد ارسالی\n\n"
                f"*لطفا تنها عدد وارد کنید! مثال : ۱۰📌*",
                RK([["🔙 بازگشت"]]))
            return
        send_message(chat_id, UNKNOWN_TEXT, attack_force_kb(u, force)); return
    if pend and pend.get("step") == "battle_qty":
        target_en = pend.get("target")
        force = dict(pend.get("force") or {})
        eid = pend.get("eq")
        u = get_user(uid)
        if text == "🔙 بازگشت":
            set_pending(uid, "battle_force", target=target_en, force=force)
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nنیرو انتخاب کنید!📌", attack_force_kb(u, force)); return
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d+", t):
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nلطفا فقط عدد وارد کنید!✔️\n\n*مثال : 10📌*"); return
        n = int(t)
        if n <= 0:
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nلطفا عددی بزرگتر از ۰ وارد کنید!✔️\n\n*مثال : 10📌*"); return
        have = int((u.get("equipment") or {}).get(eid, 0) or 0)
        if n > have:
            send_message(chat_id,
                f"*کاربر گرامی⚠️*\n\nنیرو های شما کمتر از {fad(n)} است!✔️\n\nشما نیروی کافی برای حمله با این تعداد نیرو ندارید!📌"); return
        force[eid] = n
        set_pending(uid, "battle_force", target=target_en, force=force)
        total_pw = 0
        total_u = 0
        for fe, fc in force.items():
            info = war_eq_info(fe)
            if info:
                total_pw += int(info[2]["power"]) * int(fc)
                total_u += int(fc)
        send_message(chat_id,
            f"*کاربر گرامی⚠️*\n\n"
            f"نیروهای شما جهت حمله آماده شدند!✔️\n\n"
            f"تعداد واحد انتخابی: {fad(total_u)}\n"
            f"مجموع قدرت تخریب: {fad(total_pw)}\n"
            f"نفت لازم برای حمله: {fad(total_u * OIL_COST_PER_UNIT)}\n\n"
            f"اگر می‌خواهید نیروی دیگر اضافه کنید روی آن کلیک کنید!📌",
            attack_force_kb(u, force))
        return

    # آیتم‌های جنگی برای خرید — فقط خارج از نبرد
    if not (pend and pend.get("step") in ("battle_target", "battle_force", "battle_qty")):
        if pend and pend.get("step") in ("war_cat", "war_buy"):
            key = pend.get("key")
            if key:
                handle_war_item_select(uid, chat_id, text, key)
                return
        for c in WAR_CATS:
            for it in c["items"]:
                label = _war_btn_label(it["name"])
                if text == label or text == it["name"]:
                    set_pending(uid, "war_cat", key=c["key"])
                    handle_war_item_select(uid, chat_id, text, c["key"])
                    return

    # ── گروهک هکری ──
    if text == "گروهک های هکری👨‍💻":
        clear_pending(uid)
        send_message(chat_id, HACK_MENU_TEXT, hack_menu_kb())
        return
    if text == "👨🏻‍💻 تجهیزات هکری":
        clear_pending(uid)
        send_message(chat_id, "🏢⚡ تجهیزات موردنیاز هکرها و ضد‌هکرها\n\nاز منوی زیر انتخاب کنید!📌", hack_eq_kb())
        return
    if text == "🛡️⚔️ گروهک‌های ضد‌هکری":
        clear_pending(uid)
        send_message(chat_id, "🛡️⚔️ گروهک‌های ضد‌هکری\n\nاز منوی زیر انتخاب کنید!📌", anti_hack_kb())
        return
    if text == "💻⚡ گروهک‌های هکری":
        clear_pending(uid)
        send_message(chat_id, "💻⚡ گروهک‌های هکری\n\nاز منوی زیر انتخاب کنید!📌", hack_group_kb())
        return

    if text == "⚡ حمله هکری":
        clear_pending(uid)
        u = get_user(uid)
        if is_hacked(u):
            send_message(chat_id, HACKED_TEXT, main_menu_kb(uid))
            return
        if not u.get("country"):
            send_message(chat_id, NEED_COUNTRY_TEXT, main_menu_kb(uid))
            return
        if not can_hack_ops(u):
            send_message(chat_id,
                "*کاربر گرامی⚠️*\n\nبرای حمله هکری باید حداقل ۵۰ عدد از هر تجهیز هکری داشته باشید!✔️",
                hack_menu_kb())
            return
        if total_hacker_power(u) <= 0:
            send_message(chat_id,
                "*کاربر گرامی⚠️*\n\nابتدا حداقل یک گروهک هکری بخرید!✔️",
                hack_menu_kb())
            return
        set_pending(uid, "hack_target")
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nکشور هدف برای حمله هکری را انتخاب کنید!✔️\n\nاز منوی زیر استفاده کنید!📌",
            hack_target_kb(uid))
        return
    if pend and pend.get("step") == "hack_target":
        if text.startswith("🎯 "):
            label = text[2:].strip()
            target_en = None
            for flag, en, name, vip in COUNTRIES:
                if label == f"{flag} {name}" or text == f"🎯 {flag} {name}":
                    target_en = en
                    break
            if not target_en:
                send_message(chat_id, UNKNOWN_TEXT, hack_target_kb(uid))
                return
            set_pending(uid, "hack_confirm", target=target_en)
            nm = country_name_fa(target_en)
            send_message(chat_id,
                f"*کاربر گرامی⚠️*\n\nاز حمله هکری به {nm} اطمینان دارید؟\n\n"
                f"قدرت نفوذ شما: {fad(total_hacker_power(get_user(uid)))}📌",
                {"inline_keyboard": IK([[("حمله✔️", f"ha:{target_en}"), ("لغو✖️", "hac")]])})
            return
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, HACK_MENU_TEXT, hack_menu_kb())
            return


    for it in HACK_EQ_ITEMS:
        if text == it["btn"]:
            set_pending(uid, "hack_eq", id=it["id"])
            send_message(chat_id, it["card"],
                         {"inline_keyboard": IK([[("خرید✔️", f"he:{it['id']}"), ("لغو✖️", "hec")]])})
            return
    for it in ANTI_HACK_GROUPS:
        if text == it["btn"]:
            set_pending(uid, "anti_hack", id=it["id"])
            send_message(chat_id, it["card"],
                         {"inline_keyboard": IK([[("خرید✔️", f"ah:{it['id']}"), ("لغو✖️", "ahc")]])})
            return
    for it in HACK_GROUPS:
        if text == it["btn"]:
            set_pending(uid, "hack_grp", id=it["id"])
            send_message(chat_id, it["card"],
                         {"inline_keyboard": IK([[("خرید✔️", f"hk:{it['id']}"), ("لغو✖️", "hkc")]])})
            return

    # ── ساخت و ساز ──
    if text == "ساخت و ساز⚙🛠":
        clear_pending(uid)
        send_message(chat_id, BUILD_INTRO, build_kb())
        return
    if text == "🏡 خانه":
        clear_pending(uid)
        send_message(chat_id, "*کاربر گرامی⚠️*\n\nخانه مورد نظر را انتخاب کنید!✔️", house_kb())
        return
    if text == "👨‍🔧 کارگر":
        clear_pending(uid)
        send_message(chat_id, "👷‍♂️ خرید و اجاره کارگر\n\nاز منوی زیر استفاده کنید!📌", worker_kb())
        return
    if text == "🍕 غذا":
        clear_pending(uid)
        set_pending(uid, "food_qty")
        send_message(chat_id,
                     "*کاربر گرامی⚠️*\n\nتعداد پک مورد نیاز را برای خرید غذا وارد کنید!✔️\n\nهر پک معادل ۱۰۰ عدد غذا می باشد!📌",
                     RK([["🔙 بازگشت"]]))
        return
    if pend and pend.get("step") == "food_qty":
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d+", t) or int(t) <= 0:
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nلطفا فقط عدد وارد کنید!✔️\n\n*مثال : 10📌*")
            return
        packs = int(t)
        cost_m = (packs * FOOD_PACK_PRICE) // 1_000_000
        set_pending(uid, "food_confirm", packs=packs)
        send_message(chat_id,
                     f"*کاربر گرامی⚠️*\n\nهزینه خرید {fad(packs)} پک غذا {fad(cost_m)} میلیون می باشد!✔️\n\nدر صورت تمایل تأیید کنید!📌",
                     {"inline_keyboard": IK([[("تأیید✔️", f"fd:{packs}"), ("لغو✖️", "fdc")]])})
        return
    for it in HOUSE_ITEMS:
        if text == it["btn"]:
            set_pending(uid, "house_buy", id=it["id"])
            send_message(chat_id, it["card"],
                         {"inline_keyboard": IK([[("خرید✔️", f"hb:{it['id']}"), ("لغو✖️", "hbc")]])})
            return
    if text == "💰 خرید کارگر دائمی":
        set_pending(uid, "worker_perm")
        send_message(chat_id,
                     f"*💰 خرید کارگر دائمی*\n\nقیمت: {coins_fa(WORKER_BUY_PRICE)}\nمصرف روزانه: {fad(WORKER_FOOD_PER_DAY)} پک غذا",
                     {"inline_keyboard": IK([[("خرید✔️", "wp"), ("لغو✖️", "wrc")]])})
        return
    for idx, w in enumerate(WORKER_RENT):
        if text == w["btn"]:
            set_pending(uid, "worker_rent", idx=idx)
            send_message(chat_id,
                         f"*{w['btn']}*\n\n💰 {coins_fa(w['price'])}\n🍖 {fad(w['food'])} پک غذا\n⏱ {fad(w['days'])} روز",
                         {"inline_keyboard": IK([[("خرید✔️", f"wr:{idx}"), ("لغو✖️", "wrc")]])})
            return

    # پنل ادمین الماس/سکه
    if is_admin(uid):
        if text == "💎 اهدا الماس":
            set_pending(uid, "gift_dia_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]]))
            return
        if text == "💎 کسر الماس":
            set_pending(uid, "deduct_dia_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]]))
            return
        if text == "💰 اهدا سکه":
            set_pending(uid, "gift_coin_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]]))
            return
        if text == "💰 کسر سکه":
            set_pending(uid, "deduct_coin_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]]))
            return

    # اگر چیزی شناخته نشد

    # ── بیانیه ──
    if text == "ارسال بیانیه📝":
        clear_pending(uid)
        u = get_user(uid)
        if is_hacked(u):
            send_message(chat_id, HACKED_TEXT, main_menu_kb(uid)); return
        if not u.get("country"):
            send_message(chat_id, NEED_COUNTRY_TEXT, main_menu_kb(uid)); return
        set_pending(uid, "statement")
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nمتن خود را جهت ارسال بیانیه ارسال نمایید!✔️\n\nمتن شما باید همراه با رعایت ادب باشد!📌",
            RK([["🔙 بازگشت"]]))
        return
    if pend and pend.get("step") == "statement":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        # فقط متن
        if not text or msg.get("photo") or msg.get("video") or msg.get("animation") or msg.get("document"):
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nلطفا تنها متن ارسال نمایید!✔️\n\nاز شما متشکریم!📌")
            return
        u = get_user(uid)
        en = u.get("country")
        flag_url = FLAG_URLS.get(en)
        caption = f"🔥⚔️ *WORLD WAR* ⚔️🔥\n\n\n{text}"
        clear_pending(uid)
        if flag_url:
            res = send_photo(CHANNEL_USERNAME, flag_url, caption, md=True)
            if not res.get("ok"):
                send_message(CHANNEL_USERNAME, caption)
        else:
            send_message(CHANNEL_USERNAME, caption)
        send_message(chat_id, "*کاربر گرامی⚠️*\n\nبیانیه شما با موفقیت در کانال ارسال شد!✔️\n\nموفق باشید!📌", main_menu_kb(uid))
        return

    # ── نبرد ──
    if text == "نبرد⚔🛡🔥":
        clear_pending(uid)
        u = get_user(uid)
        if is_hacked(u):
            send_message(chat_id, HACKED_TEXT, main_menu_kb(uid)); return
        if not u.get("country"):
            send_message(chat_id, NEED_COUNTRY_TEXT, main_menu_kb(uid)); return
        set_pending(uid, "battle_target")
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nمی خواهید به کدام کشور حمله کنید!✔️\n\nکشور مورد نظر را انتخاب کنید!📌",
            owned_countries_kb(u.get("country")))
        return
    if pend and pend.get("step") == "battle_target":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        if text.startswith("⚔ "):
            label = text[2:].strip()
            target_en = None
            for flag, en, name, vip in COUNTRIES:
                if label == f"{flag} {name}":
                    target_en = en
                    break
            if not target_en:
                send_message(chat_id, UNKNOWN_TEXT, owned_countries_kb(get_user(uid).get("country"))); return
            set_pending(uid, "battle_force", target=target_en, force={})
            u = get_user(uid)
            send_message(chat_id,
                "*کاربر گرامی⚠️*\n\nنیرو های شما به شرح زیر است!✔️\n\nنیرو های مورد نظر برای حمله انتخاب نمایید!📌",
                attack_force_kb(u, {}))
            return
    if pend and pend.get("step") == "battle_force":
        target_en = pend.get("target")
        force = dict(pend.get("force") or {})
        u = get_user(uid)
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        if text == "حمله🚀":
            if not force:
                send_message(chat_id, "*کاربر گرامی⚠️*\n\nابتدا نیرو انتخاب کنید!✔️", attack_force_kb(u, force)); return
            ok, msg = do_military_attack(uid, target_en, force)
            clear_pending(uid)
            send_message(chat_id, msg, main_menu_kb(uid))
            return
        # انتخاب تجهیز
        matched = None
        for eid, cnt, it in user_war_equipment(u):
            label = attack_force_btn_label(eid)
            short = war_eq_short_name(eid)
            full = (it.get("name") or "").strip()
            if text == label or text == short or text == full or text == _war_btn_label(full):
                matched = (eid, cnt, it)
                break
        if matched:
            eid, cnt, it = matched
            if force.get(eid):
                send_message(chat_id,
                    f"*کاربر گرامی⚠️*\n\nشما {fad(force[eid])} عدد از این تجهیزات را آماده حمله کردید!✔️\n\n"
                    f"اگر می خواهید با تعداد بیشتری از این نیرو حمله کنید، ابتدا حمله خود را انجام داده و سپس دوباره حمله کنید!📌",
                    attack_force_kb(u, force))
                return
            set_pending(uid, "battle_qty", target=target_en, force=force, eq=eid)
            pw = int(it["power"])
            send_message(chat_id,
                f"*کاربر گرامی⚠️*\n\n"
                f"شما {fad(cnt)} عدد از این تجهیزات دارید!\n"
                f"چند عدد را به کشور دشمن ارسال می‌کنید؟✔️\n\n"
                f"⚡ قدرت هر ۱ واحد: {fad(pw)}\n"
                f"⚡ مجموع اگر همه {fad(cnt)} تا را بفرستید: {fad(pw * cnt)}\n\n"
                f"مجموع تخریب = قدرت هر واحد × تعداد ارسالی\n\n"
                f"*لطفا تنها عدد وارد کنید! مثال : ۱۰📌*",
                RK([["🔙 بازگشت"]]))
            return
        send_message(chat_id, UNKNOWN_TEXT, attack_force_kb(u, force)); return
    if pend and pend.get("step") == "battle_qty":
        target_en = pend.get("target")
        force = dict(pend.get("force") or {})
        eid = pend.get("eq")
        u = get_user(uid)
        if text == "🔙 بازگشت":
            set_pending(uid, "battle_force", target=target_en, force=force)
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nنیرو انتخاب کنید!📌", attack_force_kb(u, force)); return
        t = to_en_digits(text).strip()
        if not re.fullmatch(r"\d+", t):
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nلطفا فقط عدد وارد کنید!✔️\n\n*مثال : 10📌*"); return
        n = int(t)
        if n <= 0:
            send_message(chat_id, "*کاربر گرامی⚠️*\n\nلطفا عددی بزرگتر از ۰ وارد کنید!✔️\n\n*مثال : 10📌*"); return
        have = int((u.get("equipment") or {}).get(eid, 0) or 0)
        if n > have:
            send_message(chat_id,
                f"*کاربر گرامی⚠️*\n\nنیرو های شما کمتر از {fad(n)} است!✔️\n\nشما نیروی کافی برای حمله با این تعداد نیرو ندارید!📌"); return
        force[eid] = n
        set_pending(uid, "battle_force", target=target_en, force=force)
        # محاسبه مجموع قدرت انتخاب‌شده
        total_pw = 0
        total_u = 0
        for fe, fc in force.items():
            info = war_eq_info(fe)
            if info:
                total_pw += int(info[2]["power"]) * int(fc)
                total_u += int(fc)
        send_message(chat_id,
            f"*کاربر گرامی⚠️*\n\n"
            f"نیروهای شما جهت حمله آماده شدند!✔️\n\n"
            f"تعداد واحد انتخابی: {fad(total_u)}\n"
            f"مجموع قدرت تخریب: {fad(total_pw)}\n"
            f"نفت لازم برای حمله: {fad(total_u * OIL_COST_PER_UNIT)}\n\n"
            f"اگر می‌خواهید نیروی دیگر اضافه کنید روی آن کلیک کنید!📌",
            attack_force_kb(u, force))
        return

    # ── ادمین اهدا نیرو / نفت ──
    if is_admin(uid):
        if text == "➕️ اهدا بشکه نفت":
            set_pending(uid, "gift_oil_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return
        if text == "➕️ اهدا نیرو":
            set_pending(uid, "gift_force_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return



    # ── فروشگاه کاربر ──
    if text == "فروشگاه🏬":
        clear_pending(uid)
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nشما می توانید از طریق این بخش، الماس و سکه خریداری کنید!✔️\n\nاز منوی زیر استفاده کنید!📌",
            shop_user_kb())
        return
    if text == "💰 خرید سکه":
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nتعرفه خرید سکه به شرح زیر است!✔️\n\n"
            "💰1 میلیون سکه : 1 هزار تومان\n\n"
            "جهت خرید به آیدی زیر مراجعه نمایید!📌\n\n*@gymrooo*",
            shop_user_kb())
        return
    if text == "💎 خرید الماس":
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nتعرفه خرید الماس به شرح زیر است!✔️\n\n"
            "💎10 الماس : 20 هزار تومان\n\n"
            "جهت خرید به آیدی زیر مراجعه نمایید!📌\n\n*@gymrooo*",
            shop_user_kb())
        return

    # ── پشتیبانی ──
    if text == "🆘️ پشتیبانی":
        clear_pending(uid)
        set_pending(uid, "support_wait")
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nپیام خود را برای پشتیبانی ارسال نمایید!✔️\n\nپشتیبانی آماده پاسخگویی به شماست!📌",
            RK([["🔙 بازگشت"]]))
        return
    if pend and pend.get("step") == "support_wait":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, "به منوی اصلی بازگشتید.", main_menu_kb(uid)); return
        deliver_support_to_admins(uid, chat_id, msg)
        clear_pending(uid)
        send_message(chat_id,
            "*کاربر گرامی⚠️*\n\nپیام شما برای پشتیبانی ارسال گشت!✔️\n\nپشتیبانی به زودی جواب شما را خواهد داد!📌",
            main_menu_kb(uid))
        return

    # ادمین در حال پاسخ پشتیبانی
    if is_admin(uid) and pend and pend.get("step") == "admin_reply":
        target = pend.get("target")
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
        try:
            # کپی انواع محتوا
            if msg.get("text"):
                send_message(target, msg.get("text"), md=False)
            elif msg.get("photo"):
                ph = msg["photo"][-1]["file_id"]
                api("sendPhoto", chat_id=target, photo=ph, caption=msg.get("caption") or "")
            elif msg.get("video"):
                api("sendVideo", chat_id=target, video=msg["video"]["file_id"], caption=msg.get("caption") or "")
            elif msg.get("voice"):
                api("sendVoice", chat_id=target, voice=msg["voice"]["file_id"])
            elif msg.get("audio"):
                api("sendAudio", chat_id=target, audio=msg["audio"]["file_id"])
            elif msg.get("document"):
                api("sendDocument", chat_id=target, document=msg["document"]["file_id"], caption=msg.get("caption") or "")
            elif msg.get("animation"):
                api("sendAnimation", chat_id=target, animation=msg["animation"]["file_id"])
            else:
                api("forwardMessage", chat_id=target, from_chat_id=chat_id, message_id=msg.get("message_id"))
            clear_pending(uid)
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nپیام شما با موفقیت برای کاربر ارسال شد!✔️\n\nاز زحمات شما سپاسگزاریم!📌",
                admin_panel_kb())
        except Exception as e:
            print("[ADMIN REPLY]", e)
            send_message(chat_id, "ارسال ناموفق بود.", admin_panel_kb())
        return

    # اولویت: ویرایش/حذف دکمه قبل از نمایش متن دکمه سفارشی
    if is_admin(uid) and pend and pend.get("step") == "btn_edit_pick":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb(uid)); return
        b = find_custom_button(text)
        if not b:
            send_message(chat_id, UNKNOWN_TEXT, custom_buttons_kb()); return
        set_pending(uid, "btn_edit_text", bid=b["id"])
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nمتن جدید دکمه را وارد کنید!✔️\n\nاز شما سپاسگزاریم!📌",
            RK([["🔙 بازگشت"]])); return
    if is_admin(uid) and pend and pend.get("step") == "btn_del_pick":
        if text == "🔙 بازگشت":
            clear_pending(uid)
            send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb(uid)); return
        b = find_custom_button(text)
        if not b:
            send_message(chat_id, UNKNOWN_TEXT, custom_buttons_kb()); return
        with LOCK:
            DATA["custom_buttons"] = [x for x in DATA.get("custom_buttons") or [] if x.get("id") != b["id"]]
            DATA.setdefault("deleted_button_names", [])
            if b["name"] not in DATA["deleted_button_names"]:
                DATA["deleted_button_names"].append(b["name"])
            save_data()
        clear_pending(uid)
        send_message(chat_id,
            "*ادمین گرامی⚠️*\n\nدکمه مورد نظر با موفقیت حذف شد!✔️\n\nاز شما سپاسگزاریم!📌",
            admin_panel_kb(uid)); return

    # ── دکمه‌های سفارشی ──
    cb = find_custom_button(text)
    if cb:
        send_message(chat_id, cb.get("text") or "—", main_menu_kb(uid))
        return
    # دکمه حذف‌شده که هنوز روی کیبورد قدیمی کاربر است
    if text and not text.startswith("/") and pend is None:
        # فقط اگر شبیه دکمه سفارشی قدیمی باشد — با لیست حذف‌شده‌ها
        deleted = DATA.get("deleted_button_names") or []
        if text in deleted:
            send_message(chat_id,
                "*کاربر گرامی⚠️*\n\nاین دکمه از ربات حذف شده است!✔️\n\nنمی توانید از این دکمه استفاده کنید!📌",
                main_menu_kb(uid))
            return

    # ── پنل ادمین: اخطار / مسدود / دکمه / جستجو / روشن‌خاموش ──
    if is_admin(uid):
        if text == "⚠️ اخطار":
            set_pending(uid, "warn_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return
        if text == "⚠️ رفع اخطار":
            set_pending(uid, "unwarn_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return
        if text == "🚫 مسدود کردن کاربر":
            set_pending(uid, "block_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return
        if text == "🚫 رفع مسدودی":
            set_pending(uid, "unblock_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return
        if text == "🔎 جست و جوی کاربر":
            set_pending(uid, "search_uid")
            send_message(chat_id, ASK_UID_ADMIN, RK([["🔙 بازگشت"]])); return
        if text == "🧑‍🔧 ساخت دکمه":
            set_pending(uid, "btn_create_name")
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nنام دکمه را وارد نمایید!✔️\n\n*مثال : جنگ جهانی📌*",
                RK([["🔙 بازگشت"]])); return
        if text == "✏️ ویرایش دکمه":
            customs = DATA.get("custom_buttons") or []
            if not customs:
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nدکمه ای تا به حال ساخته نشده است!✔️\n\nنیازی به ویرایش یک دکمه نیست!📌",
                    admin_panel_kb()); return
            set_pending(uid, "btn_edit_pick")
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nدکمه مورد نظر را انتخاب نمایید!✔️\n\nاز منوی زیر استفاده کنید!📌",
                custom_buttons_kb()); return
        if text == "❌️ حذف دکمه":
            customs = DATA.get("custom_buttons") or []
            if not customs:
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nدکمه ای تا به حال ساخته نشده است!✔️\n\nنیازی به حذف یک دکمه نیست!📌",
                    admin_panel_kb()); return
            set_pending(uid, "btn_del_pick")
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nدکمه مورد نظر را انتخاب نمایید!✔️\n\nاز منوی زیر استفاده کنید!📌",
                custom_buttons_kb()); return
        if text == "📱 اطلاعات" and int(uid) == int(ADMIN_ID):
            try:
                save_data()
                caption = (
                    "📱 اطلاعات ربات\n"
                    "────────────\n"
                    "فایل دیتای کامل (radar3_data.json)\n"
                    "آخرین ذخیره‌سازی لحظه‌ای"
                )
                url = API_BASE + "/sendDocument"
                with open(DATA_FILE, "rb") as f:
                    files = {"document": (DATA_FILE, f, "application/json")}
                    data_form = {"chat_id": chat_id, "caption": caption}
                    SESSION.post(url, data=data_form, files=files, timeout=60)
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nفایل اطلاعات با موفقیت ارسال شد!✔️",
                    admin_panel_kb(uid))
            except Exception as e:
                print("[INFO FILE]", e)
                send_message(chat_id, f"خطا در ارسال فایل: {e}", admin_panel_kb(uid))
            return
        if text == "✅️ روشن کردن ربات" or text == "✅ روشن کردن ربات" or "روشن کردن ربات" in text:
            if is_bot_on():
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات در حال حاضر روشن است!✔️\n\nنیازی به روشن کردن مجدد ربات نیست!📌",
                    admin_panel_kb())
            else:
                DATA["bot_on"] = True
                save_data()
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات با موفقیت روشن شد!✔️\n\nممنون از شما!📌",
                    admin_panel_kb())
            return
        if text == "❌️ خاموش کردن ربات" or text == "❌ خاموش کردن ربات" or "خاموش کردن ربات" in text:
            if not is_bot_on():
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات در حال حاضر خاموش است!✔️\n\nنیازی به خاموش کردن مجدد ربات نیست!📌",
                    admin_panel_kb())
            else:
                DATA["bot_on"] = False
                save_data()
                send_message(chat_id,
                    "*ادمین گرامی⚠️*\n\nربات با موفقیت خاموش شد!✔️\n\nممنون از شما!📌",
                    admin_panel_kb())
            return

        # انتخاب ویرایش/حذف دکمه
        if pend and pend.get("step") == "btn_edit_pick":
            if text == "🔙 بازگشت":
                clear_pending(uid); send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
            b = find_custom_button(text)
            if not b:
                send_message(chat_id, UNKNOWN_TEXT, custom_buttons_kb()); return
            set_pending(uid, "btn_edit_text", bid=b["id"])
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nمتن جدید دکمه را وارد کنید!✔️\n\nاز شما سپاسگزاریم!📌",
                RK([["🔙 بازگشت"]])); return
        if pend and pend.get("step") == "btn_del_pick":
            if text == "🔙 بازگشت":
                clear_pending(uid); send_message(chat_id, ADMIN_PANEL_TEXT, admin_panel_kb()); return
            b = find_custom_button(text)
            if not b:
                send_message(chat_id, UNKNOWN_TEXT, custom_buttons_kb()); return
            with LOCK:
                DATA["custom_buttons"] = [x for x in DATA.get("custom_buttons") or [] if x.get("id") != b["id"]]
                DATA.setdefault("deleted_button_names", [])
                if b["name"] not in DATA["deleted_button_names"]:
                    DATA["deleted_button_names"].append(b["name"])
                save_data()
            clear_pending(uid)
            send_message(chat_id,
                "*ادمین گرامی⚠️*\n\nدکمه مورد نظر با موفقیت حذف شد!✔️\n\nاز شما سپاسگزاریم!📌",
                admin_panel_kb()); return


    send_message(chat_id, UNKNOWN_TEXT, main_menu_kb(uid))

def handle_update(upd):
    # فقط پیام و کال‌بک چت خصوصی — channel_post و گروه نادیده
    if upd.get("callback_query"):
        on_callback(upd["callback_query"])
    elif upd.get("message"):
        on_message(upd["message"])
    # channel_post / edited_channel_post / ... → هیچ واکنشی نده

# ───────────────────────────── اجرا ─────────────────────────────
def poll_loop():
    print("Bot started")
    offset = 0
    while True:
        res = api("getUpdates", offset=offset, timeout=30)
        if not res.get("ok"):
            time.sleep(2)
            continue
        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            try:
                handle_update(upd)
            except Exception as e:
                print("[UPDATE ERROR]", e)

def main():
    load_data()
    api("deleteWebhook")
    threading.Thread(target=profit_worker, daemon=True).start()
    poll_loop()

if __name__ == "__main__":
    main()
