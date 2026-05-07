import os

class Config:
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://sriharshaboindla_db_user:harsha123@cluster0.eej2j3r.mongodb.net/?appName=Cluster0")
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
