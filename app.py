import sqlite3
import os
import random
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, g, session
from flask_socketio import SocketIO, emit, join_room
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'sphinx of black quartz judge my vow'
DB_NAME = 'queue_system.db'
socketio = SocketIO(app, cors_allowed_origins="*")

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
mail = Mail(app)

def send_verification_email(email, code):
    """Send a 6-digit verification code to the given email.
    Returns True if it sent successfully, False otherwise (and logs the error)."""
    try:
        msg = Message('Verify your Queues account', recipients=[email])
        msg.body = f'Your verification code is: {code}'
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False

def get_db_connection():
    if 'db' not in g:
        # Adding timeout=20 gives SQLite 20 seconds to wait for open locks before raising an error
        g.db = sqlite3.connect(DB_NAME, timeout=20)
        g.db.row_factory = sqlite3.Row
    return g.db

def create_notification(user_id, message):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO notification (user_id, message) VALUES (?, ?)",
        (user_id, message)
    )
    conn.commit()

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = get_db_connection()
    with open('schema.sql') as f:
        conn.executescript(f.read())
    conn.commit()

def create_admin():
    conn = get_db_connection()

    existing_admin = conn.execute(
        'SELECT * FROM user WHERE username = ?',
        ('admin',)
    ).fetchone()

    if not existing_admin:
        conn.execute(
            '''
            INSERT INTO user (username, password, role, is_verified)
            VALUES (?, ?, ?, ?)
            ''',
            ('admin', 'admin123', 'ADMIN', 1)
        )
        conn.commit()
        print("Admin account created.")


@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'ADMIN':
        return redirect(url_for('login'))

    return render_template('admin_dashboard.html')

def admin_required():
    return session.get('role') == 'ADMIN' and session.get('user_id') is not None

