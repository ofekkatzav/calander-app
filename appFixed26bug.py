from flask import Flask, request, render_template, send_file
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import os
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
        date_match = re.match(r"^\*?\w*\s*(\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?)", line)
        if date_match:
            try:
                date_str = date_match.group(1)
                if len(date_str.split(".")) == 2:  # אם אין שנה, הוסף שנה נוכחית
                    date_str += f".{datetime.now().year}"
                current_date = datetime.strptime(date_str, "%d.%m.%Y")
                current_date = local_tz.localize(current_date)
                continue
            except Exception as e:
                print(f"Error parsing date: {e}")

        # זיהוי טווחי שעות ותיאור המשמרת
        time_match = re.match(r"^(\d{1,2}(:\d{2})?)-(\\d{1,2}(:\\d{2})?)\\s+(.+)$", line)
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

                # אם המשמרת חוצה חצות, שייכת ליום הבא
                if start.hour > end.hour:
                    end += timedelta(days=1)

                # אם המשמרת מתחילה לפני 6 בבוקר, שייכת ליום הבא
                if start.hour < 6:
                    start += timedelta(days=1)

                start_utc = start.astimezone(pytz.utc)
                end_utc = end.astimezone(pytz.utc)

                events.append({
                    "start": start_utc,
                    "end": end_utc,
                    "description": description,
                    "start_local": start,
                    "end_local": end
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

@app.route("/download/<file_name>")
def download_ics(file_name):
    try:
        return send_file(file_name, as_attachment=True)
    except FileNotFoundError:
        return "קובץ לא נמצא.", 404

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        schedule_text = request.form["schedule"]

        # פענוח האירועים
        parsed_events = parse_schedule(schedule_text)
        if parsed_events:
            file_name = create_ics(parsed_events)

            # יצירת קישור webcal ליומן אפל
            webcal_url = request.host_url.replace("http://", "webcal://") + f"download/{file_name}"

            # הצעת אפשרויות למשתמש עם תצוגה מקדימה
            return render_template(
                "success.html",
                file_name=file_name,
                webcal_url=webcal_url,
                events=parsed_events
            )

        return "לא נמצאו אירועים תקפים בטקסט שהוזן. ודא שהטקסט בפורמט הנכון."

    return render_template("index.html")

if __name__ == "__main__":
    print("Developed by Ofek Katzav")
    app.run(debug=True)
