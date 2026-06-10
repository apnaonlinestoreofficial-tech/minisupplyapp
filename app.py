from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, send_from_directory
from functools import wraps
import json
import os
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = 'mini-supply-secret-2026-change-this'

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Upload folder setup
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==================== DATABASE CONFIGURATION ====================
# PostgreSQL for Render, SQLite for local development
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Render uses postgres:// but SQLAlchemy needs postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Local development fallback
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///supply.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== PAKISTAN TIMEZONE ====================
# پاکستان کا ٹائم زون (UTC+5)
pk_timezone = timezone(timedelta(hours=5))

def get_pakistan_time():
    """پاکستان کا موجودہ وقت"""
    return datetime.now(pk_timezone)

# ==================== DATABASE MODELS ====================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    image_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=get_pakistan_time)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(200), nullable=False)
    items = db.Column(db.Text, nullable=False)  # JSON string
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, purchased, delivered, cancelled
    
    # Dates for workflow
    order_date = db.Column(db.DateTime, default=get_pakistan_time)
    purchase_date = db.Column(db.DateTime, nullable=True)  # Day 2: خریداری
    delivery_date = db.Column(db.DateTime, nullable=True)  # Day 3: ڈیلیوری
    
    # Auto-expiry: 7 days after order
    expire_date = db.Column(db.DateTime, default=lambda: get_pakistan_time() + timedelta(days=7))

# Create tables
with app.app_context():
    db.create_all()

# ==================== AUTO CLEANUP SCHEDULER ====================

def cleanup_old_orders():
    """7 دن پرانے آرڈرز خودکار طور پر ڈیلیٹ کریں"""
    with app.app_context():
        cutoff_date = get_pakistan_time()
        old_orders = Order.query.filter(Order.expire_date < cutoff_date).all()
        count = len(old_orders)
        for order in old_orders:
            db.session.delete(order)
        db.session.commit()
        if count > 0:
            print(f"✅ {count} پرانے آرڈرز ڈیلیٹ ہو گئے")

# Start scheduler - runs every 24 hours
scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_old_orders, trigger="interval", hours=24)
scheduler.start()

