from flask import Flask, request, render_template, Response, redirect, url_for, flash, session
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import re
import io

app = Flask(__name__)
app.secret_key = 'Yyt7M@RW^El*o'  

def _parse_hour_minute(hhmm):
    """
    פונקציית עזר שמקבלת מחרוזת '22' או '22:30'
    ומחזירה (22, 30). אם אין דקות מצוינות, מניחים 00.
    """
    parts = hhmm.split(":")
    if len(parts) == 1:
        hour = int(parts[0])
        minute = 0
    else:
        hour = int(parts[0])
        minute = int(parts[1])
    return hour, minute

def parse_schedule(schedule_text):
    events = []
    errors = []
    lines = schedule_text.split("\n")
    local_tz = pytz.timezone("Asia/Jerusalem")

    # מזהים "יום X" כמו "ראשון 23.03"
    date_pattern = re.compile(r"^(?:\*?)?(?:יום )?(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)\s+(\d{1,2}[./-]\d{1,2})")
    # מזהים כותרת שבוע, לדוגמה: 🌟שבוע 13 (23-29/3) או 🌟שבוע 14 (30/3-5/4)
    week_pattern = re.compile(r"^.*?שבוע\s+\d+\s+\((\d{1,2}[./-]\d{1,2})-?(\d{1,2}[./-]\d{1,2})\).*?$")
    # תבנית גמישה יותר עבור טווח שעות בכל מקום בשורה (למשל "22-2 קשה", "קשה 22-2")
    time_pattern = re.compile(r'(?:.*?)(\d{1,2}(?::\d{2})?)\s*-\s*(\d{1,2}(?::\d{2})?)(?:.*?)')

    instructions_keywords = ["בקשות לחילופים", "כדי להכניס ללו״ז"]

    i = 0
    current_date = None
    current_day_name = None

    while i < len(lines):
        line = lines[i].strip()
        # אם הגענו לשורת הנחיות - מפסיקים עיבוד
        if any(keyword in line for keyword in instructions_keywords):
            break

        # בדיקה אם זו שורת שבוע
        if week_pattern.match(line):
            i += 1
            continue

        # בדיקה אם זו שורת תאריך (לדוגמה: "ראשון 30.03")
        date_match = date_pattern.match(line)
        if date_match:
            current_day_name = date_match.group(1).strip()  # "ראשון", "שבת" וכו'
            date_str = date_match.group(2).replace("/", ".").replace("-", ".")

            try:
                # אם לא צוינה שנה, נוסיף את השנה הנוכחית
                if len(date_str.split(".")) == 2:
                    current_month = int(date_str.split(".")[1])
                    current_year = datetime.now().year
                    
                    # אם החודש קטן מהחודש הנוכחי והוא לא דצמבר/ינואר, כנראה מדובר בשנה הבאה
                    now = datetime.now()
                    if current_month < now.month and not (now.month == 12 and current_month == 1):
                        current_year += 1
                        
                    date_str += f".{current_year}"

                parsed_date = datetime.strptime(date_str, "%d.%m.%Y")

                # אם התאריך כבר עבר (קטן מהיום), נניח שמדובר בשנה הבאה (ניתן להסיר אם לא רצוי)
                if parsed_date.date() < datetime.now().date():
                    parsed_date = parsed_date.replace(year=parsed_date.year + 1)

                current_date = local_tz.localize(parsed_date)

            except Exception as e:
                errors.append(f"שגיאה בעיבוד תאריך בשורה {i+1}: {e}")
                current_date = None

            i += 1

            # לאחר זיהוי תאריך, נטפל בשורות הבאות עד שנגיע לתאריך חדש / שבוע חדש / הנחיות
            while i < len(lines):
                next_line = lines[i].strip()

                # אם הגענו להנחיות - מפסיקים
                if any(keyword in next_line for keyword in instructions_keywords):
                    return events, errors

                # יום חדש / שבוע חדש / שורה ריקה => נעצור את העיבוד ליום הזה
                if not next_line or date_pattern.match(next_line) or week_pattern.match(next_line):
                    break

                if current_date is None:
                    i += 1
                    continue

                # אם יש מילה "כוננות 60" בשורה
                if "כוננות 60" in next_line:
                    # נגדיר לדוגמה 08:00-08:00 למחרת
                    start = datetime.combine(current_date.date(), datetime.strptime("08:00", "%H:%M").time())
                    end = start + timedelta(days=1)
                    events.append({
                        "start": local_tz.localize(start).astimezone(pytz.utc),
                        "end": local_tz.localize(end).astimezone(pytz.utc),
                        "description": next_line  # כל הטקסט המקורי
                    })
                    i += 1
                    continue

                # ננסה לזהות טווח שעות בכל מקום בשורה:
                time_match_res = time_pattern.search(next_line)  # <-- משתמשים ב-search

                # אם זו שורה ריקה או רק עם הכותרת של היום - נדלג
                if not next_line.strip() or next_line.strip() == current_day_name:
                    i += 1
                    continue

                if time_match_res:
                    # דוגמים את השעות
                    start_time_raw = time_match_res.group(1).strip()  # לדוגמה "22", "22:30"
                    end_time_raw   = time_match_res.group(2).strip()  # לדוגמה "2", "02:00"

                    # יוצרים תיאור מלא מהטקסט השלם
                    description = next_line
                    
                    # ננסה לחלץ את סוג המשמרת (למשל "קשה")
                    shift_type = ""
                    shift_types = ["קשה", "קל", "בינוני", "מאומץ", "נינוח", "רגיל"]
                    special_events = ["שיחת מפעילים", "קה\"ד", "הכשרה", "תדריך", "ישיבה"]
                    
                    # בדיקה לאירועים מיוחדים
                    event_title = ""
                    for special in special_events:
                        if special.lower() in next_line.lower():
                            event_title = f"{special} {start_time_raw}-{end_time_raw}"
                            break
                    
                    # אם לא מצאנו אירוע מיוחד, נחפש סוג משמרת
                    if not event_title:
                        for shift in shift_types:
                            if shift in next_line:
                                shift_type = shift
                                break
                        
                        # נוסיף את סוג המשמרת לתיאור אם יש צורך
                        if shift_type:
                            event_title = f"{shift_type} {start_time_raw}-{end_time_raw}"
                        else:
                            event_title = f"משמרת {start_time_raw}-{end_time_raw}"

                    # ממירים את השעות למספרים
                    sh, sm = _parse_hour_minute(start_time_raw)
                    eh, em = _parse_hour_minute(end_time_raw)

                    start_dt = datetime.combine(current_date.date(), datetime.min.time()).replace(hour=sh, minute=sm)
                    end_dt   = datetime.combine(current_date.date(), datetime.min.time()).replace(hour=eh, minute=em)

                    # אם שעת הסיום <= שעת ההתחלה, נניח שזה נמשך עד היום למחרת
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)

                    events.append({
                        "start": local_tz.localize(start_dt).astimezone(pytz.utc),
                        "end": local_tz.localize(end_dt).astimezone(pytz.utc),
                        "description": description,  # שומרת את כל השורה
                        "title": event_title  # כותרת מתומצתת לאירוע
                    })
                else:
                    # לא זוהה טווח שעות, ולא "כוננות 60"
                    # נבדוק אם "יום" או "לילה"
                    if "יום" in next_line:
                        # לדוגמה 06:00–18:00
                        start = datetime.combine(current_date.date(), datetime.strptime("06:00", "%H:%M").time())
                        end = datetime.combine(current_date.date(), datetime.strptime("18:00", "%H:%M").time())
                        events.append({
                            "start": local_tz.localize(start).astimezone(pytz.utc),
                            "end": local_tz.localize(end).astimezone(pytz.utc),
                            "description": next_line
                        })
                    elif "לילה" in next_line:
                        # 18:00–06:00 למחרת
                        start = datetime.combine(current_date.date(), datetime.strptime("18:00", "%H:%M").time())
                        end = datetime.combine(current_date.date(), datetime.strptime("06:00", "%H:%M").time()) + timedelta(days=1)
                        events.append({
                            "start": local_tz.localize(start).astimezone(pytz.utc),
                            "end": local_tz.localize(end).astimezone(pytz.utc),
                            "description": next_line
                        })
                    else:
                        # ברירת מחדל: 08:00–08:00
                        start = datetime.combine(current_date.date(), datetime.strptime("08:00", "%H:%M").time())
                        end = start + timedelta(days=1)
                        events.append({
                            "start": local_tz.localize(start).astimezone(pytz.utc),
                            "end": local_tz.localize(end).astimezone(pytz.utc),
                            "description": next_line
                        })

                i += 1

            continue  # סיימנו את הטיפול באותו תאריך
        else:
            # לא תאריך, לא שבוע ולא הנחיות => סתם טקסט
            if any(keyword in line for keyword in instructions_keywords):
                break
            i += 1

    # אם לא נוצרו אירועים וגם אין שגיאות – שגיאה כללית
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
            e.name = event.get("title", event["description"])  # משתמשים בכותרת אם קיימת, אחרת בתיאור המלא
            e.description = event["description"]
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
