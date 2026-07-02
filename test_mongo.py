import certifi
from pymongo import MongoClient
import time
import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://sriharshaboindla_db_user:harsha123@cluster0.eej2j3r.mongodb.net/?appName=Cluster0")

print("Connecting...")
start = time.time()
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    db = client.get_database("smart_attendance")
    db.command("ping")
    print(f"Connected in {time.time() - start:.2f}s")
    
    # Test insertion
    res = db.classes.insert_one({"name": "TestClass", "department": "TestDept"})
    print(f"Inserted document with ID: {res.inserted_id}")
    db.classes.delete_one({"_id": res.inserted_id})
    print("Deleted test document")
except Exception as e:
    print(f"Failed in {time.time() - start:.2f}s: {e}")
