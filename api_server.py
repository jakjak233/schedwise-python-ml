from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import sys
from datetime import datetime
from ml_scheduler import ReinforcementLearningScheduler
import traceback

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
app = Flask(__name__)
CORS(app)

scheduler = None

def get_scheduler():
    global scheduler
    try:
        if scheduler is None:
            logging.info("Initializing ML scheduler...")
            scheduler = ReinforcementLearningScheduler()
        return scheduler
    except Exception as e:
        logging.error(f"Failed to initialize scheduler: {e}")
        raise Exception(f"Scheduler initialization failed: {str(e)}")

@app.route('/api/generate-schedules', methods=['POST'])
def generate_schedules():
    try:
        logging.info("Starting DEMO schedule generation...")
        scheduler = get_scheduler()

        data = request.get_json(silent=True) or {}
        semester = data.get('semester', '2nd Sem')

        scheduler.load_data(semester=semester)
        schedule_data = scheduler.generate_schedule(semester=semester)
        formatted_data = scheduler.format_weekly_schedule_display(schedule_data)

        result = {
            'success': True,
            'generated_at': datetime.now().isoformat(),
            'data': {
                'weekly_schedules': formatted_data['weekly_schedules'],
                'schedules': formatted_data['schedules'],
                'summary': {
                    'total_sections': len(scheduler.sections),
                    'total_courses': len(scheduler.courses),
                    'total_faculty': len(scheduler.faculty),
                    'schedules_generated': len(formatted_data['schedules']),
                    'message': 'DEMO: Generated with minimal test data',
                    'semester': semester,
                    'status': 'TEST_SUCCESS'
                }
            }
        }

        logging.info("DEMO schedule generation completed successfully")
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error generating schedules: {e}")
        error_result = {
            'success': False,
            'error': str(e),
            'generated_at': datetime.now().isoformat()
        }
        return jsonify(error_result), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ml_backend': True,
        'mode': 'DEMO_TEST'
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
