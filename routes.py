from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database import db
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError
import face_utils
import calendar

api = Blueprint('api', __name__)

# Ensure unique index on user_id and date for attendance
try:
    db.attendance.create_index([("user_id", 1), ("date", 1)], unique=True)
    db.users.create_index([("class_id", 1)])
    db.users.create_index([("roll_number", 1)])
    db.users.create_index([("role", 1)])
except:
    pass


# ---------------------------------------------------------------------------
# Helper: resolve class name from class_id
# ---------------------------------------------------------------------------
def _class_name_map():
    classes = list(db.classes.find({}, {"_id": 1, "name": 1, "department": 1, "section": 1}))
    return {
        str(c["_id"]): f"{c.get('name', '—')}{' - ' + c.get('department') if c.get('department') else ''}{' (' + c.get('section') + ')' if c.get('section') else ''}"
        for c in classes
    }


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------
@api.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    
    # Hardcoded admin credentials based on user request
    if phone == '6281871173' and password == 'admin':
        return jsonify({'message': 'Login successful', 'token': 'admin-dummy-token'}), 200
        
    return jsonify({'error': 'Invalid credentials'}), 401

# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@api.route('/dashboard', methods=['GET'])
def get_dashboard():
    total_users = db.users.count_documents({})
    total_classes = db.classes.count_documents({})

    today = datetime.utcnow().strftime('%Y-%m-%d')
    present_today = db.attendance.count_documents({'date': today, 'status': 'Present'})
    absent_today = max(0, total_users - present_today)

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
        total_students = db.users.count_documents({'class_id': class_id_str, 'role': 'student'})
        students = list(db.users.find({'class_id': class_id_str, 'role': 'student'}, {'_id': 1}))
        student_ids = [str(s['_id']) for s in students]

        present_today = db.attendance.count_documents({
            'date': today,
            'status': 'Present',
            'user_id': {'$in': student_ids}
        })
        absent_today = max(0, total_students - present_today)

        result.append({
            'id': class_id_str,
            'name': c.get('name', 'Unknown'),
            'department': c.get('department', ''),
            'section': c.get('section', ''),
            'year': c.get('year', ''),
            'total_students': total_students,
            'present_today': present_today,
            'absent_today': absent_today
        })

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# CLASSES
# ---------------------------------------------------------------------------
@api.route('/classes', methods=['GET', 'POST'])
def handle_classes():
    if request.method == 'GET':
        classes = db.classes.find()
        result = []
        for c in classes:
            result.append({
                'id': str(c['_id']),
                'name': c.get('name', ''),
                'department': c.get('department', ''),
                'section': c.get('section', ''),
                'year': c.get('year', ''),
                'staff_id': c.get('staff_id')
            })
        return jsonify(result), 200

    if request.method == 'POST':
        data = request.json or {}
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Class name is required'}), 400

        new_class = {
            'name': name,
            'department': data.get('department', '').strip(),
            'section': data.get('section', '').strip(),
            'year': data.get('year', '').strip(),
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
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------
@api.route('/users', methods=['GET', 'POST'])
def handle_users():
    if request.method == 'GET':
        class_id = request.args.get('class_id')
        query = {}
        if class_id:
            query['class_id'] = class_id

        users = db.users.find(query)
        cname_map = _class_name_map()
        result = []
        for u in users:
            result.append({
                'id': str(u['_id']),
                'name': u.get('name', ''),
                'roll_number': u.get('roll_number', ''),
                'role': u.get('role', 'student'),
                'department': u.get('department', ''),
                'year_of_study': u.get('year_of_study', ''),
                'class_id': u.get('class_id', ''),
                'class_name': cname_map.get(u.get('class_id', ''), '—'),
                'has_face': u.get('face_encoding') is not None
            })
        return jsonify(result), 200

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'student').strip()
        class_id = request.form.get('class_id', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        department = request.form.get('department', '').strip()
        year_of_study = request.form.get('year_of_study', '').strip()

        if not name or not role:
            return jsonify({'error': 'Name and role are required'}), 400

        new_user = {
            'name': name,
            'role': role,
            'roll_number': roll_number,
            'department': department,
            'year_of_study': year_of_study
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


@api.route('/users/search', methods=['GET'])
def search_users():
    """Search users by name or roll_number (case-insensitive partial match)."""
    q = request.args.get('q', '').strip()
    class_id = request.args.get('class_id', '').strip()

    if not q:
        return jsonify([]), 200

    regex_query = {'$regex': q, '$options': 'i'}
    mongo_query = {'$or': [{'name': regex_query}, {'roll_number': regex_query}]}
    if class_id:
        mongo_query['class_id'] = class_id

    users = db.users.find(mongo_query)
    cname_map = _class_name_map()
    result = []
    for u in users:
        result.append({
            'id': str(u['_id']),
            'name': u.get('name', ''),
            'roll_number': u.get('roll_number', ''),
            'role': u.get('role', 'student'),
            'department': u.get('department', ''),
            'year_of_study': u.get('year_of_study', ''),
            'class_id': u.get('class_id', ''),
            'class_name': cname_map.get(u.get('class_id', ''), '—'),
            'has_face': u.get('face_encoding') is not None
        })
    return jsonify(result), 200


@api.route('/users/<id>', methods=['DELETE'])
def delete_user(id):
    try:
        res = db.users.delete_one({'_id': ObjectId(id)})
        if res.deleted_count > 0:
            return jsonify({'message': 'User deleted'}), 200
        return jsonify({'error': 'User not found'}), 404
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400


# ---------------------------------------------------------------------------
# ATTENDANCE — MARK (Live face recognition & Manual)
# ---------------------------------------------------------------------------
@api.route('/attendance/manual', methods=['POST'])
def mark_attendance_manual():
    data = request.json or {}
    roll_number = data.get('roll_number', '').strip()
    class_id = data.get('class_id', '').strip()
    
    if not roll_number:
        return jsonify({'error': 'Roll number is required'}), 400
        
    query = {'roll_number': {'$regex': f"^{roll_number}$", '$options': 'i'}}
    if class_id:
        query['class_id'] = class_id
        
    user = db.users.find_one(query)
    if not user:
        return jsonify({'error': 'Student not found with this roll number'}), 404
        
    today = datetime.utcnow().strftime('%Y-%m-%d')
    timestamp = datetime.utcnow()

    existing = db.attendance.find_one({'user_id': str(user['_id']), 'date': today})
    if existing:
        return jsonify({
            'message': f'Attendance already marked for {user.get("name")} today.',
            'user': {'name': user.get('name'), 'role': user.get('role'), 'roll_number': user.get('roll_number')}
        }), 200

    new_attendance = {
        'user_id': str(user['_id']),
        'date': today,
        'timestamp': timestamp,
        'status': 'Present'
    }

    try:
        db.attendance.insert_one(new_attendance)
        return jsonify({
            'message': f'Attendance marked manually for {user.get("name")}.',
            'user': {'name': user.get('name'), 'role': user.get('role'), 'roll_number': user.get('roll_number')}
        }), 201
    except DuplicateKeyError:
        return jsonify({'error': 'Attendance already recorded.'}), 400

@api.route('/attendance/mark', methods=['POST'])
def mark_attendance():
    data = request.json
    base64_image = data.get('image')
    class_id = data.get('class_id')

    if not base64_image:
        return jsonify({'error': 'No image provided'}), 400

    face_encoding = face_utils.get_encoding_from_base64(base64_image)
    if face_encoding is None:
        return jsonify({'error': 'No face detected in frame'}), 400

    query = {"face_encoding": {"$ne": None}}
    if class_id:
        query["class_id"] = class_id

    users = list(db.users.find(query))
    if not users:
        return jsonify({'error': 'No users with registered faces found in database for this filter'}), 404

    known_encodings = [face_utils.string_to_encoding(u['face_encoding']) for u in users]

    class MockUser:
        def __init__(self, u_dict):
            self.id = str(u_dict['_id'])
            self.name = u_dict.get('name')
            self.role = u_dict.get('role')
            self.roll_number = u_dict.get('roll_number', '')

    mock_users = [MockUser(u) for u in users]
    matched_user = face_utils.find_match(known_encodings, mock_users, face_encoding)

    if not matched_user:
        return jsonify({'error': 'Unknown face. Access denied.'}), 403

    today = datetime.utcnow().strftime('%Y-%m-%d')
    timestamp = datetime.utcnow()

    existing = db.attendance.find_one({'user_id': matched_user.id, 'date': today})
    if existing:
        return jsonify({
            'message': f'Attendance already marked for {matched_user.name} today.',
            'user': {'name': matched_user.name, 'role': matched_user.role, 'roll_number': matched_user.roll_number}
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
            'user': {'name': matched_user.name, 'role': matched_user.role, 'roll_number': matched_user.roll_number}
        }), 201
    except DuplicateKeyError:
        return jsonify({'error': 'Attendance already recorded.'}), 400


# ---------------------------------------------------------------------------
# ATTENDANCE — REPORTS (daily logs, last N days)
# ---------------------------------------------------------------------------
@api.route('/attendance/reports', methods=['GET'])
def get_reports():
    class_id = request.args.get('class_id')

    today_dt = datetime.utcnow()
    seven_days_ago_str = (today_dt - timedelta(days=6)).strftime('%Y-%m-%d')

    query = {'date': {'$gte': seven_days_ago_str}}
    attendances = list(db.attendance.find(query))

    user_ids = list(set([a['user_id'] for a in attendances]))
    valid_user_ids = []
    for uid in user_ids:
        try:
            valid_user_ids.append(ObjectId(uid))
        except Exception:
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
            'roll_number': user.get('roll_number', ''),
            'role': user.get('role', 'student'),
            'class_id': user.get('class_id', ''),
            'date': a['date'],
            'time': a['timestamp'].strftime('%H:%M:%S') if 'timestamp' in a else '',
            'status': a.get('status', 'Present')
        })

    return jsonify(report_data), 200


