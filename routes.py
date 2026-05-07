from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database import db
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError
import face_utils

api = Blueprint('api', __name__)

# Ensure unique index on user_id and date for attendance
try:
    db.attendance.create_index([("user_id", 1), ("date", 1)], unique=True)
except:
    pass

@api.route('/dashboard', methods=['GET'])
def get_dashboard():
    total_users = db.users.count_documents({})
    total_classes = db.classes.count_documents({})
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    present_today = db.attendance.count_documents({'date': today, 'status': 'Present'})
    
    absent_today = total_users - present_today if total_users > present_today else 0

    return jsonify({
        'total_users': total_users,
        'total_classes': total_classes,
        'present_today': present_today,
        'absent_today': absent_today
    }), 200

@api.route('/dashboard/classes', methods=['GET'])
def get_dashboard_classes():
    classes_cursor = db.classes.find()
    result = []
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    for c in classes_cursor:
        class_id_str = str(c['_id'])
        # Get total students in this class
        total_students = db.users.count_documents({'class_id': class_id_str, 'role': 'student'})
        
        # To get present students, we need to find all students in this class, then check attendance
        students = list(db.users.find({'class_id': class_id_str, 'role': 'student'}, {'_id': 1}))
        student_ids = [str(s['_id']) for s in students]
        
        present_today = db.attendance.count_documents({
            'date': today,
            'status': 'Present',
            'user_id': {'$in': student_ids}
        })
        
        absent_today = total_students - present_today if total_students > present_today else 0
        
        result.append({
            'id': class_id_str,
            'name': c.get('name', 'Unknown'),
            'total_students': total_students,
            'present_today': present_today,
            'absent_today': absent_today
        })
        
    return jsonify(result), 200

@api.route('/classes', methods=['GET', 'POST'])
def handle_classes():
    if request.method == 'GET':
        classes = db.classes.find()
        result = []
        for c in classes:
            result.append({
                'id': str(c['_id']),
                'name': c.get('name'),
                'staff_id': c.get('staff_id')
            })
        return jsonify(result), 200
        
    if request.method == 'POST':
        data = request.json
        new_class = {
            'name': data['name'],
            'staff_id': data.get('staff_id')
        }
        res = db.classes.insert_one(new_class)
        return jsonify({'message': 'Class created successfully', 'id': str(res.inserted_id)}), 201

@api.route('/classes/<id>', methods=['DELETE'])
def delete_class(id):
    try:
        res = db.classes.delete_one({'_id': ObjectId(id)})
        if res.deleted_count > 0:
            return jsonify({'message': 'Class deleted'}), 200
        return jsonify({'error': 'Class not found'}), 404
    except:
        return jsonify({'error': 'Invalid ID'}), 400

@api.route('/users', methods=['GET', 'POST'])
def handle_users():
    if request.method == 'GET':
        class_id = request.args.get('class_id')
        query = {}
        if class_id:
            query['class_id'] = class_id
            
        users = db.users.find(query)
        result = []
        for u in users:
            result.append({
                'id': str(u['_id']),
                'name': u.get('name'),
                'role': u.get('role'),
                'class_id': u.get('class_id'),
                'has_face': u.get('face_encoding') is not None
            })
        return jsonify(result), 200

    if request.method == 'POST':
        name = request.form.get('name')
        role = request.form.get('role')
        class_id = request.form.get('class_id')
        
        if not name or not role:
            return jsonify({'error': 'Name and role are required'}), 400
            
        new_user = {
            'name': name,
            'role': role
        }
        if class_id:
            new_user['class_id'] = class_id
            
        file = request.files.get('image')
        base64_img = request.form.get('image_base64')
        
        encoding = None
        if file:
            encoding = face_utils.get_encoding_from_image(file.read(), robust=True)
        elif base64_img:
            encoding = face_utils.get_encoding_from_base64(base64_img, robust=True)
            
        if encoding is not None:
            new_user['face_encoding'] = face_utils.encoding_to_string(encoding)
        else:
            return jsonify({'error': 'No face found. Please capture or upload a clear photo.'}), 400
        
        res = db.users.insert_one(new_user)
        return jsonify({'message': 'User created successfully', 'id': str(res.inserted_id)}), 201

@api.route('/users/<id>', methods=['DELETE'])
def delete_user(id):
    try:
        res = db.users.delete_one({'_id': ObjectId(id)})
        if res.deleted_count > 0:
            return jsonify({'message': 'User deleted'}), 200
        return jsonify({'error': 'User not found'}), 404
    except:
        return jsonify({'error': 'Invalid ID'}), 400