# ==================== HELPER FUNCTIONS =================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== HTML TEMPLATES ====================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>Mini Supply App</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1976d2">
    <link rel="manifest" href="/static/manifest.json">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f0f4f8; padding: 20px; }
        .header {
            background: #1976d2;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-width: 400px;
            margin: 50px auto;
            text-align: center;
        }
        .login-box input {            width: 100%;
            padding: 12px;
            margin: 15px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        .btn {
            background: #1976d2;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            text-decoration: none;
            display: inline-block;
        }
        .btn:hover { background: #1565c0; }
        .btn-success { background: #388e3c; }
        .btn-success:hover { background: #2e7d32; }
        .btn-danger { background: #d32f2f; }
        .btn-danger:hover { background: #c62828; }
        .btn-warning { background: #f57c00; }
        .btn-info { background: #0288d1; }
        .search-bar {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .search-bar input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .product-card {
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;        }
        .product-card:hover { transform: translateY(-5px); }
        .product-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            background: #f5f5f5;
        }
        .product-info { padding: 15px; }
        .product-info h3 { color: #333; margin-bottom: 8px; font-size: 18px; }
        .product-info p { color: #388e3c; font-weight: bold; font-size: 20px; }
        .product-info .category { color: #757575; font-size: 14px; margin-top: 5px; }
        .cart {
            background: white;
            padding: 20px;
            border-radius: 10px;
            position: fixed;
            right: 20px;
            top: 100px;
            width: 320px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.2);
            max-height: 80vh;
            overflow-y: auto;
        }
        .cart h3 { margin-bottom: 15px; color: #1976d2; border-bottom: 2px solid #1976d2; padding-bottom: 10px; }
        .cart-item {
            padding: 12px 0;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .cart-item-info { flex: 1; }
        .cart-item-name { font-weight: bold; margin-bottom: 5px; }
        .cart-item-price { color: #757575; font-size: 14px; }
        .cart-item-controls { display: flex; align-items: center; gap: 10px; }
        .qty-btn {
            background: #1976d2;
            color: white;
            border: none;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
        }
        .qty-btn:hover { background: #1565c0; }
        .remove-btn {
            background: #d32f2f;
            color: white;            border: none;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
        }
        .cart-total {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 3px solid #1976d2;
            font-weight: bold;
            font-size: 22px;
            text-align: right;
        }
        .nav-links {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        .my-orders-link {
            color: white;
            background: #0288d1;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
        }
        .admin-link {
            color: white;
            background: #7b1fa2;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
        }
        .logout-btn { background: #d32f2f; }
        @media (max-width: 768px) {
            .cart {
                position: fixed;
                bottom: 0;
                top: auto;
                right: 0;
                left: 0;
                width: 100%;
                max-height: 50vh;
                border-radius: 10px 10px 0 0;
            }
            .products-grid {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 10px;
                margin-bottom: 350px;            }
            .product-image { height: 150px; }
            .header { flex-direction: column; text-align: center; }
            .nav-links { margin-top: 10px; justify-content: center; }
            body { padding: 10px; }
        }
    </style>
</head>
<body>
    {% if not session.get('logged_in') %}
    <div class="container">
        <div class="login-box">
            <h1 style="color: #1976d2; margin-bottom: 10px;">🛒 Mini Supply App</h1>
            <p style="color: #757575; margin-bottom: 30px;">Welcome! Please login to continue</p>
            <form method="POST" action="/login">
                <input type="text" name="shop_name" placeholder="Enter Shop Name" required>
                <button type="submit" class="btn" style="width: 100%;">Login</button>
            </form>
        </div>
    </div>
    {% else %}
    <div class="container">
        <div class="header">
            <h1>🛒 Mini Supply App</h1>
            <div class="nav-links">
                <span>Welcome: <strong>{{ session.shop_name }}</strong></span>
                <a href="/my_orders" class="my-orders-link">📦 My Orders</a>
                <a href="/logout" class="btn logout-btn">Logout</a>
            </div>
        </div>
        
        <div class="search-bar">
            <input type="text" id="searchBox" placeholder="Search products..." onkeyup="filterProducts()">
        </div>
        
        <div class="products-grid" id="productsGrid">
            {% for product in products %}
            <div class="product-card" data-name="{{ product.name.lower() }}">
                {% if product.image_path %}
                <img src="{{ product.image_path }}" alt="{{ product.name }}" class="product-image">
                {% else %}
                <div class="product-image" style="display: flex; align-items: center; justify-content: center; background: #e0e0e0; color: #757575;">
                    No Image
                </div>
                {% endif %}
                <div class="product-info">
                    <h3>{{ product.name }}</h3>
                    <p>Rs. {{ product.price }}</p>
                    {% if product.category %}
                    <div class="category">Category: {{ product.category }}</div>                    {% endif %}
                    <button class="btn btn-success" style="width: 100%; margin-top: 10px;" 
                            onclick="addToCart({{ product.id }}, '{{ product.name }}', {{ product.price }})">
                        🛒 Add to Cart
                    </button>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <div class="cart">
        <h3>🛒 Shopping Cart</h3>
        <div id="cartItems">
            <p style="color: #999; text-align: center; padding: 20px;">Cart is empty</p>
        </div>
        <div class="cart-total">
            Total: Rs. <span id="cartTotal">0</span>
        </div>
        <button class="btn btn-success" style="width: 100%; margin-top: 15px; padding: 15px;" onclick="submitOrder()">
            📦 Submit Order
        </button>
    </div>
    {% endif %}
    
    <script>
        let cart = [];
        
        function addToCart(id, name, price) {
            const existingItem = cart.find(item => item.id === id);
            if (existingItem) {
                existingItem.quantity += 1;
            } else {
                cart.push({ id, name, price, quantity: 1 });
            }
            updateCart();
        }
        
        function updateQuantity(id, change) {
            const item = cart.find(item => item.id === id);
            if (item) {
                item.quantity += change;
                if (item.quantity <= 0) {
                    cart = cart.filter(i => i.id !== id);
                }
                updateCart();
            }
        }
        
        function removeItem(id) {            cart = cart.filter(item => item.id !== id);
            updateCart();
        }
        
        function updateCart() {
            const cartItems = document.getElementById('cartItems');
            const cartTotal = document.getElementById('cartTotal');
            
            if (cart.length === 0) {
                cartItems.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">Cart is empty</p>';
                cartTotal.textContent = '0';
                return;
            }
            
            let html = '';
            let total = 0;
            
            cart.forEach(item => {
                const itemTotal = item.price * item.quantity;
                total += itemTotal;
                html += `
                    <div class="cart-item">
                        <div class="cart-item-info">
                            <div class="cart-item-name">${item.name}</div>
                            <div class="cart-item-price">Rs. ${item.price} x ${item.quantity}</div>
                        </div>
                        <div class="cart-item-controls">
                            <button class="qty-btn" onclick="updateQuantity(${item.id}, -1)">-</button>
                            <span>${item.quantity}</span>
                            <button class="qty-btn" onclick="updateQuantity(${item.id}, 1)">+</button>
                            <button class="remove-btn" onclick="removeItem(${item.id})">✕</button>
                        </div>
                    </div>
                `;
            });
            
            cartItems.innerHTML = html;
            cartTotal.textContent = total;
        }
        
        function filterProducts() {
            const searchTerm = document.getElementById('searchBox').value.toLowerCase();
            const products = document.querySelectorAll('.product-card');
            
            products.forEach(product => {
                const name = product.getAttribute('data-name');
                if (name.includes(searchTerm)) {
                    product.style.display = 'block';
                } else {
                    product.style.display = 'none';                }
            });
        }
        
        function submitOrder() {
            if (cart.length === 0) {
                alert('Cart is empty! Please add some products.');
                return;
            }
            
            const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
            
            const today = new Date();
            const deliveryDate = new Date(today);
            deliveryDate.setDate(deliveryDate.getDate() + 2); // آج سے 2 دن بعد (تیسرے دن ڈیلیوری)
            
            const deliveryDateStr = deliveryDate.toLocaleDateString('en-US', { 
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            if (!confirm(`Order Total: Rs. ${total}\n\nExpected Delivery: ${deliveryDateStr}\n\nConfirm order?`)) {
                return;
            }
            
            fetch('/submit_order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    shop_name: '{{ session.shop_name }}',
                    items: cart,
                    total: total,
                    delivery_date: deliveryDate.toISOString()
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ Order submitted successfully!\n\nDelivery Date: ' + deliveryDateStr);
                    cart = [];
                    updateCart();
                } else {
                    alert('Error submitting order');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error submitting order');
            });        }
        
        updateCart();
        
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/static/service-worker.js')
                    .then(reg => console.log('Service Worker registered'))
                    .catch(err => console.log('SW registration failed:', err));
            });
        }
    </script>
</body>
</html>
'''

MY_ORDERS_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>My Orders - Mini Supply App</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1976d2">
    <link rel="manifest" href="/static/manifest.json">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f0f4f8; padding: 20px; }
        .header {
            background: #1976d2;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .order-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 4px solid #1976d2;
        }
        .order-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;            padding-bottom: 10px;
            border-bottom: 1px solid #ddd;
        }
        .order-status {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-purchased { background: #cce5ff; color: #004085; }
        .status-delivered { background: #d4edda; color: #155724; }
        .status-cancelled { background: #f8d7da; color: #721c24; }
        .delivery-info {
            background: #e3f2fd;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            margin: 5px;
        }
        .btn-primary { background: #1976d2; color: white; }
        .btn-danger { background: #d32f2f; color: white; }
        .btn-success { background: #388e3c; color: white; }
        .nav-links {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        @media (max-width: 768px) {
            .header { flex-direction: column; text-align: center; }
            .nav-links { margin-top: 10px; }
            .order-header { flex-direction: column; }
            body { padding: 10px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 My Orders</h1>
            <div class="nav-links">                <span>Welcome: <strong>{{ session.shop_name }}</strong></span>
                <a href="/" class="btn btn-primary">🛒 Products</a>
                <a href="/logout" class="btn btn-danger">Logout</a>
            </div>
        </div>
        
        <h2 style="margin-bottom: 20px; color: #1976d2;">Your Orders ({{ orders|length }})</h2>
        
        {% if orders %}
            {% for order in orders %}
            <div class="order-card">
                <div class="order-header">
                    <div>
                        <strong>Order #{{ order.id }}</strong><br>
                        <small>
                            Order Date: {{ order.order_date.strftime('%Y-%m-%d %I:%M %p') if order.order_date else 'N/A' }} (PKT)<br>
                            Purchase Date: {{ order.purchase_date.strftime('%Y-%m-%d') if order.purchase_date else 'N/A' }}<br>
                            Delivery Date: {{ order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else 'N/A' }}
                        </small>
                    </div>
                    <div>
                        <span class="order-status status-{{ order.status }}">{{ order.status.upper() }}</span>
                    </div>
                </div>
                <div>
                    <strong>📦 Order Items:</strong>
                    <table style="width: 100%; margin: 10px 0; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f5f5f5;">
                                <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Product</th>
                                <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Qty</th>
                                <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Price</th>
                                <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if order.items_list %}
                                {% for item in order.items_list %}
                                <tr>
                                    <td style="padding: 10px; border: 1px solid #ddd;">{{ item.name }}</td>
                                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{{ item.quantity }}</td>
                                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">Rs. {{ item.price }}</td>
                                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">Rs. {{ item.price * item.quantity }}</td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr><td colspan="4" style="padding: 10px; text-align: center;">No items</td></tr>
                            {% endif %}
                        </tbody>
                        <tfoot>                            <tr style="background: #e3f2fd; font-weight: bold;">
                                <td colspan="3" style="padding: 10px; border: 1px solid #ddd; text-align: right;">Total:</td>
                                <td style="padding: 10px; border: 1px solid #ddd; text-align: right; color: #388e3c; font-size: 18px;">Rs. {{ order.total }}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                {% if order.status == 'pending' %}
                <div style="margin-top: 15px;">
                    <form method="POST" action="/cancel_order/{{ order.id }}" style="display: inline;" onsubmit="return confirm('Are you sure you want to cancel this order?');">
                        <button type="submit" class="btn btn-danger">❌ Cancel Order</button>
                    </form>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div style="background: white; padding: 40px; border-radius: 10px; text-align: center;">
                <p style="color: #999; font-size: 18px;">No orders yet</p>
                <a href="/" class="btn btn-primary" style="margin-top: 20px;">🛒 Start Shopping</a>
            </div>
        {% endif %}
    </div>
    
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/static/service-worker.js')
                    .then(reg => console.log('Service Worker registered'))
                    .catch(err => console.log('SW registration failed:', err));
            });
        }
    </script>
</body>
</html>
'''

ADMIN_LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial; background: #f5f5f5; padding: 20px; }
        .login-box { 
            background: white; 
            padding: 40px; 
            max-width: 400px; 
            margin: 100px auto;             border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #7b1fa2; text-align: center; margin-bottom: 30px; }
        input { 
            width: 100%; 
            padding: 12px; 
            margin: 10px 0; 
            border: 1px solid #ddd; 
            border-radius: 5px;
            font-size: 16px;
        }
        button { 
            width: 100%; 
            padding: 12px; 
            background: #7b1fa2; 
            color: white; 
            border: none; 
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover { background: #6a1b9a; }
        .error { color: red; text-align: center; margin: 10px 0; }
        .back { text-align: center; margin-top: 20px; }
        .back a { color: #1976d2; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🔧 Admin Login</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        <div class="back">
            <a href="/">← Back to App</a>
        </div>
    </div>
</body>
</html>
'''

ADMIN_PRODUCTS_TEMPLATE = '''
<!DOCTYPE html>
<html><head>
    <title>Admin - Products Management</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#7b1fa2">
    <link rel="manifest" href="/static/manifest.json">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .header {
            background: #7b1fa2;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .section {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #7b1fa2;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #7b1fa2;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            margin: 5px;
        }
        .btn-primary { background: #1976d2; color: white; }
        .btn-success { background: #388e3c; color: white; }
        .btn-danger { background: #d32f2f; color: white; }
        .btn-warning { background: #f57c00; color: white; }
        .btn-info { background: #0288d1; color: white; }
        .btn:hover { opacity: 0.9; }
        input, select {            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            margin: 5px 0;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th { background: #7b1fa2; color: white; }
        tr:hover { background: #f5f5f5; }
        .product-image {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 5px;
        }
        .nav-links {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 500px;
            margin: 50px auto;
        }
        .close-modal {
            float: right;            font-size: 28px;
            cursor: pointer;
            color: #999;
        }
        @media (max-width: 768px) {
            .header { flex-direction: column; text-align: center; }
            table { font-size: 12px; }
            th, td { padding: 8px 4px; }
            .product-image { width: 50px; height: 50px; }
            .btn { padding: 6px 10px; font-size: 12px; }
            body { padding: 10px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 Products Management</h1>
            <div class="nav-links">
                <a href="/admin/orders" class="btn btn-info">📬 Orders</a>
                <a href="/admin_logout" class="btn btn-danger">Logout</a>
            </div>
        </div>
        
        <div class="section">
            <h2>➕ Add New Product</h2>
            <form method="POST" action="/admin/add_product" enctype="multipart/form-data">
                <div class="form-group">
                    <label>Product Name:</label>
                    <input type="text" name="name" required style="width: 100%;">
                </div>
                <div class="form-group">
                    <label>Price (Rs.):</label>
                    <input type="number" name="price" step="0.01" required style="width: 200px;">
                </div>
                <div class="form-group">
                    <label>Category:</label>
                    <input type="text" name="category" placeholder="e.g., Rice, Flour, Spices" style="width: 300px;">
                </div>
                <div class="form-group">
                    <label>Product Image:</label>
                    <input type="file" name="image" accept="image/*">
                </div>
                <button type="submit" class="btn btn-success">➕ Add Product</button>
            </form>
        </div>
        
        <div class="section">
            <h2>📋 All Products ({{ products|length }})</h2>
            <table>                <thead>
                    <tr>
                        <th>Image</th>
                        <th>Name</th>
                        <th>Category</th>
                        <th>Price</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for product in products %}
                    <tr>
                        <td>
                            {% if product.image_path %}
                            <img src="{{ product.image_path }}" alt="{{ product.name }}" class="product-image">
                            {% else %}
                            <div style="width: 80px; height: 80px; background: #e0e0e0; display: flex; align-items: center; justify-content: center; border-radius: 5px;">No Image</div>
                            {% endif %}
                        </td>
                        <td>{{ product.name }}</td>
                        <td>{{ product.category or 'N/A' }}</td>
                        <td>Rs. {{ product.price }}</td>
                        <td>
                            <button class="btn btn-warning" onclick="editProduct({{ product.id }}, '{{ product.name }}', {{ product.price }}, '{{ product.category or '' }}')">Edit</button>
                            <form method="POST" action="/admin/delete_product/{{ product.id }}" style="display: inline;" onsubmit="return confirm('Delete this product?');">
                                <button type="submit" class="btn btn-danger">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <div id="editModal" class="modal">
        <div class="modal-content">
            <span class="close-modal" onclick="closeModal()">&times;</span>
            <h2>Edit Product</h2>
            <form id="editForm" method="POST" action="/admin/edit_product">
                <input type="hidden" name="id" id="editId">
                <div class="form-group">
                    <label>Product Name:</label>
                    <input type="text" name="name" id="editName" required style="width: 100%;">
                </div>
                <div class="form-group">
                    <label>Price:</label>
                    <input type="number" name="price" id="editPrice" step="0.01" required style="width: 200px;">
                </div>
                <div class="form-group">                    <label>Category:</label>
                    <input type="text" name="category" id="editCategory" style="width: 300px;">
                </div>
                <button type="submit" class="btn btn-success">💾 Save Changes</button>
            </form>
        </div>
    </div>
    
    <script>
        function editProduct(id, name, price, category) {
            document.getElementById('editId').value = id;
            document.getElementById('editName').value = name;
            document.getElementById('editPrice').value = price;
            document.getElementById('editCategory').value = category;
            document.getElementById('editModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('editModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
'''

ADMIN_ORDERS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin - Orders Management</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#7b1fa2">
    <link rel="manifest" href="/static/manifest.json">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .header {
            background: #7b1fa2;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .section {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #7b1fa2;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #7b1fa2;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            margin: 5px;
        }
        .btn-primary { background: #1976d2; color: white; }
        .btn-success { background: #388e3c; color: white; }
        .btn-danger { background: #d32f2f; color: white; }
        .btn-info { background: #0288d1; color: white; }
        .btn:hover { opacity: 0.9; }
        .order-card {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #1976d2;
        }
        .order-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #ddd;
        }
        .order-status {
            padding: 5px 15px;
            border-radius: 20px;            font-size: 12px;
            font-weight: bold;
        }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-purchased { background: #cce5ff; color: #004085; }
        .status-delivered { background: #d4edda; color: #155724; }
        .status-cancelled { background: #f8d7da; color: #721c24; }
        .delivery-info {
            background: #e3f2fd;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }
        .nav-links {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        select {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        @media (max-width: 768px) {
            .header { flex-direction: column; text-align: center; }
            .order-header { flex-direction: column; }
            body { padding: 10px; }
            .section { padding: 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📬 Orders Management</h1>
            <div class="nav-links">
                <a href="/admin/products" class="btn btn-info">📦 Products</a>
                <a href="/admin_logout" class="btn btn-danger">Logout</a>
            </div>
        </div>
        
        <div class="section">
            <h2>📦 All Orders ({{ orders|length }})</h2>
            {% if orders %}
                {% for order in orders %}
                <div class="order-card">
                    <div class="order-header">
                        <div>
                            <strong>🏪 {{ order.shop_name }}</strong><br>                            <small>
                                Order #{{ order.id }}<br>
                                Order Date: {{ order.order_date.strftime('%Y-%m-%d %I:%M %p') if order.order_date else 'N/A' }} (PKT)<br>
                                Purchase Date: {{ order.purchase_date.strftime('%Y-%m-%d') if order.purchase_date else 'N/A' }}<br>
                                Delivery Date: {{ order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else 'N/A' }}
                            </small>
                        </div>
                        <div>
                            <span class="order-status status-{{ order.status }}">{{ order.status.upper() }}</span>
                        </div>
                    </div>
                    <div>
                        <strong>📦 Order Items:</strong>
                        <table style="width: 100%; margin: 10px 0; border-collapse: collapse;">
                            <thead>
                                <tr style="background: #f5f5f5;">
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Product</th>
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Qty</th>
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Price</th>
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Subtotal</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if order.items_list %}
                                    {% for item in order.items_list %}
                                    <tr>
                                        <td style="padding: 10px; border: 1px solid #ddd;">{{ item.name }}</td>
                                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{{ item.quantity }}</td>
                                        <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">Rs. {{ item.price }}</td>
                                        <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">Rs. {{ item.price * item.quantity }}</td>
                                    </tr>
                                    {% endfor %}
                                {% else %}
                                    <tr><td colspan="4" style="padding: 10px; text-align: center;">No items</td></tr>
                                {% endif %}
                            </tbody>
                            <tfoot>
                                <tr style="background: #e3f2fd; font-weight: bold;">
                                    <td colspan="3" style="padding: 10px; border: 1px solid #ddd; text-align: right;">Total:</td>
                                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right; color: #388e3c; font-size: 18px;">Rs. {{ order.total }}</td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                    <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                        <form method="POST" action="/admin/update_order/{{ order.id }}" style="display: inline;">
                            <select name="status" style="margin-right: 10px;">
                                <option value="pending" {% if order.status == 'pending' %}selected{% endif %}>Pending</option>
                                <option value="purchased" {% if order.status == 'purchased' %}selected{% endif %}>Purchased</option>
                                <option value="delivered" {% if order.status == 'delivered' %}selected{% endif %}>Delivered</option>                                <option value="cancelled" {% if order.status == 'cancelled' %}selected{% endif %}>Cancelled</option>
                            </select>
                            <button type="submit" class="btn btn-primary">Update Status</button>
                        </form>
                        <form method="POST" action="/admin/delete_order/{{ order.id }}" style="display: inline;" onsubmit="return confirm('Delete this order? This cannot be undone!');">
                            <button type="submit" class="btn btn-danger">🗑️ Delete Order</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p style="color: #999; text-align: center; padding: 40px;">No orders yet</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

# ==================== CUSTOMER ROUTES ====================

@app.route('/')
def home():
    if not session.get('logged_in'):
        return render_template_string(HTML_TEMPLATE, products=[], categories=[])
    
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template_string(HTML_TEMPLATE, products=products, categories=[])

@app.route('/login', methods=['POST'])
def login():
    shop_name = request.form.get('shop_name')
    session['logged_in'] = True
    session['shop_name'] = shop_name
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/my_orders')
def my_orders():
    if not session.get('logged_in'):
        return redirect(url_for('home'))
    
    shop_name = session.get('shop_name')
    orders = Order.query.filter_by(shop_name=shop_name).order_by(Order.order_date.desc()).all()
    
    # Parse JSON items for each order
    for order in orders:
        try:
            order.items_list = json.loads(order.items) if order.items else []
        except:
            order.items_list = []
    
    return render_template_string(MY_ORDERS_TEMPLATE, orders=orders)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    if not session.get('logged_in'):
        return redirect(url_for('home'))
    
    shop_name = session.get('shop_name')
    order = Order.query.filter_by(id=order_id, shop_name=shop_name).first()
    if order:
        order.status = 'cancelled'
        db.session.commit()
    
    return redirect(url_for('my_orders'))

@app.route('/submit_order', methods=['POST'])
def submit_order():
    data = request.json
    shop_name = data.get('shop_name')
    items = data.get('items')
    total = data.get('total')
    delivery_date_str = data.get('delivery_date')
    
    # پاکستان کا ٹائم زون (UTC+5)
    pk_timezone = timezone(timedelta(hours=5))
    
    # آج کا ٹائم (پاکستان کے مطابق)
    order_date = datetime.now(pk_timezone)
    
    # خریداری کا دن (اگلے دن)
    purchase_date = order_date + timedelta(days=1)
    
    # ڈیلیوری کا دن (دوسرے دن بعد)
    delivery_date = order_date + timedelta(days=2)
    
    # 7 دن بعد ایکسپائر
    expire_date = order_date + timedelta(days=7)
    
    new_order = Order(
        shop_name=shop_name,
        items=json.dumps(items),
        total=total,
        status='pending',
        order_date=order_date,        purchase_date=purchase_date,
        delivery_date=delivery_date,
        expire_date=expire_date
    )
    
    db.session.add(new_order)
    db.session.commit()
    
    return jsonify({'success': True})

# ==================== ADMIN ROUTES ====================

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_products'))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error='Invalid username or password')
    
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=None)

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))

@app.route('/admin')
@admin_required
def admin():
    return redirect(url_for('admin_products'))

@app.route('/admin/products')
@admin_required
def admin_products():
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template_string(ADMIN_PRODUCTS_TEMPLATE, products=products)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    
    # Parse JSON items for each order
    for order in orders:
        try:            order.items_list = json.loads(order.items) if order.items else []
        except:
            order.items_list = []
    
    return render_template_string(ADMIN_ORDERS_TEMPLATE, orders=orders)

@app.route('/admin/add_product', methods=['POST'])
@admin_required
def add_product():
    name = request.form.get('name')
    price = float(request.form.get('price'))
    category = request.form.get('category')
    
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            
            upload_folder = app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)

            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            image_path = '/static/uploads/' + filename
    
    new_product = Product(
        name=name,
        price=price,
        category=category,
        image_path=image_path
    )
    db.session.add(new_product)
    db.session.commit()
    
    return redirect(url_for('admin_products'))

@app.route('/admin/edit_product', methods=['POST'])
@admin_required
def edit_product():
    product_id = request.form.get('id')
    name = request.form.get('name')
    price = float(request.form.get('price'))
    category = request.form.get('category')
    
    product = Product.query.get_or_404(product_id)
    product.name = name
    product.price = price
    product.category = category
    
    db.session.commit()
    
    return redirect(url_for('admin_products'))

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('admin_products'))

@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
@admin_required
def update_order(order_id):
    status = request.form.get('status')
    order = Order.query.get_or_404(order_id)
    order.status = status
    
    # Auto-set purchase date when status changes to purchased
    if status == 'purchased' and not order.purchase_date:
        order.purchase_date = get_pakistan_time()
    
    # Auto-set delivery date when status changes to delivered
    if status == 'delivered' and not order.delivery_date:
        order.delivery_date = get_pakistan_time()
    
    db.session.commit()
    return redirect(url_for('admin_orders'))

@app.route('/admin/delete_order/<int:order_id>', methods=['POST'])
@admin_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for('admin_orders'))

# ==================== PWA ROUTES ====================

@app.route('/static/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/static/service-worker.js')
def serve_sw():
    return send_from_directory('static', 'service-worker.js')
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ==================== RUN APP ====================

import os
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8550))
    app.run(host='0.0.0.0', port=port, debug=False)
