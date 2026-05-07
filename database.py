from pymongo import MongoClient
import certifi
from config import Config

# Initialize MongoDB client
# certifi is used to prevent SSL certificate errors with MongoDB Atlas
client = MongoClient(Config.MONGO_URI, tlsCAFile=certifi.where())
# Use 'smart_attendance' as the database
db = client.get_database("smart_attendance")