@api.route('/attendance/mark', methods=['POST'])
def mark_attendance():
    data = request.json
    base64_image = data.get('image')
    
    if not base64_image:
        return jsonify({'error': 'No image provided'}), 400
        
    face_encoding = face_utils.get_encoding_from_base64(base64_image)
    if face_encoding is None:
        return jsonify({'error': 'No face detected in frame'}), 400
        
    users = list(db.users.find({"face_encoding": {"$ne": None}}))
    if not users:
        return jsonify({'error': 'No users with registered faces found in database'}), 404
        
    known_encodings = [face_utils.string_to_encoding(u['face_encoding']) for u in users]
    
    class MockUser:
        def __init__(self, u_dict):
            self.id = str(u_dict['_id'])
            self.name = u_dict.get('name')
            self.role = u_dict.get('role')
            
    mock_users = [MockUser(u) for u in users]
    
    matched_user = face_utils.find_match(known_encodings, mock_users, face_encoding)
    
    if not matched_user:
        return jsonify({'error': 'Unknown face. Access denied.'}), 403
        
    today = datetime.utcnow().strftime('%Y-%m-%d')
    timestamp = datetime.utcnow()
    
    existing_attendance = db.attendance.find_one({'user_id': matched_user.id, 'date': today})
    if existing_attendance:
        return jsonify({
            'message': f'Attendance already marked for {matched_user.name} today.',
            'user': {'name': matched_user.name, 'role': matched_user.role}
        }), 200
        
    new_attendance = {
        'user_id': matched_user.id,
        'date': today,
        'timestamp': timestamp,
        'status': 'Present'
    }
    
    try:
        db.attendance.insert_one(new_attendance)
        return jsonify({
            'message': f'Attendance marked successfully for {matched_user.name}.',
            'user': {'name': matched_user.name, 'role': matched_user.role}
        }), 201
    except DuplicateKeyError:
        return jsonify({'error': 'Attendance already recorded.'}), 400

@api.route('/attendance/reports', methods=['GET'])
def get_reports():
    class_id = request.args.get('class_id')
    
    today_dt = datetime.utcnow()
    seven_days_ago_dt = today_dt - timedelta(days=6)
    seven_days_ago_str = seven_days_ago_dt.strftime('%Y-%m-%d')
    
    query = {'date': {'$gte': seven_days_ago_str}}
    attendances = list(db.attendance.find(query))
    
    user_ids = list(set([a['user_id'] for a in attendances]))
    # Only valid ObjectIds
    valid_user_ids = []
    for uid in user_ids:
        try:
            valid_user_ids.append(ObjectId(uid))
        except:
            pass
            
    users_cursor = db.users.find({'_id': {'$in': valid_user_ids}})
    user_map = {str(u['_id']): u for u in users_cursor}
    
    report_data = []
    for a in attendances:
        user = user_map.get(a['user_id'])
        if not user:
            continue
            
        if class_id and user.get('class_id') != class_id:
            continue
            
        report_data.append({
            'id': str(a['_id']),
            'user_name': user.get('name', 'Unknown'),
            'role': user.get('role', 'student'),
            'class_id': user.get('class_id'),
            'date': a['date'],
            'time': a['timestamp'].strftime('%H:%M:%S') if 'timestamp' in a else '',
            'status': a.get('status', 'Present')
        })
        
    return jsonify(report_data), 200

@api.route('/attendance/monthly', methods=['GET'])
def get_monthly_attendance():
    class_id = request.args.get('class_id')
    year = request.args.get('year')
    month = request.args.get('month')
    
    if not all([class_id, year, month]):
        return jsonify({'error': 'class_id, year, and month are required'}), 400
        
    try:
        year = int(year)
        month = int(month)
    except ValueError:
        return jsonify({'error': 'Invalid year or month format'}), 400

    students_cursor = db.users.find({'class_id': class_id, 'role': 'student'})
    students = list(students_cursor)
    student_ids = [str(s['_id']) for s in students]
    
    start_date = f"{year}-{month:02d}-01"
    
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{days_in_month:02d}"
    
    attendance_cursor = db.attendance.find({
        'user_id': {'$in': student_ids},
        'date': {'$gte': start_date, '$lte': end_date}
    })
    
    attendance_map = {sid: {} for sid in student_ids}
    for a in attendance_cursor:
        # Get just the day part e.g. "05" -> 5
        day_str = a['date'].split('-')[2]
        day = int(day_str)
        attendance_map[a['user_id']][day] = a['status']
        
    result = []
    for s in students:
        sid = str(s['_id'])
        student_data = {
            'id': sid,
            'name': s.get('name'),
            'attendance': attendance_map.get(sid, {})
        }
        result.append(student_data)
        
    return jsonify({
        'days_in_month': days_in_month,
        'year': year,
        'month': month,
        'students': result
    }), 200
