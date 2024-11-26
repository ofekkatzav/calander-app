from flask import Flask, request, render_template
from ics import Calendar, Event
from datetime import datetime
import pytz
import requests
import os
import base64
import re

app = Flask(__name__)

# פונקציה לעיבוד הטקסט

def parse_schedule(schedule_text):
    events = []
    lines = schedule_text.split("\n")
    current_date = None

    # הגדרת אזור הזמן המקומי
    local_tz = pytz.timezone("Asia/Jerusalem")

    for line in lines:
        line = line.strip()

        # זיהוי תאריך בפורמטים גמישים
        date_match = re.match(r"^(\w+)?\s*(\d{1,2}[./-]\d{1,2}[./-]?(\d{2,4})?)", line)
        if date_match:
            try:
                date_str = date_match.group(2)
                if len(date_str.split(".")) == 2:  # אם אין שנה, הוסף שנה נוכחית
                    date_str += f".{datetime.now().year}"
                current_date = datetime.strptime(date_str, "%d.%m.%Y")
                current_date = local_tz.localize(current_date)
                continue
            except Exception as e:
                print(f"Error parsing date: {e}")

        # זיהוי טווחי שעות ותיאור המשמרת
        time_match = re.match(r"^(\d{1,2}(:\d{2})?)-(\d{1,2}(:\d{2})?)\s*(.+)$", line)
        if current_date and time_match:
            try:
                start_time = time_match.group(1)
                end_time = time_match.group(3)
                description = time_match.group(5)

                start = current_date.replace(
                    hour=int(start_time.split(":")[0]),
                    minute=int(start_time.split(":")[1]) if ":" in start_time else 0
                )
                end = current_date.replace(
                    hour=int(end_time.split(":")[0]),
                    minute=int(end_time.split(":")[1]) if ":" in end_time else 0
                )

                start_utc = start.astimezone(pytz.utc)
                end_utc = end.astimezone(pytz.utc)

                events.append({
                    "start": start_utc,
                    "end": end_utc,
                    "description": description
                })
            except Exception as e:
                print(f"Error parsing shift: {e}")

    return events

# פונקציה ליצירת קובץ ICS
def create_ics(events, file_name="schedule.ics"):
    calendar = Calendar()

    for event in events:
        e = Event()
        e.name = event["description"]
        e.begin = event["start"]
        e.end = event["end"]
        calendar.events.add(e)

    with open(file_name, "w", encoding="utf-8") as f:
        f.writelines(calendar)

    return file_name

# פונקציה לשליחת אימייל עם SendGrid
def send_email_with_sendgrid(recipient_email, file_name):
    sendgrid_api_key = "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"  # הכנס את ה-API Key שלך
    sender_email = "t.166calander@outlook.com"  # כתובת המייל המאומתת שלך ב-SendGrid

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {sendgrid_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "personalizations": [
            {"to": [{"email": recipient_email}]}
        ],
        "from": {"email": sender_email},
        "subject": "קובץ ICS - לוח זמנים",
        "content": [{"type": "text/plain", "value": "מצורף קובץ ה-ICS שלך."}]
    }

    # צרף את הקובץ
    with open(file_name, "rb") as f:
        file_content = base64.b64encode(f.read()).decode("utf-8")
    attachment = {
        "content": file_content,
        "type": "application/octet-stream",
        "filename": file_name,
        "disposition": "attachment"
    }
    data["attachments"] = [attachment]

    response = requests.post(url, headers=headers, json=data)
    print(f"Response status code: {response.status_code}")
    if response.status_code != 202:
        print(f"Error: {response.text}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        schedule_text = request.form["schedule"]
        recipient_email = request.form["email"]

        parsed_events = parse_schedule(schedule_text)
        if parsed_events:
            file_name = create_ics(parsed_events)
            send_email_with_sendgrid(recipient_email, file_name)
            os.remove(file_name)  # מחיקת הקובץ לאחר השליחה
            return f"הקובץ נשלח בהצלחה ל-{recipient_email}."

        return "לא נמצאו אירועים תקפים בטקסט שהוזן."

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
