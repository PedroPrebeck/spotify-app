import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
    SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
    SESSION_TYPE = 'filesystem'
    CLUSTERING_ALGORITHM = os.getenv('CLUSTERING_ALGORITHM', 'kmeans')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
