from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_mail import Mail, Message
import bcrypt
import random
import os
import traceback
import hmac
import hashlib

from werkzeug.utils import secure_filename

import razorpay

import config
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

from utils.pdf_generator import generate_pdf



client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))

app = Flask(__name__, template_folder='templates')
app.secret_key = config.SECRET_KEY

# ---------------- UPLOAD CONFIG ----------------
PRODUCT_UPLOAD_FOLDER = 'static/uploads/product_images'
ADMIN_UPLOAD_FOLDER = 'static/uploads/admin_profiles'

app.config['UPLOAD_FOLDER'] = PRODUCT_UPLOAD_FOLDER
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER

os.makedirs(PRODUCT_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ADMIN_UPLOAD_FOLDER, exist_ok=True)

# ---------------- EMAIL CONFIG ----------------
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD

mail = Mail(app)

# ---------------- DB ----------------
import sqlite3
from config import DATABASE

# ================================================================
# DATABASE CONNECTION (FIXED - SQLITE)
# ================================================================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- ADMIN CONTEXT ----------------
@app.context_processor
def inject_admin():
    admin = None

    if 'admin_id' in session:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT * FROM admin WHERE admin_id = ?",
            (session['admin_id'],)
        )

        admin = cursor.fetchone()
        db.close()

    return dict(admin=admin)

# ================================================================
# PUBLIC ROUTES
# ================================================================

@app.route('/')
def home():
    return redirect(url_for('user_register'))


@app.route('/products')
def user_products():
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    db = get_db()
    cursor = db.cursor()

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")

    if category:
        query += " AND category = ?"
        params.append(category)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    db.close()

    return render_template(
        'user/products.html',
        products=products,
        categories=categories,
        search=search,
        selected_category=category
    )


@app.route('/product/<int:id>')
def public_view_product(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products WHERE product_id=?", (id,))
    product = cursor.fetchone()
    db.close()
    return render_template("user/view_product.html", product=product)

# ================================================================
# ADMIN ROUTES
# ================================================================

@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == "GET":
        return render_template("admin/admin_signup.html")

    name = request.form['name']
    email = request.form['email']

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT admin_id FROM admin WHERE email=?", (email,))
    if cursor.fetchone():
        db.close()
        flash("Email already exists!", "danger")
        return redirect('/admin-login')
    db.close()

    session['signup_name'] = name
    session['signup_email'] = email

    otp = random.randint(100000, 999999)
    session['otp'] = otp

    msg = Message("SmartCart OTP", sender=config.MAIL_USERNAME, recipients=[email])
    msg.body = f"Your OTP is: {otp}"
    mail.send(msg)

    flash("OTP sent!", "success")
    return redirect('/verify-otp')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'GET':
        return render_template("admin/verify_otp.html")

    if str(session.get('otp')) != request.form['otp']:
        flash("Invalid OTP!", "danger")
        return redirect('/verify-otp')

    password = bcrypt.hashpw(
        request.form['password'].encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')  

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO admin (name, email, password) VALUES (?, ?, ?)",
        (session['signup_name'], session['signup_email'], password)
    )
    db.commit()
    db.close()

    session.clear()
    flash("Registered successfully!", "success")
    return redirect('/admin-login')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'GET':
        return render_template("admin/admin_login.html")

    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash("Please fill all fields!", "danger")
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM admin WHERE email=?", (email,))
    admin = cursor.fetchone()

    db.close()

    if not admin:
        flash("Email not found!", "danger")
        return redirect('/admin-login')

    stored_password = admin['password']

    if stored_password is None:
        flash("Password not set!", "danger")
        return redirect('/admin-login')

    # bcrypt check
    if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
        flash("Incorrect password!", "danger")
        return redirect('/admin-login')

    # SUCCESS LOGIN
    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']

    flash("Login successful!", "success")
    return redirect('/admin-dashboard')



@app.route('/admin-dashboard')
def admin_dashboard():

    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    # TOTAL PRODUCTS
    cursor.execute("SELECT COUNT(*) AS total FROM products")
    product_count = cursor.fetchone()['total']

    # TOTAL ORDERS
    cursor.execute("SELECT COUNT(*) AS total FROM orders")
    order_count = cursor.fetchone()['total']

    cursor.close()
    db.close()

    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        order_count=order_count
    )


