#!/usr/bin/env python3
# build_project_zip.py
# Usage: python build_project_zip.py
#
# This script creates a project folder "multiagent_event_tracker" and a zip
# "multiagent_event_tracker_full.zip" with the backend and frontend skeleton.

import os, zipfile, shutil, json
from pathlib import Path

base = Path.cwd() / "multiagent_event_tracker"
if base.exists():
    shutil.rmtree(base)
# create directories
dirs = [
    base / "backend" / "agents",
    base / "backend" / "static" / "uploads",
    base / "backend" / "templates",
    base / "frontend" / "src" / "pages",
    base / "frontend" / "src" / "components",
    base / "frontend" / "public"
]
for d in dirs:
    d.mkdir(parents=True, exist_ok=True)

files = {}

# --- BACKEND FILES ---
files["backend/requirements.txt"] = """Flask==2.3.3
Flask-SQLAlchemy==3.0.3
Flask-Migrate==4.0.4
PyJWT==2.8.0
paddleocr==2.5.1.1
paddlepaddle==2.5.0
spacy==3.6.1
python-dateutil==2.8.2
reportlab==4.0.0
requests==2.31.0
python-dotenv==1.0.0
gunicorn==20.1.0
"""

files["backend/config.py"] = """import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY','dev-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR/'app.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR/'static'/'uploads'))
    JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-secret-key')
"""

files["backend/models.py"] = """from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # student, teacher, iqc
    department = db.Column(db.String(120), nullable=True)  # AIML, CSE(Core), ALL

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(400), nullable=False)
    uploaded_by = db.Column(db.String(120), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='uploaded')  # uploaded, processing, needs_review, saved, failed
    raw_text = db.Column(db.Text, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

class ExtractedEntity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    label = db.Column(db.String(100))  # EVENT_NAME, DATE, DEPARTMENT, CATEGORY
    text = db.Column(db.Text)
    confidence = db.Column(db.Float, default=0.0)

    document = db.relationship('Document', backref='entities')

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    name = db.Column(db.String(500))
    date = db.Column(db.Date)
    department = db.Column(db.String(120))
    category = db.Column(db.String(120))  # Faculty Event, Student Event, Student Quiz
    validated = db.Column(db.Boolean, default=False)

    document = db.relationship('Document', backref='events')
"""