@app.route('/staff/dashboard/<int:store_id>')
def staff_dashboard(store_id):

    # Only STAFF can access Staff Dashboard
    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))

    conn = get_db_connection()

    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE store_id = ?
        AND owner_id = ?
        """,
        (
            store_id,
            session['user_id']
        )
    ).fetchone()

    if not store:
        return "You do not have access to this store.", 403

    if store['store_status'] != 'APPROVED':
        return redirect(url_for('staff_status'))

    return render_template(
        'staff_dashboard.html',
        store_id=store_id
    )
    

#======================================================================
# -- Member 1 (Syahmi): User & Store Api
#======================================================================


# =========================
# HOME PAGE
# =========================

@app.route('/')
def home():
    return redirect(url_for('login'))


# =========================
# STORE DIRECTORY
# =========================

@app.route('/stores')
def store_discovery():

    search_query = request.args.get('search', '')

    # Grab the logged in user's name from memory
    current_username = session.get('username')

    conn = get_db_connection()

    if search_query:
        stores = conn.execute(
            'SELECT * FROM store WHERE store_name LIKE ?',
            ('%' + search_query + '%',)
        ).fetchall()
    else:
        stores = conn.execute(
            'SELECT * FROM store'
        ).fetchall()

    return render_template(
        'stores.html',
        stores=stores,
        search_query=search_query,
        username=current_username
    )

# User Registration

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        # Receive what they typed in the boxes
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email', '').strip()

        # Grab the role they picked from the dropdown menu/
        role = request.form.get('role', 'CUSTOMER')

        conn = get_db_connection()
         # Check if username already exists
        existing_user = conn.execute('SELECT * FROM user WHERE username =?', (username,)).fetchone()

        if existing_user:
            error = "That username is already taken! Choose another one."
            return render_template('register.html', error=error)

        code = str(random.randint(100000, 999999))

        conn.execute(
            'INSERT INTO user (username, password, role, email, verification_code) VALUES (?, ?, ?, ?, ?)',
            (username, password, role, email, code)
        )
        conn.commit()

        send_verification_email(email, code)

        session['pending_verify'] = username
        return redirect(url_for('verify_email'))

    return render_template('register.html', error=error)


# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()

        user = conn.execute(
            '''
            SELECT *
            FROM user
            WHERE username = ?
            AND password = ?
            ''',
            (username, password)
        ).fetchone()

        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']

            if user['role'] == 'ADMIN':
                return redirect(url_for('admin_dashboard'))

            elif user['role'] == 'STAFF':

                 conn = get_db_connection()

                 store = conn.execute(
                   """
                   SELECT *
                   FROM store
                   WHERE owner_id = ?
                   ORDER BY store_id DESC
                   LIMIT 1
                   """,
                   (user['user_id'],)
                ).fetchone()

                # STAFF has never submitted a store proposal
                 if not store:
                     return redirect(url_for('register_store'))

                # Proposal is still waiting for ADMIN
                 if store['store_status'] == 'PENDING':
                     return redirect(url_for('staff_status'))

                # ADMIN rejected the proposal
                 if store['store_status'] == 'REJECTED':
                     return redirect(url_for('staff_status'))

                # ADMIN approved the proposal
                 if store['store_status'] == 'APPROVED':
                     return redirect(
                         url_for(
                             'staff_dashboard',
                             store_id=store['store_id']
                         )
               )

            else:
                return redirect(url_for('store_discovery'))
        else:
            return render_template(
                'login.html',
                error='Incorrect username or password. Please try again!'
            )

    return render_template('login.html')

# User Verify
@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    username = session.get('pending_verify')
    if not username:
        return redirect(url_for('login'))

    error = None
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

        if user and user['verification_code'] == code:
            conn.execute('UPDATE user SET is_verified = 1, verification_code = NULL WHERE username = ?', (username,))
            conn.commit()
            session.pop('pending_verify', None)
            return redirect(url_for('login'))
        error = "Incorrect code."

    return render_template('verify_email.html', error=error, username=username)


# Resend OTP: generates a fresh code, overwrites the old one, re-sends it.
@app.route('/resend_code', methods=['POST'])
def resend_code():
    username = session.get('pending_verify')
    if not username:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

    if not user:
        return redirect(url_for('login'))

    new_code = str(random.randint(100000, 999999))
    conn.execute('UPDATE user SET verification_code = ? WHERE username = ?', (new_code, username))
    conn.commit()

    sent = send_verification_email(user['email'], new_code)
    notice = "A new code has been sent to your email." if sent else \
        "Couldn't send the email right now, please try again in a moment."

    return render_template('verify_email.html', error=None, notice=notice, username=username)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM user WHERE email = ?', (email,)).fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(minutes=30)

            conn.execute(
                'UPDATE user SET reset_token = ?, reset_token_expire = ? WHERE user_id = ?',
                (token, expiry, user['user_id'])
            )
            conn.commit()

            reset_link = url_for('reset_password', token=token, _external=True)

            try:
                msg = Message('Reset your Queues password', recipients=[email])
                msg.body = f'Click here to reset your password: {reset_link}\nThis link expires in 30 minutes.'
                mail.send(msg)
            except Exception as e:
                print(f"Failed to send reset email: {e}")

        message = "If that email is registered, a reset link has been sent."

    return render_template('forgot_password.html', message=message)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM user WHERE reset_token = ?', (token,)).fetchone()

    if not user:
        return "Invalid or expired reset link."

    expiry = datetime.fromisoformat(user['reset_token_expire'])
    if datetime.now() > expiry:
        conn.close()
        return "This reset link has expired. Please request a new one."

    error = None
    if request.method == 'POST':
        new_password = request.form['password']

        conn.execute(
            'UPDATE user SET password = ?, reset_token = NULL, reset_token_expire = NULL WHERE user_id = ?',
            (new_password, user['user_id'])
        )
        conn.commit()
        return redirect(url_for('login'))

    return render_template('reset_password.html', error=error, token=token)


@app.route('/my-store')
def my_store():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    stores = conn.execute(
        'SELECT * FROM store WHERE owner_id = ?', (session['user_id'],)
    ).fetchall()

    return render_template('my_store.html', stores=stores, username=session.get('username'))

# Store registration ----> Week 4: Adding form
@app.route('/register_store', methods=['GET', 'POST'])
def register_store():
    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))
    conn = get_db_connection()

    # Check whether this staff already has a proposal
    existing_store = conn.execute(
           """
           SELECT *
           FROM store
           WHERE owner_id = ?
           ORDER BY store_id DESC
           LIMIT 1
           """,
           (session['user_id'],)
     ).fetchone()

    # If they already have a proposal, don't create another one
    if existing_store:
        return redirect(url_for('staff_status'))

    if request.method == 'POST':

        store_name = request.form['name']
        hours = request.form['hours']

        conn.execute(
            """
            INSERT INTO store
            (
                store_name,
                operating_hours,
                store_status,
                owner_id
            )
            VALUES (?, ?, 'PENDING', ?)
            """,
            (
                store_name,
                hours,
                session['user_id']
            )
        )

        conn.commit()

        return redirect(url_for('staff_status'))


    return render_template('register_store.html')

@app.route('/staff/status')
def staff_status():

    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))

    conn = get_db_connection()

    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE owner_id = ?
        ORDER BY store_id DESC
        LIMIT 1
        """,
        (session['user_id'],)
    ).fetchone()


    return render_template(
        'staff_status.html',
        store=store
    )

