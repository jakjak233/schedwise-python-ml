def generate_schedule(self, semester: Optional[str] = None):
    """Optimized version to use less memory"""
    logging.info("Generating schedule using optimized ML model...")
    
    # Reset environment with memory optimization
    self._reset_environment()
    
    # Process in smaller batches
    batch_size = 5
    successful_assignments = 0
    
    # Get assignments in smaller chunks
    assignments = []
    for section in self.sections:
        for course in self.courses:
            if (course.program_id == section.program_id and 
                course.year_level == section.year_level):
                assignments.append((section, course))
    
    # Process in batches to save memory
    for i in range(0, len(assignments), batch_size):
        batch = assignments[i:i + batch_size]
        logging.info(f"Processing batch {i//batch_size + 1}/{(len(assignments)+batch_size-1)//batch_size}")
        
        for section, course in batch:
            # Your existing assignment logic here, but simplified
            best_faculty = self._find_best_faculty_rl(course, section)
            if best_faculty:
                success = self._assign_course_sessions_rl(course, section, best_faculty, None, weekly_schedules, schedules_list)
                if success:
                    successful_assignments += 1
    
    logging.info(f"Successfully assigned {successful_assignments} courses")
    return {
        'weekly_schedules': weekly_schedules,
        'schedules': schedules_list
    }
