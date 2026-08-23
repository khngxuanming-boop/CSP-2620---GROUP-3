-- Member 1(Syahmi): user table
CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'CUSTOMER'
);

-- Member 1(Syahmi): store table
CREATE TABLE IF NOT EXISTS store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    operating_hours TEXT,
    estimated_wait_time INTEGER DEFAULT 0
);

-- Member 3(Kh'Ng): service table
CREATE TABLE Service (
    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    FOREIGN KEY (store_id)
    REFERENCES Store(store_id)
);

-- Member 3(Kh'Ng): counter table
CREATE TABLE Counter (
    counter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    counter_name TEXT NOT NULL,
    counter_status TEXT NOT NULL DEFAULT 'Closed',
    FOREIGN KEY (store_id)
    REFERENCES Store(store_id)
);

-- Member 2(Eugene): appoinment table
CREATE TABLE IF NOT EXISTS appointment (
    appt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    appt_datetime DATETIME NOT NULL,
    status TEXT DEFAULT 'BOOKED',
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (service_id) REFERENCES service(service_id)
);

-- Member 2(Eugene): queue table
CREATE TABLE IF NOT EXISTS queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    counter_id INTEGER,
    queue_number TEXT NOT NULL,
    status TEXT DEFAULT 'WAITING',
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (service_id) REFERENCES service(service_id),
    FOREIGN KEY (counter_id) REFERENCES counter(counter_id)
);

-- Member 3(Kh'Ng): queue_history table
CREATE TABLE Queue_History (
    queue_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL,
    status_changed_to TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (queue_id)
    REFERENCES Queue(queue_id)
); 

-- Member 2(Eugene): notification table
CREATE TABLE IF NOT EXISTS notification (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);