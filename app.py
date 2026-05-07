from flask import Flask
from flask_cors import CORS
from config import Config
from routes import api
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    CORS(app, origins="*")
    
    app.register_blueprint(api, url_prefix='/api')
    
    return app

# Create app at module level so gunicorn can find it with "app:app"
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
