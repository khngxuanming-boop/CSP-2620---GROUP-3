import sqlite3
connection = sqlite3.connect('queue_system.db')
connection.execute("PRAGMA foreign_keys = ON;")

with open('schema.sql') as f:
    connection.executescript(f.read())
cur = connection.cursor()

# Adding test values

cur.execute("INSERT INTO store (store_name, operating_hours, store_status) VALUES ('Trading Cardz Haven', '9 AM - 5PM', 'APPROVED')")
store_id = cur.lastrowid

cur.execute("INSERT INTO user (username, password, role) VALUES ('testuser', 'password123', 'CUSTOMER')")
user_id = cur.lastrowid

# For Testing (Member 2)
cur.execute("INSERT INTO service (store_id, service_name) VALUES (?, 'Card Authentication')", (store_id,))
service_id = cur.lastrowid
cur.execute("INSERT INTO counter (store_id, counter_name, counter_status) VALUES (?, 'Counter 1', 'OPEN')", (store_id,))
counter_id = cur.lastrowid
cur.execute("INSERT INTO appointment (user_id, service_id, appt_datetime, appt_status) VALUES (?, ?, '2026-09-20 14:00:00', 'BOOKED')", (user_id, service_id))
cur.execute("INSERT INTO queue (user_id, service_id, counter_id, queue_number, queue_status) VALUES (?, ?, NULL, 'A-001', 'WAITING')", (user_id, service_id))
cur.execute("INSERT INTO notification (user_id, message, is_read) VALUES (?, 'Your turn is approaching! There are 2 customers ahead.', 0)", (user_id,))

connection.commit()
connection.close()

print ("Database created successfully.")