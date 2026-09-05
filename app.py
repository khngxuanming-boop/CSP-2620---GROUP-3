import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'sphinx of black quartz judge my vow'
DB_NAME = 'queue_system.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

#======================================================================
# -- Member 1 (Syahmi): User & Store Api
#======================================================================

# Store Discovery Engine
@app.route('/stores')
def store_discovery():
    # Check if they are logged in. ---> Week 3; Check authentication
    if 'user_id' not in session:
        # If not logged in, redirect to login page instead.
        return redirect(url_for('login'))

    # Grab searched text from the web address (if user typed something)
    search_query = request.args.get('search', '')

    # Grab the logged in user's name from memory
    current_username = session.get('username')

    conn = get_db_connection()
    if search_query:
        # Search the database for stores matching text typed by the customer
        stores = conn.execute('SELECT * FROM store WHERE store_name LIKE ?', ('%' + search_query + '%',)).fetchall()
    else:
        # If no search was made, select all store in the database instead
        stores = conn.execute('SELECT * FROM store').fetchall()
    conn.close()

    # Pass the username to HTML template
    return render_template('stores.html', stores=stores, search_query=search_query, username=current_username)

# User Registration

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        # Receive what they typed in the boxes
        username = request.form['username']
        password = request.form['password']

        # Grab the role they picked from the dropdown menu/
        role = request.form.get('role', 'CUSTOMER')

        conn = get_db_connection()
         # Check if username already exists
        existing_user = conn.execute('SELECT * FROM user WHERE username =?', (username,)).fetchone()

        if existing_user:
            error = "That username is already taken! Choose another one."
            conn.close() # Close since failed.
        else:
        # Save into the database as 'CUSTOMER'
            conn.execute('INSERT INTO user (username, password, role) VALUES (?, ?, ?)' , (username, password, 'CUSTOMER'))
            conn.commit()
            conn.close()

        # ONLY send them to login page if success
        return redirect(url_for('login'))

    # If it's a GET request or if there was an error, show the page with the error message
    return render_template('register.html', error=error)

