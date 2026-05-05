import os

# ---------------- BASE ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------- SECRET ----------------
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")

# ---------------- DATABASE ----------------
DATABASE = os.path.join(BASE_DIR, "smartcart.db")   # ✅ keep consistent

# ---------------- EMAIL ----------------
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

# ---------------- UPLOAD ----------------
PRODUCT_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/product_images')
ADMIN_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/admin_profiles')

# ---------------- RAZORPAY ----------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")