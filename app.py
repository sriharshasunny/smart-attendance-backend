from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    CORS(app, origins="*")

    # Health check route — always works, even if DB/routes fail
    @app.route('/')
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'smart-attendance-backend'})

    # Attempt to register main API routes
    try:
        from routes import api
        app.register_blueprint(api, url_prefix='/api')
    except Exception as e:
        # If routes fail to import (e.g. face_recognition missing), log clearly
        @app.route('/api/status')
        def api_status():
            return jsonify({'error': str(e)}), 500
        print(f"[STARTUP ERROR] Failed to register API routes: {e}")
    
    return app

# Create app at module level so gunicorn can find it with "app:app"
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
