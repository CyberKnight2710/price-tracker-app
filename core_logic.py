import requests
from bs4 import BeautifulSoup
import re  # For cleaning the price text
import psycopg2
from datetime import datetime

# ==========================================================
# 1. DATABASE CONFIGURATION (MUST BE UPDATED) ⚠️
# ==========================================================
# *** REPLACE THESE WITH YOUR ACTUAL POSTGRESQL CREDENTIALS ***
DB_CONFIG = {
    "host": "localhost",
    "database": "price_tracker_db",
    "user": "postgres",        # <-- REPLACE with your PostgreSQL username (e.g., 'postgres')
    "password": "post2705"  # <-- REPLACE with the password you set during installation
}

# Assuming your first test product will have an ID of 1 after inserting it in pgAdmin
TEST_PRODUCT_ID = 1

# ==========================================================
# 2. SCRAPING CONFIGURATION
# ==========================================================
# Using the guaranteed working URL for the price inspection steps
SAMPLE_URL = "http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"

# Define headers to pretend we are a real web browser (crucial for scraping)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ==========================================================
# 3. CORE FUNCTIONS
# ==========================================================

def fetch_product_page(url):
    """Fetches the raw HTML content of a given URL."""
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status() 
        return response.text
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page: {e}")
        return None

def extract_price(html_content):
    """Parses HTML and extracts a clean numeric price."""
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')

    # **CRITICAL LINE:** Uses the selector found on the training site (p tag with class price_color)
    price_tag = soup.find('p', {'class': 'price_color'}) 
    
    if price_tag:
        raw_price = price_tag.get_text(strip=True)

        # Cleaning the price: remove non-numeric characters (like '£' or '$') except for decimal points, and remove commas
        cleaned_price_text = re.sub(r'[^0-9\.]', '', raw_price.replace(',', ''))

        try:
            return float(cleaned_price_text)
        except ValueError:
            print(f"Error: Could not convert '{raw_price}' to a number.")
            return None
    else:
        print("Error: Price tag selector not found. Check your class name!")
        return None

def save_price_data(product_id, price):
    """Connects to the DB and saves the scraped price."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO price_history (product_id, price, recorded_at) 
        VALUES (%s, %s, %s);
        """
        # Execute the query, using parameters (%s) to prevent SQL Injection
        cursor.execute(insert_query, (product_id, price, datetime.now()))

        conn.commit() # Save changes permanently
        print(f"✅ Success: Recorded price {price} for product ID {product_id}.")

    except Exception as e:
        print(f"❌ Database error during insertion: {e}")

    finally:
        if conn:
            # Safely close cursor and connection
            if 'cursor' in locals() and cursor:
                 cursor.close()
            conn.close()

# core_logic.py (Add this new function)

def add_new_product(name, url, target_price, user_email):
    """Inserts a new product entry into the 'products' table."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO products (name, url, target_price, user_email) 
        VALUES (%s, %s, %s, %s) RETURNING id;
        """
        
        # Execute the query and retrieve the ID of the new product
        cursor.execute(insert_query, (name, url, target_price, user_email))
        new_id = cursor.fetchone()[0]
        
        conn.commit()
        return new_id

    except psycopg2.IntegrityError:
        # Handles errors where the URL already exists (UNIQUE constraint violation)
        return f"Error: Product with URL {url} already exists."
    except Exception as e:
        print(f"Database error during product addition: {e}")
        return None
    finally:
        if conn:
            conn.close()            

# ==========================================================
# 4. FINAL TEST RUN FOR PHASE 2 (Executed when running the file)
# ==========================================================
if __name__ == "__main__":
    print("--- Starting Price Scrape Test ---")
    
    html_content = fetch_product_page(SAMPLE_URL)
    
    if html_content:
        print("Fetch successful. First 500 characters:", html_content[:500])
        current_price = extract_price(html_content)

        if current_price is not None:
            print(f"Extracted Price: {current_price}")
            save_price_data(TEST_PRODUCT_ID, current_price)
        else:
            print("Test failed. Price not extracted.")
    else:
        print("Test failed. HTML content was not fetched.")