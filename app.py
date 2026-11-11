import os
import re
import uuid
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('SHOPEASE_SECRET_KEY', 'shopease-super-secret-production-key-2026')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', 'products')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max upload

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'}

# Initialize SQLite database & seed data automatically
init_db()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-') or f"item-{uuid.uuid4().hex[:6]}"


def get_effective_price(product):
    if product['discount_price'] is not None and product['discount_price'] > 0 and product['discount_price'] < product['price']:
        return float(product['discount_price'])
    return float(product['price'])


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access that page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Administrator authentication required.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def get_cart_items_and_totals():
    conn = get_db_connection()
    items = []
    subtotal = 0.0
    original_subtotal = 0.0
    total_qty = 0

    if 'user_id' in session:
        rows = conn.execute('''
            SELECT ci.product_id, ci.quantity,
                   p.name, p.slug, p.price, p.discount_price, p.stock, p.image_url, p.brand,
                   c.name AS category_name
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE ci.user_id = ?
            ORDER BY ci.id DESC
        ''', (session['user_id'],)).fetchall()

        for row in rows:
            unit_price = get_effective_price(row)
            qty = min(row['quantity'], max(1, row['stock'])) if row['stock'] > 0 else row['quantity']
            line_total = round(unit_price * qty, 2)
            subtotal += line_total
            original_subtotal += round(float(row['price']) * qty, 2)
            total_qty += qty
            items.append({
                'product_id': row['product_id'],
                'name': row['name'],
                'slug': row['slug'],
                'brand': row['brand'],
                'category_name': row['category_name'],
                'price': float(row['price']),
                'discount_price': float(row['discount_price']) if row['discount_price'] else None,
                'unit_price': unit_price,
                'quantity': qty,
                'stock': row['stock'],
                'image_url': row['image_url'],
                'line_total': line_total
            })
    else:
        session_cart = session.get('guest_cart', {})
        if session_cart:
            product_ids = [int(pid) for pid in session_cart.keys() if str(pid).isdigit()]
            if product_ids:
                placeholders = ','.join(['?'] * len(product_ids))
                rows = conn.execute(f'''
                    SELECT p.id AS product_id, p.name, p.slug, p.price, p.discount_price,
                           p.stock, p.image_url, p.brand, c.name AS category_name
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.id IN ({placeholders})
                ''', product_ids).fetchall()

                for row in rows:
                    raw_qty = int(session_cart.get(str(row['product_id']), 1))
                    qty = max(1, min(raw_qty, row['stock'])) if row['stock'] > 0 else raw_qty
                    unit_price = get_effective_price(row)
                    line_total = round(unit_price * qty, 2)
                    subtotal += line_total
                    original_subtotal += round(float(row['price']) * qty, 2)
                    total_qty += qty
                    items.append({
                        'product_id': row['product_id'],
                        'name': row['name'],
                        'slug': row['slug'],
                        'brand': row['brand'],
                        'category_name': row['category_name'],
                        'price': float(row['price']),
                        'discount_price': float(row['discount_price']) if row['discount_price'] else None,
                        'unit_price': unit_price,
                        'quantity': qty,
                        'stock': row['stock'],
                        'image_url': row['image_url'],
                        'line_total': line_total
                    })

    conn.close()
    subtotal = round(subtotal, 2)
    original_subtotal = round(original_subtotal, 2)
    discount_savings = round(max(0.0, original_subtotal - subtotal), 2)
    shipping_fee = 0.0 if (subtotal >= 100.0 or subtotal == 0.0) else 9.99
    total_amount = round(subtotal + shipping_fee, 2)

    return {
        'items': items,
        'total_qty': total_qty,
        'subtotal': subtotal,
        'original_subtotal': original_subtotal,
        'discount_savings': discount_savings,
        'shipping_fee': shipping_fee,
        'total_amount': total_amount
    }


def merge_guest_cart_into_user(user_id):
    guest_cart = session.pop('guest_cart', {})
    if not guest_cart:
        return
    conn = get_db_connection()
    for pid_str, qty in guest_cart.items():
        if not str(pid_str).isdigit():
            continue
        pid = int(pid_str)
        prod = conn.execute('SELECT stock FROM products WHERE id = ?', (pid,)).fetchone()
        if not prod or prod['stock'] <= 0:
            continue
        existing = conn.execute(
            'SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?',
            (user_id, pid)
        ).fetchone()
        if existing:
            new_qty = min(prod['stock'], existing['quantity'] + int(qty))
            conn.execute(
                'UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?',
                (new_qty, user_id, pid)
            )
        else:
            new_qty = min(prod['stock'], max(1, int(qty)))
            conn.execute(
                'INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)',
                (user_id, pid, new_qty)
            )
    conn.commit()
    conn.close()


