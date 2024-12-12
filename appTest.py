import re
import pytz
import logging
from datetime import datetime, timedelta
from flask import Flask, request, render_template, Response
from ics import Calendar, Event
import io

app = Flask(__name__)

# הגדרת לוגים
logger = logging.getLogger('flask_app')
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def parse_schedule(schedule_text):
    events = []
    errors = []
    lines = schedule_text.split("\n")
    local_tz = pytz.timezone("Asia/Jerusalem")
    current_year = datetime.now().year
    day_names = "ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת"

    combined_regex = re.compile(
        rf"^(?:\*?)?(?:בלילה\s+)?(?:שבין\s+)?(?:ביום\s+)?יום\s+(?P<day_name1>{day_names})\s+(?P<day1>\d{{1,2}})[./-](?P<month1>\d{{1,2}})(?:\.(?P<year1>\d{{4}}))?"
        rf"(?:\s+ליום\s+(?P<day_name2>{day_names})\s+(?P<day2>\d{{1,2}})[./-](?P<month2>\d{{1,2}})(?:\.(?P<year2>\d{{4}}))?)?,?\s*"
        rf"(?:תדריך\s+ב(?P<briefing>\d{{1,2}}:\d{{2}}(?::\d{{2}})?)\s*,\s*)?"
        rf"נתחיל\s+ב(?P<start>\d{{1,2}}:\d{{2}}(?::\d{{2}})?)\s*,\s*"
        rf"נסיים\s+ב(?P<end>\d{{1,2}}:\d{{2}}(?::\d{{2}})?)(?:\*)?$"
    )

    for i, line in enumerate(lines):
        line = re.sub(r'^\*+|\*+$', '', line).strip()
        
        # התעלמות משורות לא רלוונטיות
        if not line or line in ["נא לאשר בהודעה נפרדת", "🌹🌶️"]:
            continue

        logger.debug(f"מעבד שורה {i + 1}: {line}")

        match = combined_regex.match(line)
        if match:
            try:
                day1 = int(match.group('day1'))
                month1 = int(match.group('month1'))
                year1 = int(match.group('year1')) if match.group('year1') else current_year
                day2 = int(match.group('day2')) if match.group('day2') else day1
                month2 = int(match.group('month2')) if match.group('month2') else month1
                year2 = int(match.group('year2')) if match.group('year2') else year1
                
                start_time_str = match.group('start')
                end_time_str = match.group('end')

                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()

                start = local_tz.localize(datetime.combine(datetime(year1, month1, day1), start_time))
                end = local_tz.localize(datetime.combine(datetime(year2, month2, day2), end_time))

                if start > end:
                    end += timedelta(days=1)

                # תיאור האירוע יהיה תמיד "פיריט - מפקד"
                event_description = "פיריט - מפקד"

                events.append({
                    "description": event_description,
                    "start": start.astimezone(pytz.utc),
                    "end": end.astimezone(pytz.utc)
                })
            except Exception as e:
                errors.append(f"שגיאה בעיבוד אירוע בשורה {i + 1}: {e}")
                logger.error(f"שגיאה בעיבוד אירוע בשורה {i + 1}: {e}")
            continue

        # טיפול בשורות נוספות כמו פיריט ומפקד
        if line in ["פיריט", "מפקד"] and events:
            events[-1]["description"] += f" - {line}"

    if not events and not errors:
        errors.append("לא נמצאו אירועים תקפים בטקסט שהוזן. ודא שהפורמט נכון.")

    return events, errors

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        schedule_text = request.form.get("schedule", "").strip()
        logger.debug(f"Received schedule text:\n{schedule_text}")
        events, errors = parse_schedule(schedule_text)

        if errors:
            logger.debug(f"Errors found: {errors}")
            return render_template("index.html", errors=errors)

        calendar = Calendar()
        for event in events:
            e = Event()
            e.name = event["description"]
            e.begin = event["start"]
            e.end = event["end"]
            calendar.events.add(e)

        ics_file = io.StringIO()
        ics_file.write(str(calendar))
        ics_file.seek(0)

        logger.debug(f"ICS Content:\n{str(calendar)}")

        return Response(
            ics_file.getvalue(),
            mimetype="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=schedule.ics",
                "Content-Type": "text/calendar; charset=utf-8",
            }
        )

    return render_template("index.html", errors=None)

if __name__ == "__main__":
    app.run(debug=True)