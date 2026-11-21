# SkillBridge — Peer-to-Peer Campus Skill Exchange

A full-stack Flask application where students can publish skills, discover peer mentors, request learning sessions, exchange skill credits and review completed sessions.

## Features
- Registration, login, logout and password hashing (Werkzeug).
- CSRF protection on all form submissions (Flask-WTF).
- Student profiles and skill listings with search/category/level filters.
- Learning session requests with accept, decline, cancel and completion flows.
- Credit ledger rules: a learner's 1 credit is reserved when a request is accepted; it is returned if an accepted session is cancelled; a teacher earns 1 credit when the session is marked completed.
- One review per completed session, submitted by the learner.
- Personal dashboard with statistics and Chart.js visualisation.
- Admin overview (set `is_admin=True` for an account in the database).
- Responsive mobile, tablet and desktop layouts.
- SQLite database by default; SQLAlchemy allows migration to another supported database.

## Requirements
- Python 3.10+
- pip

## Setup (Windows PowerShell)
```powershell
cd skillbridge
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY = "replace-this-with-a-long-random-secret"
flask --app app seed-demo
flask --app app run
```
Open http://127.0.0.1:5000.

## Setup (macOS / Linux)
```bash
cd skillbridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="replace-this-with-a-long-random-secret"
flask --app app seed-demo
flask --app app run
```

## Demo login
After running `flask --app app seed-demo`:
- Email: `maya@example.com`
- Password: `SkillBridge123!`

Other demo users: `aarav@example.com`, `riya@example.com`, `kabir@example.com` (same demo password).

## Project structure
```text
skillbridge/
├── app.py                 # Flask routes, models, auth and business logic
├── requirements.txt
├── .env.example
├── README.md
├── templates/             # Jinja pages
│   ├── base.html
│   ├── landing.html
│   ├── auth.html
│   ├── dashboard.html
│   ├── skills.html
│   ├── skill_form.html
│   ├── profile.html
│   ├── review.html
│   ├── admin.html
│   └── error.html
└── static/
    ├── style.css
    ├── app.js
    └── dashboard.js
```

## Database
The default database is SQLite (`skillbridge.db`), created automatically at startup. Tables: `user`, `skill`, `learning_session`, and `review`. For PostgreSQL, set `DATABASE_URL` to a SQLAlchemy PostgreSQL URI and install the appropriate PostgreSQL driver. For MongoDB, the data layer would need a deliberate redesign using PyMongo or MongoEngine; MongoDB is not enabled in this version.

## Security and deployment notes
- Passwords are stored as Werkzeug password hashes, never as plaintext.
- Flask-WTF CSRF protection is enabled globally.
- SQLAlchemy parameterises ORM queries; user-provided content is rendered with Jinja autoescaping.
- Session cookies are HttpOnly and SameSite=Lax. Set `COOKIE_SECURE=1` behind HTTPS.
- Set a strong, unique `SECRET_KEY` in the environment. Never deploy with the development fallback key.
- Set `FLASK_DEBUG=0` in production and run behind a production WSGI server such as Gunicorn or Waitress.
- Add email verification, password reset, rate limiting, audit logs and automated backups before public production use.

## Important credit behaviour
A request does not immediately deduct credits. When the teacher accepts it, one learner credit is deducted. If the accepted session is cancelled, the credit is refunded. When either participant marks an accepted session completed, the teacher earns one credit. For a real deployment, add a separate immutable credit-transaction table and stronger concurrency controls to provide a full financial-style audit trail.

## Future improvements
1. Add calendar scheduling and in-app messaging.
2. Add skill recommendations using tags and collaborative filtering.
3. Add email notifications and reminders.
4. Add mentor verification, report/block tools and moderation queues.
5. Add pagination, API tests, rate limiting and an immutable credit transaction ledger.
6. Add a React frontend or mobile app while retaining the Flask API/domain layer.