@app.route('/admin/add-item', methods=['GET', 'POST'])
def add_item():

    if 'admin_id' not in session:
        return redirect('/admin-login')

    if request.method == 'POST':

        image = request.files['image']

        if image.filename == '':
            flash("No image selected", "error")
            return redirect('/admin/add-item')

        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO products (name, description, category, price, image)
            VALUES (?, ?, ?, ?, ?)
        """, (
            request.form['name'],
            request.form['description'],
            request.form['category'],
            request.form['price'],
            filename
        ))

        db.commit()
        cursor.close()
        db.close()

        flash("Product added successfully!", "success")
        return redirect('/admin/add-item')

    return render_template('admin/add_item.html')

# ================================================================
# USER ROUTES
# ================================================================

@app.route('/user-register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'GET':
        return render_template("user/user_register.html")

    # ---------------- GET FORM DATA ----------------
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']  # ✅ FIXED

    # ---------------- HASH PASSWORD ----------------
    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    # ---------------- DB CONNECTION ----------------
    db = get_db()
    cursor = db.cursor()

    # ---------------- CHECK EXISTING EMAIL ----------------
    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    if cursor.fetchone():
        db.close()
        flash("Email already exists!", "danger")
        return redirect('/user-register')

    # ---------------- INSERT USER ----------------
    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, hashed_password)
    )

    db.commit()
    db.close()

    flash("Registered successfully!", "success")
    return redirect('/user-login')


@app.route('/user-login', methods=['GET', 'POST'])
def user_login():

    if request.method == 'GET':
        return render_template("user/user_login.html")

    email = request.form['email']
    password = request.form['password']   # ✅ FIXED

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    db.close()

    if not user:
        flash("Email not found!", "danger")
        return redirect('/user-login')

    stored_password = user['password']

    # convert stored password to bytes if needed
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')

    # check password
    if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
        flash("Incorrect password!", "danger")
        return redirect('/user-login')

    session['user_id'] = user['user_id']
    session['user_name'] = user['name']

    flash("Login successful!", "success")
    return redirect('/user-dashboard')


@app.route('/user-dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect('/user-login')

    return render_template("user/user_home.html", user_name=session['user_name'])


@app.route('/user-logout')
def user_logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect('/user-login')

# ================================================================
# CART
# ================================================================

@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):

    if 'user_id' not in session:
        return jsonify({"status": "login_required"}), 401

    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    # check product already exists
    cursor.execute("""
        SELECT * FROM cart 
        WHERE user_id=? AND product_id=?
    """, (user_id, product_id))

    item = cursor.fetchone()

    if item:
        cursor.execute("""
            UPDATE cart 
            SET quantity = quantity + 1 
            WHERE cart_id=?
        """, (item['cart_id'],))
    else:
        cursor.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (?, ?, 1)
        """, (user_id, product_id))

    db.commit()

    # get updated count
    cursor.execute("""
        SELECT SUM(quantity) as total 
        FROM cart 
        WHERE user_id=?
    """, (user_id,))

    count = cursor.fetchone()["total"]

    db.close()

    return jsonify({
        "status": "success",
        "cart_count": count or 0
    })

@app.route('/buy-now/<int:product_id>')
def buy_now(product_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        db.close()
        return "Product not found"

    session['buy_now'] = {
        "product_id": product['product_id'],
        "name": product['name'],
        "price": float(product['price']),
        "quantity": 1
    }

    cursor.close()
    db.close()

    return redirect(url_for('checkout'))

@app.route('/user/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect('/user-login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.product_id, p.name, p.price, c.quantity
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (session['user_id'],))

    cart_items = cursor.fetchall()

    cursor.close()
    conn.close()

    # ✅ CALCULATE GRAND TOTAL IN PYTHON
    total = sum(item['price'] * item['quantity'] for item in cart_items)

    return render_template(
        "user/cart.html",
        cart_items=cart_items,
        total=total
    )

# ================================================================
# CHECKOUT
# ================================================================

@app.route("/checkout")
def checkout():

    if 'user_id' not in session:
        flash("Please login first", "danger")
        return redirect("/user-login")

    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT c.quantity, p.price
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))

    cart_items = cursor.fetchall()
    db.close()

    if not cart_items:
        flash("Cart is empty", "warning")
        return redirect("/user/cart")

    # 🔥 DO NOT go to payment yet
    # 👉 Go to address page first
    return redirect("/checkout-address")

