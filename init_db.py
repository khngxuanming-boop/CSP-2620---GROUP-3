import sqlite3
connection = sqlite3.connect('queue_system.db')
with open('schema.sql') as f:
    connection.executescript(f.read())
cur = connection. cursor()

# Adding test values

cur.execute("INSERT INTO store (name, operating_hours, status) VALUES ('Trading Cardz Haven', '9 AM - 5PM', 'APPROVED')")

cur.execute("INSERT INTO user (username, password, role) VALUES ('testuser', 'password123', 'CUSTOMER')")

connection.commit()
connection.close()

print ("Databse created successfully.")