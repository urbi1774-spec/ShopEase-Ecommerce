# ShopEase — Full-Stack E-Commerce Platform

**ShopEase** is a complete, production-ready e-commerce web application built from scratch using **Python Flask**, **SQLite**, **HTML5**, **CSS3**, and **Vanilla JavaScript**.

---

## Technology Stack

- **Backend**: Python Flask (`app.py`, `database.py`)
- **Database**: SQLite (`ecommerce.db` with 7 relational tables and foreign keys)
- **Frontend**: Semantic HTML5 (Jinja2 Reusable Templates), Modern CSS3 (`style.css`, `admin.css`), Vanilla JavaScript (`main.js`, `cart.js`)
- **Payment Method**: Cash on Delivery (COD)

---

## Project Structure

```text
Ecommerce_Project/
├── app.py
├── database.py
├── requirements.txt
├── README.md
├── ecommerce.db
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── shop.html
│   ├── product_details.html
│   ├── cart.html
│   ├── checkout.html
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── orders.html
│   └── admin/
│       ├── dashboard.html
│       ├── products.html
│       ├── add_product.html
│       ├── orders.html
│       ├── customers.html
│       └── categories.html
└── static/
    ├── css/
    │   ├── style.css
    │   └── admin.css
    ├── js/
    │   ├── main.js
    │   └── cart.js
    └── images/
        └── products/
```

---

## Demo Credentials

### Customer Login (`/login`)
- **Email**: `customer@shopease.com`
- **Password**: `customer123`

### Administrator Portal (`/admin/login`)
- **Username**: `admin` (or `admin@shopease.com`)
- **Password**: `admin123`

---

## Installation & Running Instructions

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the application**:
   ```bash
   python app.py
   ```

3. **Open in your browser**:
   - Customer Storefront: [http://127.0.0.1:5000](http://127.0.0.1:5000)
   - Admin Dashboard: [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)
