from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)

    # Allow all origins — safe for a public data tool
    CORS(app)

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