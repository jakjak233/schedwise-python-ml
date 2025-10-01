from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import sys
from datetime import datetime
from ml_scheduler import ReinforcementLearningScheduler
import traceback
import requests

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
    """API endpoint to generate weekly schedules using PHP proxy"""
    try:
        logging.info("Starting schedule generation via PHP proxy...")
        
        # Read semester from request
        data = request.get_json(silent=True) or {}
        semester = data.get('semester', '2nd Sem')

        # Call PHP proxy instead of direct database connection
        php_proxy_url = "https://uipbsit3y.com/schedwise/schedwiseAPI/schedule_generator.php"
        
        response = requests.post(
            php_proxy_url,
            json={'semester': semester},
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            logging.info("Schedule generation completed via PHP proxy")
            return jsonify(result)
        else:
            raise Exception(f"PHP proxy returned error: {response.status_code}")
            
    except Exception as e:
        logging.error(f"Error generating schedules: {e}")
        traceback.print_exc()
        error_result = {
            'success': False,
            'error': str(e),
            'generated_at': datetime.now().isoformat()
        }
        return jsonify(error_result), 500

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    """API endpoint to get existing schedules via PHP proxy"""
    try:
        # For getting schedules, we can also use PHP proxy or keep direct DB connection
        # Since this is just reading data, direct connection might work
        scheduler = get_scheduler()
        scheduler.connect_database()
        
        cursor = scheduler.connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT cs.*, f.faculty_name, c.course_code, c.descriptive_title, 
                   r.room_name, s.section_name, p.program_name
            FROM ClassSchedules cs
            JOIN Faculty f ON cs.faculty_id = f.faculty_id
            JOIN Courses c ON cs.course_id = c.course_id
            JOIN Rooms r ON cs.room_id = r.room_id
            JOIN Sections s ON cs.section_id = s.section_id
            JOIN Programs p ON s.program_id = p.program_id
            ORDER BY cs.days, cs.time_start
        """)
        
        schedules = cursor.fetchall()
        cursor.close()
        scheduler.connection.close()
        
        return jsonify({
            'success': True,
            'schedules': schedules
        })
        
    except Exception as e:
        logging.error(f"Error getting schedules: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'ml_backend': True,
            'php_proxy_url': 'https://uipbsit3y.com/schedwise/schedwiseAPI/schedule_generator.php'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'ml_backend': True,
            'error': str(e)
        }), 500

@app.route('/api/test-php-proxy', methods=['POST'])
def test_php_proxy():
    """Test endpoint to verify PHP proxy connection"""
    try:
        logging.info("Testing PHP proxy connection...")
        
        data = request.get_json(silent=True) or {}
        semester = data.get('semester', '2nd Sem')

        php_proxy_url = "https://uipbsit3y.com/schedwise/schedwiseAPI/schedule_generator.php"
        
        response = requests.post(
            php_proxy_url,
            json={'semester': semester},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'success': True,
                'php_proxy_status': 'connected',
                'response': result
            })
        else:
            return jsonify({
                'success': False,
                'php_proxy_status': 'error',
                'error': f"PHP proxy returned status: {response.status_code}",
                'response_text': response.text
            })
            
    except Exception as e:
        logging.error(f"Error testing PHP proxy: {e}")
        return jsonify({
            'success': False,
            'php_proxy_status': 'error',
            'error': str(e)
        }), 500

if __name__ == "__main__":
    try:
        logging.info("Starting ML API server...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        traceback.print_exc()
