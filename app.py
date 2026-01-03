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

                    # המרה לפורמט עם אפסים מובילים
                    sh, sm = _parse_hour_minute(start_time_raw)
                    eh, em = _parse_hour_minute(end_time_raw)
                    
                    start_time_formatted = f"{sh:02d}:{sm:02d}"
                    end_time_formatted = f"{eh:02d}:{em:02d}"

                    # מסירים את הדקות אם הן 00
                    start_time_display = start_time_formatted[:2] if start_time_formatted.endswith(":00") else start_time_formatted
                    end_time_display = end_time_formatted[:2] if end_time_formatted.endswith(":00") else end_time_formatted
                    
                    # יוצרים תיאור מלא מהטקסט השלם
                    description = next_line
                    
                    # ננסה לחלץ את התפקיד במשמרת (לא סוג המשמרת)
                    roles = ["קשה", "קל", "בינוני", "מאומץ", "נינוח", "רגיל", "חוץ", "פנים"]
                    special_events = ["שיחת מפעילים", "קה\"ד", "הכשרה", "תדריך", "ישיבה"]
                    
                    # בדיקה לאירועים מיוחדים
                    event_title = ""
                    for special in special_events:
                        if special.lower() in next_line.lower():
                            event_title = f"{special} ({start_time_display}-{end_time_display})"
                            break
                    
                    # אם לא מצאנו אירוע מיוחד, נחפש תפקיד
                    if not event_title:
                        role = ""
                        for r in roles:
                            if r in next_line:
                                role = r
                                break
                        
                        # נוסיף את התפקיד לתיאור
                        if role:
                            event_title = f"{role} ({start_time_display}-{end_time_display})"
                        else:
                            event_title = f"משמרת ({start_time_display}-{end_time_display})"

                    # ממירים את השעות למספרים שכבר חילצנו למעלה
                    start_dt = datetime.combine(current_date.date(), datetime.min.time()).replace(hour=sh, minute=sm)
                    end_dt   = datetime.combine(current_date.date(), datetime.min.time()).replace(hour=eh, minute=em)

                    # לוגיקת "יום עבודה" בטייסות: 06:00 עד 06:00 למחרת
                    # כל שעה 00:00-05:59 שייכת ליום העבודה הקודם (תאריך קלנדרי הבא)
                    
                    if sh >= 0 and sh < 6:
                        # מקרה 1: שעת התחלה בין חצות ל-06:00 בבוקר
                        # דוגמה: "שלישי 2-6" → רביעי 02:00-06:00
                        start_dt += timedelta(days=1)
                        end_dt += timedelta(days=1)
                    elif eh >= 0 and eh < 6:
                        # מקרה 2: שעת התחלה מ-06:00 ואילך, אבל סיום לפני 06:00
                        # דוגמה: "שלישי 22-02" → שלישי 22:00 ועד רביעי 02:00
                        end_dt += timedelta(days=1)
                    elif end_dt <= start_dt:
                        # מקרה 3: מקרי קצה (למשל 14-12 למחרת)
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
        # מוחק את כל ההודעות הקודמות
        session.pop('_flashes', None)
        
        schedule_text = request.form.get("schedule", "").strip()

        if len(schedule_text) > 5000:
            flash("קלט ארוך מדי. אנא צמצם את לוח הזמנים שהוזן.", "error")
            return redirect(url_for('index'))

        events, errors = parse_schedule(schedule_text)

        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for('index'))

        if not events:
            flash("לא נמצאו אירועים תקפים בטקסט שהוזן.", "error")
            return redirect(url_for('index'))

        # הדפסת האירועים לדיבאג - רק אם הכל תקין
        debug_info = []
        for event in events:
            start_time = event["start"].astimezone(pytz.timezone("Asia/Jerusalem")).strftime("%d/%m/%Y %H:%M")
            end_time = event["end"].astimezone(pytz.timezone("Asia/Jerusalem")).strftime("%d/%m/%Y %H:%M")
            title = event.get("title", event["description"])
            debug_info.append(f"{title}: {start_time} - {end_time}")

        # שומרים בפלאש במקום ב-session
        for info in debug_info:
            flash(info, "success")  # שימוש בקטגוריה 'success' כדי להבדיל משגיאות

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
        # אין צורך בטיפול ב-session
        # מנקה הודעות ישנות בעת טעינת הדף
        session.pop('_flashes', None)
        return render_template("index.html")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
