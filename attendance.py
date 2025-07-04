import os
import face_recognition
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_attendance_file_if_not_exists(subject, attendance_dir):
    current_date = datetime.now().strftime("%Y-%m-%d")
    attendance_file = os.path.join(attendance_dir, f"{subject}_attendance_{current_date}.csv")
    
    # Check if the attendance file exists
    if not os.path.exists(attendance_file):
        # Create an empty dataframe with the required columns
        attendance_df = pd.DataFrame(columns=['ID', 'Name', 'Date', 'Time', 'Status'])
        # Save the empty dataframe to the CSV file
        attendance_df.to_csv(attendance_file, index=False)
        logging.info(f"Created new attendance file: {attendance_file}")
    else:
        logging.info(f"Attendance file already exists: {attendance_file}")

def load_known_faces(known_faces_dir):
    known_face_encodings = []
    known_face_names = []
    known_face_ids = []

    # Load student data from JSON file
    student_data_file = os.path.join(known_faces_dir, "students.json")
    if os.path.exists(student_data_file):
        with open(student_data_file, "r") as file:
            student_data = json.load(file)

        for student_id, student_info in student_data.items():
            # Load the student's photo
            photo_path = os.path.join(known_faces_dir, student_info['photo'])
            if os.path.exists(photo_path):
                image = face_recognition.load_image_file(photo_path)
                encoding = face_recognition.face_encodings(image)[0]  # Get the face encoding
                known_face_encodings.append(encoding)
                known_face_names.append(student_info['name'])  # Assuming name is stored in student_info
                known_face_ids.append(student_id)  # Append student ID

    return known_face_encodings, known_face_ids, known_face_names

def recognize_and_mark_attendance(subject, group_photo_path, known_face_encodings, known_face_ids, known_face_names, attendance_dir, threshold=0.6):
    current_datetime = datetime.now()
    today_date = current_datetime.strftime("%Y-%m-%d")
    current_time = current_datetime.strftime("%H:%M:%S")

    attendance_file = os.path.join(attendance_dir, f"{subject}_attendance_{today_date}.csv")
    group_photo = face_recognition.load_image_file(group_photo_path)
    face_locations = face_recognition.face_locations(group_photo)
    face_encodings = face_recognition.face_encodings(group_photo, face_locations)

    recognized_ids = []
    recognized_names = []

    for face_encoding in face_encodings:
        # Compare the face encodings to known faces with a threshold
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances)  # Get index of best match
        best_face_distance = face_distances[best_match_index]

        if matches[best_match_index] and best_face_distance < threshold:
            name = known_face_names[best_match_index]
            student_id = known_face_ids[best_match_index]
            recognized_ids.append(student_id)
            recognized_names.append(name)

    # Load existing attendance or create new dataframe if the file is empty
    if os.path.exists(attendance_file):
        attendance_df = pd.read_csv(attendance_file)
    else:
        attendance_df = pd.DataFrame(columns=['ID', 'Name', 'Date', 'Time', 'Status'])

    # Get the list of all known students
    all_students = set(known_face_ids)
    # Get the list of recognized students (excluding "Unknown")
    recognized_students = set(recognized_ids)

    # Determine students who are absent
    absent_students = all_students - recognized_students

    # Mark attendance for recognized students
    for student_id in recognized_students:
        name = known_face_names[known_face_ids.index(student_id)]
        if student_id in attendance_df['ID'].values:
            # Update existing record to present
            attendance_df.loc[attendance_df['ID'] == student_id, 'Status'] = 'Present'
        else:
            new_row = pd.DataFrame([{'ID': student_id, 'Name': name, 'Date': today_date, 'Time': current_time, 'Status': 'Present'}])
            attendance_df = pd.concat([attendance_df, new_row], ignore_index=True)

    # Mark absence for unrecognized students
    for student_id in absent_students:
        if student_id not in attendance_df['ID'].values:
            name = known_face_names[known_face_ids.index(student_id)]
            new_row = pd.DataFrame([{'ID': student_id, 'Name': name, 'Date': today_date, 'Time': current_time, 'Status': 'Absent'}])
            attendance_df = pd.concat([attendance_df, new_row], ignore_index=True)

    # Save updated attendance back to the file
    attendance_df.to_csv(attendance_file, index=False)
    logging.info(f"Attendance has been updated for {subject}.")
