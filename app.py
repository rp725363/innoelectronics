import csv
import io
import os
import re
import time
import requests
import threading
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, session, redirect, url_for, flash, Response
from collections import defaultdict
from datetime import datetime

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.environ.get('SECRET_KEY') or 'dev-insecure-change-me'

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Email configuration
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'sales.innoelectronics@gmail.com')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'sales.innoelectronics@gmail.com')

_SHEET_CACHE = None
_SHEET_CACHE_TS = 0.0
SHEET_CACHE_TTL_SEC = 120

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email_async(subject, body, recipients):
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        logger.warning("Email skipped: set MAIL_USERNAME and MAIL_PASSWORD in the environment")
        return
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = MAIL_DEFAULT_SENDER
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject

        # Add body to email
        msg.attach(MIMEText(body, 'plain'))

        # Create SMTP session
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        if MAIL_USE_TLS:
            server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(MAIL_DEFAULT_SENDER, recipients, text)
        server.quit()

        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")

def get_products_from_sheet():
    global _SHEET_CACHE, _SHEET_CACHE_TS
    now = time.monotonic()
    if _SHEET_CACHE is not None and (now - _SHEET_CACHE_TS) < SHEET_CACHE_TTL_SEC:
        return _SHEET_CACHE
    sheet_id = '12CYpadbOJkj4HUCDTTHflMPHH2sWCqJ8-6x8X8pZbUs'
    sheet_name = 'Products'
    url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}'
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    csv_data = response.content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(csv_data))
    products = defaultdict(list)
    for row in reader:
        category = row.get('catogary', '').strip()
        if category:
            products[category].append({
                'sku': (row.get('SKU') or '').strip(),
                'name': (row.get('name') or '').strip(),
                'description': (row.get('Description') or '').strip(),
                'image': (row.get('imageUrl') or '').strip(),
                'price': (row.get('price') or '').strip(),
                'datasheet': (row.get('datasheetUrl') or '').strip(),
                'stock': (row.get('stock') or '').strip(),
                'partcode': (row.get('partcode') or '').strip()
            })
    _SHEET_CACHE = dict(products)
    _SHEET_CACHE_TS = now
    return _SHEET_CACHE


def _parse_price(price_str):
    if not price_str:
        return None
    s = re.sub(r'[^\d.]', '', str(price_str).replace(',', ''))
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _product_search_text(p):
    parts = [
        p.get('name', ''),
        p.get('description', ''),
        p.get('partcode', ''),
        p.get('sku', ''),
    ]
    return ' '.join(parts).lower()


def _pin_matches(text_lower, spec):
    if spec == '2':
        return bool(re.search(r'\b2[\s-]*pins?\b', text_lower)) or bool(re.search(r'\b2p\b', text_lower))
    if spec == '3':
        return bool(re.search(r'\b3[\s-]*pins?\b', text_lower)) or bool(re.search(r'\b3p\b', text_lower))
    if spec == '4+':
        for m in re.finditer(r'(\d+)[\s-]*pins?\b', text_lower):
            try:
                if int(m.group(1)) >= 4:
                    return True
            except ValueError:
                pass
        return bool(re.search(r'\b(4|5|6|7|8|9|1\d+)\s*[\s-]*pins?\b', text_lower))
    return False


def filter_and_sort_category_items(category_rows, brands, types, pins_filters, sort_opt):
    """category_rows: list of (sheet_index, product_dict). Returns filtered/sorted copies with sheet_index preserved."""
    items = []
    for sheet_index, p in category_rows:
        text = _product_search_text(p)
        if brands:
            if not any(b.lower() in text for b in brands):
                continue
        if types:
            if not any(t.lower() in text for t in types):
                continue
        if pins_filters:
            if not any(_pin_matches(text, pf) for pf in pins_filters):
                continue
        row = dict(p)
        row['sheet_index'] = sheet_index
        items.append(row)

    if sort_opt == 'price_low':
        items.sort(key=lambda r: (1, 0) if _parse_price(r.get('price')) is None else (0, _parse_price(r.get('price'))))
    elif sort_opt == 'price_high':
        items.sort(key=lambda r: (1, 0) if _parse_price(r.get('price')) is None else (0, -_parse_price(r.get('price'))))
    elif sort_opt == 'newest':
        items.reverse()

    return items


@app.context_processor
def inject_nav_catalog():
    try:
        return {'all_products': get_products_from_sheet()}
    except Exception as e:
        logger.warning("Nav catalog unavailable: %s", e)
        return {'all_products': {}}

@app.route('/')
def home():
    products = get_products_from_sheet()
    return render_template('index.html', products=products)


@app.route('/products')
def products_hub():
    return redirect(url_for('home'))


