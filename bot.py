import asyncio
import json
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import os
import time

# ---------- إعدادات التخزين في Gist ----------
GIST_TOKEN = os.environ.get("GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID")
GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
HEADERS = {"Authorization": f"token {GIST_TOKEN}"}


def download_old_ids():
    response = requests.get(GIST_URL, headers=HEADERS)
    response.raise_for_status()
    content = response.json()["files"]["old_ids.txt"]["content"]
    return return set(line.strip() for line in content.strip().split("\n") if line.strip())


def upload_old_ids(ids, limit=200):
    ids = list(dict.fromkeys(ids))
    ids = ids[-limit:]
    content = "\n".join(ids)
    data = {
        "files": {
            "old_ids.txt": {
                "content": content
            }
        }
    }
    response = requests.patch(GIST_URL, headers=HEADERS, json=data)
    response.raise_for_status()


# ---------- تحميل الإعدادات ----------
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
    try:
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
    try:
        url = "https://mostaql.com/projects?category=development&budget_max=10000&sort=latest"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "lxml")
        projects = soup.find_all("tr", class_="project-row")

        old_ids = download_old_ids()
        new_ids = set()
        new_projects = []

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

            new_projects.append({
                "message": (
                    f"📌 {title}\n"
                    f"🔗 {path}\n"
                    f"📌 الحالة: {details['status']}\n"
                    f"🕒 النشر: {details['posted']} | 📅 المدة: {details['duration']} | 💰 الميزانية: {details['budget']}\n"
                    f"📝 {description[:100]}..."
                ),
                "project_id": project_id
            })

            new_ids.add(project_id)

        for p in reversed(new_projects):
            await send_to_telegram(bot, p["message"])

        if new_ids:
            all_ids = list(old_ids.union(new_ids))
            print("🟢 IDs التي سيتم رفعها:", all_ids)
            upload_old_ids(all_ids)
            print("✅ تم رفع IDs بنجاح.")

    except Exception as e:
        print(f"❗ خطأ في جلب المشاريع: {e}")


if __name__ == "__main__":
    asyncio.run(fetch_projects())