@app.context_processor
def inject_globals():
    conn = get_db_connection()
    nav_categories = conn.execute('SELECT id, name, slug, icon FROM categories ORDER BY id ASC').fetchall()
    conn.close()
    cart_summary = get_cart_items_and_totals()
    return {
        'nav_categories': nav_categories,
        'cart_count': cart_summary['total_qty'],
        'cart_subtotal': cart_summary['subtotal'],
        'current_user_id': session.get('user_id'),
        'current_user_name': session.get('user_name'),
        'current_user_email': session.get('user_email'),
        'current_admin_id': session.get('admin_id'),
        'current_admin_name': session.get('admin_name')
    }


# ==========================================
# CUSTOMER ROUTES
# ==========================================

@app.route('/')
def index():
    conn = get_db_connection()
    categories = conn.execute('''
        SELECT c.*, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        GROUP BY c.id
        ORDER BY c.id ASC
    ''').fetchall()

    featured_products = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.is_featured = 1
        ORDER BY p.id ASC
        LIMIT 8
    ''').fetchall()

    trending_products = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.is_trending = 1
        ORDER BY p.views DESC
        LIMIT 4
    ''').fetchall()

    latest_products = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY p.id DESC
        LIMIT 4
    ''').fetchall()

    conn.close()
    return render_template(
        'index.html',
        categories=categories,
        featured_products=featured_products,
        trending_products=trending_products,
        latest_products=latest_products
    )


@app.route('/shop')
def shop():
    conn = get_db_connection()

    q = request.args.get('q', '').strip()
    category_slug = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    sort_by = request.args.get('sort', 'popular').strip()
    in_stock_only = request.args.get('in_stock', '') == '1'

    query = '''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug,
               COALESCE(p.discount_price, p.price) AS effective_price
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    '''
    params = []

    if q:
        query += ' AND (p.name LIKE ? OR p.description LIKE ? OR p.brand LIKE ? OR c.name LIKE ?)'
        like_q = f'%{q}%'
        params.extend([like_q, like_q, like_q, like_q])

    if category_slug:
        if category_slug.isdigit():
            query += ' AND c.id = ?'
            params.append(int(category_slug))
        else:
            query += ' AND c.slug = ?'
            params.append(category_slug)

    if min_price:
        try:
            val = float(min_price)
            query += ' AND COALESCE(p.discount_price, p.price) >= ?'
            params.append(val)
        except ValueError:
            pass

    if max_price:
        try:
            val = float(max_price)
            query += ' AND COALESCE(p.discount_price, p.price) <= ?'
            params.append(val)
        except ValueError:
            pass

    if in_stock_only:
        query += ' AND p.stock > 0'

    if sort_by == 'price_asc':
        query += ' ORDER BY effective_price ASC'
    elif sort_by == 'price_desc':
        query += ' ORDER BY effective_price DESC'
    elif sort_by == 'newest':
        query += ' ORDER BY p.id DESC'
    elif sort_by == 'rating':
        query += ' ORDER BY p.rating DESC, p.reviews_count DESC'
    else:
        # default: popularity
        query += ' ORDER BY p.views DESC, p.reviews_count DESC'

    products = conn.execute(query, params).fetchall()

    categories = conn.execute('''
        SELECT c.*, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        GROUP BY c.id
        ORDER BY c.id ASC
    ''').fetchall()

    price_bounds = conn.execute('''
        SELECT MIN(COALESCE(discount_price, price)) AS min_p,
               MAX(COALESCE(discount_price, price)) AS max_p
        FROM products
    ''').fetchone()

    conn.close()
    return render_template(
        'shop.html',
        products=products,
        categories=categories,
        q=q,
        selected_category=category_slug,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        in_stock_only=in_stock_only,
        price_bounds=price_bounds
    )


@app.route('/deals')
def deals():
    conn = get_db_connection()

    category_slug = request.args.get('category', '').strip()
    sort_by = request.args.get('sort', 'discount_desc').strip()

    base_sql = '''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug,
               ROUND(((p.price - p.discount_price) / p.price) * 100.0, 0) AS discount_pct,
               ROUND(p.price - p.discount_price, 2) AS savings_amount
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.discount_price IS NOT NULL
          AND p.discount_price > 0
          AND p.discount_price < p.price
    '''
    params = []

    if category_slug:
        if category_slug.isdigit():
            base_sql += ' AND c.id = ?'
            params.append(int(category_slug))
        else:
            base_sql += ' AND c.slug = ?'
            params.append(category_slug)

    if sort_by == 'price_asc':
        order_clause = ' ORDER BY p.discount_price ASC'
    elif sort_by == 'savings_desc':
        order_clause = ' ORDER BY savings_amount DESC, discount_pct DESC'
    elif sort_by == 'popular':
        order_clause = ' ORDER BY p.views DESC, p.rating DESC'
    else:
        # default: highest discount percentage first
        order_clause = ' ORDER BY discount_pct DESC, savings_amount DESC'

    deal_products = conn.execute(base_sql + order_clause, params).fetchall()

    # Best Deals Section: Top 4 highest percentage / biggest savings deals from SQLite
    best_deals = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug,
               ROUND(((p.price - p.discount_price) / p.price) * 100.0, 0) AS discount_pct,
               ROUND(p.price - p.discount_price, 2) AS savings_amount
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.discount_price IS NOT NULL
          AND p.discount_price > 0
          AND p.discount_price < p.price
        ORDER BY discount_pct DESC, savings_amount DESC
        LIMIT 4
    ''').fetchall()

    # Limited Time Offers Section: Discounted items with limited stock or trending demand
    limited_time_offers = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug,
               ROUND(((p.price - p.discount_price) / p.price) * 100.0, 0) AS discount_pct,
               ROUND(p.price - p.discount_price, 2) AS savings_amount
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.discount_price IS NOT NULL
          AND p.discount_price > 0
          AND p.discount_price < p.price
          AND p.stock > 0
        ORDER BY p.stock ASC, discount_pct DESC
        LIMIT 4
    ''').fetchall()

    # Categories that have discounted products
    deal_categories = conn.execute('''
        SELECT c.*, COUNT(p.id) AS deal_count
        FROM categories c
        JOIN products p ON c.id = p.category_id
        WHERE p.discount_price IS NOT NULL
          AND p.discount_price > 0
          AND p.discount_price < p.price
        GROUP BY c.id
        ORDER BY deal_count DESC
    ''').fetchall()

    # Aggregate Deal Stats from DB
    deal_stats = conn.execute('''
        SELECT COUNT(*) AS total_deals,
               MAX(ROUND(((price - discount_price) / price) * 100.0, 0)) AS max_discount_pct,
               ROUND(SUM(price - discount_price), 2) AS total_catalog_savings
        FROM products
        WHERE discount_price IS NOT NULL
          AND discount_price > 0
          AND discount_price < price
    ''').fetchone()

    conn.close()
    return render_template(
        'deals.html',
        deal_products=deal_products,
        best_deals=best_deals,
        limited_time_offers=limited_time_offers,
        deal_categories=deal_categories,
        deal_stats=deal_stats,
        selected_category=category_slug,
        sort_by=sort_by
    )


@app.route('/product/<int:product_id>')
def product_details(product_id):
    conn = get_db_connection()
    product = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    ''', (product_id,)).fetchone()

    if not product:
        conn.close()
        abort(404)

    # Increment view count
    conn.execute('UPDATE products SET views = views + 1 WHERE id = ?', (product_id,))
    conn.commit()

    related_products = conn.execute('''
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.category_id = ? AND p.id != ?
        ORDER BY p.views DESC
        LIMIT 4
    ''', (product['category_id'], product_id)).fetchall()

    if len(related_products) < 4:
        exclude_ids = [product_id] + [r['id'] for r in related_products]
        placeholders = ','.join(['?'] * len(exclude_ids))
        more_related = conn.execute(f'''
            SELECT p.*, c.name AS category_name, c.slug AS category_slug
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE p.id NOT IN ({placeholders})
            ORDER BY p.is_featured DESC, p.views DESC
            LIMIT ?
        ''', exclude_ids + [4 - len(related_products)]).fetchall()
        related_products = list(related_products) + list(more_related)

    conn.close()
    return render_template(
        'product_details.html',
        product=product,
        related_products=related_products
    )