@app.route('/remove-from-cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'user_id' not in session:
        return redirect('/user-login')

    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM cart
        WHERE user_id=? AND product_id=?
    """, (user_id, product_id))

    db.commit()
    db.close()

    return redirect('/user/cart')

@app.route('/decrease-cart/<int:product_id>')
def decrease_cart(product_id):
    if 'user_id' not in session:
        return redirect('/user-login')

    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE cart
        SET quantity = quantity - 1
        WHERE user_id=? AND product_id=?
    """, (user_id, product_id))

    cursor.execute("""
        DELETE FROM cart
        WHERE user_id=? AND product_id=? AND quantity <= 0
    """, (user_id, product_id))

    db.commit()
    db.close()

    return redirect('/user/cart')

@app.route('/checkout-address', methods=['GET', 'POST'])
def checkout_address():

    if 'user_id' not in session:
        return redirect('/user-login')

    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    # 🔥 GET LAST SAVED ADDRESS
    cursor.execute("""
        SELECT * FROM user_address
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))
    address = cursor.fetchone()

    if request.method == 'POST':

        cursor.execute("""
            INSERT INTO user_address
            (user_id, house_no, area, locality, mandal, city, state, pincode)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            user_id,
            request.form.get('house_no'),
            request.form.get('area'),
            request.form.get('locality'),
            request.form.get('mandal'),
            request.form.get('city'),
            request.form.get('state'),
            request.form.get('pincode')
        ))

        db.commit()

        # 🔥 SAFE FLOW DECISION BEFORE CLOSE
        buy_now = session.get('buy_now')

        db.close()

        # 🔥 ROUTE DECISION
        if buy_now:
            session.pop('buy_now', None)  # clear flag
            return redirect('/checkout-buy-now')

        return redirect('/payment')

    db.close()

    return render_template("user/address.html", address=address)

# ================================================================
# PAYMENT ROUTES (FIXED)
# ================================================================