files["backend/app.py"] = """import os, datetime, jwt
from flask import Flask, request, jsonify, send_file
from flask_migrate import Migrate
from config import Config
from models import db, User, Document, ExtractedEntity, Event
from werkzeug.utils import secure_filename
from agents.orchestrator_agent import OrchestratorAgent
from functools import wraps

ALLOWED_EXT = {'pdf','png','jpg','jpeg','tiff'}

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)
    migrate = Migrate(app, db)

    orchestrator = OrchestratorAgent(app)

    def token_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                auth = request.headers.get('Authorization')
                if auth and auth.startswith('Bearer '):
                    token = auth.split(' ',1)[1]
            if not token:
                return jsonify({'message':'Token is missing'}), 401
            try:
                data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
                user = User.query.filter_by(username=data['sub']).first()
                if not user:
                    return jsonify({'message':'User not found'}), 401
                request.user = user
            except Exception as e:
                return jsonify({'message':'Token invalid', 'error':str(e)}), 401
            return f(*args, **kwargs)
        return wrapper

    def role_required(roles):
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                user = getattr(request, 'user', None)
                if not user or user.role not in roles:
                    return jsonify({'message':'Forbidden'}), 403
                return f(*args, **kwargs)
            return wrapped
        return decorator

    @app.route('/api/ping')
    def ping():
        return jsonify({'message':'pong'})

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.json or {}
        username = data.get('username'); password = data.get('password')
        if not username or not password:
            return jsonify({'message':'username and password required'}), 400
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify({'message':'Invalid credentials'}), 401
        token = jwt.encode({'sub': user.username, 'role': user.role, 'exp': datetime.datetime.utcnow()+datetime.timedelta(hours=8)}, app.config['JWT_SECRET'], algorithm='HS256')
        return jsonify({'token': token, 'user': {'username': user.username, 'role': user.role, 'department': user.department}})

    @app.route('/api/init', methods=['POST'])
    def init_data():
        if User.query.count() == 0:
            u1 = User(username='student1', role='student', department='AIML'); u1.set_password('student1')
            u2 = User(username='teacher1', role='teacher', department='CSE(Core)'); u2.set_password('teacher1')
            u3 = User(username='iqc', role='iqc', department='ALL'); u3.set_password('adminpass')
            db.session.add_all([u1,u2,u3]); db.session.commit()
        return jsonify({'message':'initialized'})

    @app.route('/api/upload', methods=['POST'])
    @token_required
    @role_required(['student','teacher'])
    def upload():
        if 'file' not in request.files:
            return jsonify({'message':'no file'}), 400
        f = request.files['file']
        if f.filename=='': return jsonify({'message':'empty filename'}), 400
        ext = f.filename.rsplit('.',1)[-1].lower()
        if ext not in ALLOWED_EXT:
            return jsonify({'message':'file type not allowed'}), 400
        filename = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)
        doc = Document(filename=filename, uploaded_by=request.user.username, status='uploaded')
        db.session.add(doc); db.session.commit()

        orchestrator.process_document(doc.id, path)

        return jsonify({'message':'uploaded','document_id':doc.id})

    @app.route('/api/documents', methods=['GET'])
    @token_required
    def list_docs():
        user = request.user
        if user.role=='iqc':
            docs = Document.query.order_by(Document.uploaded_at.desc()).all()
        else:
            docs = Document.query.filter_by(uploaded_by=user.username).order_by(Document.uploaded_at.desc()).all()
        out = [{'id':d.id,'filename':d.filename,'status':d.status,'uploaded_at':d.uploaded_at.isoformat()} for d in docs]
        return jsonify(out)

    @app.route('/api/document/<int:doc_id>', methods=['GET'])
    @token_required
    def doc_detail(doc_id):
        d = Document.query.get_or_404(doc_id)
        ents = [{'label':e.label,'text':e.text,'confidence':e.confidence} for e in d.entities]
        evs = [{'id':ev.id,'name':ev.name,'date':ev.date.isoformat() if ev.date else None,'department':ev.department,'category':ev.category,'validated':ev.validated} for ev in d.events]
        return jsonify({'document':{'id':d.id,'filename':d.filename,'status':d.status,'raw_text':d.raw_text}, 'entities':ents, 'events':evs})

    @app.route('/api/validate/<int:event_id>', methods=['POST'])
    @token_required
    @role_required(['teacher','iqc'])
    def validate_event(event_id):
        data = request.json or {}
        ev = Event.query.get_or_404(event_id)
        ev.name = data.get('name', ev.name)
        date_str = data.get('date', None)
        if date_str:
            try:
                ev.date = datetime.date.fromisoformat(date_str)
            except:
                pass
        ev.department = data.get('department', ev.department)
        ev.category = data.get('category', ev.category)
        ev.validated = True
        db.session.commit()
        return jsonify({'message':'validated'})

    @app.route('/api/tracker', methods=['GET'])
    @token_required
    def tracker():
        depts = ['AIML','CSE(Core)']
        out = {}
        for dept in depts:
            events = Event.query.filter_by(department=dept).all()
            total = len(events)
            cat_counts = {}
            for ev in events:
                cat_counts[ev.category] = cat_counts.get(ev.category,0)+1
            out[dept] = {'total': total, 'by_category': cat_counts, 'events':[{'name':e.name,'date': e.date.isoformat() if e.date else None,'category':e.category} for e in events]}
        return jsonify(out)

    @app.route('/api/report/<dept>', methods=['GET'])
    @token_required
    def report(dept):
        import csv, io
        events = Event.query.filter_by(department=dept).all()
        si = io.StringIO()
        writer = csv.writer(si)
        writer.writerow(['name','date','category','validated'])
        for e in events:
            writer.writerow([e.name, e.date.isoformat() if e.date else '', e.category, e.validated])
        output = io.BytesIO()
        output.write(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f'{dept}_report.csv', mimetype='text/csv')

    @app.route('/', defaults={'path':''})
    def index(path=''):
        return jsonify({'message':'API Running'})

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
"""