# ==========================================
# SHOPPING CART ROUTES (AJAX + STANDARD POST)
# ==========================================

@app.route('/cart')
def cart():
    cart_data = get_cart_items_and_totals()
    return render_template('cart.html', cart=cart_data)


@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    data = request.get_json(silent=True) or request.form

    try:
        product_id = int(data.get('product_id', 0))
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid product or quantity.'}), 400
        flash('Invalid product or quantity.', 'error')
        return redirect(request.referrer or url_for('shop'))

    if quantity < 1:
        quantity = 1

    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Product not found.'}), 404
        flash('Product not found.', 'error')
        return redirect(url_for('shop'))

    if product['stock'] <= 0:
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Sorry, this product is currently out of stock.'}), 400
        flash('Sorry, this product is currently out of stock.', 'error')
        return redirect(request.referrer or url_for('product_details', product_id=product_id))

    if 'user_id' in session:
        user_id = session['user_id']
        existing = conn.execute(
            'SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?',
            (user_id, product_id)
        ).fetchone()
        if existing:
            new_qty = min(product['stock'], existing['quantity'] + quantity)
            conn.execute(
                'UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?',
                (new_qty, user_id, product_id)
            )
        else:
            new_qty = min(product['stock'], quantity)
            conn.execute(
                'INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)',
                (user_id, product_id, new_qty)
            )
        conn.commit()
    else:
        guest_cart = session.get('guest_cart', {})
        pid_key = str(product_id)
        current_qty = int(guest_cart.get(pid_key, 0))
        guest_cart[pid_key] = min(product['stock'], current_qty + quantity)
        session['guest_cart'] = guest_cart
        session.modified = True

    conn.close()
    cart_summary = get_cart_items_and_totals()
    msg = f'Added "{product["name"]}" to your cart!'

    if is_ajax:
        return jsonify({
            'success': True,
            'message': msg,
            'cart_count': cart_summary['total_qty'],
            'subtotal': cart_summary['subtotal'],
            'total_amount': cart_summary['total_amount']
        })

    flash(msg, 'success')
    return redirect(request.referrer or url_for('cart'))