@app.route('/products/<category>')
def category_page(category):
    products = get_products_from_sheet()
    if category not in products:
        return "Category not found", 404
    pairs = list(enumerate(products[category]))
    brands = request.args.getlist('brand')
    types = request.args.getlist('type')
    pins_filters = request.args.getlist('pins')
    sort_opt = (request.args.get('sort') or '').strip()
    items = filter_and_sort_category_items(pairs, brands, types, pins_filters, sort_opt)
    return render_template('category.html', category=category, products=items, all_products=products)

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
            'quantity': quantity,
            'partcode': product['partcode']
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

        if not MAIL_USERNAME or not MAIL_PASSWORD:
            flash('Ordering by email is not configured. Please contact us by phone or WhatsApp.')
            return redirect(url_for('checkout'))

        # Prepare email content
        order_details = f"Order from {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\n\nCart Items:\n"
        for item in cart_items:
            order_details += f"- {item['name']} ({item['category']}) - Partcode: {item.get('partcode', 'N/A')} - Quantity: {item['quantity']}\n"

        logger.info("Starting checkout process for user: %s", email)
        try:
            # Send email asynchronously
            thread = threading.Thread(target=send_email_async, args=('New Order', order_details, ['sales.innoelectronics@gmail.com']))
            thread.start()
            session.pop('cart', None)
            flash('Order submitted successfully! We will contact you soon.')
            logger.info("Checkout completed successfully for user: %s", email)
            return redirect(url_for('home'))
        except Exception as e:
            logger.error("Error during checkout for user %s: %s", email, str(e))
            flash('Error sending email. Please try again.')
            return redirect(url_for('checkout'))
    return render_template('checkout.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    products = get_products_from_sheet()
    flat_search_results = []
    for category, prods in products.items():
        for index, prod in enumerate(prods):
            if query in prod['name'].lower() or query in prod['description'].lower() or query in prod.get('sku', '').lower() or query in str(prod).lower():
                result = prod.copy()
                result['category'] = category
                result['index'] = index
                flat_search_results.append(result)
    return render_template('index.html', flat_search_results=flat_search_results, products={}, search_query=query)

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

    if not MAIL_USERNAME or not MAIL_PASSWORD:
        flash('The contact form cannot send mail right now. Please email sales.innoelectronics@gmail.com directly.')
        return redirect(url_for('contact'))

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

    # Send confirmation email to customer
    confirmation_body = f"""
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
        # Send email to business
        threading.Thread(target=send_email_async, args=(f'Contact Form: {subject}', email_content, ['sales.innoelectronics@gmail.com'])).start()

        # Send confirmation email to customer
        threading.Thread(target=send_email_async, args=('Thank you for contacting Innoelectronics', confirmation_body, [email])).start()

        flash('Thank you for your message! We will get back to you soon. A confirmation email has been sent to your inbox.')
    except Exception as e:
        flash('Error sending email. Please try again.')

    return redirect(url_for('contact'))

@app.route('/google04f7938352655765.html')
def google_verification():
    return 'google-site-verification: google04f7938352655765.html'

@app.route('/robots.txt')
def robots():
    try:
        with open('robots.txt', 'r') as f:
            content = f.read()
        return Response(content, mimetype='text/plain')
    except FileNotFoundError:
        return "File not found", 404

@app.route('/sitemap.xml')
def sitemap():
    base_url = request.url_root.rstrip('/')
    products = get_products_from_sheet()
    lastmod = datetime.now().strftime('%Y-%m-%d')

    # Start XML sitemap
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Static pages
    static_pages = [
        {'loc': '/', 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': '/products', 'priority': '0.9', 'changefreq': 'daily'},
        {'loc': '/about', 'priority': '0.8', 'changefreq': 'monthly'},
        {'loc': '/contact', 'priority': '0.8', 'changefreq': 'monthly'},
        {'loc': '/cart', 'priority': '0.5', 'changefreq': 'weekly'},
    ]

    for page in static_pages:
        sitemap_xml += f'  <url>\n'
        sitemap_xml += f'    <loc>{base_url}{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{lastmod}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += f'  </url>\n'

    # Category pages
    for category in products.keys():
        sitemap_xml += f'  <url>\n'
        sitemap_xml += f'    <loc>{base_url}/products/{category}</loc>\n'
        sitemap_xml += f'    <lastmod>{lastmod}</lastmod>\n'
        sitemap_xml += f'    <changefreq>weekly</changefreq>\n'
        sitemap_xml += f'    <priority>0.7</priority>\n'
        sitemap_xml += f'  </url>\n'

        # Product pages
        for index in range(len(products[category])):
            sitemap_xml += f'  <url>\n'
            sitemap_xml += f'    <loc>{base_url}/product/{category}/{index}</loc>\n'
            sitemap_xml += f'    <lastmod>{lastmod}</lastmod>\n'
            sitemap_xml += f'    <changefreq>monthly</changefreq>\n'
            sitemap_xml += f'    <priority>0.6</priority>\n'
            sitemap_xml += f'  </url>\n'

    sitemap_xml += '</urlset>\n'

    return Response(sitemap_xml, mimetype='application/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)), debug=True)
