import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ecommerce.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            postal_code TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. admins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            icon TEXT DEFAULT 'fa-box',
            image_url TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            discount_price REAL,
            stock INTEGER NOT NULL DEFAULT 0,
            image_url TEXT NOT NULL,
            sku TEXT DEFAULT '',
            brand TEXT DEFAULT 'ShopEase Originals',
            rating REAL DEFAULT 4.8,
            reviews_count INTEGER DEFAULT 24,
            views INTEGER DEFAULT 0,
            is_featured INTEGER DEFAULT 0,
            is_trending INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
        )
    ''')

    # 5. cart_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')

    # 6. orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL UNIQUE,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            phone TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            city TEXT NOT NULL,
            postal_code TEXT NOT NULL,
            order_notes TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            shipping_fee REAL NOT NULL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Cash on Delivery',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')

    # 7. order_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            product_image TEXT NOT NULL,
            unit_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
        )
    ''')

    conn.commit()
    seed_initial_data(conn)
    conn.close()

def seed_initial_data(conn):
    cursor = conn.cursor()

    # Seed Admin
    cursor.execute("SELECT COUNT(*) FROM admins")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO admins (username, email, full_name, password_hash)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@shopease.com', 'Alex Morgan (Administrator)', generate_password_hash('admin123')))

    # Seed Demo Customer
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        demo_users = [
            ('Sarah Jenkins', 'customer@shopease.com', generate_password_hash('customer123'), '+1 (555) 234-5678', '742 Evergreen Terrace, Apt 4B', 'San Francisco, CA', '94107'),
            ('Michael Chen', 'michael.chen@example.com', generate_password_hash('customer123'), '+1 (555) 876-5432', '1280 Innovation Way', 'Austin, TX', '78701'),
            ('Elena Rodriguez', 'elena.r@example.com', generate_password_hash('customer123'), '+1 (555) 392-1109', '450 Park Avenue South', 'New York, NY', '10016')
        ]
        cursor.executemany('''
            INSERT INTO users (full_name, email, password_hash, phone, address, city, postal_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', demo_users)

    # Seed Categories
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        categories = [
            ('Electronics & Audio', 'electronics-audio', 'Flagship headphones, smart devices, and wireless audio gear.', 'fa-headphones-simple', '/static/images/products/headphones.svg'),
            ('Smart Watches & Wearables', 'smart-watches', 'Next-gen health trackers, luxury smartwatches, and fitness bands.', 'fa-clock', '/static/images/products/smartwatch.svg'),
            ('Fashion & Apparel', 'fashion-apparel', 'Contemporary streetwear, tailored jackets, and everyday essentials.', 'fa-shirt', '/static/images/products/jacket.svg'),
            ('Footwear & Sneakers', 'footwear-sneakers', 'Performance running shoes, urban sneakers, and handcrafted boots.', 'fa-shoe-prints', '/static/images/products/sneakers.svg'),
            ('Bags & Accessories', 'bags-accessories', 'Minimalist commuter backpacks, leather goods, and designer eyewear.', 'fa-bag-shopping', '/static/images/products/backpack.svg'),
            ('Home & Workspace', 'home-workspace', 'Ergonomic desk accessories, mechanical keyboards, and smart lighting.', 'fa-laptop-code', '/static/images/products/keyboard.svg')
        ]
        cursor.executemany('''
            INSERT INTO categories (name, slug, description, icon, image_url)
            VALUES (?, ?, ?, ?, ?)
        ''', categories)
        conn.commit()

    # Seed Products
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id, slug FROM categories")
        cat_map = {row['slug']: row['id'] for row in cursor.fetchall()}

        products = [
            (
                cat_map['electronics-audio'],
                'AuraSonic Pro ANC Wireless Headphones',
                'aurasonic-pro-anc-headphones',
                'Experience studio-grade spatial audio with hybrid active noise cancellation. Engineered with custom 45mm beryllium drivers, memory-foam protein leather earcups, and an industry-leading 48-hour battery life with rapid USB-C charging.',
                299.99, 229.99, 35,
                '/static/images/products/headphones.svg',
                'SE-AUD-001', 'AuraSonic', 4.9, 142, 680, 1, 1
            ),
            (
                cat_map['smart-watches'],
                'ChronoPulse Ultra Titanium Smartwatch',
                'chronopulse-ultra-smartwatch',
                'Precision aerospace-grade titanium chassis paired with a 2000-nit sapphire AMOLED display. Features dual-frequency GPS, ECG heart monitoring, blood oxygen tracking, and 100m water resistance for peak athletic performance.',
                399.00, 329.00, 22,
                '/static/images/products/smartwatch.svg',
                'SE-WTC-002', 'ChronoPulse', 4.8, 98, 540, 1, 1
            ),
            (
                cat_map['footwear-sneakers'],
                'Velocity Nitro Cloud Runner Sneakers',
                'velocity-nitro-cloud-sneakers',
                'Ultra-lightweight nitrogen-infused foam midsole delivers effortless energy return with every stride. Designed with a breathable engineered mesh upper and high-traction continental rubber outsole.',
                165.00, 129.99, 48,
                '/static/images/products/sneakers.svg',
                'SE-FTW-003', 'Velocity Lab', 4.9, 215, 890, 1, 1
            ),
            (
                cat_map['bags-accessories'],
                'Nomad Pro 24L Weatherproof Commuter Pack',
                'nomad-pro-24l-commuter-pack',
                'Crafted from recycled ballistic Cordura nylon with waterproof YKK AquaGuard zippers. Includes a suspended 16-inch plush laptop compartment, magnetic sternum strap, and hidden RFID-blocking passport pocket.',
                189.00, None, 30,
                '/static/images/products/backpack.svg',
                'SE-BAG-004', 'Nomad Gear', 4.7, 76, 410, 1, 0
            ),
            (
                cat_map['home-workspace'],
                'KeyCraft Halo75 Wireless Mechanical Keyboard',
                'keycraft-halo75-mechanical-keyboard',
                'Gasket-mounted aluminum mechanical keyboard with hot-swappable tactile switches, double-shot PBT keycaps, and customizable South-facing RGB lighting. Connects seamlessly via Bluetooth 5.3, 2.4GHz wireless, or USB-C.',
                179.99, 144.99, 40,
                '/static/images/products/keyboard.svg',
                'SE-WRK-005', 'KeyCraft', 4.9, 164, 720, 1, 1
            ),
            (
                cat_map['electronics-audio'],
                'LumixPro 4K Mirrorless Creator Camera',
                'lumixpro-4k-mirrorless-camera',
                'Compact full-frame mirrorless camera featuring a 33MP BSI CMOS sensor, 10-bit 4K 60p internal video recording, 5-axis in-body image stabilization, and real-time AI subject autofocus.',
                1299.00, None, 12,
                '/static/images/products/camera.svg',
                'SE-CAM-006', 'LumixPro', 4.9, 53, 620, 1, 0
            ),
            (
                cat_map['fashion-apparel'],
                'Vertex All-Weather Tech Shell Jacket',
                'vertex-all-weather-tech-jacket',
                '3-layer breathable membrane windbreaker engineered for urban exploration. Fully seam-sealed with articulated sleeves, laser-cut ventilation, and four concealed waterproof utility pockets.',
                220.00, 174.99, 28,
                '/static/images/products/jacket.svg',
                'SE-FSH-007', 'Vertex Studio', 4.7, 89, 390, 0, 1
            ),
            (
                cat_map['bags-accessories'],
                'Solstice Polarized Acetate Sunglasses',
                'solstice-polarized-sunglasses',
                'Hand-polished Italian Mazzucchelli acetate frames fitted with scratch-resistant UV400 polarized sapphire lenses. Lightweight five-barrel titanium hinges ensure all-day comfort.',
                145.00, None, 55,
                '/static/images/products/sunglasses.svg',
                'SE-ACC-008', 'Solstice Eyewear', 4.6, 61, 310, 0, 0
            ),
            (
                cat_map['home-workspace'],
                'Lumina Qi2 Magnetic Desk Lamp & Charger',
                'lumina-qi2-desk-lamp',
                'Architectural anodized aluminum LED desk bar with circadian color temperature adjustment (2700K-6500K) and an integrated 15W Qi2 fast wireless charging pad in the base.',
                119.00, 89.99, 44,
                '/static/images/products/desklamp.svg',
                'SE-WRK-009', 'Lumina Home', 4.8, 112, 460, 0, 1
            ),
            (
                cat_map['electronics-audio'],
                'PulseMini 360 Spatial Bluetooth Speaker',
                'pulsemini-360-bluetooth-speaker',
                'Pocket-sized acoustic powerhouse with dual passive radiators and 360-degree omnidirectional sound. IP67 waterproof and dustproof rating with 18 hours of continuous playtime.',
                129.00, 94.99, 60,
                '/static/images/products/speaker.svg',
                'SE-AUD-010', 'AuraSonic', 4.7, 138, 515, 0, 1
            ),
            (
                cat_map['smart-watches'],
                'AeroBand Pro Recovery & Sleep Tracker',
                'aeroband-pro-sleep-tracker',
                'Screen-free minimalist biometric strap that continuously measures HRV, skin temperature, sleep stages, and daily strain score with a 14-day battery life.',
                199.00, None, 33,
                '/static/images/products/fitnessband.svg',
                'SE-WTC-011', 'ChronoPulse', 4.6, 47, 290, 0, 0
            ),
            (
                cat_map['footwear-sneakers'],
                'Monarch Chelsea Weatherproof Leather Boots',
                'monarch-chelsea-leather-boots',
                'Full-grain hydrophobic Italian calfskin upper with Goodyear welt construction and shock-absorbing Vibram lug soles. Timeless silhouette built for comfort from boardroom to cobblestone.',
                245.00, 199.00, 19,
                '/static/images/products/boots.svg',
                'SE-FTW-012', 'Monarch Supply', 4.9, 83, 355, 1, 0
            )
        ]

        cursor.executemany('''
            INSERT INTO products (
                category_id, name, slug, description, price, discount_price,
                stock, image_url, sku, brand, rating, reviews_count, views,
                is_featured, is_trending
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', products)
        conn.commit()

    # Seed Demo Orders so Admin Dashboard has realistic analytics right away
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id, full_name, email, phone, address, city, postal_code FROM users ORDER BY id")
        users = cursor.fetchall()
        cursor.execute("SELECT id, name, image_url, price, discount_price FROM products ORDER BY id")
        prods = cursor.fetchall()

        if users and len(prods) >= 5:
            u1, u2, u3 = users[0], users[1], users[2]
            p1, p2, p3, p4, p5 = prods[0], prods[1], prods[2], prods[3], prods[4]

            p1_price = p1['discount_price'] or p1['price']
            p2_price = p2['discount_price'] or p2['price']
            p3_price = p3['discount_price'] or p3['price']
            p4_price = p4['discount_price'] or p4['price']
            p5_price = p5['discount_price'] or p5['price']

            # Order 1 - Delivered
            sub1 = round(p1_price + p3_price, 2)
            cursor.execute('''
                INSERT INTO orders (
                    order_number, user_id, customer_name, customer_email, phone,
                    shipping_address, city, postal_code, order_notes,
                    subtotal, shipping_fee, total_amount, payment_method, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-5 days'))
            ''', (
                'SE-2026-1001', u1['id'], u1['full_name'], u1['email'], u1['phone'],
                u1['address'], u1['city'], u1['postal_code'], 'Leave at front concierge desk.',
                sub1, 0.0, sub1, 'Cash on Delivery', 'Delivered'
            ))
            o1_id = cursor.lastrowid
            cursor.executemany('''
                INSERT INTO order_items (order_id, product_id, product_name, product_image, unit_price, quantity, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                (o1_id, p1['id'], p1['name'], p1['image_url'], p1_price, 1, p1_price),
                (o1_id, p3['id'], p3['name'], p3['image_url'], p3_price, 1, p3_price)
            ])

            # Order 2 - Shipped
            sub2 = round(p2_price + p5_price, 2)
            cursor.execute('''
                INSERT INTO orders (
                    order_number, user_id, customer_name, customer_email, phone,
                    shipping_address, city, postal_code, order_notes,
                    subtotal, shipping_fee, total_amount, payment_method, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-2 days'))
            ''', (
                'SE-2026-1002', u2['id'], u2['full_name'], u2['email'], u2['phone'],
                u2['address'], u2['city'], u2['postal_code'], 'Call upon arrival.',
                sub2, 0.0, sub2, 'Cash on Delivery', 'Shipped'
            ))
            o2_id = cursor.lastrowid
            cursor.executemany('''
                INSERT INTO order_items (order_id, product_id, product_name, product_image, unit_price, quantity, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                (o2_id, p2['id'], p2['name'], p2['image_url'], p2_price, 1, p2_price),
                (o2_id, p5['id'], p5['name'], p5['image_url'], p5_price, 1, p5_price)
            ])

            # Order 3 - Processing
            sub3 = round(p4_price * 2, 2)
            cursor.execute('''
                INSERT INTO orders (
                    order_number, user_id, customer_name, customer_email, phone,
                    shipping_address, city, postal_code, order_notes,
                    subtotal, shipping_fee, total_amount, payment_method, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-6 hours'))
            ''', (
                'SE-2026-1003', u3['id'], u3['full_name'], u3['email'], u3['phone'],
                u3['address'], u3['city'], u3['postal_code'], '',
                sub3, 0.0, sub3, 'Cash on Delivery', 'Processing'
            ))
            o3_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, product_name, product_image, unit_price, quantity, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (o3_id, p4['id'], p4['name'], p4['image_url'], p4_price, 2, sub3))

            conn.commit()