files["backend/agents/orchestrator_agent.py"] = """import traceback
from .ocr_agent import OcrAgent
from .ner_agent import NerAgent
from .categorizer_agent import CategorizerAgent
from .validator_agent import ValidatorAgent
from .tracker_agent import TrackerAgent
from models import db, Document, Event, ExtractedEntity

class OrchestratorAgent:
    def __init__(self, app=None):
        self.app = app
        self.ocr = OcrAgent()
        self.ner = NerAgent()
        self.categorizer = CategorizerAgent()
        self.validator = ValidatorAgent()
        self.tracker = TrackerAgent()

    def process_document(self, doc_id, file_path):
        try:
            doc = Document.query.get(doc_id)
            raw = self.ocr.process({'file_path':file_path})
            doc.raw_text = raw.get('raw_text')
            db.session.commit()
            ner_out = self.ner.process({'raw_text': doc.raw_text})
            for label, text, conf in ner_out.get('entities', []):
                ee = ExtractedEntity(document_id=doc.id, label=label, text=text, confidence=conf)
                db.session.add(ee)
            db.session.commit()
            cat = self.categorizer.process({'raw_text': doc.raw_text})
            ev = Event(document_id=doc.id, name=ner_out.get('event_name') or 'Unknown', department=ner_out.get('department') or 'Unknown', category=cat.get('category'))
            if ner_out.get('date'):
                ev.date = ner_out.get('date')
            db.session.add(ev); db.session.commit()
            val = self.validator.process({'event':ev})
            if val.get('status')=='needs_review':
                doc.status = 'needs_review'
            else:
                ev.validated = True
                doc.status = 'saved'
                self.tracker.update(ev)
            db.session.commit()
        except Exception as e:
            doc = Document.query.get(doc_id)
            doc.status = 'failed'
            doc.last_error = traceback.format_exc()
            db.session.commit()
"""

files["backend/agents/ocr_agent.py"] = """# PaddleOCR-based OCR Agent
from paddleocr import PaddleOCR
ocr_model = PaddleOCR(use_angle_cls=True, lang='en')

class OcrAgent:
    def __init__(self):
        self.model = ocr_model

    def process(self, data):
        path = data.get('file_path')
        result_text = []
        try:
            res = self.model.ocr(path, cls=True)
            for line in res:
                for box, txt, score in line:
                    result_text.append(txt)
        except Exception as e:
            result_text = []
        return {'raw_text': '\\n'.join(result_text)}
"""

files["backend/agents/ner_agent.py"] = """import re
import spacy
from dateutil import parser as dateparser
nlp = spacy.load('en_core_web_sm')

EVENT_PATTERNS = [r'(workshop on .+)', r'(seminar on .+)', r'(guest lecture on .+)', r'(symposium on .+)', r'(conference on .+)', r'(annual day .+)']

class NerAgent:
    def __init__(self):
        self.nlp = nlp

    def process(self, data):
        text = data.get('raw_text','')
        entities = []
        event_name = None; date = None; department = None
        for pat in EVENT_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                event_name = m.group(1).strip()
                entities.append(('EVENT_NAME', event_name, 0.95))
                break
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ == 'ORG' and not department:
                department = ent.text
                entities.append(('DEPARTMENT', department, 0.7))
            if ent.label_ == 'DATE' and not date:
                try:
                    parsed = dateparser.parse(ent.text, fuzzy=True).date()
                    date = parsed
                    entities.append(('DATE', ent.text, 0.9))
                except:
                    pass
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not event_name and lines:
            event_name = lines[0]
            entities.append(('EVENT_NAME', event_name, 0.6))
        return {'entities': entities, 'event_name': event_name, 'date': date, 'department': department}
"""