@app.route('/cart/update', methods=['POST'])
def update_cart():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    data = request.get_json(silent=True) or request.form

    try:
        product_id = int(data.get('product_id', 0))
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid input.'}), 400
        return redirect(url_for('cart'))

    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Product not found.'}), 404
        return redirect(url_for('cart'))

    if quantity <= 0:
        if 'user_id' in session:
            conn.execute('DELETE FROM cart_items WHERE user_id = ? AND product_id = ?', (session['user_id'], product_id))
            conn.commit()
        else:
            guest_cart = session.get('guest_cart', {})
            guest_cart.pop(str(product_id), None)
            session['guest_cart'] = guest_cart
            session.modified = True
        conn.close()
        cart_summary = get_cart_items_and_totals()
        if is_ajax:
            return jsonify({
                'success': True,
                'removed': True,
                'message': 'Item removed from cart.',
                'cart_count': cart_summary['total_qty'],
                'subtotal': cart_summary['subtotal'],
                'discount_savings': cart_summary['discount_savings'],
                'shipping_fee': cart_summary['shipping_fee'],
                'total_amount': cart_summary['total_amount']
            })
        flash('Item removed from cart.', 'info')
        return redirect(url_for('cart'))

    capped_qty = min(quantity, max(1, product['stock']))
    if 'user_id' in session:
        conn.execute(
            'UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?',
            (capped_qty, session['user_id'], product_id)
        )
        conn.commit()
    else:
        guest_cart = session.get('guest_cart', {})
        guest_cart[str(product_id)] = capped_qty
        session['guest_cart'] = guest_cart
        session.modified = True

    conn.close()
    cart_summary = get_cart_items_and_totals()
    unit_price = get_effective_price(product)
    line_total = round(unit_price * capped_qty, 2)

    msg = 'Cart quantity updated.'
    if quantity > product['stock']:
        msg = f'Maximum available stock ({product["stock"]}) reached.'

    if is_ajax:
        return jsonify({
            'success': True,
            'removed': False,
            'message': msg,
            'quantity': capped_qty,
            'line_total': line_total,
            'cart_count': cart_summary['total_qty'],
            'subtotal': cart_summary['subtotal'],
            'discount_savings': cart_summary['discount_savings'],
            'shipping_fee': cart_summary['shipping_fee'],
            'total_amount': cart_summary['total_amount']
        })

    flash(msg, 'info')
    return redirect(url_for('cart'))


@app.route('/cart/remove', methods=['POST'])
def remove_from_cart():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    data = request.get_json(silent=True) or request.form

    try:
        product_id = int(data.get('product_id', 0))
    except (ValueError, TypeError):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid product.'}), 400
        return redirect(url_for('cart'))

    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute('DELETE FROM cart_items WHERE user_id = ? AND product_id = ?', (session['user_id'], product_id))
        conn.commit()
        conn.close()
    else:
        guest_cart = session.get('guest_cart', {})
        guest_cart.pop(str(product_id), None)
        session['guest_cart'] = guest_cart
        session.modified = True

    cart_summary = get_cart_items_and_totals()
    if is_ajax:
        return jsonify({
            'success': True,
            'message': 'Product removed from your cart.',
            'cart_count': cart_summary['total_qty'],
            'subtotal': cart_summary['subtotal'],
            'discount_savings': cart_summary['discount_savings'],
            'shipping_fee': cart_summary['shipping_fee'],
            'total_amount': cart_summary['total_amount']
        })

    flash('Product removed from your cart.', 'info')
    return redirect(url_for('cart'))


