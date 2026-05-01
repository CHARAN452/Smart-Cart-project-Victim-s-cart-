import os

# ---------------- BASIC ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = "secret123"

# ---------------- SQLITE ----------------
DATABASE = os.path.join(BASE_DIR, "smartcart.db")

# ---------------- EMAIL (Gmail SMTP) ----------------
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = "charanv003@gmail.com"
MAIL_PASSWORD = "lrlmybdifqdizfxh"  # (fix: remove spaces if any)

# ---------------- UPLOAD ----------------
UPLOAD_FOLDER = "static/uploads/product_images"

# ---------------- RAZORPAY ----------------
RAZORPAY_KEY_ID = "rzp_test_SiDOOQfWdiHjAt"
RAZORPAY_KEY_SECRET = "q6r9x7SlTRUlxHawh5Qlafvi"