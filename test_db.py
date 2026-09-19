import sqlite3
connection = sqlite3.connect('queue_system.db')
connection.execute("PRAGMA foreign_keys = ON;")

with open('schema.sql') as f:
    connection.executescript(f.read())
cur = connection.cursor()

# Adding test values

cur.execute("INSERT INTO store (store_name, operating_hours, store_status) VALUES ('Trading Cardz Haven', '9 AM - 5PM', 'APPROVED')")

cur.execute("INSERT INTO user (username, password, role) VALUES ('testuser', 'password123', 'CUSTOMER')")

# For Testing (Member 2)
cur.execute("INSERT INTO service (store_id, service_name) VALUES (1, 'Card Authentication')")
cur.execute("INSERT INTO counter (store_id, counter_name, counter_status) VALUES (1, 'Counter 1', 'OPEN')")
cur.execute("INSERT INTO appointment (user_id, service_id, appt_datetime, appt_status) VALUES (1, 1, '2026-09-20 14:00:00', 'BOOKED')")
cur.execute("INSERT INTO queue (user_id, service_id, counter_id, queue_number, queue_status) VALUES (1, 1, NULL, 'A-001', 'WAITING')")
cur.execute("INSERT INTO notification (user_id, message, is_read) VALUES (1, 'Your turn is approaching! There are 2 customers ahead.', 0)")

connection.commit()
connection.close()

print ("Database created successfully.")