from flask import Flask, render_template, session
from flask_session import Session
from routes import overview, broken, reallocation, after_effect, upload, product
import os
from datetime import timedelta

app = Flask(__name__)

# Session configuration
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production-make-it-long-and-random')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configure Flask-Session for server-side sessions
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'inventory:'

# Ngrok/HTTPS compatibility
app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cross-site requests

# Initialize Flask-Session
Session(app)

# Make sure session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Register blueprints
app.register_blueprint(overview.bp)
app.register_blueprint(broken.bp)
app.register_blueprint(reallocation.bp)
app.register_blueprint(after_effect.bp)
app.register_blueprint(upload.bp)
app.register_blueprint(product.bp)
# app.register_blueprint(data.bp)

@app.route('/')
def index():
    return render_template('base.html', active_tab='overview')

@app.route('/product')
def product():
    return render_template('base.html', active_tab='product')

@app.route('/test-upload')
def test_upload():
    return render_template('test_upload.html')

@app.route('/debug-test')
def debug_test():
    return render_template('debug_test.html')

@app.route('/api/data_status')
def data_status():
    """Check if data is loaded in session"""
    from flask import jsonify
    has_data = all([
        'df_stores' in session,
        'df_warehouse' in session,
        'df_broken' in session,
        'store_profiles' in session
    ])

    return jsonify({
        'stores_loaded': 'df_stores' in session,
        'warehouse_loaded': 'df_warehouse' in session,
        'broken_loaded': 'df_broken' in session,
        'profiles_loaded': 'store_profiles' in session,
        'optimization_done': session.get('optimization_done', False),
        'all_loaded': has_data,
        'session_keys': list(session.keys())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)