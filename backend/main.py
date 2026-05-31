import os, datetime, jwt
from flask import Flask, request, jsonify, send_file
from flask_migrate import Migrate
from config import Config
from models import db, User, Document, ExtractedEntity, Event
from werkzeug.utils import secure_filename
from agents.orchestrator_agent import OrchestratorAgent
from functools import wraps
from flask_cors import CORS
from fpdf import FPDF
from io import BytesIO
import secrets
from werkzeug.security import generate_password_hash
from flask import send_file
from flask import send_from_directory, abort
from agents.validator_agent import ValidatorAgent
validator_agent = ValidatorAgent()


ALLOWED_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'tiff'}


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)
    migrate = Migrate(app, db)


    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"]
    )



    orchestrator = OrchestratorAgent()

    # ---------------- AUTH HELPERS ---------------- #
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                auth = request.headers['Authorization']
                if auth.startswith("Bearer "):
                    token = auth.split(" ")[1]
            elif 'token' in request.args:
                token = request.args.get('token')

            if not token:
                return jsonify({'message': 'Token is missing'}), 401

            try:
                data = jwt.decode(token, app.config['JWT_SECRET'], algorithms=['HS256'])
                user = User.query.filter_by(username=data['sub']).first()
                if not user:
                    return jsonify({'message': 'User not found'}), 401
                request.user = user
            except Exception as e:
                return jsonify({'message': 'Token invalid', 'error': str(e)}), 401

            # ✅ Pass user explicitly into the wrapped function
            return f(user, *args, **kwargs)
        return decorated



    def role_required(roles):
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                user = getattr(request, 'user', None)
                if not user or user.role not in roles:
                    return jsonify({'message': 'Forbidden'}), 403
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
            # Sample users for each department
            u1 = User(username='student1', role='student', department='AIML'); u1.set_password('student1')
            u2 = User(username='student2', role='student', department='CSE-DS'); u2.set_password('student2')
            u3 = User(username='teacher1', role='teacher', department='CSE(Core)'); u3.set_password('teacher1')
            u4 = User(username='teacher2', role='teacher', department='AIML'); u4.set_password('teacher2')
            u5 = User(username='teacher3', role='teacher', department='CSE-CY'); u5.set_password('teacher3')
            u6 = User(username='iqc', role='iqc', department='ALL'); u6.set_password('iqc123')
            db.session.add_all([u1,u2,u3,u4,u5,u6]); db.session.commit()
        return jsonify({'message':'initialized'})

    @app.route('/api/upload', methods=['POST'])
    @token_required
    @role_required(['student','teacher'])
    def upload(current_user):
        """
        Handle file upload and trigger document processing.
        
        Args:
            current_user: User object injected by @token_required decorator
            
        Returns:
            JSON response with success status and document_id
        """
        try:
            # Check if file is in request
            if 'file' not in request.files:
                print("[Upload] ❌ No file in request")
                return jsonify({'message':'No file provided'}), 400

            file = request.files['file']
            
            # Check if filename is empty
            if file.filename == '':
                print("[Upload] ❌ Empty filename")
                return jsonify({'message':'No file selected'}), 400

            # Validate file extension
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext not in ALLOWED_EXT:
                print(f"[Upload] ❌ Invalid file type: .{ext}")
                return jsonify({'message':f'File type .{ext} not allowed. Allowed: {", ".join(ALLOWED_EXT)}'}), 400

            # Secure filename and create path
            filename = secure_filename(file.filename)
            upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            
            print(f"[Upload] 📂 Saving file: {filename}")
            print(f"[Upload] 📍 Path: {file_path}")
            print(f"[Upload] 👤 Uploaded by: {current_user.username}")
            print(f"[Upload] 🏢 User department: {current_user.department}")
            
            # Save file to disk
            file.save(file_path)
            print(f"[Upload] ✅ File saved successfully")

            # Create document record in database
            doc = Document(
                filename=filename, 
                uploaded_by=current_user.username,
                status='needs_review',
                department=current_user.department  # Pre-populate from user
            )
            db.session.add(doc)
            db.session.commit()
            
            print(f"[Upload] 💾 Document record created (ID: {doc.id})")

            # Trigger orchestration with explicit file_path parameter
            print(f"[Upload] 🚀 Triggering orchestration...")
            orchestrator.process_document(doc.id, file_path=file_path)
            
            print(f"[Upload] ✅ Processing initiated for document {doc.id}")

            return jsonify({
                "success": True,
                "message": f"Document '{filename}' uploaded and queued for processing",
                "document_id": doc.id,
                "status": "processing"
            }), 200

        except Exception as e:
            print(f"[Upload] ❌ Upload failed: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "success": False,
                "message": "Upload failed",
                "error": str(e)
            }), 500



    @app.route('/api/documents', methods=['GET'])
    @token_required
    def get_documents(current_user):
        query = Document.query

        # 🧠 Filter by role
        if current_user.role == 'student':
            query = query.filter_by(uploaded_by=current_user.username)
        elif current_user.role == 'teacher':
            query = query.filter_by(department=current_user.department)
        elif current_user.role == 'iqc':
            pass  # IQC sees all

        documents = query.order_by(Document.uploaded_at.desc()).all()

        return jsonify([{
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "uploaded_at": d.uploaded_at.isoformat(),
            "uploaded_by": d.uploaded_by,
            "department": d.department
        } for d in documents])


    @app.route('/api/document/<int:doc_id>', methods=['GET'])
    @token_required
    def doc_detail(current_user, doc_id):
        d = Document.query.get_or_404(doc_id)

        # Basic entities
        ents = [{
            "entity_type": e.entity_type,
            "entity_value": e.entity_value,
            "confidence": e.confidence
        } for e in d.entities]

        # Related events
        evs = [{
            "id": ev.id,
            "name": ev.name,
            "date": ev.date.isoformat() if ev.date else None,
            "department": ev.department,
            "category": ev.category,
            "validated": ev.validated,
            "type": ev.type 
        } for ev in d.events]

        # 🧩 New helper — fetch entity value by name
        def get_entity_value(name):
            for e in d.entities:
                if e.entity_type.lower() == name.lower():
                    return e.entity_value
            return ""

        # 🧩 Return all + new fields (abstract, venue, organizer)
        return jsonify({
            "document": {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "raw_text": d.raw_text
            },
            "entities": ents,
            "events": evs,
            "abstract": get_entity_value("abstract"),
            "venue": get_entity_value("venue"),
            "organizer": get_entity_value("organizer")
        })





    @app.route('/api/report/<dept>', methods=['GET'])
    @token_required
    def report(current_user, dept):
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
    
    @app.route("/api/validate/events", methods=["GET"])
    @token_required
    @role_required(["teacher", "iqc"])
    def list_pending_events(current_user):
        try:
            # 🧑‍🏫 Teachers → See only events from their department that are unvalidated
            if current_user.role == "teacher":
                events = Event.query.filter_by(validated=False, department=current_user.department).all()
            
            # 🧑‍💼 IQC → See all unvalidated events from all departments
            elif current_user.role == "iqc":
                events = Event.query.filter_by(validated=False).all()
            
            else:
                return jsonify({"message": "Forbidden"}), 403

            event_list = []
            for e in events:
                event_list.append({
                    "id": e.id,
                    "name": e.name,
                    "date": e.date.isoformat() if e.date else None,
                    "category": e.category,
                    "department": e.department,
                    "type": e.type,
                    "document_id": e.document_id,
                    "uploaded_by": e.document.uploaded_by if e.document else "Unknown",
                    "validated": e.validated
                })

            return jsonify({"events": event_list}), 200

        except Exception as e:
            print("[Error] Event fetch failed:", e)
            return jsonify({"message": "Error fetching events", "error": str(e)}), 500

            
    @app.route('/api/document/<int:doc_id>/file', methods=['GET'])
    @token_required
    def document_file(current_user, doc_id):
        d = Document.query.get_or_404(doc_id)
        filename = d.filename
        upload_dir = app.config.get('UPLOAD_FOLDER', 'uploads')
        try:
            # Determine mimetype
            mimetype = 'application/pdf'
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                mimetype = 'image/jpeg' if filename.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
            elif filename.lower().endswith('.gif'):
                mimetype = 'image/gif'
            
            response = send_from_directory(
                upload_dir, 
                filename, 
                mimetype=mimetype,
                as_attachment=False
            )
            # Force inline display
            response.headers['Content-Disposition'] = 'inline'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        except Exception as e:
            print("File send error:", e)
            abort(404)

    @app.route('/', defaults={'path':''})
    def index(path=''):
        return jsonify({'message':'API Running'})
    
    @app.route('/api/tracker', methods=['GET'])
    @token_required
    @role_required(['iqc'])
    def iqc_tracker(current_user):
        try:
            departments = {
                "AIML": 10,
                "CSE(Core)": 10,
                "CSE-DS": 10,
                "CSE-CY": 10,
                "ISE": 10,
                "ECE": 10,
                "AERO": 10
            }

            result = {}

            for dept, fixed_total in departments.items():
                validated = Event.query.filter_by(department=dept, validated=True).count()

                # ✅ progress = validated / fixed_total
                progress = round((validated / fixed_total) * 100, 2) if fixed_total > 0 else 0
                result[dept] = {
                    "validated": validated,
                    "total": fixed_total,
                    "progress": progress
                }

            return jsonify(result), 200

        except Exception as e:
            print("[Tracker Error]", e)
            return jsonify({"message": "Error generating tracker data", "error": str(e)}), 500


    @app.route('/api/tracker/<dept>', methods=['GET'])
    @token_required
    @role_required(['iqc', 'teacher', 'student'])
    def department_details(current_user, dept):
        try:
            categories = [
                "Seminar",
                "Workshop / Hands-on / Training",
                "Guest Lecture / Expert Talk",
                "Conference / Symposium",
                "Competition / Hackathon / Quiz",
                "Orientation / Induction / Welcome",
                "Research / Report / Paper Presentation",
                "General / Department Activity",
            ]
            events = Event.query.filter_by(department=dept, validated=True).all()

            # Group events by category (fuzzy match like report generator)
            grouped = {cat: [] for cat in categories}
            for e in events:
                matched = False
                raw_cat = e.category.strip() if e.category else ""
                for cat in categories:
                    if cat.split("/")[0].strip().lower() in raw_cat.lower():
                        grouped[cat].append({
                            "id": e.id,
                            "name": e.name,
                            "date": e.date.isoformat() if e.date else None,
                            "category": cat,
                            "validated": e.validated
                        })
                        matched = True
                        break
                if not matched:
                    grouped["General / Department Activity"].append({
                        "id": e.id,
                        "name": e.name,
                        "date": e.date.isoformat() if e.date else None,
                        "category": "General / Department Activity",
                        "validated": e.validated
                    })

            return jsonify({"department": dept, "events_by_category": grouped}), 200

        except Exception as e:
            print("[Department Details Error]", e)
            return jsonify({"message": "Error fetching department details", "error": str(e)}), 500
        

    @app.route('/api/tracker/rejected/<username>', methods=['GET'])
    @token_required
    @role_required(['student'])
    def rejected_events(current_user, username):
        try:
            # Ensure student can only see their own
            if current_user.username != username:
                return jsonify({"message": "Forbidden"}), 403

            events = (
                Event.query
                .join(Document, Event.document_id == Document.id)
                .filter(Document.uploaded_by == username, Event.status == "rejected")
                .all()
            )

            return jsonify({
                "rejected_events": [
                    {
                        "id": e.id,
                        "name": e.name,
                        "date": e.date.isoformat() if e.date else None,
                        "category": e.category,
                        "department": e.department,
                        "comment": e.reviewer_comment or "No comment provided",
                    }
                    for e in events
                ]
            }), 200

        except Exception as e:
            print("[Rejected Tracker Error]", e)
            return jsonify({"message": "Error fetching rejected events", "error": str(e)}), 500


    @app.route('/api/tracker/<dept>/report', methods=['GET'])
    @token_required
    @role_required(['iqc', 'teacher'])
    def generate_dept_report(current_user, dept):
        try:
            from fpdf import FPDF
            import datetime
            from io import BytesIO
            import os
            import traceback

            # ✅ Path to DSU logo
            logo_path = os.path.join(os.getcwd(), "static", "dsu_logo.png")

            # ✅ Full standardized event categories (same as frontend Validate.js)
            EVENT_CATEGORIES = [
                "Seminar",
                "Workshop / Hands-on / Training",
                "Guest Lecture / Expert Talk",
                "Conference / Symposium",
                "Competition / Hackathon / Quiz",
                "Orientation / Induction / Welcome",
                "Research / Report / Paper Presentation",
                "General / Department Activity",
            ]

            # ✅ Fetch validated events for the department
            events = Event.query.filter_by(department=dept, validated=True).all()
            pending_events = Event.query.filter_by(department=dept, validated=False, status="pending").all()

            # ✅ Group events by their closest category
            grouped = {cat: [] for cat in EVENT_CATEGORIES}
            for e in events:
                matched = False
                for cat in EVENT_CATEGORIES:
                    if cat.split("/")[0].strip().lower() in e.category.lower():
                        grouped[cat].append(e)
                        matched = True
                        break
                if not matched:
                    grouped["General / Department Activity"].append(e)

            # -------------------- Enhanced PDF Creation --------------------
            class PDF(FPDF):
                def header(self):
                    if self.page_no() == 1:
                        return
                    # Header for subsequent pages
                    self.set_font('Times', 'I', 9)
                    self.set_text_color(128, 128, 128)
                    self.cell(0, 8, f'IQC Report - Department of {dept}', 0, 0, 'L')
                    self.ln(10)

                def footer(self):
                    self.set_y(-15)
                    self.set_font('Times', 'I', 9)
                    self.set_text_color(100, 100, 100)
                    self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

            pdf = PDF()
            pdf.set_auto_page_break(auto=True, margin=20)
            pdf.add_page()

            # 🏫 Professional Header Section
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=15, y=12, w=30)

            pdf.set_xy(50, 12)
            pdf.set_font("Times", "B", 20)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, "DAYANANDA SAGAR UNIVERSITY", ln=True, align="C")
            
            pdf.set_xy(50, 22)
            pdf.set_font("Times", "", 11)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 6, "Shavige Malleshwara Hills, Kumaraswamy Layout, Bengaluru - 560078", ln=True, align="C")
            
            pdf.set_xy(50, 29)
            pdf.set_font("Times", "B", 15)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, f"Department of {dept}", ln=True, align="C")
            
            pdf.set_xy(50, 38)
            pdf.set_font("Times", "B", 13)
            pdf.set_text_color(204, 0, 0)
            pdf.cell(0, 7, "Internal Quality Control (IQC) Report", ln=True, align="C")

            # Decorative line
            pdf.set_draw_color(0, 102, 204)
            pdf.set_line_width(1.5)
            pdf.line(15, 50, 195, 50)
            pdf.ln(15)

            # 📋 Report Metadata Box
            pdf.set_font("Times", "B", 11)
            pdf.set_text_color(0, 0, 0)
            pdf.set_fill_color(240, 248, 255)
            
            # Academic year calculation
            today = datetime.date.today()
            academic_year = f"{today.year-1}-{today.year}" if today.month < 6 else f"{today.year}-{today.year+1}"
            
            pdf.cell(0, 8, "REPORT INFORMATION", ln=True, fill=True, border=1)
            pdf.set_font("Times", "", 11)
            
            # Two-column layout for report info
            col_width = 95
            pdf.cell(col_width, 7, f"Academic Year: {academic_year}", border=1)
            pdf.cell(col_width, 7, f"Report Date: {today.strftime('%d-%m-%Y')}", border=1, ln=True)
            
            pdf.cell(col_width, 7, f"Department: {dept}", border=1)
            pdf.cell(col_width, 7, f"Report Type: IQC Validation", border=1, ln=True)
            
            pdf.cell(col_width, 7, f"Total Validated Events: {len(events)}", border=1)
            pdf.cell(col_width, 7, f"Pending Validation: {len(pending_events)}", border=1, ln=True)
            
            pdf.ln(10)

            # 📊 Executive Summary
            pdf.set_font("Times", "B", 13)
            pdf.set_fill_color(0, 102, 204)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 9, "EXECUTIVE SUMMARY", ln=True, fill=True, align="C")
            pdf.ln(3)

            # Category-wise statistics
            pdf.set_font("Times", "B", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.set_fill_color(230, 240, 250)
            pdf.cell(110, 7, "Event Category", border=1, fill=True)
            pdf.cell(40, 7, "Count", border=1, align="C", fill=True)
            pdf.cell(40, 7, "Percentage", border=1, align="C", fill=True, ln=True)

            pdf.set_font("Times", "", 10)
            for cat in EVENT_CATEGORIES:
                cat_count = len(grouped[cat])
                if cat_count > 0:
                    percentage = (cat_count / len(events) * 100) if len(events) > 0 else 0
                    pdf.cell(110, 6, cat[:45], border=1)
                    pdf.cell(40, 6, str(cat_count), border=1, align="C")
                    pdf.cell(40, 6, f"{percentage:.1f}%", border=1, align="C", ln=True)

            pdf.ln(8)

            # 📑 Detailed Event Listings by Category
            pdf.set_font("Times", "B", 13)
            pdf.set_fill_color(0, 102, 204)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 9, "DETAILED EVENT LISTINGS", ln=True, fill=True, align="C")
            pdf.ln(5)

            for cat, cat_events in grouped.items():
                if not cat_events:
                    continue

                # Category header
                pdf.set_font("Times", "B", 12)
                pdf.set_fill_color(200, 220, 255)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 8, f"Category: {cat} ({len(cat_events)} events)", ln=True, fill=True, border=1)
                pdf.ln(1)

                # Table header
                pdf.set_font("Times", "B", 10)
                pdf.set_fill_color(230, 240, 250)
                pdf.cell(15, 7, "S.No", border=1, align="C", fill=True)
                pdf.cell(105, 7, "Event Title", border=1, align="C", fill=True)
                pdf.cell(35, 7, "Date", border=1, align="C", fill=True)
                pdf.cell(35, 7, "Type", border=1, align="C", fill=True, ln=True)

                # Event rows
                pdf.set_font("Times", "", 9)
                for idx, ev in enumerate(cat_events, 1):
                    event_type = ev.type or "N/A"
                    pdf.cell(15, 6, str(idx), border=1, align="C")
                    pdf.cell(105, 6, ev.name[:52], border=1)
                    pdf.cell(35, 6, ev.date.strftime("%d-%m-%Y") if ev.date else "N/A", border=1, align="C")
                    pdf.cell(35, 6, event_type[:15], border=1, align="C", ln=True)

                pdf.ln(6)

            # 📝 Approval Section
            pdf.add_page()
            pdf.set_font("Times", "B", 14)
            pdf.set_fill_color(0, 102, 204)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 10, "APPROVAL & CERTIFICATION", ln=True, fill=True, align="C")
            pdf.ln(10)

            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Times", "", 11)
            pdf.multi_cell(0, 6, "This is to certify that the events listed in this report have been reviewed and validated by the Internal Quality Control (IQC) team as per the university's quality assurance standards and guidelines.")
            pdf.ln(10)

            # Signature boxes
            pdf.set_font("Times", "B", 11)
            pdf.cell(0, 7, "SIGNATURES AND APPROVALS", ln=True)
            pdf.set_draw_color(0, 0, 0)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(10)

            # HOD Section
            pdf.set_font("Times", "B", 10)
            pdf.cell(0, 6, "Head of Department (HOD)", ln=True)
            pdf.ln(2)
            pdf.set_font("Times", "", 10)
            pdf.cell(95, 6, "Name: _________________________________", ln=False)
            pdf.ln(8)
            pdf.cell(95, 6, "Signature: _____________________________", ln=False)
            pdf.cell(95, 6, f"Date: {today.strftime('%d-%m-%Y')}", ln=True)
            pdf.ln(12)

            # IQC Reviewer Section
            pdf.set_font("Times", "B", 10)
            pdf.cell(0, 6, "IQC Reviewer", ln=True)
            pdf.ln(2)
            pdf.set_font("Times", "", 10)
            pdf.cell(95, 6, f"Name: {current_user.username}", ln=False)
            pdf.ln(8)
            pdf.cell(95, 6, "Signature: _____________________________", ln=False)
            pdf.cell(95, 6, f"Date: {today.strftime('%d-%m-%Y')}", ln=True)
            pdf.ln(12)

            # Principal/Director Section
            pdf.set_font("Times", "B", 10)
            pdf.cell(0, 6, "Principal/Director Approval", ln=True)
            pdf.ln(2)
            pdf.set_font("Times", "", 10)
            pdf.cell(95, 6, "Name: _________________________________", ln=False)
            pdf.ln(8)
            pdf.cell(95, 6, "Signature: _____________________________", ln=False)
            pdf.cell(95, 6, "Date: ___________________", ln=True)
            pdf.ln(15)

            # Official seal box
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.5)
            pdf.rect(140, pdf.get_y(), 50, 30)
            pdf.set_font("Times", "I", 9)
            pdf.set_xy(140, pdf.get_y() + 12)
            pdf.cell(50, 6, "Official Seal", align="C")

            # Final footer with disclaimer
            pdf.set_y(-35)
            pdf.set_font("Times", "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(3)
            pdf.multi_cell(0, 4, "This is a computer-generated report from the IQC Management System. For any queries or clarifications, please contact the Quality Assurance Cell at qa@dsu.edu.in", align="C")
            pdf.cell(0, 4, f"Generated on {today.strftime('%d-%m-%Y at %H:%M:%S')}", 0, 0, "C")

            # ✅ Output safely
            try:
                pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            except Exception as enc_err:
                print("[Encoding Fallback Triggered]", enc_err)
                pdf_bytes = pdf.output(dest="S").encode("utf-8", "replace")

            pdf_stream = BytesIO(pdf_bytes)

            return send_file(
                pdf_stream,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"{dept}_IQC_Report_{today.strftime('%Y%m%d')}.pdf"
            )

        except Exception as err:
            print("[Report Generation Error]", err)
            traceback.print_exc()
            return jsonify({"message": "Failed to generate report", "error": str(err)}), 500



    # ------------------ USER MANAGEMENT (IQC ADMIN) ------------------ #
    @app.route('/api/auth/add_user', methods=['POST'])
    @token_required
    @role_required(['iqc'])
    def add_user(current_user):
        try:
            data = request.get_json() or {}
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            role = data.get('role', '').strip()
            department = data.get('department', '').strip()

            if not username or not password or not role:
                return jsonify({"message": "Missing required fields"}), 400

            # ✅ Check for any existing (possibly undeleted) record
            existing = User.query.filter_by(username=username).first()
            if existing:
                print(f"⚠️ Removing existing user '{username}' before re-creation...")
                db.session.delete(existing)
                db.session.commit()

            # ✅ Create fresh user
            user = User(username=username, role=role, department=department)
            user.set_password(password)  # sets both password_hash + plain_password
            db.session.add(user)
            db.session.commit()

            print(f"✅ Created user '{username}' ({role} - {department}) successfully.")
            return jsonify({
                "message": f"User '{username}' created successfully",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "department": user.department,
                    "plain_password": user.plain_password
                }
            }), 201

        except Exception as e:
            print("[Add User Error]", e)
            db.session.rollback()
            return jsonify({"message": "Failed to create user", "error": str(e)}), 500



    @app.route('/api/auth/users', methods=['GET'])
    @token_required
    @role_required(['iqc'])
    def api_list_users(current_user):
        users = User.query.all()
        return jsonify({
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "department": u.department,
                    "plain_password": u.plain_password or "N/A"
                } for u in users
            ]
        }), 200



    @app.route('/api/auth/users/<int:user_id>', methods=['DELETE'])
    @token_required
    @role_required(['iqc'])
    def api_delete_user(current_user, user_id):
        user = User.query.get(user_id)
        if not user:
            return jsonify({"message": "User not found"}), 404
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200


    @app.route('/api/auth/users/<int:user_id>/set_password', methods=['POST'])
    @token_required
    @role_required(['iqc'])
    def api_set_password(current_user, user_id):
        data = request.get_json() or {}
        new_password = data.get('password')

        if not new_password:
            return jsonify({"message": "Password is required"}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({"message": "User not found"}), 404

        user.set_password(new_password)
        db.session.commit()

        return jsonify({"message": f"Password updated for {user.username}"}), 200


    @app.route('/api/validate/<int:event_id>', methods=['POST'])
    @token_required
    @role_required(['teacher', 'iqc'])
    def validate_event(current_user, event_id):
        try:
            event = Event.query.get_or_404(event_id)
            data = request.get_json() or {}
            print("[Validate Debug] Incoming JSON:", data)

            # Build a validation packet
            validation_input = {
                "event": {
                    "event_name": data.get("name"),
                    "date": data.get("date"),
                    "category": data.get("category"),
                    "department": data.get("department"),
                },
                "entities": {
                    "venue": data.get("venue"),
                    "organizer": data.get("organizer"),
                    "abstract": data.get("abstract"),
                }
            }

            # Run validation
            result = validator_agent.process(validation_input)

            # If valid → update event
            if result["status"] == "ok":
                event.name = data.get("name")
                event.date = datetime.datetime.strptime(data.get("date"), "%Y-%m-%d").date()
                event.category = data.get("category")
                event.department = data.get("department")
                event.validated = True
                db.session.commit()

                print(f"[Validate] ✅ Event {event.id} validated successfully by {current_user.username}")
                return jsonify({"message": "validated", "errors": []}), 200

            else:
                print(f"[Validate] ⚠ Validation issues for event {event.id}: {result['errors']}")
                return jsonify({"message": "validation_failed", "errors": result["errors"]}), 400

        except Exception as e:
            print("[Validate] ❌ Error:", e)
            return jsonify({"message": "Validation failed", "error": str(e)}), 500
    
    @app.route('/api/validate/<int:event_id>/save', methods=['POST'])
    @token_required
    @role_required(['teacher', 'iqc'])
    def save_event_without_validation(current_user, event_id):
        """Save event data without validation - allows partial completion"""
        try:
            event = Event.query.get_or_404(event_id)
            data = request.get_json() or {}
            print("[Save] Saving event without validation:", data)

            # Update event fields directly without validation
            if data.get("name"):
                event.name = data.get("name")
            if data.get("date"):
                event.date = datetime.datetime.strptime(data.get("date"), "%Y-%m-%d").date()
            if data.get("category"):
                event.category = data.get("category")
            if data.get("department"):
                event.department = data.get("department")
            
            # Optional fields
            event.venue = data.get("venue", "")
            event.organizer = data.get("organizer", "")
            event.abstract = data.get("abstract", "")
            
            # Add reviewer comment if provided
            if data.get("comment"):
                event.reviewer_comment = data.get("comment")
            
            # Keep validated as False - this is a draft save
            event.validated = False
            db.session.commit()

            print(f"[Save] ✅ Event {event.id} saved (without validation) by {current_user.username}")
            return jsonify({"message": "saved", "event_id": event.id}), 200

        except Exception as e:
            print("[Save] ❌ Error:", e)
            return jsonify({"message": "Save failed", "error": str(e)}), 500
    
    @app.route('/api/validate/<int:event_id>/reject', methods=['POST'])
    @token_required
    @role_required(['teacher', 'iqc'])
    def reject_event(current_user, event_id):
        try:
            data = request.get_json() or {}
            comment = data.get("comment", "No reason provided.")
            event = Event.query.get_or_404(event_id)

            # Update event status
            event.validated = False
            event.status = "rejected"
            event.reviewer_comment = comment
            db.session.commit()

            print(f"[Reject] Error: Event {event.id} rejected by {current_user.username} - {comment}")

            return jsonify({
                "message": "Event rejected successfully.",
                "comment": comment
            }), 200
        except Exception as e:
            print("[Reject] Error:", e)
            return jsonify({"message": "Reject failed", "error": str(e)}), 500

    @app.route('/api/events/<int:event_id>', methods=['DELETE'])
    @token_required
    def delete_event(current_user, event_id):
        try:
            event = Event.query.get_or_404(event_id)
            
            # Check authorization - only student who uploaded can delete their rejected event
            doc = Document.query.get(event.document_id) if event.document_id else None
            if doc and doc.uploaded_by != current_user.username:
                return jsonify({"message": "Unauthorized - only uploader can delete"}), 403
            
            # Delete related entities first
            ExtractedEntity.query.filter_by(document_id=event.document_id).delete()
            
            # Delete the event
            db.session.delete(event)
            
            # Delete document if it has no other events
            if doc and not Event.query.filter_by(document_id=doc.id).first():
                db.session.delete(doc)
            
            db.session.commit()
            
            print(f"[Delete] Event {event_id} deleted by {current_user.username}")
            return jsonify({"message": "Event deleted successfully"}), 200
            
        except Exception as e:
            print(f"[Delete] Error: {e}")
            return jsonify({"message": "Delete failed", "error": str(e)}), 500

    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
