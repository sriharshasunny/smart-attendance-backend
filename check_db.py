import os
import certifi
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://sriharshaboindla_db_user:harsha123@cluster0.eej2j3r.mongodb.net/?appName=Cluster0")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client.get_database("smart_attendance")

print(f"Classes count: {db.classes.count_documents({})}")
for c in db.classes.find():
    print(c)

print(f"Users count: {db.users.count_documents({})}")
for u in db.users.find({}, {"face_encoding": 0}):
    print(u)
