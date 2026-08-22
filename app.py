import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
DB_NAME = 'database.db'

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



if __name__ == '__main__':
    init_db()
    print("Database initialized successfully from schema.sql")
    app.run(debug=True, port=5000)