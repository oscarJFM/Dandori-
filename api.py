#!/usr/bin/env python3
"""
School of Dandori - Course API Server
Exposes course data via REST API
"""

import io
import os
import re
import sqlite3
import uuid
import tempfile
from pathlib import Path

import psycopg2
from psycopg2 import extras
from flask import Flask, jsonify, request, render_template, send_file
from werkzeug.utils import secure_filename
import PyPDF2
from google.cloud import storage

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

DB_PATH = os.environ.get("DB_PATH", "courses.db")
DATABASE_URL = os.environ.get("DATABASE_URL")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
GCS_CREDENTIALS = os.environ.get("GCS_CREDENTIALS_JSON")

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    """Create database connection - supports both SQLite (local) and PostgreSQL (Supabase)"""
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(DB_PATH)
    return conn


def upload_to_gcs(file_data, filename):
    """Upload file to Google Cloud Storage"""
    if not GCS_BUCKET_NAME:
        return None

    try:
        if GCS_CREDENTIALS:
            client = storage.Client.from_service_account_json(
                io.StringIO(GCS_CREDENTIALS)
            )
        else:
            client = storage.Client()

        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"pdfs/{filename}")
        blob.upload_from_string(file_data, content_type="application/pdf")

        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/pdfs/{filename}"
    except Exception as e:
        print(f"GCS upload error: {e}")
        return None


def extract_from_pdf(file_data):
    """Extract course data from PDF bytes"""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_data))
        text = ""
        for page in reader.pages:
            text += page.extract_text()

        return parse_course_data(text)
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None


def parse_course_data(text):
    """Parse extracted text into structured course data"""
    title_match = re.search(r"^(.+?)(?:\n|Instructor:)", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Unknown"

    instructor_match = re.search(r"Instructor:\s*(.+?)(?:\n|Location:)", text)
    instructor = instructor_match.group(1).strip() if instructor_match else None

    location_match = re.search(r"Location:\s*(.+?)(?:\n|Course Type:)", text)
    location = location_match.group(1).strip() if location_match else None

    course_type_match = re.search(r"Course Type:\s*(.+?)(?:\n|Cost:)", text)
    course_type = course_type_match.group(1).strip() if course_type_match else None

    cost_match = re.search(r"Cost:\s*(.+?)(?:\n|Learning)", text)
    cost = cost_match.group(1).strip() if cost_match else None

    class_id_match = re.search(r"Class ID:\s*(CLASS_\d+)", text)
    class_id = class_id_match.group(1) if class_id_match else None

    objectives_match = re.search(
        r"Learning Objectives(.+?)Provided Materials", text, re.DOTALL
    )
    learning_objectives = (
        objectives_match.group(1).strip() if objectives_match else None
    )

    materials_match = re.search(
        r"Provided Materials(.+?)Skills Developed", text, re.DOTALL
    )
    provided_materials = materials_match.group(1).strip() if materials_match else None

    skills_match = re.search(
        r"Skills Developed(.+?)Course Description", text, re.DOTALL
    )
    skills = skills_match.group(1).strip() if skills_match else None

    description_match = re.search(r"Course Description(.+?)Class ID:", text, re.DOTALL)
    description = description_match.group(1).strip() if description_match else None

    return {
        "class_id": class_id,
        "title": title,
        "instructor": instructor,
        "location": location,
        "course_type": course_type,
        "cost": cost,
        "learning_objectives": learning_objectives,
        "provided_materials": provided_materials,
        "skills": skills,
        "description": description,
    }


@app.route("/")
def index():
    """Serve the HTML interface"""
    return render_template("index.html")


@app.route("/api/courses", methods=["GET"])
def get_courses():
    """Get all courses with optional filtering"""
    search = request.args.get("search", "")
    location = request.args.get("location", "")
    course_type = request.args.get("course_type", "")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT id, class_id, title, instructor, location, course_type, cost, 
               skills, filename, pdf_url, created_at, updated_at
        FROM courses
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (title ILIKE %s OR class_id ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if location:
        query += " AND location ILIKE %s"
        params.append(f"%{location}%")

    if course_type:
        query += " AND course_type ILIKE %s"
        params.append(f"%{course_type}%")

    query += " ORDER BY class_id"

    cursor.execute(query, params)
    courses = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"count": len(courses), "courses": courses})


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    """Get a single course by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM courses WHERE id = %s", (course_id,))

    course = cursor.fetchone()
    conn.close()

    if course:
        return jsonify(dict(course))
    else:
        return jsonify({"error": "Course not found"}), 404


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    """Upload a PDF, process it through the pipeline, and store in database"""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    file_data = file.read()
    filename = secure_filename(file.filename) if file.filename else "unknown.pdf"

    unique_filename = f"{uuid.uuid4().hex}_{filename}"

    course_data = extract_from_pdf(file_data)

    if not course_data:
        return jsonify({"error": "Failed to extract data from PDF"}), 400

    pdf_url = upload_to_gcs(file_data, unique_filename)
    course_data["filename"] = unique_filename
    course_data["pdf_url"] = pdf_url

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO courses (
                class_id, title, instructor, location, course_type, cost,
                learning_objectives, provided_materials, skills, description, filename, pdf_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """,
            (
                course_data.get("class_id"),
                course_data.get("title"),
                course_data.get("instructor"),
                course_data.get("location"),
                course_data.get("course_type"),
                course_data.get("cost"),
                course_data.get("learning_objectives"),
                course_data.get("provided_materials"),
                course_data.get("skills"),
                course_data.get("description"),
                course_data.get("filename"),
                course_data.get("pdf_url"),
            ),
        )
        course_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        return jsonify(
            {
                "id": course_id,
                "message": "Course created",
                "pdf_url": pdf_url,
                "data": course_data,
            }
        ), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400


@app.route("/api/courses", methods=["POST"])
def create_course():
    """Create a new course manually"""
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO courses (
                class_id, title, instructor, location, course_type, cost,
                learning_objectives, provided_materials, skills, description, filename
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """,
            (
                data.get("class_id"),
                data.get("title"),
                data.get("instructor"),
                data.get("location"),
                data.get("course_type"),
                data.get("cost"),
                data.get("learning_objectives"),
                data.get("provided_materials"),
                data.get("skills"),
                data.get("description"),
                f"{data.get('class_id', 'manual')}.pdf",
            ),
        )
        course_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        return jsonify({"id": course_id, "message": "Course created"}), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """Update an existing course"""
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE courses SET
                class_id = %s,
                title = %s,
                instructor = %s,
                location = %s,
                course_type = %s,
                cost = %s,
                learning_objectives = %s,
                provided_materials = %s,
                skills = %s,
                description = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """,
            (
                data.get("class_id"),
                data.get("title"),
                data.get("instructor"),
                data.get("location"),
                data.get("course_type"),
                data.get("cost"),
                data.get("learning_objectives"),
                data.get("provided_materials"),
                data.get("skills"),
                data.get("description"),
                course_id,
            ),
        )
        conn.commit()
        conn.close()

        return jsonify({"message": "Course updated"}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
