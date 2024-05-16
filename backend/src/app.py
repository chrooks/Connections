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
from flask import Flask
from src.api import api_bp
from src.utils import create_response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://postgres:{os.getenv("POSTGRES_USER_PASSWORD")}@localhost:5432/connectionsdb'
db = SQLAlchemy(app)

app.register_blueprint(api_bp, url_prefix="/connections")


@app.route("/")
def index():
    return create_response(data={"message": "Welcome to the Connections game API!"})


@app.errorhandler(404)
def not_found(error):
    return create_response(error="Not Found", status_code=404)


@app.errorhandler(500)
def internal_server_error(error):
    return create_response(error="Internal Server Error", status_code=500)


if __name__ == "__main__":
    app.run(debug=True)
