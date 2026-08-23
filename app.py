import sqlite3
from flask import Flask, request, jsonify

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
# -- Member 1: User & Store Api
#======================================================================



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

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully from schema.sql")
    app.run(debug=True, port=5000)