@app.route('/cart/clear', methods=['POST'])
def clear_cart():
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute('DELETE FROM cart_items WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        conn.close()
    else:
        session.pop('guest_cart', None)
    flash('Your shopping cart has been cleared.', 'info')
    return redirect(url_for('cart'))


# ==========================================
# CHECKOUT & ORDER PLACEMENT
# ==========================================

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_data = get_cart_items_and_totals()
    if not cart_data['items']:
        flash('Your cart is empty. Add some products before checking out.', 'warning')
        return redirect(url_for('shop'))

    conn = get_db_connection()
    user_info = None
    if 'user_id' in session:
        user_info = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        phone = request.form.get('phone', '').strip()
        shipping_address = request.form.get('shipping_address', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        order_notes = request.form.get('order_notes', '').strip()
        payment_method = 'Cash on Delivery'

        errors = []
        if len(customer_name) < 2:
            errors.append('Please enter your full name.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', customer_email):
            errors.append('Please enter a valid email address.')
        if len(phone) < 7:
            errors.append('Please enter a valid phone number.')
        if len(shipping_address) < 5:
            errors.append('Please enter a complete street shipping address.')
        if len(city) < 2:
            errors.append('Please enter your city.')
        if len(postal_code) < 3:
            errors.append('Please enter a valid postal / ZIP code.')

        # Check stock availability
        for item in cart_data['items']:
            prod_row = conn.execute('SELECT stock, name FROM products WHERE id = ?', (item['product_id'],)).fetchone()
            if not prod_row or prod_row['stock'] < item['quantity']:
                avail = prod_row['stock'] if prod_row else 0
                errors.append(f'Insufficient stock for "{item["name"]}" (Available: {avail}).')

        if errors:
            for err in errors:
                flash(err, 'error')
            conn.close()
            return render_template('checkout.html', cart=cart_data, user=user_info, form_data=request.form)

        # Generate unique Order Number
        count_row = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        order_number = f"SE-2026-{1001 + count_row + int(uuid.uuid4().int % 900)}"
        while conn.execute('SELECT 1 FROM orders WHERE order_number = ?', (order_number,)).fetchone():
            order_number = f"SE-2026-{uuid.uuid4().hex[:6].upper()}"

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (
                order_number, user_id, customer_name, customer_email, phone,
                shipping_address, city, postal_code, order_notes,
                subtotal, shipping_fee, total_amount, payment_method, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_number,
            session.get('user_id'),
            customer_name,
            customer_email,
            phone,
            shipping_address,
            city,
            postal_code,
            order_notes,
            cart_data['subtotal'],
            cart_data['shipping_fee'],
            cart_data['total_amount'],
            payment_method,
            'Pending'
        ))
        order_id = cursor.lastrowid

        for item in cart_data['items']:
            cursor.execute('''
                INSERT INTO order_items (
                    order_id, product_id, product_name, product_image,
                    unit_price, quantity, subtotal
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_id,
                item['product_id'],
                item['name'],
                item['image_url'],
                item['unit_price'],
                item['quantity'],
                item['line_total']
            ))
            cursor.execute(
                'UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?',
                (item['quantity'], item['product_id'])
            )

        # Save user shipping details if logged in
        if 'user_id' in session:
            cursor.execute('''
                UPDATE users
                SET phone = COALESCE(NULLIF(?, ''), phone),
                    address = COALESCE(NULLIF(?, ''), address),
                    city = COALESCE(NULLIF(?, ''), city),
                    postal_code = COALESCE(NULLIF(?, ''), postal_code)
                WHERE id = ?
            ''', (phone, shipping_address, city, postal_code, session['user_id']))
            cursor.execute('DELETE FROM cart_items WHERE user_id = ?', (session['user_id'],))
        else:
            session.pop('guest_cart', None)

        conn.commit()
        conn.close()

        session['last_order_number'] = order_number
        flash(f'Order {order_number} placed successfully via Cash on Delivery!', 'success')
        return redirect(url_for('order_confirmation', order_number=order_number))

    conn.close()
    return render_template('checkout.html', cart=cart_data, user=user_info, form_data={})


@app.route('/order-confirmation/<order_number>')
def order_confirmation(order_number):
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE order_number = ?', (order_number,)).fetchone()
    if not order:
        conn.close()
        abort(404)

    # Allow viewing if owner, admin, or just placed in this session
    if order['user_id'] and session.get('user_id') != order['user_id'] and 'admin_id' not in session:
        if session.get('last_order_number') != order_number:
            conn.close()
            flash('Please log in to view this order.', 'warning')
            return redirect(url_for('login'))

    items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (order['id'],)).fetchall()
    conn.close()
    return render_template('checkout.html', confirmed_order=order, confirmed_items=items, cart=None)


# ==========================================
# USER AUTHENTICATION & ACCOUNT ROUTES
# ==========================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = []
        if len(full_name) < 2:
            errors.append('Full name must be at least 2 characters.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            errors.append('An account with this email already exists.')

        if errors:
            conn.close()
            for err in errors:
                flash(err, 'error')
            return render_template('register.html', form_data=request.form)

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (full_name, email, phone, password_hash)
            VALUES (?, ?, ?, ?)
        ''', (full_name, email, phone, generate_password_hash(password)))
        new_user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        session['user_id'] = new_user_id
        session['user_name'] = full_name
        session['user_email'] = email
        merge_guest_cart_into_user(new_user_id)

        flash(f'Welcome to ShopEase, {full_name}! Your account has been created.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html', form_data={})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    next_url = request.args.get('next') or request.form.get('next') or ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE lower(email) = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            merge_guest_cart_into_user(user['id'])
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('login.html', next_url=next_url, mode='customer')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db_connection()
    user_id = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action', 'update_profile')
        if action == 'update_profile':
            full_name = request.form.get('full_name', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            postal_code = request.form.get('postal_code', '').strip()

            if len(full_name) < 2:
                flash('Full name must be at least 2 characters.', 'error')
            else:
                conn.execute('''
                    UPDATE users
                    SET full_name = ?, phone = ?, address = ?, city = ?, postal_code = ?
                    WHERE id = ?
                ''', (full_name, phone, address, city, postal_code, user_id))
                conn.commit()
                session['user_name'] = full_name
                flash('Profile details updated successfully!', 'success')

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            user_row = conn.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,)).fetchone()
            if not check_password_hash(user_row['password_hash'], current_password):
                flash('Current password is incorrect.', 'error')
            elif len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'error')
            else:
                conn.execute(
                    'UPDATE users SET password_hash = ? WHERE id = ?',
                    (generate_password_hash(new_password), user_id)
                )
                conn.commit()
                flash('Password updated successfully!', 'success')

    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    stats = conn.execute('''
        SELECT COUNT(*) AS total_orders,
               COALESCE(SUM(total_amount), 0) AS total_spent
        FROM orders
        WHERE user_id = ?
    ''', (user_id,)).fetchone()
    recent_orders = conn.execute('''
        SELECT * FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 3
    ''', (user_id,)).fetchall()
    conn.close()
    return render_template('profile.html', user=user, stats=stats, recent_orders=recent_orders)


