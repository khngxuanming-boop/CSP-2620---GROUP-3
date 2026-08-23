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
        stores = conn.execute('SELECT * FROM store WHERE name LIKE ?', ('%' + search_query + '%',)).fetchall()
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
        conn.execute('INSERT INTO store (name, operating_hours, status) VALUES (?, ?, ?)', (store_name, hours, 'PENDING'))
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
# -- Member 3: Service & Counter Api
#======================================================================



if __name__ == '__main__':
    init_db()
    print("Database initialized successfully from schema.sql")
    app.run(debug=True, port=5000)