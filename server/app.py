import os
import uuid
import qrcode
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENT_FOLDER = os.path.join(BASE_DIR, "documents")
QR_FOLDER = os.path.join(BASE_DIR, "static", "qr")
os.makedirs(DOCUMENT_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "change-this-agent-token")
ALLOWED_EXTENSIONS = {"pdf"}

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class PrintJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="pending")
    copies = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def authorized_agent():
    return request.headers.get("X-Agent-Token") == AGENT_TOKEN

@app.route("/")
def index():
    documents = Document.query.order_by(Document.id.desc()).all()
    return render_template("index.html", documents=documents)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            return "No file selected", 400
        if not allowed_file(file.filename):
            return "Only PDF files are allowed", 400
        code = "DOC-" + uuid.uuid4().hex[:8].upper()
        original_name = secure_filename(file.filename)
        stored_name = code + ".pdf"
        file.save(os.path.join(DOCUMENT_FOLDER, stored_name))
        document = Document(code=code, original_name=original_name, stored_name=stored_name)
        db.session.add(document)
        db.session.commit()
        qr_url = url_for("print_document", code=code, _external=True)
        qrcode.make(qr_url).save(os.path.join(QR_FOLDER, code + ".png"))
        return redirect(url_for("print_document", code=code))
    return render_template("upload.html")

@app.route("/p/<code>")
def print_document(code):
    document = Document.query.filter_by(code=code).first_or_404()
    return render_template("print.html", document=document)

@app.route("/file/<filename>")
def document_file(filename):
    return send_from_directory(DOCUMENT_FOLDER, filename)

@app.route("/qr/<code>")
def qr_file(code):
    return send_from_directory(QR_FOLDER, code + ".png")

@app.route("/api/print", methods=["POST"])
def create_print_job():
    data = request.get_json() or {}
    document = Document.query.filter_by(code=data.get("code")).first()
    if not document:
        return jsonify(error="Document not found"), 404
    copies = max(1, min(int(data.get("copies", 1)), 20))
    job = PrintJob(document_id=document.id, copies=copies, status="pending")
    db.session.add(job)
    db.session.commit()
    return jsonify(success=True, job_id=job.id)

@app.route("/agent/jobs")
def agent_jobs():
    if not authorized_agent():
        return jsonify(error="Unauthorized"), 401
    job = PrintJob.query.filter_by(status="pending").order_by(PrintJob.id.asc()).first()
    if not job:
        return jsonify(job=None)
    document = Document.query.get(job.document_id)
    job.status = "printing"
    db.session.commit()
    return jsonify(job={"id": job.id, "code": document.code, "filename": document.stored_name, "copies": job.copies, "url": url_for("document_file", filename=document.stored_name, _external=True)})

@app.route("/agent/jobs/<int:job_id>", methods=["POST"])
def update_job(job_id):
    if not authorized_agent():
        return jsonify(error="Unauthorized"), 401
    job = PrintJob.query.get_or_404(job_id)
    status = (request.get_json() or {}).get("status", "completed")
    job.status = status if status in {"completed", "failed"} else "failed"
    db.session.commit()
    return jsonify(success=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
