-- Member 1 (Syahmi): user table
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'CUSTOMER'
);
-- Member 1 (Syahmi): store table
CREATE TABLE IF NOT EXISTS store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    operating_hours TEXT,
    estimated_wait_time INTEGER DEFAULT 0
);
-- (Member 3 will write the CREATE TABLE service here...)
-- (Member 3 will write the CREATE TABLE counter here...)

-- Member 2(Eugene): appoinment table
CREATE TABLE IF NOT EXISTS appointment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    appt_datetime DATETIME NOT NULL,
    status TEXT DEFAULT 'BOOKED',
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (service_id) REFERENCES service(id)
);

-- Member 2(Eugene): queue table
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    counter_id INTEGER,
    queue_number TEXT NOT NULL,
    status TEXT DEFAULT 'WAITING',
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (service_id) REFERENCES service(id),
    FOREIGN KEY (counter_id) REFERENCES counter(id)
);

-- (Member 3 will write the CREATE TABLE queue_history here...)

-- Member 2(Eugene): notification table
CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES user(id)
);