@app.route('/orders')
@login_required
def customer_orders():
    conn = get_db_connection()
    status_filter = request.args.get('status', '').strip()

    query = 'SELECT * FROM orders WHERE user_id = ?'
    params = [session['user_id']]
    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)
    query += ' ORDER BY id DESC'

    orders_rows = conn.execute(query, params).fetchall()
    orders_with_items = []
    for o in orders_rows:
        items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (o['id'],)).fetchall()
        orders_with_items.append({
            'order': o,
            'items': items
        })

    conn.close()
    return render_template('orders.html', orders_with_items=orders_with_items, status_filter=status_filter)


# ==========================================
# ADMIN AUTHENTICATION & DASHBOARD ROUTES
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        admin = conn.execute(
            'SELECT * FROM admins WHERE lower(username) = lower(?) OR lower(email) = lower(?)',
            (identifier, identifier)
        ).fetchone()
        conn.close()

        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['full_name']
            session['admin_username'] = admin['username']
            flash(f'Logged in to ShopEase Admin Portal as {admin["full_name"]}.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid administrator credentials.', 'error')

    return render_template('login.html', mode='admin')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_username', None)
    flash('Logged out from Admin Dashboard.', 'info')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()

    total_sales = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'Cancelled'"
    ).fetchone()[0]
    total_orders = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    total_products = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    total_customers = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_categories = conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0]

    status_counts = {}
    for s in ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']:
        status_counts[s] = conn.execute('SELECT COUNT(*) FROM orders WHERE status = ?', (s,)).fetchone()[0]

    recent_orders = conn.execute('''
        SELECT * FROM orders
        ORDER BY id DESC
        LIMIT 6
    ''').fetchall()

    low_stock_products = conn.execute('''
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.stock <= 20
        ORDER BY p.stock ASC
        LIMIT 5
    ''').fetchall()

    top_products = conn.execute('''
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY p.views DESC
        LIMIT 5
    ''').fetchall()

    conn.close()
    return render_template(
        'admin/dashboard.html',
        total_sales=round(float(total_sales), 2),
        total_orders=total_orders,
        total_products=total_products,
        total_customers=total_customers,
        total_categories=total_categories,
        status_counts=status_counts,
        recent_orders=recent_orders,
        low_stock_products=low_stock_products,
        top_products=top_products
    )


