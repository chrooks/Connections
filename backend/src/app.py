"""
Main application module for the Connections game API.

This module sets up the Flask application, registers the API Blueprint,
and defines the root route and error handlers.

Routes:
- /: Welcome message for the Connections game API.

Error Handlers:
- 404 Not Found: Handles requests for non-existent routes.
- 500 Internal Server Error: Handles internal server errors.
"""

import os
import logging
from dotenv import load_dotenv
from flask import Flask

# Load environment variables from .env file
load_dotenv()

# Configure logging: suppress noisy third-party libs, show DEBUG for our code only.
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logging.getLogger("src").setLevel(logging.DEBUG)
from flask_cors import CORS
from .extensions import limiter
from .blueprints.api.routes import api_bp
from .blueprints.admin.routes import admin_bp
from .services.utils import create_response


def create_app():
    app = Flask(__name__)
    allowed_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]
    CORS(app, origins=allowed_origins)

    limiter.init_app(app)

    app.register_blueprint(api_bp, url_prefix="/connections")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return create_response(error="Too many requests. Please slow down.", status_code=429)

    @app.route("/")
    def index():
        return create_response(data={"message": "Welcome to the Connections game API!"})

    @app.errorhandler(404)
    def not_found(error):
        return create_response(error="Not Found", status_code=404)

    @app.errorhandler(500)
    def internal_server_error(error):
        return create_response(error="Internal Server Error", status_code=500)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
