import sqlite3
import os

# ---------------- DB PATH ----------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "smartcart.db")

# ---------------- FORCE RESET (DEV ONLY) ----------------
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("🗑️ Old DB deleted")

# ---------------- CONNECT DB ----------------
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ---------------- ADMIN TABLE ----------------
cursor.execute("""
CREATE TABLE admin (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    profile_image TEXT
)
""")

# ---------------- USERS TABLE ----------------
cursor.execute("""
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT
)
""")

# ---------------- PRODUCTS TABLE ----------------
cursor.execute("""
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    category TEXT,
    price REAL,
    image TEXT
)
""")

# ---------------- CART TABLE ----------------
cursor.execute("""
CREATE TABLE cart (
    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER
)
""")

# ---------------- ORDERS TABLE ----------------
cursor.execute("""
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    order_status TEXT,
    razorpay_order_id TEXT,
    razorpay_payment_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ---------------- ORDER ITEMS TABLE ----------------
cursor.execute("""
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    price REAL
)
""")

# ---------------- USER ADDRESS TABLE ----------------
cursor.execute("""
CREATE TABLE user_address (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    house_no TEXT,
    area TEXT,
    locality TEXT,
    mandal TEXT,
    city TEXT,
    state TEXT,
    pincode TEXT
)
""")

# ---------------- SAVE & CLOSE ----------------
conn.commit()
conn.close()

print("✅ Fresh SmartCart DB created successfully with all tables")