@app.route('/admin/products')
@admin_required
def admin_products():
    conn = get_db_connection()
    q = request.args.get('q', '').strip()
    cat_id = request.args.get('category', '').strip()
    stock_filter = request.args.get('stock', '').strip()

    query = '''
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    '''
    params = []

    if q:
        query += ' AND (p.name LIKE ? OR p.sku LIKE ? OR p.brand LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])

    if cat_id and cat_id.isdigit():
        query += ' AND p.category_id = ?'
        params.append(int(cat_id))

    if stock_filter == 'low':
        query += ' AND p.stock > 0 AND p.stock <= 15'
    elif stock_filter == 'out':
        query += ' AND p.stock <= 0'

    query += ' ORDER BY p.id DESC'
    products = conn.execute(query, params).fetchall()
    categories = conn.execute('SELECT * FROM categories ORDER BY name ASC').fetchall()
    conn.close()

    return render_template(
        'admin/products.html',
        products=products,
        categories=categories,
        q=q,
        selected_category=cat_id,
        stock_filter=stock_filter
    )


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories ORDER BY name ASC').fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', '').strip()
        brand = request.form.get('brand', 'ShopEase Originals').strip() or 'ShopEase Originals'
        sku = request.form.get('sku', '').strip() or f"SE-{uuid.uuid4().hex[:6].upper()}"
        price_raw = request.form.get('price', '0').strip()
        discount_raw = request.form.get('discount_price', '').strip()
        stock_raw = request.form.get('stock', '0').strip()
        description = request.form.get('description', '').strip()
        image_url_input = request.form.get('image_url', '').strip()
        is_featured = 1 if request.form.get('is_featured') == '1' else 0
        is_trending = 1 if request.form.get('is_trending') == '1' else 0

        errors = []
        if len(name) < 2:
            errors.append('Product name is required.')
        if not category_id.isdigit():
            errors.append('Please select a valid category.')
        try:
            price = round(float(price_raw), 2)
            if price <= 0:
                errors.append('Price must be greater than 0.')
        except ValueError:
            price = 0.0
            errors.append('Invalid price value.')

        discount_price = None
        if discount_raw:
            try:
                discount_price = round(float(discount_raw), 2)
                if discount_price <= 0 or discount_price >= price:
                    errors.append('Discount price must be greater than 0 and less than the regular price.')
            except ValueError:
                errors.append('Invalid discount price.')

        try:
            stock = max(0, int(stock_raw))
        except ValueError:
            stock = 0
            errors.append('Invalid stock quantity.')

        if len(description) < 10:
            errors.append('Please provide a product description (at least 10 characters).')

        # Handle image upload or fallback URL
        final_image_url = image_url_input or '/static/images/products/headphones.svg'
        file = request.files.get('image_file')
        if file and file.filename:
            if allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                safe_name = f"{slugify(name)[:30]}-{uuid.uuid4().hex[:6]}.{ext}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                file.save(save_path)
                final_image_url = f"/static/images/products/{safe_name}"
            else:
                errors.append('Unsupported image file format. Allowed: PNG, JPG, JPEG, WEBP, GIF, SVG.')

        if errors:
            conn.close()
            for err in errors:
                flash(err, 'error')
            return render_template('admin/add_product.html', categories=categories, product=request.form, is_edit=False)

        conn.execute('''
            INSERT INTO products (
                category_id, name, slug, description, price, discount_price,
                stock, image_url, sku, brand, is_featured, is_trending
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(category_id), name, slugify(name), description, price, discount_price,
            stock, final_image_url, sku, brand, is_featured, is_trending
        ))
        conn.commit()
        conn.close()
        flash(f'Product "{name}" added to catalog successfully!', 'success')
        return redirect(url_for('admin_products'))

    conn.close()
    return render_template('admin/add_product.html', categories=categories, product={}, is_edit=False)


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        abort(404)

    categories = conn.execute('SELECT * FROM categories ORDER BY name ASC').fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', '').strip()
        brand = request.form.get('brand', 'ShopEase Originals').strip() or 'ShopEase Originals'
        sku = request.form.get('sku', '').strip() or product['sku']
        price_raw = request.form.get('price', '0').strip()
        discount_raw = request.form.get('discount_price', '').strip()
        stock_raw = request.form.get('stock', '0').strip()
        description = request.form.get('description', '').strip()
        image_url_input = request.form.get('image_url', '').strip()
        is_featured = 1 if request.form.get('is_featured') == '1' else 0
        is_trending = 1 if request.form.get('is_trending') == '1' else 0

        errors = []
        if len(name) < 2:
            errors.append('Product name is required.')
        if not category_id.isdigit():
            errors.append('Please select a valid category.')
        try:
            price = round(float(price_raw), 2)
            if price <= 0:
                errors.append('Price must be greater than 0.')
        except ValueError:
            price = float(product['price'])
            errors.append('Invalid price value.')

        discount_price = None
        if discount_raw:
            try:
                discount_price = round(float(discount_raw), 2)
                if discount_price <= 0 or discount_price >= price:
                    errors.append('Discount price must be less than the regular price.')
            except ValueError:
                errors.append('Invalid discount price.')

        try:
            stock = max(0, int(stock_raw))
        except ValueError:
            stock = product['stock']
            errors.append('Invalid stock quantity.')

        final_image_url = image_url_input or product['image_url']
        file = request.files.get('image_file')
        if file and file.filename:
            if allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                safe_name = f"{slugify(name)[:30]}-{uuid.uuid4().hex[:6]}.{ext}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                file.save(save_path)
                final_image_url = f"/static/images/products/{safe_name}"
            else:
                errors.append('Unsupported image file format.')

        if errors:
            conn.close()
            for err in errors:
                flash(err, 'error')
            return render_template('admin/add_product.html', categories=categories, product=product, is_edit=True)

        conn.execute('''
            UPDATE products
            SET category_id = ?, name = ?, slug = ?, description = ?,
                price = ?, discount_price = ?, stock = ?, image_url = ?,
                sku = ?, brand = ?, is_featured = ?, is_trending = ?
            WHERE id = ?
        ''', (
            int(category_id), name, slugify(name), description,
            price, discount_price, stock, final_image_url,
            sku, brand, is_featured, is_trending, product_id
        ))
        conn.commit()
        conn.close()
        flash(f'Product "{name}" updated successfully!', 'success')
        return redirect(url_for('admin_products'))

    conn.close()
    return render_template('admin/add_product.html', categories=categories, product=product, is_edit=True)


@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    conn = get_db_connection()
    prod = conn.execute('SELECT name FROM products WHERE id = ?', (product_id,)).fetchone()
    if prod:
        conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        flash(f'Product "{prod["name"]}" deleted from catalog.', 'info')
    conn.close()
    return redirect(url_for('admin_products'))


@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_required
def admin_categories():
    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action', 'add')
        if action == 'add':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            icon = request.form.get('icon', 'fa-tag').strip() or 'fa-tag'
            image_url = request.form.get('image_url', '/static/images/products/headphones.svg').strip() or '/static/images/products/headphones.svg'

            if len(name) < 2:
                flash('Category name must be at least 2 characters.', 'error')
            else:
                slug = slugify(name)
                exists = conn.execute('SELECT id FROM categories WHERE lower(name) = lower(?) OR slug = ?', (name, slug)).fetchone()
                if exists:
                    flash('A category with that name already exists.', 'error')
                else:
                    conn.execute('''
                        INSERT INTO categories (name, slug, description, icon, image_url)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (name, slug, description, icon, image_url))
                    conn.commit()
                    flash(f'Category "{name}" created successfully!', 'success')

        elif action == 'edit':
            cat_id = request.form.get('category_id', '')
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            icon = request.form.get('icon', 'fa-tag').strip() or 'fa-tag'
            image_url = request.form.get('image_url', '').strip()

            if cat_id.isdigit() and len(name) >= 2:
                conn.execute('''
                    UPDATE categories
                    SET name = ?, slug = ?, description = ?, icon = ?,
                        image_url = COALESCE(NULLIF(?, ''), image_url)
                    WHERE id = ?
                ''', (name, slugify(name), description, icon, image_url, int(cat_id)))
                conn.commit()
                flash(f'Category "{name}" updated.', 'success')

        elif action == 'delete':
            cat_id = request.form.get('category_id', '')
            if cat_id.isdigit():
                count = conn.execute('SELECT COUNT(*) FROM products WHERE category_id = ?', (int(cat_id),)).fetchone()[0]
                if count > 0:
                    flash(f'Cannot delete category while it still contains {count} product(s). Reassign or delete those products first.', 'error')
                else:
                    conn.execute('DELETE FROM categories WHERE id = ?', (int(cat_id),))
                    conn.commit()
                    flash('Category deleted.', 'info')

    categories = conn.execute('''
        SELECT c.*, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        GROUP BY c.id
        ORDER BY c.id ASC
    ''').fetchall()
    conn.close()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/orders', methods=['GET', 'POST'])
