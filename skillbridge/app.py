import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-development-secret-before-deploying')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///skillbridge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '0') == '1'
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(300), default='')
    interests = db.Column(db.String(250), default='')
    credits = db.Column(db.Integer, default=5, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    skills = db.relationship('Skill', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(600), nullable=False)
    level = db.Column(db.String(20), default='Beginner')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LearningSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(300), default='')
    status = db.Column(db.String(20), default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    skill = db.relationship('Skill')
    learner = db.relationship('User', foreign_keys=[learner_id])
    teacher = db.relationship('User', foreign_keys=[teacher_id])

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('learning_session.id'), unique=True, nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(300), default='')
    session = db.relationship('LearningSession', backref=db.backref('review', uselist=False))
    reviewer = db.relationship('User')

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin: abort(403)
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_counts():
    if current_user.is_authenticated:
        return {'pending_count': LearningSession.query.filter_by(teacher_id=current_user.id, status='pending').count()}
    return {'pending_count': 0}

@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    skills = Skill.query.order_by(Skill.created_at.desc()).limit(6).all()
    return render_template('landing.html', skills=skills)

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        if len(name) < 2 or len(name) > 80: flash('Name must be between 2 and 80 characters.', 'error')
        elif '@' not in email or len(email) > 120: flash('Enter a valid email address.', 'error')
        elif len(password) < 8: flash('Password must contain at least 8 characters.', 'error')
        elif User.query.filter_by(email=email).first(): flash('An account with this email already exists.', 'error')
        else:
            user = User(name=name, email=email); user.set_password(password)
            db.session.add(user); db.session.commit(); login_user(user)
            flash('Welcome to SkillBridge! Your account is ready.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower(); password = request.form.get('password','')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=False); flash('You are now logged in.', 'success')
            return redirect(url_for('dashboard'))
        flash('Incorrect email or password.', 'error')
    return render_template('auth.html', mode='login')

@app.post('/logout')
@login_required
def logout(): logout_user(); flash('You have been logged out.', 'success'); return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    offered = Skill.query.filter_by(owner_id=current_user.id).count()
    taught = LearningSession.query.filter_by(teacher_id=current_user.id, status='completed').count()
    learned = LearningSession.query.filter_by(learner_id=current_user.id, status='completed').count()
    pending = LearningSession.query.filter(or_(LearningSession.teacher_id==current_user.id, LearningSession.learner_id==current_user.id), LearningSession.status=='pending').order_by(LearningSession.created_at.desc()).all()
    recent = LearningSession.query.filter(or_(LearningSession.teacher_id==current_user.id, LearningSession.learner_id==current_user.id)).order_by(LearningSession.created_at.desc()).limit(5).all()
    categories = db.session.query(Skill.category, func.count(Skill.id)).group_by(Skill.category).all()
    return render_template('dashboard.html', offered=offered, taught=taught, learned=learned, pending=pending, recent=recent, categories=categories)

@app.route('/skills')
@login_required
def skills():
    query = request.args.get('q','').strip(); category = request.args.get('category','').strip(); level = request.args.get('level','').strip()
    q = Skill.query.join(User)
    if query: q = q.filter(or_(Skill.title.ilike(f'%{query}%'), Skill.description.ilike(f'%{query}%'), User.name.ilike(f'%{query}%')))
    if category: q = q.filter(Skill.category == category)
    if level: q = q.filter(Skill.level == level)
    results = q.order_by(Skill.created_at.desc()).all()
    categories = [x[0] for x in db.session.query(Skill.category).distinct().order_by(Skill.category).all()]
    return render_template('skills.html', skills=results, categories=categories, query=query, selected_category=category, selected_level=level)

@app.route('/skills/new', methods=['GET','POST'])
@login_required
def new_skill():
    if request.method == 'POST':
        title=request.form.get('title','').strip(); category=request.form.get('category','').strip(); description=request.form.get('description','').strip(); level=request.form.get('level','Beginner')
        if not 3 <= len(title) <= 100 or not category or not 10 <= len(description) <= 600 or level not in ['Beginner','Intermediate','Advanced']:
            flash('Please complete all fields. Title: 3–100 characters; description: 10–600 characters.', 'error')
        else:
            db.session.add(Skill(title=title, category=category, description=description, level=level, owner_id=current_user.id)); db.session.commit()
            flash('Your skill has been published.', 'success'); return redirect(url_for('skills'))
    return render_template('skill_form.html')

@app.post('/skills/<int:skill_id>/delete')
@login_required
def delete_skill(skill_id):
    skill=db.get_or_404(Skill, skill_id)
    if skill.owner_id != current_user.id and not current_user.is_admin: abort(403)
    if LearningSession.query.filter_by(skill_id=skill.id, status='pending').first():
        flash('This skill has a pending request. Resolve it before deleting.', 'error')
    else:
        db.session.delete(skill); db.session.commit(); flash('Skill deleted.', 'success')
    return redirect(url_for('skills'))

@app.post('/skills/<int:skill_id>/request')
@login_required
def request_session(skill_id):
    skill=db.get_or_404(Skill, skill_id)
    if skill.owner_id == current_user.id: flash('You cannot request a session for your own skill.', 'error')
    elif current_user.credits < 1: flash('You need at least 1 credit to request a learning session.', 'error')
    elif LearningSession.query.filter_by(skill_id=skill.id, learner_id=current_user.id, status='pending').first(): flash('You already have a pending request for this skill.', 'error')
    else:
        session=LearningSession(skill_id=skill.id, learner_id=current_user.id, teacher_id=skill.owner_id, message=request.form.get('message','').strip()[:300])
        db.session.add(session); db.session.commit(); flash('Learning request sent. One credit will be used when the session is accepted.', 'success')
    return redirect(url_for('skills'))

@app.post('/sessions/<int:session_id>/<action>')
@login_required
def update_session(session_id, action):
    s=db.get_or_404(LearningSession, session_id)
    if action == 'accept' and s.teacher_id == current_user.id and s.status == 'pending':
        if s.learner.credits < 1: flash('The learner no longer has enough credits.', 'error')
        else:
            s.learner.credits -= 1; s.status='accepted'; db.session.commit(); flash('Request accepted. The learner used 1 credit.', 'success')
    elif action == 'decline' and s.teacher_id == current_user.id and s.status == 'pending':
        s.status='declined'; db.session.commit(); flash('Request declined.', 'success')
    elif action == 'complete' and current_user.id in [s.teacher_id, s.learner_id] and s.status == 'accepted':
        s.status='completed'; s.teacher.credits += 1; db.session.commit(); flash('Session completed. 1 credit has been awarded to the teacher.', 'success')
    elif action == 'cancel' and current_user.id in [s.teacher_id, s.learner_id] and s.status in ['pending','accepted']:
        if s.status == 'accepted': s.learner.credits += 1
        s.status='cancelled'; db.session.commit(); flash('Session cancelled. Any reserved credit was returned.', 'success')
    else: abort(403)
    return redirect(url_for('dashboard'))

@app.route('/sessions/<int:session_id>/review', methods=['GET','POST'])
@login_required
def review_session(session_id):
    s=db.get_or_404(LearningSession, session_id)
    if s.status != 'completed' or s.learner_id != current_user.id or s.review: abort(403)
    if request.method == 'POST':
        try: rating=int(request.form.get('rating','0'))
        except ValueError: rating=0
        comment=request.form.get('comment','').strip()
        if rating not in range(1,6) or len(comment)>300: flash('Choose a rating from 1 to 5 and keep the comment under 300 characters.', 'error')
        else:
            db.session.add(Review(session_id=s.id, reviewer_id=current_user.id, rating=rating, comment=comment)); db.session.commit(); flash('Thanks for sharing your feedback!', 'success'); return redirect(url_for('dashboard'))
    return render_template('review.html', session=s)

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        bio=request.form.get('bio','').strip(); interests=request.form.get('interests','').strip()
        if len(bio)>300 or len(interests)>250: flash('Please shorten your bio or interests.', 'error')
        else: current_user.bio=bio; current_user.interests=interests; db.session.commit(); flash('Profile updated.', 'success'); return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', users=User.query.order_by(User.created_at.desc()).all(), skills=Skill.query.count(), sessions=LearningSession.query.count())

@app.errorhandler(403)
def forbidden(_): return render_template('error.html', code=403, message='You do not have permission to access this page.'), 403
@app.errorhandler(404)
def not_found(_): return render_template('error.html', code=404, message='The page or item you requested could not be found.'), 404

@app.cli.command('seed-demo')
def seed_demo():
    """Create demo users and sample skills. Demo password: SkillBridge123!"""
    if User.query.filter_by(email='maya@example.com').first(): print('Demo data already exists.'); return
    users=[]
    for name,email in [('Maya Sharma','maya@example.com'),('Aarav Mehta','aarav@example.com'),('Riya Singh','riya@example.com'),('Kabir Das','kabir@example.com')]:
        u=User(name=name,email=email,bio='Curious learner sharing practical skills.',interests='Coding, design, collaboration',credits=5); u.set_password('SkillBridge123!'); users.append(u); db.session.add(u)
    db.session.commit()
    samples=[('Python for Beginners','Programming','Learn variables, loops, functions and build your first Python mini-project.','Beginner',0),('UI Design with Figma','Design','Understand layout, typography, colour systems and create a polished mobile screen.','Intermediate',1),('Excel Essentials','Productivity','Learn formulas, sorting, filters and useful spreadsheet shortcuts.','Beginner',2),('Video Editing Basics','Creative','Explore editing workflow, transitions, audio cleanup and export settings.','Beginner',3),('C++ Problem Solving','Programming','Practice arrays, strings, functions and common coding interview patterns.','Intermediate',1),('Public Speaking','Communication','Build confidence, structure a short talk and improve delivery through practice.','Beginner',2)]
    for title,cat,desc,level,owner in samples: db.session.add(Skill(title=title,category=cat,description=desc,level=level,owner_id=users[owner].id))
    db.session.commit(); print('Demo data created. Sign in with maya@example.com / SkillBridge123!')

with app.app_context(): db.create_all()

if __name__ == '__main__': app.run(debug=os.environ.get('FLASK_DEBUG','0') == '1')
