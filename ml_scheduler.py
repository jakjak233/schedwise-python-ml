import numpy as np
import mysql.connector
import logging
import sys
from datetime import time, datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import gc

# Configure for memory efficiency
np.set_printoptions(precision=3, suppress=True)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

@dataclass
class Room:
    room_id: int
    room_name: str
    room_type: str
    capacity: int
    program_id: Optional[int] = None

@dataclass
class Faculty:
    faculty_id: int
    faculty_name: str
    employment_type: str
    specialization: Optional[str] = None
    program_id: Optional[int] = None

@dataclass
class Course:
    course_id: int
    course_code: str
    descriptive_title: str
    units: int
    course_type: str = 'Major'
    year_level: int = 1
    semester: str = '1st Sem'
    program_id: Optional[int] = None

@dataclass
class Section:
    section_id: int
    section_name: str
    program_id: int
    year_level: int

class ReinforcementLearningScheduler:
    def __init__(self):
        self.connection = None
        self.rooms = []
        self.faculty = []
        self.courses = []
        self.sections = []
        self.weekdays = ['M', 'T', 'W', 'TH', 'F']
        
    def get_database_config(self):
        return {
            'host': '23.111.150.178',
            'user': 'uipbsit3_jimvoy',
            'password': 'x3mpassword', 
            'database': 'uipbsit3_schedwise'
        }

    def connect_database(self):
        try:
            config = self.get_database_config()
            self.connection = mysql.connector.connect(
                host=config['host'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                autocommit=True
            )
            logging.info("Database connection established")
            return True
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            raise Exception(f"Database connection failed: {str(e)}")

    def load_data(self, semester: Optional[str] = None):
        """Load ULTRA MINIMAL data for testing"""
        try:
            if not self.connection:
                self.connect_database()

            cursor = self.connection.cursor(dictionary=True)

            # Load ULTRA MINIMAL data - only 1 of each for testing
            logging.info("Loading ULTRA MINIMAL data for testing...")
            
            # Load only 1 program
            cursor.execute("SELECT program_id, program_code, program_name FROM Programs LIMIT 1")
            programs_data = cursor.fetchall()
            self.programs = programs_data
            program_id = programs_data[0]['program_id'] if programs_data else None

            # Load only 2 rooms
            cursor.execute("SELECT room_id, room_name, room_type, capacity, program_id FROM Rooms LIMIT 2")
            self.rooms = [Room(**row) for row in cursor.fetchall()]

            # Load only 3 faculty
            cursor.execute("SELECT faculty_id, faculty_name, employment_type, specialization, program_id FROM Faculty LIMIT 3")
            self.faculty = [Faculty(**row) for row in cursor.fetchall()]

            # Load only 3 courses
            cursor.execute("SELECT course_id, course_code, descriptive_title, units, course_type, year_level, semester, program_id FROM Courses LIMIT 3")
            all_courses = [Course(**row) for row in cursor.fetchall()]
            if semester:
                sem_norm = semester.strip().lower()
                self.courses = [c for c in all_courses if (c.semester or '').strip().lower() == sem_norm]
            else:
                self.courses = all_courses

            # Load only 1 section
            cursor.execute("SELECT section_id, section_name, program_id, year_level FROM Sections LIMIT 1")
            self.sections = [Section(**row) for row in cursor.fetchall()]

            cursor.close()

            logging.info(f"ULTRA MINIMAL DATA: {len(self.rooms)} rooms, {len(self.faculty)} faculty, {len(self.courses)} courses, {len(self.sections)} sections")
            return True

        except Exception as e:
            logging.error(f"Error loading data: {e}")
            raise Exception(f"Failed to load data: {str(e)}")

    def generate_schedule(self, semester: Optional[str] = None):
        """Generate simple demo schedule"""
        logging.info("Generating DEMO schedule with minimal data...")
        
        # Create simple demo schedules
        schedules_list = []
        weekly_schedules = {}
        
        for section in self.sections:
            weekly_schedules[section.section_id] = {
                'section_name': section.section_name,
                'weekly_schedule': {}
            }
            
            for day in self.weekdays[:2]:  # Only Monday & Tuesday for demo
                weekly_schedules[section.section_id]['weekly_schedule'][day] = {
                    'face_to_face': [],
                    'online': []
                }
                
                # Add 1-2 demo classes per day
                for i, course in enumerate(self.courses[:2]):
                    if i == 0:  # First course - face to face
                        faculty = self.faculty[0] if self.faculty else None
                        room = self.rooms[0] if self.rooms else None
                        
                        class_info = {
                            'course_code': course.course_code,
                            'course_title': course.descriptive_title,
                            'faculty_name': faculty.faculty_name if faculty else 'TBA',
                            'room_name': room.room_name if room else 'Online',
                            'time_start': '08:00',
                            'time_end': '09:30',
                            'delivery_mode': 'Face-to-face'
                        }
                        
                        weekly_schedules[section.section_id]['weekly_schedule'][day]['face_to_face'].append(class_info)
                        
                        schedules_list.append({
                            'course_code': course.course_code,
                            'descriptive_title': course.descriptive_title,
                            'section_name': section.section_name,
                            'faculty_name': faculty.faculty_name if faculty else 'TBA',
                            'room_name': room.room_name if room else 'Online',
                            'time_start': '08:00',
                            'time_end': '09:30',
                            'days': day,
                            'delivery_mode': 'Face-to-face'
                        })
                    
                    else:  # Second course - online
                        class_info = {
                            'course_code': course.course_code,
                            'course_title': course.descriptive_title,
                            'faculty_name': self.faculty[1].faculty_name if len(self.faculty) > 1 else 'TBA',
                            'room_name': 'Online',
                            'time_start': '10:00',
                            'time_end': '11:30',
                            'delivery_mode': 'Online'
                        }
                        
                        weekly_schedules[section.section_id]['weekly_schedule'][day]['online'].append(class_info)
                        
                        schedules_list.append({
                            'course_code': course.course_code,
                            'descriptive_title': course.descriptive_title,
                            'section_name': section.section_name,
                            'faculty_name': self.faculty[1].faculty_name if len(self.faculty) > 1 else 'TBA',
                            'room_name': 'Online',
                            'time_start': '10:00',
                            'time_end': '11:30',
                            'days': day,
                            'delivery_mode': 'Online'
                        })

        logging.info(f"DEMO SCHEDULE GENERATED: {len(schedules_list)} class sessions")
        
        return {
            'weekly_schedules': weekly_schedules,
            'schedules': schedules_list
        }

    def format_weekly_schedule_display(self, schedule_data):
        """Format for frontend display"""
        return schedule_data

    def save_schedules_to_database(self, schedule_data):
        """Demo version - just log instead of saving"""
        logging.info("DEMO: Would save schedules to database")
        return len(schedule_data.get('schedules', []))
