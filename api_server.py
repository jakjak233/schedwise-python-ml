from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import sys
from datetime import datetime
from ml_scheduler import TestScheduler
import traceback

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
app = Flask(__name__)
CORS(app)

scheduler = None

def get_scheduler():
    global scheduler
    try:
        if scheduler is None:
            logging.info("🔄 Initializing TEST scheduler...")
            scheduler = TestScheduler()
        return scheduler
    except Exception as e:
        logging.error(f"❌ Failed to initialize scheduler: {e}")
        raise Exception(f"Scheduler initialization failed: {str(e)}")

@app.route('/api/generate-schedules', methods=['POST'])
def generate_schedules():
    try:
        logging.info("🚀 Starting SUPER SIMPLE schedule generation...")
        scheduler = get_scheduler()

        data = request.get_json(silent=True) or {}
        semester = data.get('semester', '2nd Sem')

        # Test database connection and data loading
        scheduler.load_data(semester=semester)
        
        # Generate static demo schedule
        schedule_data = scheduler.generate_schedule(semester=semester)
        formatted_data = scheduler.format_weekly_schedule_display(schedule_data)

        result = {
            'success': True,
            'generated_at': datetime.now().isoformat(),
            'data': {
                'weekly_schedules': formatted_data['weekly_schedules'],
                'schedules': formatted_data['schedules'],
                'summary': {
                    'total_sections': 1,
                    'total_courses': 2, 
                    'total_faculty': 2,
                    'schedules_generated': len(formatted_data['schedules']),
                    'message': '✅ SYSTEM TEST SUCCESSFUL - Database connected and API working!',
                    'semester': semester,
                    'status': 'READY_FOR_UPGRADE',
                    'next_step': 'Upgrade to Starter plan for full ML functionality'
                }
            }
        }

        logging.info("🎉 SUPER SIMPLE TEST COMPLETED SUCCESSFULLY!")
        return jsonify(result)

    except Exception as e:
        logging.error(f"❌ Error in test: {e}")
        error_result = {
            'success': False,
            'error': str(e),
            'generated_at': datetime.now().isoformat(),
            'message': 'System test failed - check database connection'
        }
        return jsonify(error_result), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'SchedWise ML Backend',
        'mode': 'SUPER_SIMPLE_TEST',
        'message': 'Service running - ready for testing'
    })

@app.route('/api/test-database', methods=['GET'])
def test_database():
    """Simple database connection test"""
    try:
        scheduler = TestScheduler()
        scheduler.connect_database()
        return jsonify({
            'success': True,
            'message': '✅ Database connection successful!',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '❌ Database connection failed'
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
