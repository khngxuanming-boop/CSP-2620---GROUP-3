-- =========================================
-- Service table
-- =========================================
CREATE TABLE Service (
    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    FOREIGN KEY (store_id)
    REFERENCES Store(store_id)
);


-- =========================================
-- Counter table 
-- =========================================
CREATE TABLE Counter (
    counter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    counter_name TEXT NOT NULL,
    counter_status TEXT NOT NULL DEFAULT 'Closed',
    FOREIGN KEY (store_id)
    REFERENCES Store(store_id)
);


-- =========================================
-- Queue history table
-- =========================================
CREATE TABLE Queue_History (
    queue_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL,
    status_changed_to TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (queue_id)
    REFERENCES Queue(queue_id)
);