@app.route('/user/order-success/<int:order_id>')
def order_success(order_id):

    if 'user_id' not in session:
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM orders
        WHERE id = ? AND user_id = ?
    """, (order_id, user_id))

    order = cursor.fetchone()

    print("ORDER DATA:", order)   # ✅ PUT HERE ONLY

    if not order:
        return "Order not found"

    cursor.execute("""
        SELECT p.name AS product_name, oi.quantity, oi.price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """, (order_id,))
    items = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM user_address
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))
    address = cursor.fetchone()

    conn.close()

    return render_template(
        "user/order_success.html",
        order=order,
        items=items,
        address=address
    )



@app.route("/payment")
def payment():

    if 'user_id' not in session:
        return redirect("/user-login")

    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    # 🔥 GET CART ITEMS
    cursor.execute("""
        SELECT c.quantity, p.price
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))

    cart_items = cursor.fetchall()

    if not cart_items:
        db.close()
        return redirect("/user/cart")

    # 🔥 GET LAST ADDRESS
    cursor.execute("""
        SELECT * FROM user_address
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))

    address = cursor.fetchone()

    db.close()

    # ===============================
    # ✅ SAFE GRAND TOTAL CALCULATION
    # ===============================
    grand_total = 0

    for item in cart_items:
        try:
            price = float(str(item["price"]).replace("₹", "").replace("rs", "").strip())
            qty = int(item["quantity"])
            grand_total += price * qty
        except:
            continue

    # 🔴 SAFETY CHECK
    if grand_total <= 0:
        return "Invalid amount", 400

    # ===============================
    # 🔥 RAZORPAY AMOUNT (PAISE)
    # ===============================
    razorpay_amount = int(round(grand_total * 100))

    # 🔴 LIMIT CHECK (Razorpay max ₹10 lakh)
    if razorpay_amount > 100000000:
        return "Amount exceeds Razorpay limit (₹10 lakh max)", 400

    # ===============================
    # 🔥 CREATE ORDER
    # ===============================
    order = client.order.create({
        "amount": razorpay_amount,
        "currency": "INR",
        "payment_capture": 1
    })

    session['razorpay_order_id'] = order['id']

    return render_template(
        "user/payment.html",
        key_id=config.RAZORPAY_KEY_ID,
        amount=grand_total,
        order_id=order['id'],
        address=address
    )
@app.route('/admin/manage-products')
def manage_products():

    # ✅ admin login check (CORRECT)
    if 'admin_id' not in session:
        return redirect('/admin-login')

    search = request.args.get('search', '')
    selected_category = request.args.get('category', '')

    db = get_db()
    cursor = db.cursor()

    # 🔥 base query
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    # 🔍 search filter
    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")

    # 📦 category filter
    if selected_category:
        query += " AND category = ?"
        params.append(selected_category)

    cursor.execute(query, params)
    products = cursor.fetchall()

    # 📂 categories for dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    db.close()

    return render_template(
        'admin/manage_products.html',
        products=products,
        categories=categories,
        search=search,
        selected_category=selected_category
    )

@app.route('/admin/delete-product/<int:product_id>')
def delete_product(product_id):

    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM products WHERE product_id=?", (product_id,))
    db.commit()
    db.close()

    return redirect(url_for('manage_products'))

@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):

    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':

        name = request.form['name']
        price = request.form['price']

        cursor.execute("""
            UPDATE products 
            SET name=?, price=? 
            WHERE product_id=?
        """, (name, price, product_id))

        db.commit()
        db.close()

        return redirect(url_for('manage_products'))

    cursor.execute("SELECT * FROM products WHERE product_id=?", (product_id,))
    product = cursor.fetchone()

    db.close()

    return render_template('admin/edit_product.html', product=product)

@app.route('/admin/update-profile', methods=['POST'])
def update_admin_profile():
    if 'admin_id' not in session:
        return redirect('/admin-login')

    name = request.form['name']
    email = request.form['email']
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    file = request.files['profile_image']

    db = get_db()
    cursor = db.cursor()

    filename = None

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        cursor.execute("""
            UPDATE admin
            SET name=?, email=?, password=?, profile_image=?
            WHERE admin_id=?
        """, (name, email, password, filename, session['admin_id']))

    else:
        # ✅ THIS IS THE FIXED PART
        cursor.execute("""
            UPDATE admin
            SET name=?, email=?, password=?
            WHERE admin_id=?
        """, (name, email, password, session['admin_id']))

    db.commit()
    db.close()

    return redirect('/admin/profile')

@app.route('/admin-logout')
def admin_logout():
    session.clear()
    return redirect('/admin-login')

@app.route('/admin/view-product/<int:product_id>')
def admin_view_product(product_id):

    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM products WHERE product_id=?", (product_id,))
    product = cursor.fetchone()

    db.close()

    return render_template('admin/view_product.html', product=product)






@app.route("/admin/update-order-status/<int:order_id>", methods=['POST'])
def update_order_status(order_id):

    if 'admin_id' not in session:
        return redirect('/admin-login')

    new_status = request.form.get('status')

    ALLOWED_STATUS = ['Pending', 'Confirmed', 'Packed', 'Shipped', 'Delivered']

    if new_status not in ALLOWED_STATUS:
        return "Invalid Status", 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET order_status=?
        WHERE id=?
    """, (new_status, order_id))

    conn.commit()
    conn.close()

    return redirect(f"/admin/order/{order_id}")

@app.route('/admin/profile')
def admin_profile():
    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM admin WHERE admin_id=?", (session['admin_id'],))
    admin = cursor.fetchone()

    return render_template("admin/profile.html", admin=admin)

@app.route('/admin/orders')
def admin_orders():

    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT 
        id,
        user_id,
        amount,
        order_status,
        razorpay_order_id,
        razorpay_payment_id,
        created_at
    FROM orders
    
    ORDER BY id DESC
""")

    orders = cursor.fetchall()

    db.close()

    return render_template("admin/orders.html", orders=orders)

@app.route('/admin/order/<int:order_id>')
def admin_order_details(order_id):

    if 'admin_id' not in session:
        return redirect('/admin-login')

    db = get_db()
    cursor = db.cursor()

    # ✅ FIX: use id not order_id
    cursor.execute("""
        SELECT * FROM orders WHERE id=?
    """, (order_id,))
    order = cursor.fetchone()

    cursor.execute("""
        SELECT 
            p.name,
            oi.quantity,
            oi.price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """, (order_id,))
    items = cursor.fetchall()

    db.close()

    return render_template("admin/order_details.html",
                           order=order,
                           items=items)

@app.route('/user/my-orders')
def my_orders():

    if 'user_id' not in session:
        return redirect('/user-login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM orders 
        WHERE user_id=? 
        ORDER BY created_at DESC
    """, (session['user_id'],))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("user/my_orders.html", orders=orders)

