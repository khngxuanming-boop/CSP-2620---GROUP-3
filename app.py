import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for

app = Flask(__name__)
DB_NAME = 'queue_system.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with open('schema.sql') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

#======================================================================
# -- Member 1 (Syahmi): User & Store Api
#======================================================================

# Store Discovery/Main Page
@app.route('/')
def store_discovery():
    # Grab searched text from the web address (if user typed something)
    search_query = request.args.get('search', '')

    conn = get_db_connection()
    if search_query:
        # Search the database for stores matching text typed by the customer
        stores = conn.execute('SELECT * FROM store WHERE store_name LIKE ?', ('%' + search_query + '%',)).fetchall()
    else:
        # If no search was made, select all store in the database instead
        stores = conn.execute('SELECT * FROM store').fetchall()
    conn.close()

    return render_template('stores.html', stores=stores, search_query=search_query)

# User Registration

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        #Receive what they typed in the boxes
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        #Save into the database as 'CUSTOMER'
        conn.execute('INSERT INTO user (username, password, role) VALUES (?, ?, ?)' , (username, password, 'CUSTOMER'))
        conn.commit()
        conn.close()

    # Send them to login page
        return redirect(url_for('login'))

    return render_template('register.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        # Search for the exact username and password
        user = conn.execute('SELECT * FROM user WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()

    if user:
        # Match found
        return redirect(url_for('store_discovery'))
    else: 
        # Match not found
        return "Incorrect password or username. Please try again!"
    return render_template('login.html')

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

#======================================================================
# -- Member 2(Eugene): Appointment & Queue Api
#======================================================================
# W1 T2: POST /api/appointments
@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    data = request.get_json()

    user_id = data.get('user_id')
    service_id = data.get('service_id')
    appt_datetime = data.get('appt_datetime')

    if not user_id or not service_id or not appt_datetime:
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO appointment (user_id, service_id, appt_datetime, status)
            VALUES (?, ?, ?, 'BOOKED')
            """,
            (user_id, service_id, appt_datetime),
        )
        conn.commit()
        appt_id = cursor.lastrowid
        conn.close()

        return (
            jsonify({
                'message': 'Appointment created successfully!',
                'appointment_id': appt_id
            }),
            201
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# W1 T3: POST /api/queues/walk-in
@app.route('/api/queues/walk-in', methods=['POST'])
def walk_in_queue():
    data = request.get_json()

    user_id = data.get('user_id')
    service_id = data.get('service_id')
    counter_id = data.get('counter_id')

    if not user_id or not service_id:
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM queue")
        count = cursor.fetchone()[0]
        queue_number = f"Q{count + 1:03d}"

        cursor.execute(
            """
            INSERT INTO queue (user_id, service_id, counter_id, queue_number, status)
            VALUES (?, ?, ?, ?, 'WAITING')
            """,
            (user_id, service_id, counter_id, queue_number)
        )
        conn.commit()
        queue_id = cursor.lastrowid
        conn.close()

        return (
            jsonify({
                'message': 'Successfully joined the walk-in queue!',
                'queue_id': queue_id,
                'queue_number': queue_number,
            }),
            201
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    
#======================================================================
# -- Member 3: Store, Service & Counter API
#======================================================================

# Service management api

@app.route('/api/service', methods=['POST'])
def create_service():
    """Create a new service for a store"""
    data = request.get_json()
    store_id = data.get('store_id')
    service_name = data.get('service_name')

    if not store_id or not service_name:
        return jsonify({'error': 'store_id and service_name are required'}), 400

    conn = get_db_connection() # Replace with your actual DB helper function
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Service (store_id, service_name) VALUES (?, ?)",
        (store_id, service_name)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'Service created successfully'}), 201


@app.route('/api/services/<int:store_id>', methods=['GET'])
def get_services(store_id):
    """Get all services belonging to a specific store"""
    conn = get_db_connection()
    services = conn.execute(
        "SELECT * FROM Service WHERE store_id = ?", (store_id,)
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in services]), 200

# Counter managment api

@app.route('/api/counter', methods=['POST'])
def create_counter():
    """Create a new counter and assign a service"""
    data = request.get_json()
    store_id = data.get('store_id')
    counter_name = data.get('counter_name') # e.g., "Counter 1"
    service_id = data.get('service_id')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Counter (store_id, counter_name, service_id, status) VALUES (?, ?, ?, 'closed')",
        (store_id, counter_name, service_id)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'Counter created successfully'}), 201


@app.route('/api/counter/<int:counter_id>/status', methods=['PATCH'])
def toggle_counter_status(counter_id):
    """Open or close a counter"""
    data = request.get_json()
    new_status = data.get('status') # 'open' or 'closed'

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Counter SET status = ? WHERE counter_id = ?",
        (new_status, counter_id)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': f'Counter status updated to {new_status}'}), 200

# Store CRUD API

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

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
