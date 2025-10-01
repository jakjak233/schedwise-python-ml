import numpy as np
import pandas as pd
import mysql.connector
import json
import logging
import sys
from datetime import time, datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import requests
import os

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

@dataclass(frozen=True)
class TimeSlot:
    start_time: time
    end_time: time
    
    def __hash__(self):
        return hash((self.start_time, self.end_time))
    
    def __eq__(self, other):
        if not isinstance(other, TimeSlot):
            return False
        return self.start_time == other.start_time and self.end_time == other.end_time

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
    total_units: Optional[int] = None
    total_equivalent_units: Optional[float] = None
    total_hours: Optional[str] = None
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

@dataclass
class Program:
    program_id: int
    program_code: str
    program_name: str

# Configuration constants (to avoid hardcoded magic numbers scattered in code)
DB_CONFIG_ENDPOINT = os.environ.get('SCHEDWISE_DB_CONFIG_URL', 'http://localhost/schedwiseAPI/config/database.php')
TIME_SLOT_START_HOUR = int(os.environ.get('SCHED_TIME_START_HOUR', 7))
TIME_SLOT_START_MINUTE = int(os.environ.get('SCHED_TIME_START_MINUTE', 30))
TIME_SLOT_END_HOUR = int(os.environ.get('SCHED_TIME_END_HOUR', 18))
TIME_SLOT_DURATION_MINUTES = int(os.environ.get('SCHED_SLOT_MINUTES', 90))
ONLINE_ROOM_FALLBACK_ID = int(os.environ.get('SCHED_ONLINE_ROOM_ID', -1))
ONLINE_ROOM_FALLBACK_NAME = os.environ.get('SCHED_ONLINE_ROOM_NAME', 'Online')
ONLINE_ROOM_FALLBACK_CAPACITY = int(os.environ.get('SCHED_ONLINE_ROOM_CAPACITY', 999))
ROOM_CAPACITY_WEIGHT = float(os.environ.get('SCHED_ROOM_CAP_WEIGHT', '0.1'))

# Global lunch break window (no classes allowed)
LUNCH_BREAK_START_HOUR = int(os.environ.get('SCHED_LUNCH_START_HOUR', 12))
LUNCH_BREAK_START_MINUTE = int(os.environ.get('SCHED_LUNCH_START_MINUTE', 0))
LUNCH_BREAK_END_HOUR = int(os.environ.get('SCHED_LUNCH_END_HOUR', 12))
LUNCH_BREAK_END_MINUTE = int(os.environ.get('SCHED_LUNCH_END_MINUTE', 30))

# Scoring and limits (avoid magic numbers)
SCORE_PROGRAM_MATCH = int(os.environ.get('SCHED_SCORE_PROGRAM_MATCH', 80))
SCORE_LOAD_BASE = int(os.environ.get('SCHED_SCORE_LOAD_BASE', 50))
SCORE_LOAD_STEP = int(os.environ.get('SCHED_SCORE_LOAD_STEP', 5))
SCORE_SLOTS_BASE = int(os.environ.get('SCHED_SCORE_SLOTS_BASE', 30))
SCORE_SLOTS_STEP = int(os.environ.get('SCHED_SCORE_SLOTS_STEP', 2))
ROOM_SCORE_PROGRAM_EXACT = int(os.environ.get('SCHED_ROOM_SCORE_PROGRAM_MATCH', 50))
ROOM_SCORE_PROGRAM_GENERAL = int(os.environ.get('SCHED_ROOM_SCORE_GENERAL', 25))
ROOM_SCORE_MINOR_LAB = int(os.environ.get('SCHED_ROOM_SCORE_MINOR_LAB', 30))
MAX_COURSES_PERMANENT = int(os.environ.get('SCHED_MAX_COURSES_PERMANENT', 10))
MAX_COURSES_NON_PERM = int(os.environ.get('SCHED_MAX_COURSES_NON_PERM', 5))


