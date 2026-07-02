import face_recognition
import numpy as np
import cv2
import base64
import json

def get_encoding_from_image(file_bytes, robust=True):
    """
    Given image bytes, return the face encoding of the first face found.
    Returns None if no face is found.
    """
    # Convert bytes to numpy array
    np_arr = np.frombuffer(file_bytes, np.uint8)
    # Decode image
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    # Convert to RGB as face_recognition expects RGB
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    if robust:
        # Using HOG model instead of CNN. CNN requires 1GB+ RAM and causes OOM crashes on Render's 512MB free tier.
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        # num_jitters=2 adds slight robustness for registration while keeping it fast
        encodings = face_recognition.face_encodings(rgb_img, known_face_locations=face_locations, num_jitters=2)
    else:
        # Standard HOG model for faster live attendance scanning
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        # num_jitters=1 (default) makes scanning incredibly fast
        encodings = face_recognition.face_encodings(rgb_img, known_face_locations=face_locations, num_jitters=1)
        
    if len(encodings) > 0:
        return encodings[0]
    return None

def get_encoding_from_base64(base64_string, robust=False):
    """
    Given a base64 string (often from canvas data URL), return face encoding.
    """
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    file_bytes = base64.b64decode(base64_string)
    return get_encoding_from_image(file_bytes, robust=robust)

def encoding_to_string(encoding):
    """
    Convert a numpy array to JSON string for database storage.
    """
    return json.dumps(encoding.tolist())

def string_to_encoding(encoding_str):
    """
    Convert a JSON string back to a numpy array.
    """
    return np.array(json.loads(encoding_str))

from concurrent.futures import ThreadPoolExecutor
import math

def find_match(known_encodings, known_users, face_encoding_to_check, tolerance=0.5):
    """
    Compare a given face encoding against a list of known encodings using multithreading.
    Returns the user object if a match is found, else None.
    """
    if not known_encodings:
        return None
        
    num_encodings = len(known_encodings)
    # If the list is small, just do it in one thread
    if num_encodings < 10:
        matches = face_recognition.compare_faces(known_encodings, face_encoding_to_check, tolerance=tolerance)
        face_distances = face_recognition.face_distance(known_encodings, face_encoding_to_check)
        
        if len(face_distances) > 0:
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                return known_users[best_match_index]
        return None

    # For larger lists, split into chunks and use threads
    # Determine number of workers based on number of encodings (max 4 for basic efficiency)
    workers = min(4, math.ceil(num_encodings / 10))
    chunk_size = math.ceil(num_encodings / workers)
    
    def match_chunk(start_idx):
        end_idx = min(start_idx + chunk_size, num_encodings)
        chunk_encodings = known_encodings[start_idx:end_idx]
        
        matches = face_recognition.compare_faces(chunk_encodings, face_encoding_to_check, tolerance=tolerance)
        distances = face_recognition.face_distance(chunk_encodings, face_encoding_to_check)
        
        best_local_idx = -1
        best_dist = 1.0 # Max distance
        
        if len(distances) > 0:
            best_local_idx = np.argmin(distances)
            if matches[best_local_idx]:
                best_dist = distances[best_local_idx]
            else:
                best_local_idx = -1
                
        return best_local_idx, best_dist, start_idx

    best_overall_dist = 1.0
    best_overall_idx = -1

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for i in range(0, num_encodings, chunk_size):
            futures.append(executor.submit(match_chunk, i))
            
        for future in futures:
            local_idx, local_dist, offset = future.result()
            if local_idx != -1 and local_dist < best_overall_dist:
                best_overall_dist = local_dist
                best_overall_idx = offset + local_idx

    if best_overall_idx != -1:
        return known_users[best_overall_idx]
        
    return None
