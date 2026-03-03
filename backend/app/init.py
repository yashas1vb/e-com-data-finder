from flask import Flask
from flask_cors import CORS  # Allow frontend to communicate with backend

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable Cross-Origin Resource Sharing

    from .routes import main
    app.register_blueprint(main)

    return app