files["backend/agents/categorizer_agent.py"] = """def categorize_text(text):
    t = text.lower()
    if 'faculty' in t or 'staff' in t or 'prof' in t:
        return 'Faculty Event'
    if 'quiz' in t:
        return 'Student Quiz'
    if 'student' in t or 'workshop' in t or 'seminar' in t:
        return 'Student Event'
    return 'General Event'

class CategorizerAgent:
    def process(self, data):
        text = data.get('raw_text','')
        return {'category': categorize_text(text)}
"""

files["backend/agents/validator_agent.py"] = """def simple_validate(event_dict):
    errors = []
    if not event_dict or not getattr(event_dict, 'date', None):
        errors.append('Missing date')
    if not getattr(event_dict, 'category', None):
        errors.append('Missing category')
    status = 'ok' if not errors else 'needs_review'
    return {'status': status, 'errors': errors}

class ValidatorAgent:
    def process(self, data):
        ev = data.get('event')
        return simple_validate(ev)
"""

files["backend/agents/tracker_agent.py"] = """from models import db, Event
class TrackerAgent:
    def __init__(self):
        pass
    def update(self, event):
        db.session.commit()
"""

files["backend/templates/index.html"] = "<!doctype html><html><head><title>Backend</title></head><body><h1>MultiAgent Event Tracker API</h1><p>Use the React frontend to interact with the system.</p></body></html>"

files["frontend/package.json"] = json.dumps({
  "name":"multiagent-frontend","version":"1.0.0","private":True,
  "scripts":{"start":"react-scripts start","build":"react-scripts build"},
  "dependencies":{"react":"18.2.0","react-dom":"18.2.0","react-scripts":"5.0.1","axios":"1.4.0","tailwindcss":"3.4.7","chart.js":"4.4.0","react-chartjs-2":"5.2.0","react-router-dom":"6.11.2"}
}, indent=2)

files["frontend/public/index.html"] = "<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width, initial-scale=1'/><title>MultiAgent Event Tracker</title></head><body><div id='root'></div></body></html>"

files["frontend/src/index.js"] = "import React from 'react';import { createRoot } from 'react-dom/client';import App from './App';import './index.css';createRoot(document.getElementById('root')).render(<App />);"

files["frontend/src/index.css"] = "@tailwind base;@tailwind components;@tailwind utilities;body{font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial;}"

files["frontend/src/App.js"] = """import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Login from './pages/Login';
import Upload from './pages/Upload';
import Tracker from './pages/Tracker';
import Validate from './pages/Validate';
import Admin from './pages/Admin';

export default function App(){
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow p-4">
          <div className="container mx-auto flex justify-between">
            <div><Link to="/" className="font-bold">MultiAgent Tracker</Link></div>
            <div className="space-x-4">
              <Link to="/upload">Upload</Link>
              <Link to="/tracker">Tracker</Link>
              <Link to="/admin">Admin</Link>
            </div>
          </div>
        </nav>
        <div className="container mx-auto p-6">
          <Routes>
            <Route path="/" element={<Login/>} />
            <Route path="/upload" element={<Upload/>} />
            <Route path="/tracker" element={<Tracker/>} />
            <Route path="/validate" element={<Validate/>} />
            <Route path="/admin" element={<Admin/>} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
"""

files["frontend/src/pages/Login.js"] = """import React, {useState} from 'react';
import axios from 'axios';
export default function Login(){
  const [username,setUsername]=useState('');
  const [password,setPassword]=useState('');
  const [msg,setMsg]=useState('');
  const login = async ()=>{
    try{
      const res = await axios.post('/api/auth/login',{username,password});
      localStorage.setItem('token', res.data.token);
      setMsg('Logged in');
    }catch(e){
      setMsg('Login failed');
    }
  };
  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-xl font-bold mb-4">Login</h2>
      <input className="w-full p-2 border mb-3" placeholder="username" value={username} onChange={e=>setUsername(e.target.value)} />
      <input type="password" className="w-full p-2 border mb-3" placeholder="password" value={password} onChange={e=>setPassword(e.target.value)} />
      <button className="bg-blue-600 text-white px-4 py-2 rounded" onClick={login}>Login</button>
      <p className="mt-3">{msg}</p>
    </div>
  );
}
"""