# Store Details Page ---> Week 3
@app.route('/store/<int:store_id>')
def store_details(store_id):
    # Check if the user has a session, if not, redirect to login
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Grab the specific store record based on the clicked store id.
    store = conn.execute('SELECT * FROM store WHERE store_id =?', (store_id,)).fetchone()

    # Grab all active services linked to this store from Member 3's service table
    services = conn.execute('SELECT * FROM service WHERE store_id = ?', (store_id,)).fetchall()


    # Fall back error response if someone manually type a fake store ID in the URL
    if not store:
        return "Store not found", 404

    # Render the template and pass along the user's session name
    return render_template('store_details.html', store=store, services=services, username=session.get('username'))

# User Logout ---> Week 3
@app.route('/logout')
def logout():
        # Clear the session memory
        session.clear()
        # Redirect user back to login
        return redirect(url_for('login'))


#======================================================================
# -- Member 2(Eugene): Appointment & Queue Api
#======================================================================
@socketio.on('join_store_room')
def on_join_store_room(data):
    store_id = data.get('store_id')
    if store_id:
        room = f"store_{store_id}"
        join_room(room)
        print(f"User joined {room}")

# POST /api/appointments
@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    data = request.get_json(silent=True) or {}

    required = ['user_id', 'service_id', 'appt_datetime']
    if not all(data.get(key) for key in required):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()    
    try:
        user = conn.execute('SELECT 1 FROM user WHERE user_id = ?', (data['user_id'],)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        service = conn.execute('SELECT 1 FROM service WHERE service_id = ?', (data['service_id'],)).fetchone()
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO appointment (user_id, service_id, appt_datetime, appt_status) VALUES (?, ?, ?, 'BOOKED')",
                (data['user_id'], data['service_id'], data['appt_datetime'])
            )
            appt_id = cursor.lastrowid

        create_notification(
            data['user_id'],
            "Your appoinment has been booked successfully."
        )

        return jsonify({'message': 'Appointment created successfully!', 'appointment_id': appt_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# POST /api/queues/walk-in
@app.route('/api/queues/walk-in', methods=['POST'])
def walk_in_queue():
    data = request.get_json(silent=True) or {}
    if not data.get('user_id') or not data.get('service_id'):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT 1 FROM user WHERE user_id = ?', (data['user_id'],)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        service = conn.execute('SELECT store_id FROM service WHERE service_id = ?', (data['service_id'],)).fetchone()
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        store_id = service['store_id']

        conn.execute("BEGIN IMMEDIATE")
        with conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT q.queue_number
                FROM queue q
                JOIN service s ON q.service_id = s.service_id
                WHERE s.store_id = ? AND q.queue_number LIKE 'W-%'
                ORDER BY q.queue_id DESC LIMIT 1
            """, (store_id,))
            last_record = cursor.fetchone()
            next_num = int(last_record['queue_number'].split('-')[1]) + 1 if last_record else 1
            queue_number = f"W-{next_num:03d}"

            cursor.execute(
                "INSERT INTO queue (user_id, service_id, counter_id, queue_number, queue_status) VALUES (?, ?, NULL, ?, 'WAITING')",
                (data['user_id'], data['service_id'], queue_number)
            )
            queue_id = cursor.lastrowid

            create_notification(
                data['user_id'],
                f"You have successfully joined the queue. Your queue number is {queue_number}."
            )

        socketio.emit('queue_status_updated', {'queue_id': queue_id}, to=f"store_{store_id}")

        return jsonify({'message': 'Successfully joined the walk-in queue!', 'queue_id': queue_id, 'queue_number': queue_number}),201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# PUT /api/appointments/<appt_id>/check-in
@app.route('/api/appointments/<int:appt_id>/check-in', methods=['PUT'])
def check_in_appointment(appt_id):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        with conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM appointment WHERE appt_id = ?", (appt_id,))
            appt = cursor.fetchone()

            if not appt:
                return jsonify({'error': 'Appointment not found'}), 404
            if appt['appt_status'] != 'BOOKED':
                return jsonify({'error': 'Appointment cannot be checked in'}), 400

            service = cursor.execute("SELECT store_id FROM service WHERE service_id = ?", (appt['service_id'],)).fetchone()

            if not service:
                return jsonify({'error': 'Service linked to this appointment no longer exists'}), 400
            
            store_id = service['store_id']

            cursor.execute("""
                SELECT q.queue_number
                FROM queue q
                JOIN service s ON q.service_id = s.service_id
                WHERE s.store_id = ? AND q.queue_number LIKE 'A-%'
                ORDER BY q.queue_id DESC LIMIT 1
            """, (store_id,))
            last_record = cursor.fetchone()
            next_num = int(last_record['queue_number'].split('-')[1]) + 1 if last_record else 1
            queue_number = f"A-{next_num:03d}"

            cursor.execute("UPDATE appointment SET appt_status = 'CHECKED_IN' WHERE appt_id = ?", (appt_id,))
            cursor.execute(
                "INSERT INTO queue (user_id, service_id, counter_id, queue_number, queue_status) VALUES (?, ?, NULL, ?, 'WAITING')",
                (appt['user_id'], appt['service_id'], queue_number)
            )
            queue_id = cursor.lastrowid

        socketio.emit('queue_status_updated', {'queue_id': queue_id}, to=f"store_{store_id}")

        return jsonify({'message': 'Appointment checked in successfully!', 'queue_id': queue_id, 'queue_number': queue_number}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GET /api/queues/my-status
@app.route('/api/queues/my-status', methods=['GET'])
def get_my_queue_status():
    queue_id = request.args.get('queue_id', type=int)
    if not queue_id:
        return jsonify({'error': 'Missing queue_id parameter'}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.queue_status, q.queue_number, q.service_id, q.counter_id, c.counter_name, s.store_id, s.service_name, st.store_name, st.estimated_wait_time
            FROM queue q
            LEFT JOIN counter c ON q.counter_id = c.counter_id
            JOIN service s ON q.service_id = s.service_id
            JOIN store st ON s.store_id = st.store_id
            WHERE q.queue_id = ?
        """, (queue_id,))
        my_queue = cursor.fetchone()

        if not my_queue:
            return jsonify({'error': 'Queue not found'}), 404

        status = my_queue['queue_status']
        queue_number = my_queue['queue_number']

        # If no counter has been assigned yet
        counter_name = my_queue['counter_name'] or '-'

        if status != 'WAITING':
            return jsonify({
                'queue_number': queue_number,
                'status': status,
                'counter_name': counter_name,
                'people_ahead': 0,
                'wait_time': 0,
                'store_id': my_queue['store_id'],
                'store_name': my_queue['store_name'],
                'service_name': my_queue['service_name']
            }), 200

        cursor.execute(
            "SELECT COUNT(*) AS people_ahead FROM queue WHERE service_id = ? AND queue_status = 'WAITING' AND queue_id < ?",
            (my_queue['service_id'], queue_id)
        )
        people_ahead = cursor.fetchone()['people_ahead']
        db_time = my_queue['estimated_wait_time']
        per_person_time = db_time if db_time else 5
        wait_time = (people_ahead + 1) * per_person_time

        return jsonify({
            'queue_number': queue_number,
            'status': status,
            'counter_name': counter_name,
            'people_ahead': people_ahead,
            'wait_time': wait_time,
            'store_id': my_queue['store_id'],
            'store_name': my_queue['store_name'],
            'service_name': my_queue['service_name']
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GET /api/notifications
@app.route('/api/notifications', methods=['GET'])
def get_notification():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'Missing user_id parameter'}), 400

    conn = get_db_connection()
    try:
        notifications = conn.execute(
            """
            SELECT notification_id, message, is_read
            FROM notification
            WHERE user_id = ?
            ORDER BY notification_id DESC
            """,
            (user_id,)
        ).fetchall()

        return jsonify([
            {
                'notification_id': notification['notification_id'],
                'message': notification['message'],
                'is_read': notification['is_read']
            }
            for notification in notifications
        ]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Page Routes
@app.route('/booking')
def booking_page():
    return render_template('booking.html')

@app.route('/check-in')
def check_in_page():
    return render_template('check_in.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

# Test Session Route for Development Purposes
@app.route('/set-test-session/<int:user_id>')
def set_test_session(user_id):
    session['user_id'] = user_id
    session['username'] = f'testuser_{user_id}'
    return f"Test session set! You are now logged in as User ID: {user_id}"


#======================================================================
# -- Member 3: Store, Service & Counter API
#======================================================================

# =========================
# SERVICE CRUD API
# =========================

# CREATE - Add a new service
@app.route('/api/services', methods=['POST'])
def create_service():
    if session.get('role') != 'STAFF':
        return jsonify({'error': 'Staff access required'}), 403

    data = request.get_json()
    store_id = data.get('store_id')
    service_name = data.get('service_name')

    if not store_id or not service_name:
        return jsonify({'error': 'store_id and service_name are required'}), 400

    conn = get_db_connection()

    store = conn.execute(
        'SELECT * FROM store WHERE store_id = ? AND owner_id = ?',
        (store_id, session['user_id'])
    ).fetchone()

    if not store:
        return jsonify({'error': 'You do not have access to this store'}), 403

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO service (store_id, service_name) VALUES (?, ?)",
        (store_id, service_name)
    )
    conn.commit()
    service_id = cursor.lastrowid

    return jsonify({'message': 'Service created successfully', 'service_id': service_id}), 201


# READ - Get all services for a store
@app.route('/api/services/<int:store_id>', methods=['GET'])
def get_services(store_id):
    conn = get_db_connection()

    services = conn.execute(
        """
        SELECT *
        FROM service
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in services
    ]), 200


# UPDATE - Update a service
@app.route('/api/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    data = request.get_json()

    service_name = data.get('service_name')

    if not service_name:
        return jsonify({
            'error': 'service_name is required'
        }), 400

    conn = get_db_connection()

    # Check whether service exists
    service = conn.execute(
        'SELECT * FROM service WHERE service_id = ?',
        (service_id,)
    ).fetchone()

    if not service:
        return jsonify({
            'error': 'Service not found'
        }), 404

    # Update service
    conn.execute(
        """
        UPDATE service
        SET service_name = ?
        WHERE service_id = ?
        """,
        (service_name, service_id)
    )

    conn.commit()

    return jsonify({
        'message': 'Service updated successfully'
    }), 200


# DELETE - Delete a service
@app.route('/api/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    conn = get_db_connection()

    # Check whether service exists
    service = conn.execute(
        'SELECT * FROM service WHERE service_id = ?',
        (service_id,)
    ).fetchone()

    if not service:
        return jsonify({
            'error': 'Service not found'
        }), 404

    # Delete service
    conn.execute(
        'DELETE FROM service WHERE service_id = ?',
        (service_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Service deleted successfully'
    }), 200

# =========================
# COUNTER CRUD API
# =========================

# CREATE - Add a new counter
@app.route('/api/counters', methods=['POST'])
def create_counter():
    if session.get('role') != 'STAFF':
        return jsonify({'error': 'Staff access required'}), 403

    data = request.get_json()
    store_id = data.get('store_id')
    counter_name = data.get('counter_name')

    if not store_id or not counter_name:
        return jsonify({'error': 'store_id and counter_name are required'}), 400

    conn = get_db_connection()

    store = conn.execute(
        'SELECT * FROM store WHERE store_id = ? AND owner_id = ?',
        (store_id, session['user_id'])
    ).fetchone()

    if not store:
        return jsonify({'error': 'You do not have access to this store'}), 403

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO counter (store_id, counter_name) VALUES (?, ?)",
        (store_id, counter_name)
    )
    conn.commit()
    counter_id = cursor.lastrowid

    return jsonify({'message': 'Counter created successfully', 'counter_id': counter_id}), 201


# READ - Get all counters for a store
@app.route('/api/counters/<int:store_id>', methods=['GET'])
def get_counters(store_id):
    conn = get_db_connection()

    counters = conn.execute(
        """
        SELECT * FROM counter
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in counters
    ]), 200


# UPDATE - Edit counter name and status
@app.route('/api/counters/<int:counter_id>', methods=['PUT'])
def update_counter(counter_id):
    data = request.get_json()

    counter_name = data.get('counter_name')
    counter_status = data.get('counter_status')

    if not counter_name or not counter_status:
        return jsonify({
            'error': 'counter_name and counter_status are required'
        }), 400

    conn = get_db_connection()

    counter = conn.execute(
        'SELECT * FROM counter WHERE counter_id = ?',
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    conn.execute(
        """
        UPDATE counter
        SET counter_name = ?,
            counter_status = ?
        WHERE counter_id = ?
        """,
        (counter_name, counter_status, counter_id)
    )

    conn.commit()

    return jsonify({
        'message': 'Counter updated successfully'
    }), 200


# DELETE - Remove a counter
@app.route('/api/counters/<int:counter_id>', methods=['DELETE'])
def delete_counter(counter_id):

    conn = get_db_connection()

    counter = conn.execute(
        'SELECT * FROM counter WHERE counter_id = ?',
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    conn.execute(
        'DELETE FROM counter WHERE counter_id = ?',
        (counter_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Counter deleted successfully'
    }), 200

# =========================
# COUNTER OPEN / CLOSE
# =========================

@app.route('/api/counters/<int:counter_id>/status', methods=['PATCH'])
def update_counter_status(counter_id):
    data = request.get_json()

    counter_status = data.get('counter_status')

    # Only allow open or closed
    if counter_status not in ['open', 'closed']:
        return jsonify({
            'error': 'counter_status must be open or closed'
        }), 400

    conn = get_db_connection()

    # Check whether counter exists
    counter = conn.execute(
        'SELECT * FROM counter WHERE counter_id = ?',
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Update counter status
    conn.execute(
        """
        UPDATE counter
        SET counter_status = ?
        WHERE counter_id = ?
        """,
        (counter_status, counter_id)
    )

    conn.commit()

    return jsonify({
        'message': f'Counter status updated to {counter_status}',
        'counter_id': counter_id,
        'counter_status': counter_status
    }), 200

#----------------------------------------------------------------------
# Store CRUD API
#----------------------------------------------------------------------

# READ - Get all stores
@app.route('/api/stores', methods=['GET'])
def get_stores():
    conn = get_db_connection()

    stores = conn.execute(
        'SELECT * FROM store'
    ).fetchall()


    return jsonify([dict(row) for row in stores]), 200

# CREATE - Add a new store
@app.route('/api/stores', methods=['POST'])
def create_store():
    data = request.get_json()

    store_name = data.get('store_name')
    store_status = data.get('store_status', 'PENDING')
    operating_hours = data.get('operating_hours')
    estimated_wait_time = data.get('estimated_wait_time', 0)

    if not store_name:
        return jsonify({
            'error': 'store_name is required'
        }), 400

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO store
        (store_name, store_status, operating_hours, estimated_wait_time)
        VALUES (?, ?, ?, ?)
        """,
        (
            store_name,
            store_status,
            operating_hours,
            estimated_wait_time
        )
    )

    conn.commit()

    store_id = cursor.lastrowid


    return jsonify({
        'message': 'Store created successfully',
        'store_id': store_id
    }), 201

# UPDATE - Update an existing store
@app.route('/api/stores/<int:store_id>', methods=['PUT'])
def update_store(store_id):
    data = request.get_json()

    store_name = data.get('store_name')
    store_status = data.get('store_status')
    operating_hours = data.get('operating_hours')
    estimated_wait_time = data.get('estimated_wait_time')

    conn = get_db_connection()

    existing_store = conn.execute(
        'SELECT * FROM store WHERE store_id = ?',
        (store_id,)
    ).fetchone()

    if not existing_store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    conn.execute(
        """
        UPDATE store
        SET store_name = ?,
            store_status = ?,
            operating_hours = ?,
            estimated_wait_time = ?
        WHERE store_id = ?
        """,
        (
            store_name,
            store_status,
            operating_hours,
            estimated_wait_time,
            store_id
        )
    )

    conn.commit()

    return jsonify({
        'message': 'Store updated successfully'
    }), 200

# DELETE - Delete a store
@app.route('/api/stores/<int:store_id>', methods=['DELETE'])
def delete_store(store_id):
    conn = get_db_connection()

    existing_store = conn.execute(
        'SELECT * FROM store WHERE store_id = ?',
        (store_id,)
    ).fetchone()

    if not existing_store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    conn.execute(
        'DELETE FROM store WHERE store_id = ?',
        (store_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Store deleted successfully'
    }), 200

# Store approval or rejection by admin
@app.route('/api/stores/<int:store_id>/status', methods=['PATCH'])
def update_store_status(store_id):

    if session.get('role') != 'ADMIN':
        return jsonify({
            'error': 'Admin access required'
        }), 403

    data = request.get_json() or {}

    new_status = data.get('store_status')

    if new_status not in ['PENDING', 'APPROVED', 'REJECTED']:
        return jsonify({
            'error': 'Invalid store status'
        }), 400

    conn = get_db_connection()

    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchone()

    if not store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    conn.execute(
        """
        UPDATE store
        SET store_status = ?
        WHERE store_id = ?
        """,
        (
            new_status,
            store_id
        )
    )

    conn.commit()

    return jsonify({
        'message': 'Store status updated successfully',
        'store_id': store_id,
        'store_status': new_status
    }), 200
    
# Pending Stores API
@app.route('/api/stores/pending', methods=['GET'])
def get_pending_stores():

    if session.get('role') != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403

    conn = get_db_connection()

    stores = conn.execute(
        """
        SELECT
            store.store_id,
            store.store_name,
            store.operating_hours,
            store.store_status,
            store.owner_id,
            user.username
        FROM store
        JOIN user
        ON store.owner_id = user.user_id
        WHERE store.store_status = 'PENDING'
        ORDER BY store.store_id DESC
        """
    ).fetchall()


    return jsonify([
        dict(store)
        for store in stores
    ]), 200
    
# =========================
# STAFF QUEUE CONTROL API
# =========================

# CALL NEXT CUSTOMER
@app.route('/api/counters/<int:counter_id>/call-next', methods=['POST'])
def call_next_customer(counter_id):

    conn = get_db_connection()

    # Check whether counter exists
    counter = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE counter_id = ?
        """,
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Check whether counter is open
    if counter['counter_status'] != 'open':
        return jsonify({
            'error': 'Counter is closed'
        }), 400

    # Find the next waiting customer assigned to this counter
    queue = conn.execute(
        """
        SELECT q.*
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        ORDER BY q.queue_id ASC
        LIMIT 1
        """,
        (counter['store_id'],)
    ).fetchone()

    if not queue:
        return jsonify({
            'message': 'No customers waiting'
        }), 404

    # Change queue status to SERVING
    conn.execute(
        """
        UPDATE queue
        SET counter_id = ?,
            queue_status = 'SERVING'
        WHERE queue_id = ?
        """,
        (counter_id, queue['queue_id'])
    )

    conn.commit()

    # Member 2 (Eugene): Notification thorugh email
    user_info = conn.execute(
        """
        SELECT u.email, u.username, c.counter_name, s.store_name
        FROM queue q
        JOIN user u ON q.user_id = u.user_id
        JOIN counter c ON c.counter_id = ?
        JOIN service serv ON q.service_id = serv.service_id
        JOIN store s ON serv.store_id = s.store_id
        WHERE q.queue_id = ?
        """,
        (counter_id, queue['queue_id'])
    ).fetchone()

    if user_info and user_info['email']:
        try:
            msg = Message(
                f"It's your turn at {user_info['store_name']}!",
                recipients=[user_info['email']]
            )
            msg.body = f"Hello {user_info['username']},\n\nIt is now your turn! Please proceed to {user_info['counter_name']} immediately.\n\nThank you for using Queues!"
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send turn notification email: {e}")

    # Get updated queue
    updated_queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue['queue_id'],)
    ).fetchone()

    socketio.emit('queue_status_updated', {'queue_id': queue['queue_id']}, to=f"store_{counter['store_id']}")
    
    return jsonify({
        'message': 'Next customer called successfully',
        'queue': dict(updated_queue)
    }), 200


# SKIP CUSTOMER
@app.route('/api/queues/<int:queue_id>/skip', methods=['PATCH'])
def skip_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Only SERVING customer can be skipped
    if queue['queue_status'] != 'SERVING':
        return jsonify({
            'error': 'Only a serving customer can be skipped'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET queue_status = 'SKIPPED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Customer skipped successfully',
        'queue_id': queue_id,
        'status': 'SKIPPED'
    }), 200


# RECALL CUSTOMER
@app.route('/api/queues/<int:queue_id>/recall', methods=['PATCH'])
def recall_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Customer must currently be SERVING
    if queue['queue_status'] != 'SERVING':
        return jsonify({
            'error': 'Only a serving customer can be recalled'
        }), 400

    return jsonify({
        'message': 'Customer recalled successfully',
        'queue_id': queue_id,
        'queue_number': queue['queue_number'],
        'status': 'SERVING'
    }), 200


# COMPLETE CUSTOMER SERVICE
@app.route('/api/queues/<int:queue_id>/complete', methods=['PATCH'])
def complete_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Only SERVING customer can be completed
    if queue['queue_status'] != 'SERVING':
        return jsonify({
            'error': 'Only a serving customer can be completed'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET queue_status = 'COMPLETED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Service completed successfully',
        'queue_id': queue_id,
        'status': 'COMPLETED'
    }), 200


# CANCEL QUEUE
@app.route('/api/queues/<int:queue_id>/cancel', methods=['PATCH'])
def cancel_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT q.*, s.store_id
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE q.queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Cannot cancel completed/skipped/cancelled queue
    if queue['queue_status'] in ['COMPLETED', 'SKIPPED', 'CANCELLED']:
        return jsonify({
            'error': 'Queue can no longer be cancelled'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET queue_status = 'CANCELLED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()
    conn.close()

    socketio.emit('queue_status_updated', {'queue_id': queue_id}, to=f"store_{queue['store_id']}")

    return jsonify({
        'message': 'Queue cancelled successfully',
        'queue_id': queue_id,
        'status': 'CANCELLED'
    }), 200

# =========================
# QUEUE STATUS & HISTORY API
# =========================

# GET - View current queue for a counter
@app.route('/api/counters/<int:counter_id>/queue', methods=['GET'])
def get_counter_queue(counter_id):

    conn = get_db_connection()

    # Check whether counter exists
    counter = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE counter_id = ?
        """,
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Get queues for this counter
    queues = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE counter_id = ?
        AND queue_status IN ('WAITING', 'SERVING')
        ORDER BY queue_id ASC
        """,
        (counter_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in queues
    ]), 200

# GET - View queue history
@app.route('/api/queues/history', methods=['GET'])
def get_queue_history():

    conn = get_db_connection()

    queues = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_status IN ('COMPLETED', 'SKIPPED', 'CANCELLED')
        ORDER BY queue_id DESC
        """
    ).fetchall()


    return jsonify([
        dict(row) for row in queues
    ]), 200

# GET - View queue status summary
@app.route('/api/counters/<int:counter_id>/queue/status', methods=['GET'])
def get_queue_status(counter_id):

    conn = get_db_connection()

    # Check counter
    counter = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE counter_id = ?
        """,
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Find currently serving customer
    serving = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE counter_id = ?
        AND queue_status = 'SERVING'
        ORDER BY queue_id ASC
        LIMIT 1
        """,
        (counter_id,)
    ).fetchone()

    # Count waiting customers
    waiting = conn.execute(
        """
        SELECT COUNT(*) AS waiting_count
        FROM queue
        WHERE counter_id = ?
        AND queue_status = 'WAITING'
        """,
        (counter_id,)
    ).fetchone()


    return jsonify({
        'counter_id': counter_id,
        'serving': dict(serving) if serving else None,
        'waiting_count': waiting['waiting_count']
    }), 200

# GET - View status history for one queue
@app.route('/api/queues/<int:queue_id>/history', methods=['GET'])
def get_queue_status_history(queue_id):

    conn = get_db_connection()

    history = conn.execute(
        """
        SELECT *
        FROM queue_history
        WHERE queue_id = ?
        ORDER BY timestamp ASC
        """,
        (queue_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in history
    ]), 200

# =========================
# STAFF DASHBOARD API
# =========================

@app.route('/api/staff/dashboard/<int:store_id>', methods=['GET'])
def get_staff_dashboard(store_id):

    conn = get_db_connection()

    # Check whether store exists
    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchone()

    if not store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    # Get all counters for this store
    counters = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchall()

    # Count waiting customers
    waiting = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        """,
        (store_id,)
    ).fetchone()

    # Count currently serving
    serving = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'SERVING'
        """,
        (store_id,)
    ).fetchone()

    # Count completed
    completed = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'COMPLETED'
        """,
        (store_id,)
    ).fetchone()

    # Count skipped
    skipped = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'SKIPPED'
        """,
        (store_id,)
    ).fetchone()

    # Count cancelled
    cancelled = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'CANCELLED'
        """,
        (store_id,)
    ).fetchone()


    return jsonify({
        'store': dict(store),

        'counters': [
            dict(counter)
            for counter in counters
        ],

        'queue_summary': {
            'waiting': waiting['total'],
            'serving': serving['total'],
            'completed': completed['total'],
            'skipped': skipped['total'],
            'cancelled': cancelled['total']
        }
    }), 200


if __name__ == '__main__':
    with app.app_context():
        init_db()
        create_admin()

    socketio.run(app, debug=True, port=5000)