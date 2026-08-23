from flask import request, jsonify

# -------------------------------------------------------------------
# SERVICE MANAGEMENT API
# -------------------------------------------------------------------

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