# ---------------------------------------------------------------------------
# ATTENDANCE — SUMMARY (Weekly / Monthly / Overall per student in a class)
# ---------------------------------------------------------------------------
@api.route('/attendance/summary', methods=['GET'])
def get_attendance_summary():
    """
    Returns per-student attendance summary for a class.
    Query params:
      - class_id (required)
      - period: 'weekly' (last 7 days) | 'monthly' (current month by year/month) | 'overall'
      - year, month: required when period=monthly
    """
    class_id = request.args.get('class_id', '').strip()
    period = request.args.get('period', 'weekly').strip()

    if not class_id:
        return jsonify({'error': 'class_id is required'}), 400

    # --- Determine date range ---
    today = datetime.utcnow()

    if period == 'weekly':
        start_date = (today - timedelta(days=6)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        # build list of working dates in range
        working_dates = [
            (today - timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(6, -1, -1)
        ]

    elif period == 'monthly':
        year = request.args.get('year')
        month = request.args.get('month')
        if not year or not month:
            return jsonify({'error': 'year and month required for monthly period'}), 400
        try:
            year = int(year)
            month = int(month)
        except ValueError:
            return jsonify({'error': 'Invalid year or month'}), 400

        days_in_month = calendar.monthrange(year, month)[1]
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-{days_in_month:02d}"
        working_dates = [f"{year}-{month:02d}-{d:02d}" for d in range(1, days_in_month + 1)]

    elif period == 'overall':
        start_date = None
        end_date = None
        working_dates = None  # determined dynamically

    else:
        return jsonify({'error': 'Invalid period. Use weekly, monthly, or overall'}), 400

    # --- Fetch students in class ---
    students = list(db.users.find({'class_id': class_id, 'role': 'student'}))
    student_ids = [str(s['_id']) for s in students]

    if not students:
        return jsonify({'students': [], 'working_dates': [], 'period': period}), 200

    # --- Fetch attendance records ---
    att_query = {'user_id': {'$in': student_ids}}
    if start_date:
        att_query['date'] = {'$gte': start_date, '$lte': end_date}

    attendance_records = list(db.attendance.find(att_query))

    # --- If overall, collect all unique dates ---
    if period == 'overall':
        all_dates = sorted(set(a['date'] for a in attendance_records))
        working_dates = all_dates

    # Build attendance map: student_id -> {date -> status}
    att_map = {sid: {} for sid in student_ids}
    for a in attendance_records:
        att_map[a['user_id']][a['date']] = a.get('status', 'Present')

    # --- Build result ---
    # Only count days that have ANY attendance recorded (actual working days)
    if working_dates:
        # For weekly/monthly: the "effective" working days are only dates that have
        # at least one student present in the whole class
        effective_dates = [
            d for d in working_dates
            if any(att_map[sid].get(d) for sid in student_ids)
        ]
        # If no attendance at all yet, fall back to all dates in range
        if not effective_dates and period != 'overall':
            effective_dates = working_dates
    else:
        effective_dates = []

    result_students = []
    for s in students:
        sid = str(s['_id'])
        present_days = sum(
            1 for d in effective_dates if att_map[sid].get(d) == 'Present'
        )
        total_working = len(effective_dates)
        percentage = round((present_days / total_working) * 100) if total_working > 0 else 0

        daily = {d: att_map[sid].get(d, 'Absent') for d in effective_dates}

        result_students.append({
            'id': sid,
            'name': s.get('name', ''),
            'roll_number': s.get('roll_number', ''),
            'present_days': present_days,
            'total_days': total_working,
            'percentage': percentage,
            'daily': daily
        })

    return jsonify({
        'period': period,
        'working_dates': effective_dates,
        'students': result_students
    }), 200


# ---------------------------------------------------------------------------
# ATTENDANCE — MONTHLY (detailed calendar grid — kept for MonthlyClassView)
# ---------------------------------------------------------------------------
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

    students = list(db.users.find({'class_id': class_id, 'role': 'student'}))
    student_ids = [str(s['_id']) for s in students]

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days_in_month:02d}"

    attendance_cursor = db.attendance.find({
        'user_id': {'$in': student_ids},
        'date': {'$gte': start_date, '$lte': end_date}
    })

    # Find working days: days where at least one student has attendance
    att_map = {sid: {} for sid in student_ids}
    all_recorded_dates = set()
    for a in attendance_cursor:
        day = int(a['date'].split('-')[2])
        att_map[a['user_id']][day] = a.get('status', 'Present')
        all_recorded_dates.add(day)

    working_days_count = len(all_recorded_dates)

    result = []
    for s in students:
        sid = str(s['_id'])
        student_att = att_map.get(sid, {})
        present_count = sum(1 for v in student_att.values() if v == 'Present')
        percentage = round((present_count / working_days_count) * 100) if working_days_count > 0 else 0

        result.append({
            'id': sid,
            'name': s.get('name', ''),
            'roll_number': s.get('roll_number', ''),
            'attendance': student_att,
            'present_count': present_count,
            'working_days': working_days_count,
            'percentage': percentage
        })

    return jsonify({
        'days_in_month': days_in_month,
        'working_days': working_days_count,
        'year': year,
        'month': month,
        'students': result
    }), 200