files["frontend/src/pages/Upload.js"] = """import React, {useState} from 'react';
import axios from 'axios';
export default function Upload(){
  const [file,setFile]=useState(null);
  const [msg,setMsg]=useState('');
  const upload = async ()=>{
    if(!file) return setMsg('Select file');
    const fd = new FormData(); fd.append('file', file);
    const token = localStorage.getItem('token');
    try{
      const res = await axios.post('/api/upload', fd, { headers: { Authorization: 'Bearer '+ token }});
      setMsg('Uploaded: '+ res.data.document_id);
    }catch(e){
      setMsg('Upload failed');
    }
  };
  return (
    <div className="max-w-lg mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-xl font-bold mb-4">Upload Event Document</h2>
      <input type="file" onChange={e=>setFile(e.target.files[0])} className="mb-4" />
      <button className="bg-green-600 text-white px-4 py-2 rounded" onClick={upload}>Upload</button>
      <p className="mt-3">{msg}</p>
    </div>
  );
}
"""

files["frontend/src/pages/Validate.js"] = """import React from 'react';
export default function Validate(){
  return (
    <div className="max-w-3xl mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-xl font-bold mb-4">Validation Queue</h2>
      <p>Teacher/IQC can validate extracted events here. (UI placeholder — connect to API)</p>
    </div>
  );
}
"""

files["frontend/src/pages/Tracker.js"] = """import React, {useState, useEffect} from 'react';
import axios from 'axios';
export default function Tracker(){
  const [data,setData]=useState(null);
  useEffect(()=>{ const token=localStorage.getItem('token'); axios.get('/api/tracker',{headers:{Authorization:'Bearer '+token}}).then(r=>setData(r.data)).catch(()=>{});},[]);
  if(!data) return <div>Loading...</div>;
  return (
    <div className="space-y-6">
      {Object.keys(data).map(dept=> (
        <div key={dept} className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-bold">{dept}</h3>
          <p>Total events: {data[dept].total}</p>
          <div className="grid grid-cols-3 gap-4 mt-3">
            {Object.entries(data[dept].by_category).map(([cat,count])=> (
              <div key={cat} className="p-3 border rounded">
                <div className="text-sm font-semibold">{cat}</div>
                <div className="text-2xl">{count}</div>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <table className="w-full table-auto">
              <thead><tr><th>Name</th><th>Date</th><th>Category</th></tr></thead>
              <tbody>
                {data[dept].events.map((e,i)=> <tr key={i}><td>{e.name}</td><td>{e.date}</td><td>{e.category}</td></tr>)}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
"""

files["frontend/src/pages/Admin.js"] = """import React from 'react';
export default function Admin(){
  return (
    <div className="max-w-4xl mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-xl font-bold mb-4">IQC Admin Dashboard</h2>
      <p>View and edit events; download reports. (UI placeholder — connect to /api/report)</p>
    </div>
  );
}
"""

files["frontend/README.md"] = "Frontend: run `npm install` then `npm start`. Ensure backend is running at /api endpoints."
files["README.md"] = "MultiAgent Event Tracker - Full Project\nThis ZIP contains a Flask backend and a React frontend skeleton. See backend/README and frontend/README for setup steps."

# write files
for rel, content in files.items():
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)

# create zip
zip_path = Path.cwd() / "multiagent_event_tracker_full.zip"
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, _, filenames in os.walk(base):
        for fn in filenames:
            full = os.path.join(root, fn)
            arc = os.path.relpath(full, base)
            zf.write(full, arcname=arc)

print("ZIP created at:", zip_path)
