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


