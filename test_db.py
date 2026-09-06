import sqlite3
connection = sqlite3.connect('queue_system.db')
with open('schema.sql') as f:
    connection.executescript(f.read())
cur = connection.cursor()

# Adding test values

cur.execute("INSERT INTO store (store_name, operating_hours, store_status) VALUES ('Trading Cardz Haven', '9 AM - 5PM', 'APPROVED')")

cur.execute("INSERT INTO user (username, password, role) VALUES ('testuser', 'password123', 'CUSTOMER')")

# For Testing (Member 2)
cur.execute("INSERT INTO service (store_id, service_name) VALUES (1, 'Card Authentication')")
cur.execute("INSERT INTO counter (store_id, counter_name, counter_status) VALUES (1, 'Counter 1', 'open')")

connection.commit()
connection.close()

print ("Database created successfully.")