class ReinforcementLearningScheduler:
    """
    Simplified Reinforcement Learning-based scheduling system
    """
    
    def __init__(self):
        self.connection = None
        self.rooms = []
        self.faculty = []
        self.courses = []
        self.sections = []
        self.programs = []
        self.time_slots = []
        self.weekdays = ['M', 'T', 'W', 'TH', 'F']
        
        # Conflict tracking
        self.faculty_schedules = {}
        self.room_schedules = {}
        self.section_schedules = {}
        
        # Performance metrics
        self.conflict_count = 0
        self.successful_assignments = 0
        
        # Faculty course load tracking (number of courses assigned)
        self.faculty_course_count = {}
        
        # Program-level room usage distribution: program_id -> {room_id: count}
        self.program_room_usage = {}

        # Track assigned section-course pairs to avoid duplicates
        self.assigned_pairs = set()

        # Specialization backlog: number of remaining specialized opportunities per faculty
        self.faculty_spec_backlog = {}

    def get_database_config(self):
        """Get database configuration with fallback"""
        try:
            # Try to get config from PHP endpoint
            response = requests.get(DB_CONFIG_ENDPOINT, timeout=5)
            if response.status_code == 200:
                config = response.json()
                return {
                    'host': config.get('host', 'localhost'),
                    'user': config.get('user', 'root'),
                    'password': config.get('password', ''),
                    'database': config.get('database', 'schedwise')
                }
        except Exception as e:
            logging.warning(f"Could not fetch database config from PHP: {e}")
        
        # Fallback configuration
        return {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'schedwise'
        }

    def connect_database(self):
        """Connect to MySQL database with error handling"""
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
        """Load all necessary data from database with error handling"""
        try:
            if not self.connection:
                self.connect_database()

            cursor = self.connection.cursor(dictionary=True)

            # Load programs
            cursor.execute("SELECT program_id, program_code, program_name FROM Programs")
            programs_data = cursor.fetchall()
            self.programs = [Program(**row) for row in programs_data]

            # Load rooms
            cursor.execute("SELECT room_id, room_name, room_type, capacity, program_id FROM Rooms")
            rooms_data = cursor.fetchall()
            self.rooms = [Room(**row) for row in rooms_data]

            # Load faculty
            cursor.execute("SELECT faculty_id, faculty_name, employment_type, specialization, total_units, total_equivalent_units, total_hours, program_id FROM Faculty")
            faculty_data = cursor.fetchall()
            self.faculty = [Faculty(**row) for row in faculty_data]

            # Load courses
            cursor.execute("SELECT course_id, course_code, descriptive_title, units, course_type, year_level, semester, program_id FROM Courses")
            courses_data = cursor.fetchall()
            all_courses = [Course(**row) for row in courses_data]
            if semester:
                sem_norm = semester.strip().lower()
                self.courses = [c for c in all_courses if (c.semester or '').strip().lower() == sem_norm]
            else:
                self.courses = all_courses

            # Load sections
            cursor.execute("SELECT section_id, section_name, program_id, year_level FROM Sections")
            sections_data = cursor.fetchall()
            self.sections = [Section(**row) for row in sections_data]

            cursor.close()

            # Generate time slots
            self._generate_time_slots()
            
            # Initialize RL environment
            self._initialize_rl_environment()

            logging.info(f"Loaded: {len(self.rooms)} rooms, {len(self.faculty)} faculty, {len(self.courses)} courses, {len(self.sections)} sections, {len(self.programs)} programs")
            return True

        except Exception as e:
            logging.error(f"Error loading data: {e}")
            raise Exception(f"Failed to load data: {str(e)}")

    def _generate_time_slots(self):
        """Generate 1.5-hour (90-minute) time slots from 7:30 AM to 6:00 PM"""
        self.time_slots = []
        
        start_hour = TIME_SLOT_START_HOUR
        start_minute = TIME_SLOT_START_MINUTE
        
        current_hour = start_hour
        current_minute = start_minute
        
        while current_hour < TIME_SLOT_END_HOUR:
            start_time = time(current_hour, current_minute)
            
            end_hour = current_hour
            end_minute = current_minute + TIME_SLOT_DURATION_MINUTES
            
            while end_minute >= 60:
                end_hour += 1
                end_minute -= 60
            
            end_time = time(end_hour, end_minute)
            
            if end_hour >= TIME_SLOT_END_HOUR:
                break
            
            # Skip slots that overlap lunch break
            lunch_start = time(LUNCH_BREAK_START_HOUR, LUNCH_BREAK_START_MINUTE)
            lunch_end = time(LUNCH_BREAK_END_HOUR, LUNCH_BREAK_END_MINUTE)
            overlaps_lunch = not (end_time <= lunch_start or lunch_end <= start_time)
            if not overlaps_lunch:
                self.time_slots.append(TimeSlot(start_time, end_time))
            
            current_minute += TIME_SLOT_DURATION_MINUTES
            while current_minute >= 60:
                current_hour += 1
                current_minute -= 60

    def _initialize_rl_environment(self):
        """Initialize the reinforcement learning environment"""
        # Initialize conflict tracking
        for faculty in self.faculty:
            self.faculty_schedules[faculty.faculty_id] = {day: [] for day in self.weekdays}
            self.faculty_course_count[faculty.faculty_id] = 0
            self.faculty_spec_backlog[faculty.faculty_id] = 0
        
        for room in self.rooms:
            self.room_schedules[room.room_id] = {day: [] for day in self.weekdays}
        
        for section in self.sections:
            self.section_schedules[section.section_id] = {day: [] for day in self.weekdays}
        
        # Initialize per-program room usage counts
        self.program_room_usage = {}
        for program in self.programs:
            self.program_room_usage[program.program_id] = {}
            for room in self.rooms:
                room_type_lower = room.room_type.lower()
                if room_type_lower in ['online', 'field', 'tba']:
                    continue
                # Track only rooms available to this program (program-specific or general)
                if room.program_id is None or room.program_id == program.program_id:
                    self.program_room_usage[program.program_id][room.room_id] = 0
        
        # Reset assigned pairs
        self.assigned_pairs = set()

    def _check_conflicts(self, faculty_id, room_id, section_id, day, time_slot):
        """Check for conflicts in faculty, room, and section schedules"""
        # Check faculty conflict
        for existing_slot in self.faculty_schedules[faculty_id][day]:
            if self._time_slots_overlap(time_slot, existing_slot):
                return True
        
        # Check room conflict (only for physical rooms)
        room = next((r for r in self.rooms if r.room_id == room_id), None)
        if room and room.room_type.lower() != 'online':
            for existing_slot in self.room_schedules[room_id][day]:
                if self._time_slots_overlap(time_slot, existing_slot):
                    return True
        
        # Check section conflict
        for existing_slot in self.section_schedules[section_id][day]:
            if self._time_slots_overlap(time_slot, existing_slot):
                return True
        
        return False

    def _time_slots_overlap(self, slot1, slot2):
        """Check if two time slots overlap"""
        return not (slot1.end_time <= slot2.start_time or slot2.end_time <= slot1.start_time)

    def _add_to_schedule(self, faculty_id, room_id, section_id, day, time_slot):
        """Add time slot to conflict tracking schedules"""
        self.faculty_schedules[faculty_id][day].append(time_slot)
        self.room_schedules[room_id][day].append(time_slot)
        self.section_schedules[section_id][day].append(time_slot)

    def _get_faculty_course_limit(self, faculty):
        """Return maximum number of courses based on employment type."""
        emp = (faculty.employment_type or '').strip().lower()
        if emp in ['permanent', 'full-time', 'full time']:
            return MAX_COURSES_PERMANENT
        if emp in ['affiliate', 'affilate', 'part-time', 'part time']:
            return MAX_COURSES_NON_PERM
        return MAX_COURSES_NON_PERM

    def _has_faculty_capacity(self, faculty):
        limit = self._get_faculty_course_limit(faculty)
        return self.faculty_course_count.get(faculty.faculty_id, 0) < limit

    def _find_best_faculty_rl(self, course, section):
        """Select faculty honoring priority and capacity rules."""
        course_code_upper = (course.course_code or '').upper()
        def is_specialized(f: Faculty) -> bool:
            return bool(f.specialization) and course_code_upper in (f.specialization or '').upper()

        # Partition faculty by employment type and specialization
        permanents_spec = []
        permanents_other = []
        affiliates_spec = []
        affiliates_other = []
        parttime_spec = []
        parttime_other = []
        for faculty in self.faculty:
            if not self._has_faculty_capacity(faculty):
                continue
            emp_raw = (faculty.employment_type or '').strip().lower()
            emp = 'permanent' if emp_raw in ['permanent', 'full-time', 'full time'] else ('affiliate' if emp_raw in ['affiliate', 'affilate'] else 'part-time')
            spec_match = is_specialized(faculty)
            if emp == 'permanent':
                (permanents_spec if spec_match else permanents_other).append(faculty)
            elif emp == 'affiliate':
                (affiliates_spec if spec_match else affiliates_other).append(faculty)
            else:
                (parttime_spec if spec_match else parttime_other).append(faculty)

        # Build deterministic scoring within each bucket
        def score(faculty: Faculty) -> int:
            s = 0
            # Program match
            if faculty.program_id == section.program_id:
                s += SCORE_PROGRAM_MATCH
            # Load balancing (fewer courses and fewer total day slots)
            s += max(0, SCORE_LOAD_BASE - SCORE_LOAD_STEP * self.faculty_course_count.get(faculty.faculty_id, 0))
            slots_total = sum(len(slots) for slots in self.faculty_schedules[faculty.faculty_id].values())
            s += max(0, SCORE_SLOTS_BASE - SCORE_SLOTS_STEP * slots_total)
            return s

        def sort_bucket(bucket: list[Faculty]) -> list[Faculty]:
            return sorted(bucket, key=lambda f: (score(f), f.faculty_id), reverse=True)

        permanents_spec = sort_bucket(permanents_spec)
        permanents_other = sort_bucket(permanents_other)
        affiliates_spec = sort_bucket(affiliates_spec)
        affiliates_other = sort_bucket(affiliates_other)
        parttime_spec = sort_bucket(parttime_spec)
        parttime_other = sort_bucket(parttime_other)

        is_major = bool(course.course_type and course.course_type.lower() == 'major')

        if is_major:
            # Majors: permanents (spec first, then other), then part-time with specialization.
            # No affiliates and no non-specialized part-time for majors. Permanents must be specialized.
            for bucket in [permanents_spec, parttime_spec]:
                if not bucket:
                    continue
                # Enforce specialization-first per faculty: skip non-specialized if backlog > 0
                for f in bucket:
                    # Permanents must match specialization for majors
                    if (f.employment_type or '').strip().lower() in ['permanent', 'full-time', 'full time'] and not is_specialized(f):
                        continue
                    if not is_specialized(f) and self.faculty_spec_backlog.get(f.faculty_id, 0) > 0:
                        continue
                    return f
            return None
        else:
            # Minors: affiliates first (spec then other), then part-time (spec then other).
            # No permanents on minors.
            for bucket in [affiliates_spec, affiliates_other, parttime_spec, parttime_other]:
                if not bucket:
                    continue
                for f in bucket:
                    # Enforce specialization-first per faculty for minors as well
                    if not is_specialized(f) and self.faculty_spec_backlog.get(f.faculty_id, 0) > 0:
                        continue
                    return f
            return None

    def _find_best_room_rl(self, program_id, course_type):
        """Find best room using simple scoring"""
        best_room = None
        best_score = float('-inf')
        
        for room in self.rooms:
            if room.room_type.lower() in ['online', 'field', 'tba']:
                continue
            
            # Enforce program-specific rooms: if room is tied to a program, only allow that program
            if room.program_id is not None and room.program_id != program_id:
                continue
            
            # Calculate score
            score = 0
            
            # Program match
            if room.program_id == program_id:
                score += ROOM_SCORE_PROGRAM_EXACT
            elif room.program_id is None:
                score += ROOM_SCORE_PROGRAM_GENERAL
            
            # Course type match
            if course_type.lower() == 'minor' and room.room_type.lower() == 'laboratory':
                score += ROOM_SCORE_MINOR_LAB
            
            # Capacity
            score += room.capacity * ROOM_CAPACITY_WEIGHT
            
            if score > best_score:
                best_score = score
                best_room = room
        
        return best_room

    def _get_available_rooms_for_program(self, program_id, course_type):
        """Return rooms for the given program first, then general rooms; exclude online/field/tba."""
        program_rooms = []
        general_rooms = []
        for room in self.rooms:
            room_type_lower = room.room_type.lower()
            if room_type_lower in ['online', 'field', 'tba']:
                continue
            # If course is major, enforce laboratory rooms only
            if course_type and course_type.lower() == 'major' and room_type_lower != 'laboratory':
                continue
            # Only allow program-specific rooms to be used by that program
            if room.program_id is not None:
                if room.program_id == program_id:
                    program_rooms.append(room)
            else:
                general_rooms.append(room)
        # Prefer least-used rooms to distribute load, with deterministic tie-breakers
        usage_map = self.program_room_usage.get(program_id, {})
        if course_type and course_type.lower() == 'minor':
            program_rooms.sort(key=lambda r: (usage_map.get(r.room_id, 0), 0 if r.room_type.lower() == 'laboratory' else 1, -r.capacity, r.room_id))
            general_rooms.sort(key=lambda r: (usage_map.get(r.room_id, 0), 0 if r.room_type.lower() == 'laboratory' else 1, -r.capacity, r.room_id))
        else:
            # Major already constrained to labs; still distribute by usage
            program_rooms.sort(key=lambda r: (usage_map.get(r.room_id, 0), -r.capacity, r.room_id))
            general_rooms.sort(key=lambda r: (usage_map.get(r.room_id, 0), -r.capacity, r.room_id))
        return program_rooms + general_rooms

    def _assign_course_sessions_rl(self, course, section, faculty, room, weekly_schedules, schedules_list):
        """Assign course sessions using RL model"""
        # Prevent duplicate section-course assignment
        pair_key = (section.section_id, course.course_id)
        if pair_key in self.assigned_pairs:
            return False
        # Find online room
        online_room = next((r for r in self.rooms if r.room_type.lower() == 'online'), None)
        if not online_room:
            online_room = Room(room_id=ONLINE_ROOM_FALLBACK_ID, room_name=ONLINE_ROOM_FALLBACK_NAME, room_type='Online', 
                             capacity=ONLINE_ROOM_FALLBACK_CAPACITY, program_id=section.program_id)
        
        # Assign face-to-face session by trying available rooms for the section's program
        f2f_success = False
        f2f_day_assigned = None
        candidate_rooms = self._get_available_rooms_for_program(section.program_id, course.course_type)
        for candidate_room in candidate_rooms:
            success, assigned_day = self._assign_session_rl(course, section, faculty, candidate_room, 'Face-to-face', weekly_schedules, schedules_list)
            if success:
                # Increment program-room usage for distribution
                try:
                    if section.program_id in self.program_room_usage and candidate_room.room_id in self.program_room_usage[section.program_id]:
                        self.program_room_usage[section.program_id][candidate_room.room_id] += 1
                except Exception:
                    pass
                f2f_success = True
                f2f_day_assigned = assigned_day
                break
        
        # Assign online session
        forbidden_days = set([f2f_day_assigned]) if f2f_day_assigned else set()
        online_success, _ = self._assign_session_rl(course, section, faculty, online_room, 
                                               'Online', weekly_schedules, schedules_list, forbidden_days=forbidden_days)
        
        # If both sessions success, count course for faculty
        if f2f_success and online_success:
            self.faculty_course_count[faculty.faculty_id] = self.faculty_course_count.get(faculty.faculty_id, 0) + 1
            self.assigned_pairs.add(pair_key)
            # Decrement specialization backlog if this was a specialized assignment
            try:
                if course.course_code.upper() in (faculty.specialization or '').upper():
                    if self.faculty_spec_backlog.get(faculty.faculty_id, 0) > 0:
                        self.faculty_spec_backlog[faculty.faculty_id] -= 1
            except Exception:
                pass
            return True
        return False

    def _assign_session_rl(self, course, section, faculty, room, delivery_mode, weekly_schedules, schedules_list, forbidden_days=None):
        """Assign a single session using RL model"""
        # Compute a deterministic day rotation seed to distribute across Monday–Friday
        # Differentiate online vs F2F by offset so they prefer different starting days
        mode_offset = 0 if delivery_mode == 'Face-to-face' else 3
        start_index = (section.section_id + course.course_id + mode_offset) % len(self.weekdays)

        # Find available time slot (respecting forbidden days when provided) starting from rotated day
        day, time_slot = self._find_available_time_slot(
            faculty.faculty_id,
            room.room_id,
            section.section_id,
            forbidden_days=forbidden_days or set(),
            start_index=start_index
        )
        
        if day and time_slot:
            # Add to schedule
            self._add_to_schedule(faculty.faculty_id, room.room_id, section.section_id, day, time_slot)
            
            # Add to weekly schedule
            session_type = 'face_to_face' if delivery_mode == 'Face-to-face' else 'online'
            
            weekly_schedules[section.section_id]['weekly_schedule'][day][session_type].append({
                'course_code': course.course_code,
                'course_title': course.descriptive_title,
                'faculty_name': faculty.faculty_name,
                'room_name': room.room_name,
                'room_id': room.room_id,
                'time_start': time_slot.start_time.strftime('%H:%M'),
                'time_end': time_slot.end_time.strftime('%H:%M'),
                'delivery_mode': delivery_mode,
                'session_type': 'lab' if room.room_type.lower() == 'laboratory' else 'lecture',
                'course_type': course.course_type,
                'year_level': course.year_level
            })
            
            # Add to schedules list for frontend
            schedules_list.append({
                'course_code': course.course_code,
                'descriptive_title': course.descriptive_title,
                'section_name': section.section_name,
                'faculty_name': faculty.faculty_name,
                'room_name': room.room_name,
                'course_id': course.course_id,
                'section_id': section.section_id,
                'faculty_id': faculty.faculty_id,
                'room_id': room.room_id,
                'time_start': time_slot.start_time.strftime('%H:%M'),
                'time_end': time_slot.end_time.strftime('%H:%M'),
                'days': day,
                'equivalent_units': course.units,
                'delivery_mode': delivery_mode
            })
            
            return True, day
        
        return False, None

    def _create_weekly_schedule_structure(self):
        """Create the basic structure for weekly schedules"""
        weekly_schedules = {}
        
        for section in self.sections:
            weekly_schedules[section.section_id] = {
                'section_name': section.section_name,
                'year_level': section.year_level,
                'program_id': section.program_id,
                'weekly_schedule': {}
            }
            
            for day in self.weekdays:
                weekly_schedules[section.section_id]['weekly_schedule'][day] = {
                    'face_to_face': [],
                    'online': []
                }
        
        return weekly_schedules

    def generate_schedule(self, semester: Optional[str] = None):
        """Generate schedule using trained RL model"""
        logging.info("Generating schedule using RL model")
        
        # Reset environment
        self._reset_environment()
        
        weekly_schedules = self._create_weekly_schedule_structure()
        schedules_list = []  # This will contain the flat list of schedules for the frontend
        
        # Get all possible assignments
        assignments = []
        for section in self.sections:
            for course in self.courses:
                if (course.program_id == section.program_id and 
                    course.year_level == section.year_level):
                    assignments.append((section, course))
        
        # Sort assignments: prioritize major courses first, then by year level and program, then course_code for tie-breaker
        assignments.sort(key=lambda x: (0 if (x[1].course_type and x[1].course_type.lower() == 'major') else 1, x[1].year_level, x[0].program_id, x[1].course_code))

        # Compute specialization backlog per faculty (number of potential specialized assignments remaining)
        self.faculty_spec_backlog = {f.faculty_id: 0 for f in self.faculty}
        for faculty in self.faculty:
            spec = (faculty.specialization or '').upper()
            if not spec:
                continue
            emp_raw = (faculty.employment_type or '').strip().lower()
            emp = 'permanent' if emp_raw in ['permanent', 'full-time', 'full time'] else ('affiliate' if emp_raw in ['affiliate', 'affilate'] else 'part-time')
            for section, course in assignments:
                if (section.section_id, course.course_id) in self.assigned_pairs:
                    continue
                # Enforce course-type by employment when counting backlog
                is_major = bool(course.course_type and course.course_type.lower() == 'major')
                if emp == 'permanent' and not is_major:
                    continue
                if emp == 'affiliate' and is_major:
                    continue
                if emp == 'part-time' and is_major and course.course_code.upper() not in spec:
                    continue
                if course.course_code.upper() in spec and course.program_id == section.program_id and course.year_level == section.year_level:
                    self.faculty_spec_backlog[faculty.faculty_id] += 1

        successful_assignments = 0
        
        for section, course in assignments:
            # Skip if already assigned
            if (section.section_id, course.course_id) in self.assigned_pairs:
                continue
            # Find best faculty using RL
            best_faculty = self._find_best_faculty_rl(course, section)
            
            if not best_faculty:
                continue
            
            # Find best room using RL
            best_room = None  # not needed now (we iterate candidate rooms in _assign_course_sessions_rl)
            
            # Assign both sessions
            success = self._assign_course_sessions_rl(course, section, best_faculty, 
                                                   best_room, weekly_schedules, schedules_list)
            
            if success:
                successful_assignments += 1

        # Ensure all faculty get at least one course assignment
        unassigned_faculty = [f for f in self.faculty if self.faculty_course_count.get(f.faculty_id, 0) == 0]
        if unassigned_faculty:
            for faculty in unassigned_faculty:
                # Prefer courses matching specialization regardless of type, within capacity
                matching = []
                for section in self.sections:
                    for course in self.courses:
                        if (course.program_id == section.program_id and course.year_level == section.year_level):
                            if (section.section_id, course.course_id) in self.assigned_pairs:
                                continue
                            # Enforce course-type by employment:
                            emp_raw = (faculty.employment_type or '').strip().lower()
                            emp = 'permanent' if emp_raw in ['permanent', 'full-time', 'full time'] else ('affiliate' if emp_raw in ['affiliate', 'affilate'] else 'part-time')
                            is_major = bool(course.course_type and course.course_type.lower() == 'major')
                            if emp == 'permanent' and not is_major:
                                continue
                            if emp in ['affiliate'] and is_major:
                                continue
                            if emp == 'part-time' and is_major and not (faculty.specialization and course.course_code.upper() in (faculty.specialization or '').upper()):
                                continue
                            if faculty.specialization and course.course_code.upper() in (faculty.specialization or '').upper():
                                matching.append((section, course))
                pool = matching if matching else assignments
                for section, course in pool:
                    if (section.section_id, course.course_id) in self.assigned_pairs:
                        continue
                    # Enforce course-type by employment in assignment too
                    emp_raw = (faculty.employment_type or '').strip().lower()
                    emp = 'permanent' if emp_raw in ['permanent', 'full-time', 'full time'] else ('affiliate' if emp_raw in ['affiliate', 'affilate'] else 'part-time')
                    is_major = bool(course.course_type and course.course_type.lower() == 'major')
                    if emp == 'permanent' and not is_major:
                        continue
                    if emp in ['affiliate'] and is_major:
                        continue
                    if emp == 'part-time' and is_major and not (faculty.specialization and course.course_code.upper() in (faculty.specialization or '').upper()):
                        continue
                    if not self._has_faculty_capacity(faculty):
                        break
                    if self._assign_course_sessions_rl(course, section, faculty, None, weekly_schedules, schedules_list):
                        break

        # Post-pass: fill specialized affiliate/part-time faculty up to their max with matching courses
        affiliates_specialized = [f for f in self.faculty if (f.employment_type or '').strip().lower() in ['affiliate', 'affilate', 'part-time', 'part time'] and f.specialization]
        # Deterministic order by faculty_id
        affiliates_specialized.sort(key=lambda f: f.faculty_id)
        for faculty in affiliates_specialized:
            while self._has_faculty_capacity(faculty):
                found = False
                # Iterate deterministically over sections and courses
                for section in sorted(self.sections, key=lambda s: (s.program_id, s.year_level, s.section_id)):
                    for course in sorted(self.courses, key=lambda c: (c.year_level, c.program_id or 0, c.course_code)):
                        if (course.program_id == section.program_id and course.year_level == section.year_level):
                            if (section.section_id, course.course_id) in self.assigned_pairs:
                                continue
                            if course.course_code.upper() in (faculty.specialization or '').upper():
                                # Enforce the same majors/minors rule here as well
                                emp_raw = (faculty.employment_type or '').strip().lower()
                                is_major = bool(course.course_type and course.course_type.lower() == 'major')
                                if emp_raw in ['affiliate', 'affilate'] and is_major:
                                    continue
                                # Assign respecting existing constraints
                                if self._assign_course_sessions_rl(course, section, faculty, None, weekly_schedules, schedules_list):
                                    found = True
                                    break
                    if found:
                        break
                if not found:
                    break
        
        logging.info(f"Successfully assigned {successful_assignments} courses")
        
        # Return both formats for compatibility
        return {
            'weekly_schedules': weekly_schedules,
            'schedules': schedules_list  # This is what the frontend expects
        }

    def _reset_environment(self):
        """Reset the environment for a new episode"""
        self.conflict_count = 0
        self.successful_assignments = 0
        
        # Clear schedules
        for faculty_id in self.faculty_schedules:
            for day in self.weekdays:
                self.faculty_schedules[faculty_id][day] = []
            self.faculty_course_count[faculty_id] = 0
        
        for room_id in self.room_schedules:
            for day in self.weekdays:
                self.room_schedules[room_id][day] = []
        
        for section_id in self.section_schedules:
            for day in self.weekdays:
                self.section_schedules[section_id][day] = []
        
        # Reset program room usage counters
        for program_id in self.program_room_usage:
            for room_id in self.program_room_usage[program_id].keys():
                self.program_room_usage[program_id][room_id] = 0
        
        # Reset assigned pairs
        self.assigned_pairs = set()
        
        # Reset specialization backlog
        for faculty in self.faculty:
            self.faculty_spec_backlog[faculty.faculty_id] = 0

    def save_schedules_to_database(self, schedule_data):
        """Save generated schedules to the database"""
        try:
            if not self.connection:
                self.connect_database()

            cursor = self.connection.cursor()

            # Clear existing schedules
            cursor.execute("DELETE FROM ClassSchedules")

            # Insert new schedules
            saved_count = 0
            schedules_list = schedule_data.get('schedules', [])
            
            for schedule in schedules_list:
                # Insert schedule into database
                insert_sql = """
                    INSERT INTO ClassSchedules
                    (faculty_id, course_id, section_id, room_id, time_start, time_end, days, delivery_mode, equivalent_units)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                cursor.execute(insert_sql, (
                    schedule['faculty_id'],
                    schedule['course_id'],
                    schedule['section_id'],
                    schedule['room_id'],
                    schedule['time_start'],
                    schedule['time_end'],
                    schedule['days'],
                    schedule['delivery_mode'],
                    schedule['equivalent_units']
                ))
                saved_count += 1

            # Commit the transaction
            self.connection.commit()
            cursor.close()

            return saved_count

        except Exception as e:
            logging.error(f"Error saving schedules to database: {e}")
            if self.connection:
                self.connection.rollback()
            raise Exception(f"Failed to save schedules: {str(e)}")

    def format_weekly_schedule_display(self, schedule_data):
        """Format weekly schedules for display"""
        weekly_schedules = schedule_data.get('weekly_schedules', {})
        schedules_list = schedule_data.get('schedules', [])
        
        formatted_schedules = {}
        
        for section_id, section_data in weekly_schedules.items():
            formatted_schedules[section_id] = {
                'section_name': section_data['section_name'],
                'year_level': section_data['year_level'],
                'program_id': section_data['program_id'],
                'weekly_schedule': {}
            }
            
            for day, day_schedules in section_data['weekly_schedule'].items():
                formatted_schedules[section_id]['weekly_schedule'][day] = {
                    'face_to_face': day_schedules['face_to_face'],
                    'online': day_schedules['online']
                }
        
        return {
            'weekly_schedules': formatted_schedules,
            'schedules': schedules_list  # Include the flat list for frontend compatibility
        }

    def _find_available_time_slot(self, faculty_id, room_id, section_id, forbidden_days=None, start_index=0):
        """Find available time slot (conflict-free), iterating days in a rotated order to spread load."""
        forbidden_days = set(forbidden_days or set())
        # Rotate weekdays to start from start_index
        rotated_days = self.weekdays[start_index:] + self.weekdays[:start_index]
        for day in rotated_days:
            if day in forbidden_days:
                continue
            for time_slot in self.time_slots:
                if not self._check_conflicts(faculty_id, room_id, section_id, day, time_slot):
                    return day, time_slot
        return None, None