# User Login
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        # Search for the exact username and password
        user = conn.execute('SELECT * FROM user WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()

    if user:
        # Match found ----> Week 3; Remember the user
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['role'] = user['role']

        return redirect(url_for('store_discovery'))
    else: 
        # Match not found
        error = "Incorrect password or username. Please try again!"
    return render_template('login.html', error=error)

# Store registration
@app.route('/register_store', methods=['GET', 'POST'])
def register_store():
    # If the business owner clicks "Submit"
    if request.method == 'POST':
        store_name = request.form['name']
        hours = request.form['hours']
        
        conn = get_db_connection()
        # Insert the new store, automatically setting its status to 'Pending'
        conn.execute('INSERT INTO store (store_name, operating_hours, store_status) VALUES (?, ?, ?)', (store_name, hours, 'PENDING'))
        conn.commit()
        conn.close()
        
        return redirect(url_for('store_discovery'))
    # Show the blank store registration form    
    return render_template('register_store.html')

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
    services = conn.execute('SELECT * FROM service WHERE store_id = ?', (store_id)).fetchall()

    conn.close()

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
# POST /api/appointments
@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    data = request.get_json()

    required = ['user_id', 'service_id', 'appt_datetime']
    if not all(data.get(key) for key in required):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()    
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO appointment (user_id, service_id, appt_datetime, status) VALUES (?, ?, ?, 'BOOKED')",
                (data['user_id'], data['service_id'], data['appt_datetime'])
            )
            appt_id = cursor.lastrowid

        return jsonify({'message': 'Appointment created successfully!', 'appointment_id': appt_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# POST /api/queues/walk-in
@app.route('/api/queues/walk-in', methods=['POST'])
def walk_in_queue():
    data = request.get_json()
    if not data.get('user_id') or not data.get('service_id'):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()

            cursor.execute("SELECT queue_number FROM queue WHERE queue_number LIKE 'W-%' ORDER BY id DESC LIMIT 1")
            last_record = cursor.fetchone()
            next_num = int(last_record['queue_number'].split('-')[1]) + 1 if last_record else 1
            queue_number = f"W-{next_num:03d}"

            cursor.execute(
                "INSERT INTO queue (user_id, service_id, counter_id, queue_number, status) VALUES (?, ?, NULL, ?, 'WAITING')",
                (data['user_id'], data['service_id'], queue_number)
            )
            queue_id = cursor.lastrowid

        return jsonify({'message': 'Successfully joined the walk-in queue!', 'queue_id': queue_id, 'queue_number': queue_number}),201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# PUT /api/appointments/<appt_id>/check-in
@app.route('/api/appointments/<int:appt_id>/check-in', methods=['PUT'])
def check_in_appointment(appt_id):
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM appointment WHERE id = ?", (appt_id,))
            appt = cursor.fetchone()

            if not appt:
                return jsonify({'error': 'Appointment not found'}), 404
            if appt['status'] != 'BOOKED':
                return jsonify({'error': 'Appointment cannot be checked in'}), 400

            cursor.execute("SELECT queue_number FROM queue WHERE queue_number LIKE 'A-%' ORDER BY id DESC LIMIT 1")
            last_record = cursor.fetchone()
            next_num = int(last_record['queue_number'].split('-')[1]) + 1 if last_record else 1
            queue_number = f"A-{next_num:03d}"

            cursor.execute("UPDATE appointment SET status = 'CHECKED_IN' WHERE id = ?", (appt_id,))
            cursor.execute(
                "INSERT INTO queue (user_id, service_id, counter_id, queue_number, status) VALUES (?, ?, NULL, ?, 'WAITING')",
                (appt['user_id'], appt['service_id'], queue_number)
            )
            queue_id = cursor.lastrowid

        return jsonify({'message': 'Appointment checked in successfully!', 'queue_id': queue_id, 'queue_number': queue_number}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
  
#======================================================================
# -- Member 3: Store, Service & Counter API
#======================================================================

# =========================
# SERVICE CRUD API
# =========================

# CREATE - Add a new service
@app.route('/api/services', methods=['POST'])
def create_service():
    data = request.get_json()

    store_id = data.get('store_id')
    service_name = data.get('service_name')

    # Check required fields
    if not store_id or not service_name:
        return jsonify({
            'error': 'store_id and service_name are required'
        }), 400

    conn = get_db_connection()

    # Check whether the store exists
    store = conn.execute(
        'SELECT * FROM store WHERE store_id = ?',
        (store_id,)
    ).fetchone()

    if not store:
        conn.close()
        return jsonify({
            'error': 'Store not found'
        }), 404

    # Insert service
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO service (store_id, service_name)
        VALUES (?, ?)
        """,
        (store_id, service_name)
    )

    conn.commit()

    service_id = cursor.lastrowid

    conn.close()

    return jsonify({
        'message': 'Service created successfully',
        'service_id': service_id
    }), 201


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

    conn.close()

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
        conn.close()
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
    conn.close()

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
        conn.close()
        return jsonify({
            'error': 'Service not found'
        }), 404

    # Delete service
    conn.execute(
        'DELETE FROM service WHERE service_id = ?',
        (service_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Service deleted successfully'
    }), 200

# =========================
# COUNTER CRUD API
# =========================

# CREATE - Add a new counter
@app.route('/api/counters', methods=['POST'])
def create_counter():
    data = request.get_json()

    store_id = data.get('store_id')
    counter_name = data.get('counter_name')

    if not store_id or not counter_name:
        return jsonify({
            'error': 'store_id and counter_name are required'
        }), 400

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO counter (store_id, counter_name)
        VALUES (?, ?)
        """,
        (store_id, counter_name)
    )

    conn.commit()
    counter_id = cursor.lastrowid
    conn.close()

    return jsonify({
        'message': 'Counter created successfully',
        'counter_id': counter_id
    }), 201


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

    conn.close()

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
        conn.close()
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
    conn.close()

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
        conn.close()
        return jsonify({
            'error': 'Counter not found'
        }), 404

    conn.execute(
        'DELETE FROM counter WHERE counter_id = ?',
        (counter_id,)
    )

    conn.commit()
    conn.close()

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
        conn.close()
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
    conn.close()

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

    conn.close()

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

    conn.close()

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
        conn.close()
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
    conn.close()

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
        conn.close()
        return jsonify({
            'error': 'Store not found'
        }), 404

    conn.execute(
        'DELETE FROM store WHERE store_id = ?',
        (store_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Store deleted successfully'
    }), 200

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
        conn.close()
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Check whether counter is open
    if counter['counter_status'] != 'open':
        conn.close()
        return jsonify({
            'error': 'Counter is closed'
        }), 400

    # Find the next waiting customer assigned to this counter
    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE counter_id = ?
        AND status = 'WAITING'
        ORDER BY queue_id ASC
        LIMIT 1
        """,
        (counter_id,)
    ).fetchone()

    if not queue:
        conn.close()
        return jsonify({
            'message': 'No customers waiting'
        }), 404

    # Change queue status to SERVING
    conn.execute(
        """
        UPDATE queue
        SET status = 'SERVING'
        WHERE queue_id = ?
        """,
        (queue['queue_id'],)
    )

    conn.commit()

    # Get updated queue
    updated_queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue['queue_id'],)
    ).fetchone()

    conn.close()

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
        conn.close()
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Only SERVING customer can be skipped
    if queue['status'] != 'SERVING':
        conn.close()
        return jsonify({
            'error': 'Only a serving customer can be skipped'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET status = 'SKIPPED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()
    conn.close()

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
        conn.close()
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Customer must currently be SERVING
    if queue['status'] != 'SERVING':
        conn.close()
        return jsonify({
            'error': 'Only a serving customer can be recalled'
        }), 400

    conn.close()

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
        conn.close()
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Only SERVING customer can be completed
    if queue['status'] != 'SERVING':
        conn.close()
        return jsonify({
            'error': 'Only a serving customer can be completed'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET status = 'COMPLETED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()
    conn.close()

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
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        conn.close()
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Cannot cancel completed/skipped/cancelled queue
    if queue['status'] in ['COMPLETED', 'SKIPPED', 'CANCELLED']:
        conn.close()
        return jsonify({
            'error': 'Queue can no longer be cancelled'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET status = 'CANCELLED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Queue cancelled successfully',
        'queue_id': queue_id,
        'status': 'CANCELLED'
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
