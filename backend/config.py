import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY','dev-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR/'app.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR/'static'/'uploads'))
    JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-secret-key')
    DEV_MODE = True  # Toggle off in production
