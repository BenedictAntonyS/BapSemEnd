from flask import Flask, render_template, redirect, url_for, request, session, flash
import sqlite3
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/images'
app.static_folder = 'static'

def secure_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks.
    """
    filename = re.sub(r'[^\w\s.-]', '', filename)
    return filename

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()# image TEXT
    conn.executescript('''
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS cart;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0, 1))
        );

         CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT NOT NULL,
            details TEXT 
        );

        CREATE TABLE cart (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );

        INSERT INTO users (username, password, is_admin) VALUES
            ('admin', 'admin', 1),
            ('user', 'user', 0);
    ''')
    conn.commit()
    conn.close()

if not os.path.exists('database.db'):
    init_db()

@app.before_request
def before_request():
    allowed_routes = ['login', 'logout']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            if user['is_admin']:
                return redirect(url_for('admin_home'))
            else:
                return redirect(url_for('user_home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

@app.route('/user_home')
def user_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_home.html')

@app.route('/admin_home')
def admin_home():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('admin_home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/products')
def products():
    
    conn = get_db_connection()
    user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if user and not user['is_admin']:
        conn = get_db_connection()
        products = conn.execute('SELECT * FROM products').fetchall()
        conn.close()
        return render_template('products.html', products=products)
    

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    categories = ['Skin Care', 'Body Care', 'Hair Care', 'Others']

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        quantity = request.form['quantity']
        category = request.form['category']
        details=request.form['details']
        new_category = request.form.get('new_category')
        image = request.files.get('image')

        if category == 'Others' and new_category:
            category = new_category
            if new_category not in categories:
                categories.append(new_category)

        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
        else:
            image_path = None

        if image_path:
            image_name = image_path.split('/')[-1]  # Get the last part of the path which is the filename
            image_name = os.path.basename(image_name)  # Get the filename part without the directory
        image_name = '/'+os.path.basename(image_path)
        print(image_name)
        conn = get_db_connection()
        conn.execute('INSERT INTO products (name, price, quantity, category, image,details) VALUES (?, ?, ?, ?, ?,?)',
                     (name, price, quantity, category, image_name,details))
        conn.commit()
        conn.close()

        return redirect(url_for('add_product'))

    return render_template('add_product.html', categories=categories)

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cart_items = conn.execute('''
        SELECT p.id, p.name, p.price, c.quantity,p.category,p.image
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    # Pass cart items and total to the template
    return render_template('cart.html', cart_items=cart_items, total=total)

# Route to display products and provide edit/delete functionality
@app.route('/manage_products')
def manage_products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    
    conn.close()
    return render_template('manage_products.html', products=products)

# Route to edit product
@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product(id):
    name = request.form['name']
    price = request.form['price']
    conn = get_db_connection()
    conn.execute('UPDATE products SET name = ?, price = ? WHERE id = ?', (name, price, id))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_products'))

# Route to delete product
@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_products'))
    
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()

    conn.execute('INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)', (session['user_id'], product_id, 1))
    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM cart WHERE user_id = ? AND product_id = ?', (session['user_id'], product_id))
    conn.commit()
    conn.close()
    return redirect(url_for('cart'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)
