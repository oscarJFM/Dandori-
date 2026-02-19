-- Supabase SQL Setup for School of Dandori
-- Run this in the Supabase SQL Editor

CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    class_id TEXT,
    title TEXT,
    instructor TEXT,
    location TEXT,
    course_type TEXT,
    cost TEXT,
    skills TEXT,
    learning_objectives TEXT,
    provided_materials TEXT,
    description TEXT,
    filename TEXT,
    pdf_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add pdf_url column if table already exists
-- ALTER TABLE courses ADD COLUMN pdf_url TEXT;

-- Enable Row Level Security (optional, adjust as needed)
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;

-- Create a policy to allow public read access (adjust as needed)
CREATE POLICY "Allow public read" ON courses
    FOR SELECT USING (true);

-- Create policy for inserts (adjust for your use case)
CREATE POLICY "Allow insert" ON courses
    FOR INSERT WITH CHECK (true);

-- Create policy for updates (adjust for your use case)
CREATE POLICY "Allow update" ON courses
    FOR UPDATE USING (true);
