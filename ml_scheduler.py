import mysql.connector
import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

class TestScheduler:
    def __init__(self):
        self.connection = None
        
    def get_database_config(self):
        return {
            'host': '23.111.150.178',
            'user': 'uipbsit3_jimvoy',
            'password': 'x3mpassword', 
            'database': 'uipbsit3_schedwise'
        }

    def connect_database(self):
        """Super simple database connection test"""
        try:
            config = self.get_database_config()
            logging.info("Testing database connection...")
            
            self.connection = mysql.connector.connect(
                host=config['host'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                autocommit=True
            )
            logging.info("✅ DATABASE CONNECTION SUCCESSFUL!")
            return True
        except Exception as e:
            logging.error(f"❌ Database connection failed: {e}")
            raise Exception(f"Database connection failed: {str(e)}")

    def load_data(self, semester=None):
        """Just test if we can query the database"""
        try:
            if not self.connection:
                self.connect_database()

            cursor = self.connection.cursor(dictionary=True)
            
            # Just count records - minimal memory usage
            cursor.execute("SELECT COUNT(*) as count FROM Programs")
            programs_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM Rooms") 
            rooms_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM Faculty")
            faculty_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM Courses")
            courses_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM Sections")
            sections_count = cursor.fetchone()['count']
            
            cursor.close()
            
            logging.info(f"✅ DATA COUNTS: {programs_count} programs, {rooms_count} rooms, {faculty_count} faculty, {courses_count} courses, {sections_count} sections")
            return True

        except Exception as e:
            logging.error(f"❌ Error loading data: {e}")
            raise Exception(f"Failed to load data: {str(e)}")

    def generate_schedule(self, semester=None):
        """Generate a static demo schedule - no ML, no memory usage"""
        logging.info("🔄 Generating STATIC demo schedule...")
        
        # Static demo data - zero memory usage
        demo_schedule = {
            'weekly_schedules': {
                'A': {
                    'section_name': 'Section A',
                    'weekly_schedule': {
                        'M': {
                            'face_to_face': [
                                {
                                    'course_code': 'MATH101',
                                    'course_title': 'Basic Mathematics',
                                    'faculty_name': 'Dr. Smith',
                                    'room_name': 'Room 101',
                                    'time_start': '08:00',
                                    'time_end': '09:30',
                                    'delivery_mode': 'Face-to-face'
                                }
                            ],
                            'online': []
                        },
                        'T': {
                            'face_to_face': [],
                            'online': [
                                {
                                    'course_code': 'SCI201', 
                                    'course_title': 'General Science',
                                    'faculty_name': 'Dr. Johnson',
                                    'room_name': 'Online',
                                    'time_start': '10:00',
                                    'time_end': '11:30',
                                    'delivery_mode': 'Online'
                                }
                            ]
                        }
                    }
                }
            },
            'schedules': [
                {
                    'course_code': 'MATH101',
                    'descriptive_title': 'Basic Mathematics', 
                    'section_name': 'Section A',
                    'faculty_name': 'Dr. Smith',
                    'room_name': 'Room 101',
                    'time_start': '08:00',
                    'time_end': '09:30',
                    'days': 'M',
                    'delivery_mode': 'Face-to-face'
                },
                {
                    'course_code': 'SCI201',
                    'descriptive_title': 'General Science',
                    'section_name': 'Section A', 
                    'faculty_name': 'Dr. Johnson',
                    'room_name': 'Online',
                    'time_start': '10:00',
                    'time_end': '11:30',
                    'days': 'T',
                    'delivery_mode': 'Online'
                }
            ]
        }
        
        logging.info("✅ STATIC SCHEDULE GENERATED SUCCESSFULLY!")
        return demo_schedule

    def format_weekly_schedule_display(self, schedule_data):
        return schedule_data
