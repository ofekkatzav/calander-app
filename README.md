# Calendar Parser & ICS Generator (Flask)

A lightweight Flask web application that parses Hebrew weekly schedules and generates a downloadable iCalendar (ICS) file. Users paste a free‑form schedule (days, time ranges, shift types), the app normalizes it, handles edge cases (overnight spans, weekend rollover, special events), and returns a valid `.ics` with events in UTC.

## Features
- Paste a Hebrew schedule and get a ready‑to‑import `.ics` file
- Robust parsing of days and flexible time formats (e.g. `22-2`, `22:30-06:45`)
- Handles overnight shifts and weekend transitions
- Detects special events (e.g. briefings, trainings) and titles them
- Timezone-aware: converts Israel time to UTC in the ICS
- Simple, clean UI with Flask + Jinja templates

## Tech Stack
- Python 3, Flask 3, Jinja2
- `ics` for iCalendar generation, `pytz` for timezones
- Deployed on Render (compatible with Gunicorn)

## Getting Started

### Prerequisites
- Python 3.12+

### Installation
```bash
git clone https://github.com/ofekkatzav/calander-app.git
cd calander-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Locally
```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=3000
# or with gunicorn
# gunicorn -w 2 -b 0.0.0.0:3000 app:app
```
Visit http://localhost:3000

## Usage
1. Paste your weekly schedule text (Hebrew supported)
2. Review parsed events preview
3. Download the generated `.ics` and import to your calendar

### Input Examples
- `ראשון 23.03` followed by lines like `קשה 22-2`, `22:30-06:00`, or `כוננות 60`
- Week headers like `שבוע 13 (23-29/3)` are ignored safely

## Project Structure
```
app.py              # Flask app, parsing logic, ICS generation
templates/          # Jinja templates (index, success, invalid_format)
static/             # Static assets (logo, styles)
requirements.txt    # Python dependencies
schedule.ics        # Sample ICS
```

## Deploy
This project runs well on Render using Gunicorn. Set the start command to:
```bash
gunicorn -w 2 -b 0.0.0.0:10000 app:app
```
Make sure the environment provides Python 3.12 and installs `requirements.txt`.

## Notes & Assumptions
- Default timezone is Asia/Jerusalem; `.ics` is exported in UTC
- Overnight logic covers end times earlier than start times (e.g. `22-06`)
- Special keywords are recognized and used as event titles when present

## Roadmap
- Add tests for additional schedule formats
- Add optional email delivery of the generated ICS
- Dockerize for reproducible deployments

## License
MIT