@admin_required
def admin_orders():
    conn = get_db_connection()

    if request.method == 'POST':
        order_id = request.form.get('order_id', '')
        new_status = request.form.get('status', '')
        valid_statuses = ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
        if order_id.isdigit() and new_status in valid_statuses:
            conn.execute('UPDATE orders SET status = ? WHERE id = ?', (new_status, int(order_id)))
            conn.commit()
            flash(f'Order status updated to "{new_status}".', 'success')

    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = 'SELECT * FROM orders WHERE 1=1'
    params = []

    if q:
        query += ' AND (order_number LIKE ? OR customer_name LIKE ? OR customer_email LIKE ? OR phone LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%'])

    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)

    query += ' ORDER BY id DESC'
    orders_rows = conn.execute(query, params).fetchall()

    orders_list = []
    for o in orders_rows:
        items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (o['id'],)).fetchall()
        orders_list.append({
            'order': o,
            'items': items
        })

    conn.close()
    return render_template(
        'admin/orders.html',
        orders_list=orders_list,
        q=q,
        status_filter=status_filter
    )


@app.route('/admin/customers', methods=['GET', 'POST'])
@admin_required
def admin_customers():
    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action', '')
        user_id = request.form.get('user_id', '')
        if action == 'delete' and user_id.isdigit():
            conn.execute('DELETE FROM users WHERE id = ?', (int(user_id),))
            conn.commit()
            flash('Customer account removed.', 'info')

    q = request.args.get('q', '').strip()
    query = '''
        SELECT u.*,
               COUNT(o.id) AS orders_count,
               COALESCE(SUM(CASE WHEN o.status != 'Cancelled' THEN o.total_amount ELSE 0 END), 0) AS total_spent
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE 1=1
    '''
    params = []
    if q:
        query += ' AND (u.full_name LIKE ? OR u.email LIKE ? OR u.phone LIKE ? OR u.city LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%'])

    query += ' GROUP BY u.id ORDER BY u.id DESC'
    customers = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('admin/customers.html', customers=customers, q=q)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html', error_404=True), 404


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
