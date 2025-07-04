import os
import face_recognition
import pandas as pd
import numpy as np
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from cryptography.fernet import Fernet
import json
import logging
from attendance import create_attendance_file_if_not_exists, load_known_faces, recognize_and_mark_attendance

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong, randomly generated key
attendance_dir = "attendance_records"  # Directory for attendance files
known_faces_dir = "known_faces"  # Directory for storing student data

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use Gmail's SMTP server
app.config['MAIL_PORT'] = 587  # TLS port
app.config['MAIL_USE_TLS'] = True  # Enable TLS
app.config['MAIL_USERNAME'] = 'kaustubh998711@gmail.com'  # Replace with your actual Gmail address
app.config['MAIL_PASSWORD'] = 'soqk ziga tdfu zoup'  # Replace with your actual app password
mail = Mail(app)

# Ensure directories exist
if not os.path.exists(attendance_dir):
    os.makedirs(attendance_dir)
if not os.path.exists(known_faces_dir):
    os.makedirs(known_faces_dir)

# Load or generate encryption key
def load_or_generate_key():
    key_file = "encryption_key.key"
    if os.path.exists(key_file):
        with open(key_file, "rb") as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, "wb") as key_file:
            key_file.write(key)
        return key

# Encrypt password
def encrypt_password(password, key):
    fernet = Fernet(key)
    return fernet.encrypt(password.encode()).decode()

# Decrypt password
def decrypt_password(encrypted_password, key):
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_password.encode()).decode()

# Save user data securely
def save_user_data(username, email, encrypted_password):
    user_data_file = "users.json"
    if os.path.exists(user_data_file):
        with open(user_data_file, "r") as file:
            user_data = json.load(file)
    else:
        user_data = {}

    user_data[username] = {"email": email, "password": encrypted_password}

    with open(user_data_file, "w") as file:
        json.dump(user_data, file)

# Load user data
def load_user_data():
    user_data_file = "users.json"
    if os.path.exists(user_data_file):
        with open(user_data_file, "r") as file:
            return json.load(file)
    return {}

# Load or initialize student data
def load_student_data():
    student_data_file = os.path.join(known_faces_dir, "students.json")
    if os.path.exists(student_data_file):
        with open(student_data_file, "r") as file:
            return json.load(file)
    return {}

def save_student_data(student_data):
    student_data_file = os.path.join(known_faces_dir, "students.json")
    with open(student_data_file, "w") as file:
        json.dump(student_data, file)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if not username or not email or not password:
            flash("Please enter all fields.")
            return redirect(url_for('signup'))

        # Check if username already exists
        users = load_user_data()
        if username in users:
            flash("Username already exists. Please choose a different one.")
            return redirect(url_for('signup'))

        key = load_or_generate_key()
        encrypted_password = encrypt_password(password, key)
        save_user_data(username, email, encrypted_password)
        flash("Signup successful!")
        return redirect(url_for('index'))

    return render_template('signup.html')

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Load users and credentials from users.json
        users = load_user_data()

        if username in users:
            key = load_or_generate_key()
            stored_password = users[username]['password']

            # Decrypt the stored password and compare
            if password == decrypt_password(stored_password, key):
                session['username'] = username  # Save login state using session
                flash("Login successful!")
                return redirect(url_for('teacher_dashboard'))  # Redirect to dashboard page
            else:
                flash("Invalid password.")
        else:
            flash("Invalid username.")
        return redirect(url_for('teacher_login'))  # Stay on login page

    return render_template('teacher_login.html')

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'username' not in session:
        flash("Please log in first.")
        return redirect(url_for('teacher_login'))

    return render_template('teacher_dashboard.html')

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_id = request.form['student_id']
        student_email = request.form['student_email']
        student_photo = request.files['student_photo']

        # Save the photo
        if student_photo:
            photo_path = os.path.join(known_faces_dir, f"{student_id}.jpg")
            student_photo.save(photo_path)

        # Load existing student data
        student_data = load_student_data()

        # Store student information in JSON
        student_data[student_id] = {
            "name": student_name,
            "email": student_email,
            "photo": f"{student_id}.jpg"
        }
        save_student_data(student_data)

        flash("Student registered successfully!")
        return redirect(url_for('student_register'))  # Redirect to the registration page

    return render_template('student_register.html')

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if 'username' not in session:
        flash("Please log in first.")
        return redirect(url_for('teacher_login'))

    subjects = ['Maths', 'Data Structure', 'Computer Graphics', 'DBMS', 'Computer Network']  # List of subjects

    if request.method == 'POST':
        subject = request.form['subject']
        group_photo = request.files['photo']  # Get the uploaded photo

        # Ensure attendance directory exists
        if not os.path.exists(attendance_dir):
            os.makedirs(attendance_dir)

        group_photo_path = os.path.join(attendance_dir, group_photo.filename)  # Save path
        group_photo.save(group_photo_path)  # Save the uploaded photo

        # Load known faces
        known_face_encodings, known_face_ids, known_face_names = load_known_faces(known_faces_dir)

        # Create attendance file if it doesn't exist
        create_attendance_file_if_not_exists(subject, attendance_dir)

        # Recognize faces and mark attendance
        recognize_and_mark_attendance(subject, group_photo_path, known_face_encodings, known_face_ids, known_face_names, attendance_dir)

        flash("Attendance processed successfully!")
        return redirect(url_for('attendance'))

    return render_template('attendance.html', subjects=subjects)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        users = load_user_data()

        # Check for the username by email
        username = next((u for u, data in users.items() if data['email'] == email), None)

        if username:
            token = secrets.token_urlsafe()  # Generate a secure token
            reset_url = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset Request',
                          sender='your_email@gmail.com',  # Replace with your actual Gmail address
                          recipients=[email])
            msg.body = f'Please click the link to reset your password: {reset_url}'
            mail.send(msg)

            flash('A password reset link has been sent to your email.', 'success')
        else:
            flash('Email not found.', 'error')

        return redirect(url_for('teacher_login'))

    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        username = request.form.get('username')  # Use get to avoid KeyError
        new_password = request.form.get('new_password')

        if not username or not new_password:
            flash("Please enter both username and new password.", "error")
            return redirect(url_for('reset_password', token=token))

        # Load users and update password logic
        users = load_user_data()
        if username in users:
            key = load_or_generate_key()
            encrypted_password = encrypt_password(new_password, key)
            users[username]['password'] = encrypted_password

            # Save the updated user data
            with open("users.json", "w") as file:
                json.dump(users, file)

            flash("Your password has been reset successfully.")
            return redirect(url_for('teacher_login'))
        else:
            flash("User not found.")

    return render_template('reset_password.html', token=token)

if __name__ == '__main__':
    app.run(debug=True)
