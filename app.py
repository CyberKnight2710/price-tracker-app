# app.py
import os
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from flask import Flask, render_template, request, jsonify, g 
import psycopg2

# Make sure you import the scraping and saving functions from core_logic
from core_logic import fetch_product_page, extract_price, save_price_data, add_new_product 
import atexit

app = Flask(__name__)

# --- Database Configuration (Load Environment Variable) ---
# NOTE: This variable is set by the Render service!
DB_URL = os.environ.get("DATABASE_URL")

if DB_URL is None:
    # Fallback to local configuration for development/local testing only
    print("WARNING: Using local database fallback configuration.")
    DB_URL = "postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost/price_tracker_db?sslmode=disable"

# --- Database Connection Management (Best Practice) ---
def get_db_connection():
    """Establishes a new database connection for the current request."""
    if 'db_conn' not in g:
        # Connect using the single DB_URL string
        g.db_conn = psycopg2.connect(DB_URL) 
    return g.db_conn

@app.teardown_appcontext
def close_db_connection(exception):
    """Closes the database connection at the end of the request."""
    conn = g.pop('db_conn', None)
    if conn is not None:
        conn.close()

# --- 1. Home Page Route (The Entry Point) ---
@app.route('/')
def index():
    # We will query and display all tracked products here
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all products from the database
    cursor.execute("SELECT id, name, url, target_price FROM products;")
    products = cursor.fetchall() # Get all rows as a list of tuples
    
    return render_template('index.html', products=products)

# --- 2. API Endpoint to Fetch Price History for Charts ---
@app.route('/api/history/<int:product_id>')
def get_price_history(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query price history for a specific product, ordered by time
    cursor.execute("""
        SELECT price, recorded_at 
        FROM price_history 
        WHERE product_id = %s 
        ORDER BY recorded_at;
    """, (product_id,))
    
    # Format the data for JSON response (required by frontend JavaScript)
    history_data = cursor.fetchall()
    
    # Convert list of tuples into a list of dictionaries/JSON-friendly format
    data = [{
        'price': float(row[0]), 
        'date': row[1].strftime('%Y-%m-%d %H:%M:%S') # Format datetime for JS
    } for row in history_data]
    
    return jsonify(data)


# --- 3. API Endpoint to Add a New Product ---
@app.route('/api/product/add', methods=['POST'])
def add_product():
    data = request.json # Get JSON data sent from the frontend
    
    # Basic data extraction and type conversion
    name = data.get('name')
    url = data.get('url')
    # Safely convert target_price to float, default to None if missing
    target_price = float(data.get('target_price')) if data.get('target_price') else None
    user_email = data.get('user_email')
    
    # Simple validation
    if not all([name, url, target_price is not None, user_email]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    # The add_new_product function was imported from core_logic.py
    result = add_new_product(name, url, target_price, user_email)
    
    if isinstance(result, int):
        # Successfully inserted, 'result' holds the new product ID
        return jsonify({"status": "success", "id": result, "message": "Product added successfully!"}), 201
    elif isinstance(result, str) and "Error: Product with URL" in result:
        # IntegrityError caught in core_logic
        return jsonify({"status": "error", "message": result}), 409 # Conflict status code
    else:
        # Generic database error
        return jsonify({"status": "error", "message": "Server error during insertion."}), 500    
    
# --- Email Configuration (REPLACE with your credentials) ---
# NOTE: If using Gmail, you MUST use an App Password, not your regular password.
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com", 
    "smtp_port": 587,
    "email_user": "allmight27102005@gmail.com", 
    "email_password": "mktp wonv dwdh kpqg" 
}

def send_alert_email(recipient, product_name, current_price, target_price):
    """Sends an email notification using SMTP."""
    msg = MIMEText(f"Price Drop Alert! The price for {product_name} is now ₹{current_price}, which is below your target of ₹{target_price}!")
    msg['Subject'] = f"PRICE DROP: {product_name}"
    msg['From'] = EMAIL_CONFIG['email_user']
    msg['To'] = recipient

    try:
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls() # Secure connection
            server.login(EMAIL_CONFIG['email_user'], EMAIL_CONFIG['email_password'])
            server.sendmail(EMAIL_CONFIG['email_user'], recipient, msg.as_string())
        print(f"Email alert sent to {recipient}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def price_check_job():
    """The recurring job: scrapes all products and checks for alerts."""
    print(f"\n--- Running Automated Price Check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    # NOTE: Using direct psycopg2 connect here as this job runs outside Flask's request context
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 1. Fetch ALL products to check
    # Ensure the column order matches the fetch order (id, name, url, target_price, user_email)
    cursor.execute("SELECT id, name, url, target_price, user_email FROM products;")
    products = cursor.fetchall()

    for product_id, name, url, target_price, user_email in products:
        html_content = fetch_product_page(url)
        current_price = extract_price(html_content)

        if current_price is None:
            print(f"Skipping Product {product_id} ({name}): Scraping failed.")
            continue

        # 2. Save the new price data (creates the historical record)
        save_price_data(product_id, current_price)

        # 3. Check for the price drop condition
        if current_price <= target_price:
            print(f"ALERT FOUND for {name}! Price: {current_price}. Target: {target_price}")
            send_alert_email(user_email, name, current_price, target_price)

    conn.close()

# --- Start the Background Scheduler ---
if __name__ == '__main__':
    # Initialize the scheduler
    scheduler = BackgroundScheduler()
    # Schedule the job to run every 1 minute (or hours=6 for production)
    scheduler.add_job(func=price_check_job, trigger="interval", minutes=1, id='price_check_job') 
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown()) 

    # Run the Flask application
    app.run(debug=True, use_reloader=False) # CRITICAL: Disable Flask's reloader for the scheduler