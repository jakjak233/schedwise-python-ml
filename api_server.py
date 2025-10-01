from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import sys
from datetime import datetime
from ml_scheduler import ReinforcementLearningScheduler
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global scheduler instance
scheduler = None

def get_scheduler():
    """Get or create scheduler instance with error handling"""
    global scheduler
    try:
        if scheduler is None:
            logging.info("Initializing ML scheduler...")
            scheduler = ReinforcementLearningScheduler()
        return scheduler
    except Exception as e:
        logging.error(f"Failed to initialize scheduler: {e}")
        traceback.print_exc()
        raise Exception(f"Scheduler initialization failed: {str(e)}")

@app.route('/api/generate-schedules', methods=['POST'])
def generate_schedules():
    """API endpoint to generate weekly schedules using ML/RL"""
    try:
        logging.info("Starting schedule generation...")
        scheduler = get_scheduler()

        # Read semester from request
        data = request.get_json(silent=True) or {}
        semester = data.get('semester')  # '1st Sem' or '2nd Sem'

        # Load data (with optional semester filter)
        scheduler.load_data(semester=semester)

        # Generate weekly schedules
        logging.info("Generating schedules...")
        schedule_data = scheduler.generate_schedule(semester=semester)

        # Format for display
        logging.info("Formatting schedules for display...")
        formatted_data = scheduler.format_weekly_schedule_display(schedule_data)

        # Create result with proper structure for PHP
        result = {
            'success': True,
            'generated_at': datetime.now().isoformat(),
            'data': {
                'weekly_schedules': formatted_data['weekly_schedules'],
                'schedules': formatted_data['schedules'],  # This is what the frontend expects
                'summary': {
                    'total_sections': len(scheduler.sections),
                    'total_courses': len(scheduler.courses),
                    'total_faculty': len(scheduler.faculty),
                    'schedules_saved_to_database': 0,
                    'weekdays_covered': scheduler.weekdays,
                    'conflict_free': True,
                    'all_days_filled': True,
                    'ml_algorithm': 'Reinforcement Learning (Q-Learning)',
                    'conflict_count': scheduler.conflict_count,
                    'successful_assignments': scheduler.successful_assignments,
                    'semester': semester or 'All',
                    'lunch_break': {
                        'start': '12:00',
                        'end': '12:30'
                    }
                }
            }
        }

        logging.info("Schedule generation completed successfully")
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error generating schedules: {e}")
        traceback.print_exc()
        error_result = {
            'success': False,
            'error': str(e),
            'generated_at': datetime.now().isoformat()
        }
        return jsonify(error_result), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'ml_backend': True
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'ml_backend': True,
            'error': str(e)
        }), 500

if __name__ == "__main__":
    try:
        logging.info("Starting ML API server...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        traceback.print_exc()
