#!/usr/bin/env python3
"""
School of Dandori - Course Data Ingestion Pipeline
Extracts course information from PDFs and loads into SQLite database
"""

import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import PyPDF2


class CourseExtractor:
    """Extracts course data from PDF files"""
    
    def extract_from_pdf(self, pdf_path: str) -> Optional[Dict]:
        """Extract course information from a single PDF"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                
                return self._parse_course_data(text, pdf_path)
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            return None
    
    def _parse_course_data(self, text: str, pdf_path: str) -> Dict:
        """Parse extracted text into structured course data"""
        # Extract title (first line)
        title_match = re.search(r'^(.+?)(?:\n|Instructor:)', text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Unknown"
        
        # Extract instructor
        instructor_match = re.search(r'Instructor:\s*(.+?)(?:\n|Location:)', text)
        instructor = instructor_match.group(1).strip() if instructor_match else None
        
        # Extract location
        location_match = re.search(r'Location:\s*(.+?)(?:\n|Course Type:)', text)
        location = location_match.group(1).strip() if location_match else None
        
        # Extract course type
        course_type_match = re.search(r'Course Type:\s*(.+?)(?:\n|Cost:)', text)
        course_type = course_type_match.group(1).strip() if course_type_match else None
        
        # Extract cost
        cost_match = re.search(r'Cost:\s*(.+?)(?:\n|Learning)', text)
        cost = cost_match.group(1).strip() if cost_match else None
        
        # Extract class ID (from bottom of PDF)
        class_id_match = re.search(r'Class ID:\s*(CLASS_\d+)', text)
        class_id = class_id_match.group(1) if class_id_match else None
        
        # Extract learning objectives
        objectives_match = re.search(r'Learning Objectives(.+?)Provided Materials', text, re.DOTALL)
        learning_objectives = objectives_match.group(1).strip() if objectives_match else None
        
        # Extract provided materials
        materials_match = re.search(r'Provided Materials(.+?)Skills Developed', text, re.DOTALL)
        provided_materials = materials_match.group(1).strip() if materials_match else None
        
        # Extract skills
        skills_match = re.search(r'Skills Developed(.+?)Course Description', text, re.DOTALL)
        skills = skills_match.group(1).strip() if skills_match else None
        
        # Extract course description
        description_match = re.search(r'Course Description(.+?)Class ID:', text, re.DOTALL)
        description = description_match.group(1).strip() if description_match else None
        
        return {
            'class_id': class_id,
            'title': title,
            'instructor': instructor,
            'location': location,
            'course_type': course_type,
            'cost': cost,
            'learning_objectives': learning_objectives,
            'provided_materials': provided_materials,
            'skills': skills,
            'description': description,
            'filename': Path(pdf_path).name
        }


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: str = "courses.db"):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def initialize_schema(self):
        """Create database tables"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT UNIQUE,
                title TEXT NOT NULL,
                instructor TEXT,
                location TEXT,
                course_type TEXT,
                cost TEXT,
                learning_objectives TEXT,
                provided_materials TEXT,
                skills TEXT,
                description TEXT,
                filename TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_class_id ON courses(class_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_title ON courses(title)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_location ON courses(location)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_course_type ON courses(course_type)
        """)
        self.conn.commit()
    
    def insert_course(self, course_data: Dict) -> bool:
        """Insert or update course data"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO courses (
                    class_id, title, instructor, location, course_type, cost,
                    learning_objectives, provided_materials, skills, description, filename
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    class_id = excluded.class_id,
                    title = excluded.title,
                    instructor = excluded.instructor,
                    location = excluded.location,
                    course_type = excluded.course_type,
                    cost = excluded.cost,
                    learning_objectives = excluded.learning_objectives,
                    provided_materials = excluded.provided_materials,
                    skills = excluded.skills,
                    description = excluded.description,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                course_data['class_id'],
                course_data['title'],
                course_data['instructor'],
                course_data['location'],
                course_data['course_type'],
                course_data['cost'],
                course_data['learning_objectives'],
                course_data['provided_materials'],
                course_data['skills'],
                course_data['description'],
                course_data['filename']
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting course: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class Pipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self, pdf_directory: str = ".", db_path: str = "courses.db"):
        self.pdf_directory = pdf_directory
        self.extractor = CourseExtractor()
        self.db = DatabaseManager(db_path)
    
    def run(self):
        """Execute the full pipeline"""
        print("Starting School of Dandori data ingestion pipeline...")
        
        # Initialize database
        self.db.connect()
        self.db.initialize_schema()
        print("✓ Database initialized")
        
        # Find all PDF files
        pdf_files = list(Path(self.pdf_directory).glob("class_*.pdf"))
        print(f"✓ Found {len(pdf_files)} course PDFs")
        
        # Process each PDF
        success_count = 0
        for pdf_path in pdf_files:
            print(f"Processing: {pdf_path.name}")
            course_data = self.extractor.extract_from_pdf(str(pdf_path))
            
            if course_data and self.db.insert_course(course_data):
                success_count += 1
        
        self.db.close()
        print(f"\n✓ Pipeline complete: {success_count}/{len(pdf_files)} courses ingested")


if __name__ == "__main__":
    pipeline = Pipeline()
    pipeline.run()