@app.route('/create-order', methods=['POST'])
def create_order():
    try:
        print("STEP 1")

        if 'user_id' not in session:
            print("NO USER")
            return jsonify({"error": "Not logged in"}), 401

        user_id = session['user_id']
        print("USER:", user_id)

        conn = get_db()
        cursor = conn.cursor()

        print("STEP 2")

        # ✅ ADD product_id also (important for order_items)
        cursor.execute("""
            SELECT c.product_id, c.quantity, p.price
            FROM cart c
            JOIN products p ON c.product_id = p.product_id
            WHERE c.user_id = ?
        """, (user_id,))

        cart_items = cursor.fetchall()
        print("CART:", cart_items)

        if not cart_items:
            return jsonify({"error": "Cart empty"}), 400

        total = sum(item['price'] * item['quantity'] for item in cart_items)
        print("TOTAL:", total)

        print("STEP 3")

        # ✅ STORE amount + status (DON'T REMOVE EXISTING FLOW)
        cursor.execute("""
            INSERT INTO orders (user_id, amount, order_status)
            VALUES (?, ?, ?)
        """, (user_id, total, 'Pending'))

        conn.commit()
        order_db_id = cursor.lastrowid

        print("DB ORDER:", order_db_id)

        # ✅ INSERT ORDER ITEMS (NEW - IMPORTANT)
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (
                order_db_id,
                item['product_id'],
                item['quantity'],
                item['price']
            ))

        conn.commit()

        # ✅ CLEAR CART AFTER ORDER
        cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        conn.commit()

        print("STEP 4")

        razorpay_order = client.order.create({
            "amount": int(total * 100),
            "currency": "INR"
        })

        print("RAZORPAY:", razorpay_order)

        conn.close()

        return jsonify({
    "id": razorpay_order['id'],      # Razorpay order id
    "amount": int(total * 100),
    "order_db_id": order_db_id,      # ✅ IMPORTANT
    "key": RAZORPAY_KEY_ID
    })
    except Exception as e:
        print("🔥 ERROR:", e)
        return jsonify({"error": str(e)}), 500
    

@app.route('/download-invoice/<int:order_id>')
def download_invoice(order_id):

    if 'user_id' not in session:
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor()

    # 🔥 GET ORDER
    cursor.execute("""
        SELECT * FROM orders
        WHERE id = ? AND user_id = ?
    """, (order_id, user_id))

    order = cursor.fetchone()

    if not order:
        conn.close()
        return "Order not found", 404

    # 🔥 GET ITEMS
    cursor.execute("""
        SELECT p.name AS product_name,
               oi.quantity,
               oi.price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    # 🔥 GET ADDRESS (IMPORTANT FOR INVOICE)
    cursor.execute("""
        SELECT * FROM user_address
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))

    address = cursor.fetchone()

    conn.close()

    # 🔥 CALCULATE TOTAL
    grand_total = sum(float(i["price"]) * int(i["quantity"]) for i in items)

    # 🔥 SEND TO PDF GENERATOR
    return generate_pdf(order, items, address, grand_total)

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    data = request.get_json(silent=True) or request.form
    required_keys = ['razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'order_db_id']
    if not all(k in data for k in required_keys):
        return "Invalid request", 400

    try:
        params_dict = {
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        }

        client.utility.verify_payment_signature(params_dict)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
    UPDATE orders
    SET order_status = ?,
        razorpay_order_id = ?,
        razorpay_payment_id = ?
    WHERE id = ?
""", (
    'Paid',
    data['razorpay_order_id'],
    data['razorpay_payment_id'],
    data['order_db_id']
))

        conn.commit()
        conn.close()

        return redirect(f"/user/order-success/{data['order_db_id']}")

    except Exception as e:
        print("VERIFY ERROR:", e)
        return "Payment Failed"
    
@app.route('/checkout-buy-now', methods=['GET', 'POST'])
def checkout_buy_now():
    return render_template('checkout_buy_now.html')



# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)