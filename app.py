from flask import Flask, request, render_template, Response, redirect, url_for

from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import re
import io

app = Flask(__name__)

# פונקציה לעיבוד לוח הזמנים
def parse_schedule(schedule_text):
    events = []
    errors = []
    lines = schedule_text.split("\n")
    local_tz = pytz.timezone("Asia/Jerusalem")
    current_date = None

    for i, line in enumerate(lines):
        line = line.strip()
    

        # זיהוי פורמט "שבוע X (תאריך-תאריך)"
        week_match = re.match(r"^\u273fשבוע \d+ \((\d{1,2}[./-]\d{1,2})-(\d{1,2}[./-]\d{1,2})\)$", line)
        if week_match:
            continue

        # זיהוי תאריך גמיש (עם או בלי כוכביות)
        date_match = re.match(r"^(?:\*?)?(?:יום )?(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת) (\d{1,2}[./-]\d{1,2})", line)
        if date_match:
            try:
                date_str = date_match.group(2)
                if len(date_str.split(".")) == 2:  # הוספת שנה נוכחית אם חסרה
                    current_year = datetime.now().year
                    date_str += f".{current_year}"
                    parsed_date = datetime.strptime(date_str, "%d.%m.%Y")
                    # בדיקה אם התאריך כבר עבר
                    if parsed_date.date() < datetime.now().date():
                        # אם כן, מוסיפים שנה אחת
                        parsed_date = parsed_date.replace(year=current_year + 1)
                    current_date = parsed_date
                else:
                    current_date = datetime.strptime(date_str, "%d.%m.%Y")
                if current_date.tzinfo is None:
                    current_date = local_tz.localize(current_date)
                continue
            except Exception as e:
                errors.append(f"שגיאה בעיבוד תאריך בשורה {i + 1}: {e}")
                continue

        # זיהוי טווחי שעות ותיאור
        time_match = re.match(r"(\d{1,2}(:\d{2})?)-(\d{1,2}(:\d{2})?)\s+(.+)$", line)
        if current_date and time_match:
            try:
                start_time = time_match.group(1)
                end_time = time_match.group(3)
                description = time_match.group(5)

                start = datetime.combine(current_date.date(), datetime.min.time()).replace(
                    hour=int(start_time.split(":")[0]),
                    minute=int(start_time.split(":")[1]) if ":" in start_time else 0
                )
                end = datetime.combine(current_date.date(), datetime.min.time()).replace(
                    hour=int(end_time.split(":")[0]),
                    minute=int(end_time.split(":")[1]) if ":" in end_time else 0
                )

                # טיפול במשמרות שחוצות חצות
                if start.hour > end.hour:
                    end += timedelta(days=1)

                # טיפול במשמרות שמתחילות לפני 6 בבוקר
                if start.hour < 6:
                    start += timedelta(days=1)
                    end += timedelta(days=1)

                events.append({
                    "start": local_tz.localize(start).astimezone(pytz.utc),
                    "end": local_tz.localize(end).astimezone(pytz.utc),
                    "description": f"{description.strip()} ({start_time}-{end_time})"
                })
            except Exception as e:
                errors.append(f"שגיאה בעיבוד טווח השעות בשורה {i + 1}: {e}")
                continue
    
    # אם לא נמצאו אירועים והטקסט אינו תואם פורמט
    if not events and not errors :
        errors.append("לא נמצאו אירועים תקפים בטקסט שהוזן. ודא שהפורמט נכון.")
    

    return events, errors

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        schedule_text = request.form.get("schedule", "").strip()
        events, errors = parse_schedule(schedule_text)

        if errors:
            return render_template("index.html", errors=errors)

        if not events:
            return render_template("index.html", errors=["לא נמצאו אירועים תקפים בטקסט שהוזן."])

        # יצירת לוח שנה
        calendar = Calendar()
        for event in events:
            e = Event()
            e.name = event["description"]
            e.begin = event["start"]
            e.end = event["end"]
            calendar.events.add(e)

        # יצירת קובץ ICS בתור StringIO
        ics_file = io.StringIO()
        ics_file.writelines(calendar)
        ics_file.seek(0)

        # החזרת קובץ ICS בתור תגובת HTTP עם כותרות מתאימות
        return Response(
            ics_file.getvalue(),
            mimetype="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=schedule.ics",
                "Content-Type": "text/calendar; charset=utf-8",
            }
        )

    # When GET method is used or after refreshing
    return render_template("index.html", errors=None)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

