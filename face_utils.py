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
    # Convert to RGB as face_recognition expects RGB
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    if robust:
        # High accuracy CNN model for registration (robust to side profiles/changes)
        face_locations = face_recognition.face_locations(rgb_img, model="cnn")
        # num_jitters=10 adds robustness by resampling the face multiple times
        encodings = face_recognition.face_encodings(rgb_img, known_face_locations=face_locations, num_jitters=10)
    else:
        # Standard HOG model for faster live attendance scanning
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        # slight jitter for better live accuracy
        encodings = face_recognition.face_encodings(rgb_img, known_face_locations=face_locations, num_jitters=2)
        
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

def find_match(known_encodings, known_users, face_encoding_to_check, tolerance=0.5):
    """
    Compare a given face encoding against a list of known encodings.
    Returns the user object if a match is found, else None.
    """
    if not known_encodings:
        return None
        
    matches = face_recognition.compare_faces(known_encodings, face_encoding_to_check, tolerance=tolerance)
    face_distances = face_recognition.face_distance(known_encodings, face_encoding_to_check)
    
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            return known_users[best_match_index]
            
    return None
