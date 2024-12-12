from flask import Flask, request, render_template, Response, redirect, url_for, flash, session
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import re
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # החלף במפתח סודי אמיתי

def parse_schedule(schedule_text):
    events = []
    errors = []
    lines = schedule_text.split("\n")
    local_tz = pytz.timezone("Asia/Jerusalem")

    date_pattern = re.compile(r"^(?:\*?)?(?:יום )?(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת) (\d{1,2}[./-]\d{1,2})")
    week_pattern = re.compile(r"^[🌟\u273f]שבוע \d+ \((\d{1,2}[./-]\d{1,2})-(\d{1,2}[./-]\d{1,2})\)$")
    time_pattern = re.compile(r"(\d{1,2}(:\d{2})?)-(\d{1,2}(:\d{2})?)\s+(.+)$")

    # מילות מפתח לזיהוי תחילת קטע ההנחיות
    instructions_keywords = ["בקשות לחילופים", "כדי להכניס ללו״ז"]

    i = 0
    current_date = None
    current_day_name = None

    while i < len(lines):
        line = lines[i].strip()
        # אם הגענו לשורת הנחיות - מפסיקים עיבוד
        if any(keyword in line for keyword in instructions_keywords):
            break

        # זיהוי שורת שבוע
        if week_pattern.match(line):
            i += 1
            continue

        # זיהוי תאריך
        date_match = date_pattern.match(line)
        if date_match:
            current_day_name = date_match.group(1).strip()
            date_str = date_match.group(2)
            try:
                if len(date_str.split(".")) == 2:
                    current_year = datetime.now().year
                    date_str += f".{current_year}"
                parsed_date = datetime.strptime(date_str, "%d.%m.%Y")
                if parsed_date.date() < datetime.now().date():
                    parsed_date = parsed_date.replace(year=parsed_date.year + 1)
                current_date = local_tz.localize(parsed_date)
            except Exception as e:
                errors.append(f"שגיאה בעיבוד תאריך בשורה {i+1}: {e}")
                current_date = None

            i += 1
            # לאחר זיהוי תאריך, נעבד את השורות הבאות עד תאריך/שבוע חדש או הנחיות
            while i < len(lines):
                next_line = lines[i].strip()
                # אם הגענו להנחיות - מפסיקים עיבוד
                if any(keyword in next_line for keyword in instructions_keywords):
                    return events, errors

                if not next_line or date_pattern.match(next_line) or week_pattern.match(next_line):
                    # הגענו ליום חדש/שבוע חדש/שורה ריקה - יוצאים מהלולאה הזו
                    break

                # לוגיקה ליצירת משמרת
                if current_day_name in ["שישי", "שבת"]:
                    # סופ"ש
                    if "יום" in next_line or "לילה" in next_line:
                        # 08:00-08:00
                        start = datetime.combine(current_date.date(), datetime.strptime("08:00", "%H:%M").time())
                        end = start + timedelta(days=1)
                        events.append({
                            "start": local_tz.localize(start).astimezone(pytz.utc),
                            "end": local_tz.localize(end).astimezone(pytz.utc),
                            "description": next_line
                        })
                    else:
                        # אולי טווח שעות?
                        time_match_res = time_pattern.match(next_line)
                        if time_match_res:
                            start_time = time_match_res.group(1)
                            end_time = time_match_res.group(3)
                            description = time_match_res.group(5).strip()

                            start = datetime.combine(current_date.date(), datetime.min.time()).replace(
                                hour=int(start_time.split(":")[0]),
                                minute=int(start_time.split(":")[1]) if ":" in start_time else 0
                            )
                            end = datetime.combine(current_date.date(), datetime.min.time()).replace(
                                hour=int(end_time.split(":")[0]),
                                minute=int(end_time.split(":")[1]) if ":" in end_time else 0
                            )
                            if start.hour > end.hour:
                                end += timedelta(days=1)
                            if start.hour < 6:
                                start += timedelta(days=1)
                                end += timedelta(days=1)

                            events.append({
                                "start": local_tz.localize(start).astimezone(pytz.utc),
                                "end": local_tz.localize(end).astimezone(pytz.utc),
                                "description": f"{description} ({start_time}-{end_time})"
                            })
                        else:
                            # אין יום/לילה ואין טווח שעות => משמרת 08:00-08:00
                            if next_line:
                                start = datetime.combine(current_date.date(), datetime.strptime("08:00", "%H:%M").time())
                                end = start + timedelta(days=1)
                                events.append({
                                    "start": local_tz.localize(start).astimezone(pytz.utc),
                                    "end": local_tz.localize(end).astimezone(pytz.utc),
                                    "description": next_line
                                })
                    i += 1
                else:
                    # יום חול
                    if "יום" in next_line or "לילה" in next_line:
                        # משמרת יום/לילה ביום חול
                        if "יום" in next_line:
                            start = datetime.combine(current_date.date(), datetime.strptime("06:00", "%H:%M").time())
                            end = datetime.combine(current_date.date(), datetime.strptime("18:00", "%H:%M").time())
                        else:
                            # לילה ביום חול
                            start = datetime.combine(current_date.date(), datetime.strptime("18:00", "%H:%M").time())
                            end = datetime.combine(current_date.date(), datetime.strptime("06:00", "%H:%M").time()) + timedelta(days=1)
                        events.append({
                            "start": local_tz.localize(start).astimezone(pytz.utc),
                            "end": local_tz.localize(end).astimezone(pytz.utc),
                            "description": next_line
                        })
                        i += 1
                    else:
                        # טווח שעות?
                        time_match_res = time_pattern.match(next_line)
                        if time_match_res:
                            start_time = time_match_res.group(1)
                            end_time = time_match_res.group(3)
                            description = time_match_res.group(5).strip()
                            start = datetime.combine(current_date.date(), datetime.min.time()).replace(
                                hour=int(start_time.split(":")[0]),
                                minute=int(start_time.split(":")[1]) if ":" in start_time else 0
                            )
                            end = datetime.combine(current_date.date(), datetime.min.time()).replace(
                                hour=int(end_time.split(":")[0]),
                                minute=int(end_time.split(":")[1]) if ":" in end_time else 0
                            )
                            if start.hour > end.hour:
                                end += timedelta(days=1)
                            if start.hour < 6:
                                start += timedelta(days=1)
                                end += timedelta(days=1)
                            events.append({
                                "start": local_tz.localize(start).astimezone(pytz.utc),
                                "end": local_tz.localize(end).astimezone(pytz.utc),
                                "description": f"{description} ({start_time}-{end_time})"
                            })
                            i += 1
                        else:
                            # לא "יום"/"לילה", לא טווח שעות -> לא יוצרים משמרת
                            i += 1
            continue
        else:
            # לא תאריך, לא שבוע
            # בדיקה אם הנחיות
            if any(keyword in line for keyword in instructions_keywords):
                break
            i += 1

    if not events and not errors:
        errors.append("לא נמצאו אירועים תקפים בטקסט שהוזן, ודא שהפורמט נכון.")

    return events, errors

@app.route("/", methods=["GET", "POST"], strict_slashes=False)
def index():
    if request.method == "POST":
        schedule_text = request.form.get("schedule", "").strip()

        if len(schedule_text) > 5000:
            flash("קלט ארוך מדי. אנא צמצם את לוח הזמנים שהוזן.")
            return redirect(url_for('index'))

        events, errors = parse_schedule(schedule_text)

        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for('index'))

        if not events:
            flash("לא נמצאו אירועים תקפים בטקסט שהוזן.")
            return redirect(url_for('index'))

        calendar = Calendar()
        for event in events:
            e = Event()
            e.name = event["description"]
            e.begin = event["start"]
            e.end = event["end"]
            calendar.events.add(e)

        ics_file = io.StringIO()
        ics_file.writelines(calendar)
        ics_file.seek(0)

        return Response(
            ics_file.getvalue(),
            mimetype="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=schedule.ics",
                "Content-Type": "text/calendar; charset=utf-8",
            }
        )
    else:
        return render_template("index.html")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
