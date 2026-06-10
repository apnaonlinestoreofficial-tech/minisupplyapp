import sqlite3
import os
from datetime import datetime
import hashlib

DATABASE_NAME = 'supply.db'

def get_db_connection():
    """Provides a connection to the database with row_factory for easy access."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # This makes it easier to access columns by name
    return conn

def hash_password(password):
    """Hashes a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Initializes the database and creates necessary tables."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"🚀 Initializing database: {DATABASE_NAME}")
    
    # 1. Shops table (for Super Admin and individual shop accounts)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            password TEXT NOT NULL, -- Store hashed passwords
            status TEXT DEFAULT 'active', -- To activate/deactivate shops
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ 'shops' table created or already exists.")
    
    # 2. Products table with foreign key to shops
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE -- If shop is deleted, delete its products
        )
    ''')
    print("✅ 'products' table created or already exists.")
    
    # 3. Orders table with foreign key to shops
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            shop_name TEXT NOT NULL, -- Keep name for easier querying in some contexts, but shop_id is the key
            customer_name TEXT,
            customer_phone TEXT,
            items TEXT NOT NULL, -- JSON string of items
            total REAL NOT NULL,
            delivery_date TEXT, -- Store as string e.g. 'YYYY-MM-DD HH:MM:SS'
            status TEXT DEFAULT 'pending', -- e.g., pending, delivered, cancelled
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE -- If shop is deleted, delete its orders
        )
    ''')
    print("✅ 'orders' table created or already exists.")
    
    # 4. Create default Super Admin shop if it doesn't exist
    SUPER_ADMIN_USERNAME = 'admin'
    SUPER_ADMIN_DEFAULT_PASSWORD = 'admin123' # Remember to change this later!
    
    cursor.execute("SELECT id FROM shops WHERE name = ?", (SUPER_ADMIN_USERNAME,))
    admin_shop = cursor.fetchone()
    
    if not admin_shop:
        try:
            hashed_admin_password = hash_password(SUPER_ADMIN_DEFAULT_PASSWORD)
            cursor.execute('''
                INSERT INTO shops (name, email, password, status) 
                VALUES (?, ?, ?, ?)
            ''', (SUPER_ADMIN_USERNAME, 'admin@example.com', hashed_admin_password, 'active'))
            print(f"✅ Default Super Admin shop ('{SUPER_ADMIN_USERNAME}') created with hashed password.")
        except sqlite3.IntegrityError:
            print("⚠️ Default Super Admin shop already exists (IntegrityError during insert).")
        except Exception as e:
            print(f"❌ Error creating default Super Admin shop: {e}")
    else:
        print(f"ℹ️ Default Super Admin shop ('{SUPER_ADMIN_USERNAME}') already exists.")
    
    conn.commit()
    conn.close()
    print("🎉 Database initialization complete!")

if __name__ == '__main__':
    # Ensure the upload directory exists for images
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)
        print(f"📁 Created upload directory: {upload_dir}")
        
    init_db()