from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)

    # Allow origins from env var (comma-separated) or default to localhost for dev
    raw_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000')
    allowed_origins = [o.strip() for o in raw_origins.split(',') if o.strip()]
    CORS(app, origins=allowed_origins)

    # Configure upload and output folders
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), '../uploads')
    app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(__file__), '../output')

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

    # Register blueprints
    from .routes import main
    app.register_blueprint(main)

    return app