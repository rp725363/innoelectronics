import csv
import io
import os
import requests
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_mail import Mail, Message
from collections import defaultdict

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key_here'  # Change this to a secure key

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sales.innoelectronics@gmail.com'  # Replace with your Gmail
app.config['MAIL_PASSWORD'] = 'oghn uehu vnpl grfe'  # Replace with your Gmail app password
app.config['MAIL_DEFAULT_SENDER'] = 'sales.innoelectronics@gmail.com'  # Replace with your Gmail

mail = Mail(app)

def get_products_from_sheet():
    sheet_id = '12CYpadbOJkj4HUCDTTHflMPHH2sWCqJ8-6x8X8pZbUs'
    sheet_name = 'Products'
    url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}'
    response = requests.get(url)
    response.raise_for_status()
    csv_data = response.content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(csv_data))
    products = defaultdict(list)
    for row in reader:
        category = row.get('catogary', '').strip()
        if category:
            products[category].append({
                'id': row.get('id', ''),
                'name': row.get('name', ''),
                'description': row.get('Description', ''),
                'image': row.get('imageUrl', '')
            })
    return dict(products)

@app.route('/')
def home():
    products = get_products_from_sheet()
    return render_template('index.html', products=products)

@app.route('/products/<category>')
def category_page(category):
    products = get_products_from_sheet()
    if category in products:
        return render_template('category.html', category=category, products=products[category], all_products=products)
    else:
        return "Category not found", 404

@app.route('/product/<category>/<int:index>')
def product_detail(category, index):
    products = get_products_from_sheet()
    if category in products and 0 <= index < len(products[category]):
        product = products[category][index]
        return render_template('product.html', product=product, category=category, index=index, all_products=products)
    else:
        return "Product not found", 404

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    category = request.form.get('category')
    index = int(request.form.get('index'))
    quantity = int(request.form.get('quantity', 1))
    products = get_products_from_sheet()
    if category in products and 0 <= index < len(products[category]) and quantity > 0:
        product = products[category][index]
        cart_item = {
            'name': product['name'],
            'description': product['description'],
            'image': product['image'],
            'category': category,
            'quantity': quantity
        }
        if 'cart' not in session:
            session['cart'] = []
        # Check if item already in cart, if so, update quantity
        found = False
        for item in session['cart']:
            if item['name'] == cart_item['name'] and item['category'] == cart_item['category']:
                item['quantity'] += quantity
                found = True
                break
        if not found:
            session['cart'].append(cart_item)
        session.modified = True
        flash(f'Added {quantity} item(s) to cart!')
    return redirect(url_for('product_detail', category=category, index=index))

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    return render_template('cart.html', cart_items=cart_items)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    action = request.form.get('action')
    item_index = int(request.form.get('item_index'))
    cart_items = session.get('cart', [])
    if 0 <= item_index < len(cart_items):
        # Ensure quantity key exists (for backward compatibility)
        if 'quantity' not in cart_items[item_index]:
            cart_items[item_index]['quantity'] = 1
        if action == 'increase':
            cart_items[item_index]['quantity'] += 1
        elif action == 'decrease':
            if cart_items[item_index]['quantity'] > 1:
                cart_items[item_index]['quantity'] -= 1
        elif action == 'remove':
            cart_items.pop(item_index)
        session['cart'] = cart_items
        session.modified = True
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        cart_items = session.get('cart', [])
        if not cart_items:
            flash('Your cart is empty!')
            return redirect(url_for('cart'))

        # Prepare email content
        order_details = f"Order from {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\n\nCart Items:\n"
        for item in cart_items:
            order_details += f"- {item['name']} ({item['category']}) - Quantity: {item['quantity']}\n"

        msg = Message('New Order', recipients=['sales.innoelectronics@gmail.com'])
        msg.body = order_details
        try:
            mail.send(msg)
            session.pop('cart', None)
            flash('Order submitted successfully! We will contact you soon.')
            return redirect(url_for('home'))
        except Exception as e:
            flash('Error sending email. Please try again.')
            return redirect(url_for('checkout'))
    return render_template('checkout.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    products = get_products_from_sheet()
    search_results = defaultdict(list)
    for category, prods in products.items():
        for prod in prods:
            if query in prod['name'].lower() or query in prod['description'].lower() or query in prod.get('id', '').lower() or query in str(prod).lower():
                search_results[category].append(prod)
    return render_template('index.html', products=dict(search_results), search_query=query)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message = request.form.get('message')

    # Prepare email content
    email_content = f"""
New Contact Form Message

From: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
This message was sent from the Innoelectronics contact form.
"""

    # Send email to business
    msg = Message(f'Contact Form: {subject}', recipients=['sales.innoelectronics@gmail.com'])
    msg.body = email_content

    # Send confirmation email to customer
    confirmation_msg = Message('Thank you for contacting Innoelectronics',
                              recipients=[email])
    confirmation_msg.body = f"""
Dear {name},

Thank you for contacting Innoelectronics. We have received your message and will get back to you within 24 hours.

Your message details:
Subject: {subject}
Message: {message}

Best regards,
Innoelectronics Team
sales.innoelectronics@gmail.com
+91 94284 47698
"""

    try:
        mail.send(msg)  # Send to business
        mail.send(confirmation_msg)  # Send confirmation to customer
        flash('Thank you for your message! We will get back to you soon. A confirmation email has been sent to your inbox.')
    except Exception as e:
        flash('Error sending email. Please try again.')

    return redirect(url_for('contact'))

@app.route('/google04f7938352655765.html')
def google_verification():
    return 'google-site-verification: google04f7938352655765.html'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)), debug=True)
