import asyncio
import json
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import os
import time
# تحميل الـ IDs القديمة من الملف
def load_old_ids(filepath="old_ids.txt"):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip().isdigit())

# حفظ ID جديد في الملف
def save_new_id(project_id, limit=100):
    try:
        with open("old_ids.txt", "r") as f:
            ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        ids = []

    ids.append(project_id)
    ids = list(dict.fromkeys(ids))  # نحيدو التكرارات
    ids = ids[-limit:]  # نخليو آخر 100 فقط

    with open("old_ids.txt", "w") as f:
        for pid in ids:
            f.write(f"{pid}\n")


# إعدادات البوت
# ⬇️ نقرأ ملف الإعدادات
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

KEYWORDS = config["keywords"]
DELAY = config["delay_seconds"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
PROJECT_CLASS = config["project_class"]

bot = Bot(token=TELEGRAM_TOKEN)

async def send_to_telegram(bot, message):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def extract_project_details(project_url):
    try :
        time.sleep(DELAY)
        response = requests.get(project_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "lxml")
        meta_panel = soup.find("div", id="project-meta-panel")
        meta_items = meta_panel.find_all("div", class_="meta-row") if meta_panel else []

        meta_data = {}
        for item in meta_items:
            label = item.find("div", class_="meta-label")
            value = item.find("div", class_="meta-value")
            if label and value:
                meta_data[label.text.strip().replace(":", "")] = value.text.strip()

        return {
            "status": meta_data.get("حالة المشروع", "غير محدد"),
            "posted": meta_data.get("تاريخ النشر", "غير محدد"),
            "duration": meta_data.get("مدة التنفيذ", "غير محدد"),
            "budget": meta_data.get("الميزانية", "غير محدد")
        }
    except Exception as e:
        print(f"❗ خطأ في استخراج تفاصيل المشروع: {e}")
        return {
            "status": "غير محدد",
            "posted": "غير محدد",
            "duration": "غير محدد",
            "budget": "غير محدد"
        }


async def fetch_projects():
    print("🔍 جاري فحص المشاريع ...")
    try : 
        url = "https://mostaql.com/projects?category=development&page=1"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "lxml")
        projects = soup.find_all("tr", class_="project-row")

        old_ids = load_old_ids()

        for project in projects:
            title_tag = project.find("a", class_="details-url")
            if not title_tag:
                continue

            path = title_tag.get("href", "")
            project_id = path.strip("/").split("/")[-1]
            title = title_tag.text.strip()
            if project_id in old_ids:
                continue

            description_div = project.find("p", class_="project-description")
            description = description_div.text.strip() if description_div else ""

            details = extract_project_details(path)

            full_text = title + description + details["budget"] + details["duration"]

            if any(keyword.lower() in full_text.lower() for keyword in KEYWORDS):
                message = (
                    f"📌 {title}\n"
                    f"🔗 {path}\n"
                    f"📌 الحالة: {details['status']}\n"
                    f"🕒 النشر: {details['posted']} | 📅 المدة: {details['duration']} | 💰 الميزانية: {details['budget']}\n"
                    f"📝 {description[:100]}..."
                )
                await send_to_telegram(bot, message)

            save_new_id(project_id)
    except Exception as e:
        print(f"❗ خطأ في جلب المشاريع: {e}")
    

if __name__ == "__main__":
    asyncio.run(fetch_projects())