import psycopg2
import psycopg2.extras
import datetime
import os # Recommended for handling connection details securely
from dotenv import load_dotenv 
load_dotenv() 

# --- PostgreSQL Connection Details ---
# It is recommended to use environment variables for security.
DB_USER = os.environ.get('DB_USER', 'your_postgres_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'your_postgres_password')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'cdi_tracker')

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        sslmode='require'
    )
    return conn

def init_db():
    """Initializes the database schema for PostgreSQL."""
    print("Attempting to connect to database for init_db...")
    conn = get_db_connection()
    print("Connected to database. Getting cursor...")
    cursor = conn.cursor()
    print("Cursor obtained. Dropping sales table if exists (legacy)...")
    # For development, dropping the old sales table if schema changes.
    # In production, use migrations.
    cursor.execute("DROP TABLE IF EXISTS sales") # This line was in the original file
    
    print("Attempting to create cards table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            set_code TEXT NOT NULL,
            collector_number TEXT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            is_foil INTEGER NOT NULL DEFAULT 0,
            market_price_usd REAL,
            foil_market_price_usd REAL,
            image_uri TEXT,
            sell_price REAL,
            location TEXT,
            rarity TEXT,
            language TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scryfall_id TEXT,
            UNIQUE(set_code, collector_number, is_foil, location, rarity, language, buy_price)
        )
    ''')
    print("Cards table creation attempted.")

    print("Attempting to create sealed_products table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sealed_products (
            id SERIAL PRIMARY KEY,
            product_name TEXT NOT NULL,
            set_name TEXT,
            product_type TEXT,
            language TEXT DEFAULT 'English',
            is_collectors_item INTEGER DEFAULT 0,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            manual_market_price REAL,
            sell_price REAL,
            image_uri TEXT,
            location TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_name, set_name, product_type, language, location, is_collectors_item, buy_price)
        )
    ''')
    print("Sealed_products table creation attempted.")

    print("Attempting to create sale_events table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sale_events (
        id SERIAL PRIMARY KEY,
        sale_date DATE NOT NULL,
        total_shipping_cost REAL DEFAULT 0.0, -- Your cost to ship
        notes TEXT,
        total_profit_loss REAL,
        date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        customer_shipping_charge REAL DEFAULT 0.0, -- What customer paid for shipping
        platform_fee REAL DEFAULT 0.0            -- Platform fees for the sale
    )
    ''')
    print("Sale_events table creation attempted.")


    print("Attempting to create sale_items table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id SERIAL PRIMARY KEY,
            sale_event_id INTEGER NOT NULL,
            inventory_item_id INTEGER,
            item_type TEXT NOT NULL,
            original_item_name TEXT,
            original_item_details TEXT,
            quantity_sold INTEGER NOT NULL,
            sell_price_per_item REAL NOT NULL,
            buy_price_per_item REAL NOT NULL,
            item_profit_loss REAL NOT NULL,
            FOREIGN KEY (sale_event_id) REFERENCES sale_events (id)
        )
    ''')
    print("Sale_items table creation attempted.")

    print("Attempting to create financial_entries table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS financial_entries (
        id SERIAL PRIMARY KEY,
        entry_date DATE NOT NULL,
        description TEXT NOT NULL,
        category TEXT,
        entry_type TEXT NOT NULL CHECK (entry_type IN ('expense', 'income')),
        amount REAL NOT NULL,
        notes TEXT,
        date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    print("Financial_entries table creation attempted.")


    _check_and_add_column(cursor, 'cards', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'cards', 'scryfall_id', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'rarity', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'language', 'TEXT')
    _check_and_add_column(cursor, 'sealed_products', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'sale_events', 'customer_shipping_charge', 'REAL DEFAULT 0.0')
    _check_and_add_column(cursor, 'sale_events', 'platform_fee', 'REAL DEFAULT 0.0')
    print("All _check_and_add_column calls attempted.")
        
    print("Attempting to commit changes...")
    conn.commit()
    print("Changes committed.")
    cursor.close()
    conn.close()
    print("Database initialization script finished.")

def _check_and_add_column(cursor, table_name, column_name, column_type):
    """Checks if a column exists and adds it if not (PostgreSQL version)."""
    try:
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """, (table_name, column_name))
        if cursor.fetchone() is None:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            print(f"Added column '{column_name}' to table '{table_name}'.")
    except psycopg2.Error as e:
        print(f"Error checking/adding column '{column_name}' to '{table_name}': {e}")
        if cursor.connection: 
            cursor.connection.rollback()


def get_item_by_id(item_type, item_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    item = None
    table_name = None
    if item_type == 'single_card':
        table_name = 'cards'
    elif item_type == 'sealed_product':
        table_name = 'sealed_products'
    else:
        conn.close()
        return None 

    try:
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (item_id,))
        item = cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB error in get_item_by_id for {item_type} ID {item_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return item

# In database.py, find and replace your add_card function with this one

def add_card(set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, scryfall_id, rarity, language):
    """Adds a new card to the inventory or updates the quantity if an identical card exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch current market price from Scryfall
    from scryfall import get_card_details
    scryfall_data = get_card_details(set_code=set_code, collector_number=collector_number)
    
    current_market_price_usd = None
    image_uri = None
    if scryfall_data and not scryfall_data.get('error'):
        prices = scryfall_data.get('prices', {})
        price_key = 'usd_foil' if is_foil else 'usd'
        current_market_price_usd = prices.get(price_key)
        
        # Get image URI from image_uris or card_faces
        if 'image_uris' in scryfall_data and 'normal' in scryfall_data['image_uris']:
            image_uri = scryfall_data['image_uris']['normal']
        elif 'card_faces' in scryfall_data and 'image_uris' in scryfall_data['card_faces'][0]:
            image_uri = scryfall_data['card_faces'][0]['image_uris']['normal']

    try:
        # Attempt to insert a new card record
        sql = """
            INSERT INTO cards (name, set_code, collector_number, is_foil, quantity, buy_price, current_market_price_usd, rarity, language, location, image_uri, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
        """
        cursor.execute(sql, (name, set_code, collector_number, is_foil, quantity, buy_price, current_market_price_usd, rarity, language, location, image_uri))
        conn.commit()
        print(f"SUCCESS (Inserted): Added {quantity} x {name} ({set_code.upper()}) to inventory.")

    except psycopg2.errors.UniqueViolation as e:
        # If the card already exists (violates unique constraint), update the quantity instead
        conn.rollback() # Rollback the failed INSERT transaction
        try:
            update_sql = """
                UPDATE cards
                SET quantity = quantity + %s,
                    last_updated = NOW()
                WHERE set_code = %s AND collector_number = %s AND is_foil = %s AND location = %s AND rarity = %s AND language = %s AND buy_price = %s;
            """
            cursor.execute(update_sql, (quantity, set_code, collector_number, is_foil, location, rarity, language, buy_price))
            conn.commit()
            print(f"SUCCESS (Updated): Added {quantity} x {name} ({set_code.upper()}) to existing stack.")
        except psycopg2.Error as update_e:
            print(f"DB Update Error after IntegrityError for {name}: {update_e}")
            conn.rollback()

    except psycopg2.Error as e:
        # Handle other potential database errors
        print(f"DB IntegrityError in add_card for {name}: {e}")
        conn.rollback()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def delete_sale_event(sale_event_id):
    """
    Deletes a sale event and its associated items.
    Attempts to add the sold quantities back to the inventory.
    All operations are performed in a single transaction.
    Returns a tuple: (success_boolean, message_string)
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # Use DictCursor for easier item access

    try:
        # Start a transaction
        # In PostgreSQL, a transaction is implicitly started with the first command.
        # We will explicitly commit or rollback.

        # 1. Get all items from the sale event
        cursor.execute("""
            SELECT inventory_item_id, item_type, quantity_sold, original_item_name
            FROM sale_items 
            WHERE sale_event_id = %s
        """, (sale_event_id,))
        items_sold = cursor.fetchall()

        if not items_sold:
            # If there are no items (e.g., an empty sale was somehow recorded),
            # we can just delete the event.
            cursor.execute("DELETE FROM sale_events WHERE id = %s", (sale_event_id,))
            if cursor.rowcount == 0:
                conn.rollback() # Should not happen if items_sold was truly empty for a valid event_id
                return False, f"Sale event ID {sale_event_id} not found."
            conn.commit()
            return True, f"Sale event ID {sale_event_id} (which had no items) deleted."

        # 2. Attempt to restock inventory for each item
        restocking_messages = []
        for item in items_sold:
            inventory_id = item['inventory_item_id']
            item_type = item['item_type']
            quantity_to_restock = item['quantity_sold']
            item_name_for_msg = item['original_item_name']

            if inventory_id is None: # Should not happen if data is clean
                restocking_messages.append(f"Warning: Sold item '{item_name_for_msg}' had no inventory ID linked; cannot restock.")
                continue

            # Use the existing helper, ensuring it's suitable for positive quantity_change
            # _update_inventory_item_quantity_with_cursor adds quantity_change
            success_restock, msg_restock = _update_inventory_item_quantity_with_cursor(
                cursor, item_type, inventory_id, quantity_to_restock 
            )
            if not success_restock:
                # If restocking a specific item fails, we'll roll back the whole transaction.
                # This is a strict approach. Alternatively, you could log failures and continue.
                conn.rollback()
                return False, f"Failed to restock '{item_name_for_msg}' (Inv ID: {inventory_id}): {msg_restock}. Sale event not deleted."
            restocking_messages.append(f"Restocked {quantity_to_restock} of '{item_name_for_msg}'.")

        # 3. Delete the sale items records for this event
        cursor.execute("DELETE FROM sale_items WHERE sale_event_id = %s", (sale_event_id,))

        # 4. Delete the sale event record
        cursor.execute("DELETE FROM sale_events WHERE id = %s", (sale_event_id,))
        if cursor.rowcount == 0: # Should have been caught earlier if items_sold was empty due to invalid event_id
            conn.rollback()
            return False, f"Sale event ID {sale_event_id} could not be deleted (was it already deleted?)"

        conn.commit()
        final_message = f"Sale event ID {sale_event_id} deleted. " + " ".join(restocking_messages)
        return True, final_message

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"DB error in delete_sale_event for event ID {sale_event_id}: {e}")
        return False, f"Database error during sale event deletion: {e}"
    except Exception as e: # Catch any other unexpected errors
        if conn:
            conn.rollback()
        print(f"Unexpected error in delete_sale_event for event ID {sale_event_id}: {e}")
        return False, f"An unexpected error occurred: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_all_cards():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cards = []
    try:
        cursor.execute("SELECT * FROM cards WHERE quantity > 0 ORDER BY name, set_code, collector_number, location, buy_price, rarity, language")
        cards = cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB error in get_all_cards: {e}")
    finally:
        cursor.close()
        conn.close()
    return cards

def get_card_by_id(card_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    card = None
    try:
        cursor.execute("SELECT * FROM cards WHERE id = %s", (card_id,))
        card = cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB error in get_card_by_id for ID {card_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return card

def update_card_quantity(card_id, quantity_change):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 
    try:
        cursor.execute("SELECT quantity FROM cards WHERE id = %s", (card_id,))
        result = cursor.fetchone()
        if not result:
            return False, "Card not found."

        current_quantity = result['quantity']
        new_quantity = current_quantity + quantity_change
        if new_quantity < 0:
            return False, "Not enough quantity in stock to remove."

        cursor.execute("UPDATE cards SET quantity = %s, last_updated = %s WHERE id = %s",
                       (new_quantity, datetime.datetime.now(), card_id))
        conn.commit()
        return True, f"Card quantity updated to {new_quantity}."
    except psycopg2.Error as e:
        print(f"DB error in update_card_quantity for ID {card_id}: {e}")
        if conn: conn.rollback()
        return False, f"Database error during quantity update: {e}"
    finally:
        if conn:
            cursor.close()
            conn.close()

def delete_card(card_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    deleted = False
    try:
        cursor.execute("DELETE FROM cards WHERE id = %s", (card_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
    except psycopg2.Error as e:
        print(f"DB error in delete_card for ID {card_id}: {e}")
        if conn: conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return deleted

def update_card_prices_and_image(card_id, market_price_usd, foil_market_price_usd, image_uri):
    conn = get_db_connection()
    cursor = conn.cursor()
    updated = False
    try:
        cursor.execute(''' UPDATE cards SET market_price_usd = %s, foil_market_price_usd = %s, image_uri = %s, last_updated = %s WHERE id = %s ''',
                       (market_price_usd, foil_market_price_usd, image_uri, datetime.datetime.now(), card_id))
        conn.commit()
        updated = cursor.rowcount > 0
    except psycopg2.Error as e:
        print(f"DB error in update_card_prices_and_image for ID {card_id}: {e}")
        if conn: conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return updated

def update_card_fields(card_id, data_to_update):
    conn = get_db_connection()
    cursor = conn.cursor()
    allowed_fields = {'quantity', 'buy_price', 'sell_price', 'location'}
    fields_to_update_sql = []
    values_for_sql = []

    if not data_to_update:
        conn.close()
        return False, "No changes were submitted."

    for key, value_from_app in data_to_update.items():
        if key not in allowed_fields:
            print(f"DB Warning: Field '{key}' not allowed in update_card_fields.")
            continue
        fields_to_update_sql.append(f"{key} = %s")
        values_for_sql.append(value_from_app)

    if not fields_to_update_sql:
        conn.close()
        return False, "No valid data fields for card update."

    fields_to_update_sql.append("last_updated = %s")
    values_for_sql.append(datetime.datetime.now())
    sql_set_clause = ", ".join(fields_to_update_sql)
    final_sql_values = tuple(values_for_sql + [card_id])
    sql = f"UPDATE cards SET {sql_set_clause} WHERE id = %s"

    try:
        cursor.execute(sql, final_sql_values)
        conn.commit()
        updated_rows = cursor.rowcount
        return (True, "Card updated successfully.") if updated_rows > 0 else (False, "Card not found or no data changed.")
    except psycopg2.IntegrityError as e:
        print(f"Integrity error update card {card_id}: {e}")
        if conn: conn.rollback()
        return False, f"Update failed (integrity): {e}"
    except psycopg2.Error as e:
        print(f"DB error update card {card_id}: {e}")
        if conn: conn.rollback()
        return False, f"DB error: {e}"
    finally:
        cursor.close()
        conn.close()

def add_sealed_product(product_name, set_name, product_type, language, is_collectors_item, quantity, buy_price, manual_market_price, sell_price, image_uri, location):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    is_collectors_int = 1 if is_collectors_item else 0
    prod_id = None 
    try:
        current_buy_price = float(buy_price)
    except (ValueError, TypeError):
        print(f"DB Error: Invalid buy_price format '{buy_price}' for sealed product '{product_name}'.")
        if conn: conn.close()
        return None

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as check_cursor:
            check_cursor.execute('''SELECT id, quantity FROM sealed_products WHERE product_name = %s AND set_name = %s AND product_type = %s AND language = %s AND location = %s AND is_collectors_item = %s AND buy_price = %s''',
                                (product_name, set_name, product_type, language, location, is_collectors_int, current_buy_price))
            existing = check_cursor.fetchone()

        if existing:
            prod_id, new_qty = existing['id'], existing['quantity'] + quantity
            cursor.execute('''UPDATE sealed_products SET quantity = %s, manual_market_price = %s, sell_price = %s, image_uri = %s, last_updated = %s WHERE id = %s''',
                           (new_qty, manual_market_price, sell_price, image_uri, timestamp, prod_id))
        else:
            cursor.execute('''INSERT INTO sealed_products (product_name, set_name, product_type, language, is_collectors_item, quantity, buy_price, manual_market_price, sell_price, image_uri, location, date_added, last_updated)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                           (product_name, set_name, product_type, language, is_collectors_int, quantity, current_buy_price, manual_market_price, sell_price, image_uri, location, timestamp, timestamp))
            result = cursor.fetchone()
            if result: prod_id = result[0]
        conn.commit()
    except psycopg2.IntegrityError as ie:
        print(f"DB IntegrityError add_sealed for {product_name}: {ie}")
        if conn: conn.rollback()
        prod_id = None
    except psycopg2.Error as e:
        print(f"DB error add_sealed for {product_name}: {e}")
        if conn: conn.rollback()
        prod_id = None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    return prod_id

def get_all_sealed_products():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    prods = []
    try:
        cursor.execute("SELECT * FROM sealed_products WHERE quantity > 0 ORDER BY product_name, set_name, location, buy_price")
        prods = cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB error in get_all_sealed_products: {e}")
    finally:
        cursor.close()
        conn.close()
    return prods

def get_sealed_product_by_id(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    prod = None
    try:
        cursor.execute("SELECT * FROM sealed_products WHERE id = %s", (product_id,))
        prod = cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB error in get_sealed_product_by_id for ID {product_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return prod

def update_sealed_product_quantity(product_id, quantity_change):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 
    try:
        cursor.execute("SELECT quantity FROM sealed_products WHERE id = %s", (product_id,))
        result = cursor.fetchone()
        if not result:
            return False, "Sealed product not found."

        current_quantity = result['quantity']
        new_quantity = current_quantity + quantity_change
        if new_quantity < 0:
            return False, "Not enough quantity in stock to remove."

        cursor.execute("UPDATE sealed_products SET quantity = %s, last_updated = %s WHERE id = %s",
                       (new_quantity, datetime.datetime.now(), product_id))
        conn.commit()
        return True, f"Sealed product quantity updated to {new_quantity}."
    except psycopg2.Error as e:
        print(f"DB error in update_sealed_product_quantity for ID {product_id}: {e}")
        if conn: conn.rollback()
        return False, f"Database error during quantity update: {e}"
    finally:
        if conn:
            cursor.close()
            conn.close()

def delete_sealed_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    deleted = False
    try:
        cursor.execute("DELETE FROM sealed_products WHERE id = %s", (product_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
    except psycopg2.Error as e:
        print(f"DB error in delete_sealed_product for ID {product_id}: {e}")
        if conn: conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return deleted

def update_sealed_product_fields(product_id, data_to_update_from_app):
    conn = get_db_connection()
    cursor = conn.cursor()
    allowed_fields_for_update = {'quantity', 'buy_price', 'manual_market_price', 'sell_price', 'location', 'image_uri', 'language', 'is_collectors_item'}
    fields_to_set_in_sql = []
    values_for_sql_query = []

    if not data_to_update_from_app:
        conn.close()
        return False, "No changes were submitted."

    for field_key, new_value in data_to_update_from_app.items():
        if field_key not in allowed_fields_for_update:
            print(f"DB Warning: Field '{field_key}' not allowed for update.")
            continue
        current_sql_value = new_value
        if field_key == 'is_collectors_item':
             current_sql_value = 1 if new_value else 0

        fields_to_set_in_sql.append(f"{field_key} = %s")
        values_for_sql_query.append(current_sql_value)

    if not fields_to_set_in_sql:
        conn.close()
        return False, "No valid data fields for update."

    fields_to_set_in_sql.append("last_updated = %s")
    values_for_sql_query.append(datetime.datetime.now())
    sql_set_clause = ", ".join(fields_to_set_in_sql)
    final_sql_values_tuple = tuple(values_for_sql_query + [product_id])
    sql_query_string = f"UPDATE sealed_products SET {sql_set_clause} WHERE id = %s"

    try:
        cursor.execute(sql_query_string, final_sql_values_tuple)
        conn.commit()
        updated_rows = cursor.rowcount
        return (True, "Sealed product updated successfully.") if updated_rows > 0 else (False, "Sealed product not found or data identical.")
    except psycopg2.IntegrityError as e:
        print(f"DB IntegrityError update sealed_product {product_id}: {e}")
        if conn: conn.rollback()
        return False, f"Update failed (integrity): {e}"
    except psycopg2.Error as e:
        print(f"DB error update sealed_product {product_id}: {e}")
        if conn: conn.rollback()
        return False, f"DB error: {e}"
    finally:
        cursor.close()
        conn.close()

def _update_inventory_item_quantity_with_cursor(cursor, item_type, item_id, quantity_change):
    table_name = 'cards' if item_type == 'single_card' else 'sealed_products'
    try:
        cursor.execute(f"SELECT quantity FROM {table_name} WHERE id = %s", (item_id,))
        result = cursor.fetchone() # This cursor might be a plain cursor or DictCursor based on context
        if not result:
            return False, f"{item_type.replace('_', ' ').capitalize()} not found."

        # Handle result as tuple or dict. If it's from a plain cursor, it's a tuple.
        current_quantity = result[0] if isinstance(result, tuple) else result['quantity']
        new_quantity = current_quantity + quantity_change

        if new_quantity < 0:
            return False, "Not enough stock to sell/remove."

        cursor.execute(f"UPDATE {table_name} SET quantity = %s, last_updated = %s WHERE id = %s",
                       (new_quantity, datetime.datetime.now(), item_id))
        print(f"DB (cursor op): Updated {table_name} ID {item_id} quantity to {new_quantity}")
        return True, f"{item_type.replace('_', ' ').capitalize()} quantity updated."
    except psycopg2.Error as e:
        print(f"DB error in _update_inventory_item_quantity_with_cursor for {table_name} ID {item_id}: {e}")
        return False, f"DB error during quantity update: {e}"

def record_multi_item_sale(sale_date_str, total_shipping_cost_str, overall_notes, items_data_from_app, 
                           customer_shipping_charge_str, platform_fee_str): # Added new params
    conn = get_db_connection()
    cursor = conn.cursor() 
    sale_event_id = None
    total_items_profit_loss = 0.0 # Renamed for clarity

    try:
        sale_date_obj = datetime.datetime.strptime(sale_date_str, '%Y-%m-%d').date()
        # Your cost for shipping
        our_total_shipping_cost = float(total_shipping_cost_str if total_shipping_cost_str and total_shipping_cost_str.strip() != '' else 0.0)
        # New fields
        customer_shipping_charge = float(customer_shipping_charge_str if customer_shipping_charge_str and customer_shipping_charge_str.strip() != '' else 0.0)
        platform_fee = float(platform_fee_str if platform_fee_str and platform_fee_str.strip() != '' else 0.0)

    except ValueError as e:
        print(f"DB Error: Invalid date/shipping/fee format: {e}")
        if conn: conn.close()
        return None, f"Invalid date/shipping/fee: {e}"

    try:
        # Insert new fields into sale_events
        cursor.execute('''INSERT INTO sale_events (sale_date, total_shipping_cost, notes, customer_shipping_charge, platform_fee) 
                          VALUES (%s, %s, %s, %s, %s) RETURNING id''',
                       (sale_date_obj, our_total_shipping_cost, overall_notes, customer_shipping_charge, platform_fee))
        result = cursor.fetchone()
        if result: sale_event_id = result[0]
        print(f"DB: Created sale_event ID {sale_event_id}")

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as item_read_cursor:
            for item_data in items_data_from_app:
                # ... (existing logic to get item_type, inventory_item_id_int, quantity_sold, sell_price_per_item) ...
                # Minor change: ensure you're using the correct sell_price_per_item for the calculation
                # The item_profit_loss stored in sale_items is (sell_price_per_item - buy_price_per_item) * quantity_sold

                inventory_id_with_prefix = item_data.get('inventory_item_id_with_prefix')
                quantity_sold_str = item_data.get('quantity_sold')
                sell_price_per_item_str = item_data.get('sell_price_per_item')
                item_type = None
                inventory_item_id_int = None

                if inventory_id_with_prefix and '-' in inventory_id_with_prefix:
                    parts = inventory_id_with_prefix.split('-', 1)
                    item_type_prefix = parts[0]
                    try:
                        inventory_item_id_int = int(parts[1])
                        if item_type_prefix == 'single_card': item_type = 'single_card'
                        elif item_type_prefix == 'sealed_product': item_type = 'sealed_product'
                    except ValueError:
                        raise ValueError(f"Invalid inv item ID format: {inventory_id_with_prefix}")

                if not all([item_type, inventory_item_id_int is not None]):
                    raise ValueError(f"Missing/invalid item identifier: {inventory_id_with_prefix}")

                quantity_sold = int(quantity_sold_str)
                sell_price_per_item = float(sell_price_per_item_str)
                if quantity_sold <= 0 or sell_price_per_item < 0:
                    raise ValueError("Qty/Sell Price invalid.")

                table_name_for_read = 'cards' if item_type == 'single_card' else 'sealed_products'
                item_read_cursor.execute(f"SELECT * FROM {table_name_for_read} WHERE id = %s", (inventory_item_id_int,))
                original_item_db_row = item_read_cursor.fetchone()

                if not original_item_db_row:
                    raise ValueError(f"Inv item not found: {item_type} id {inventory_item_id_int}")
                if quantity_sold > original_item_db_row['quantity']:
                    name_key = 'name' if item_type == 'single_card' else 'product_name'
                    raise ValueError(f"Not enough stock for {original_item_db_row[name_key]}. Have: {original_item_db_row['quantity']}")

                buy_price_per_item = float(original_item_db_row['buy_price'])
                item_profit_loss = (sell_price_per_item - buy_price_per_item) * quantity_sold
                total_items_profit_loss += item_profit_loss # Accumulate item-specific P/L

                # ... (existing logic to get original_item_name_snapshot, original_item_details_snapshot) ...
                original_item_name_snapshot = ""
                original_item_details_snapshot = ""
                if item_type == 'single_card':
                    original_item_name_snapshot = original_item_db_row['name']
                    rarity_str = (original_item_db_row.get('rarity') if original_item_db_row.get('rarity') is not None else 'N/A')
                    lang_str = (original_item_db_row.get('language') if original_item_db_row.get('language') is not None else 'N/A')
                    original_item_details_snapshot = f"{original_item_db_row['set_code']}-{original_item_db_row['collector_number']} {'(Foil)' if original_item_db_row['is_foil'] else ''} (R: {rarity_str.capitalize()}, L: {lang_str.upper()})"
                elif item_type == 'sealed_product':
                    original_item_name_snapshot = original_item_db_row['product_name']
                    lang_str_sealed = (original_item_db_row.get('language') if original_item_db_row.get('language') is not None else 'N/A')
                    original_item_details_snapshot = f"{original_item_db_row['set_name']} - {original_item_db_row['product_type']} {'(Collector)' if original_item_db_row['is_collectors_item'] else ''} (L: {lang_str_sealed.upper()})"

                cursor.execute('''INSERT INTO sale_items (sale_event_id, inventory_item_id, item_type, original_item_name, original_item_details, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                               (sale_event_id, inventory_item_id_int, item_type, original_item_name_snapshot, original_item_details_snapshot, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss))

                success_inv_update, msg_inv_update = _update_inventory_item_quantity_with_cursor(cursor, item_type, inventory_item_id_int, -quantity_sold)
                if not success_inv_update:
                    raise Exception(f"Inv update failed: {msg_inv_update}")

        # Calculate the final P/L for the event including new fields
        # total_items_profit_loss = Sum of (item_sell_price - item_buy_price) * quantity_sold
        # Net Event P/L = total_items_profit_loss + customer_shipping_charge - our_total_shipping_cost - platform_fee
        final_event_profit_loss = total_items_profit_loss + customer_shipping_charge - our_total_shipping_cost - platform_fee

        cursor.execute('''UPDATE sale_events SET total_profit_loss = %s WHERE id = %s''', (final_event_profit_loss, sale_event_id))
        conn.commit()
        print(f"DB: Committed sale_event ID {sale_event_id} with total P/L: {final_event_profit_loss}")
        return sale_event_id, "Sale event recorded successfully."
    except Exception as e:
        print(f"DB Error in record_multi_item_sale: {e}")
        if conn: conn.rollback()
        return None, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_all_sale_events_with_items():
    conn = get_db_connection()
    # Use DictCursor to access columns by name
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 
    sale_events_processed = []
    try:
        # Select all necessary fields from sale_events, including the new ones
        cursor.execute('''SELECT id, sale_date, total_shipping_cost, notes, total_profit_loss, date_recorded,
                                 customer_shipping_charge, platform_fee 
                          FROM sale_events ORDER BY sale_date DESC, id DESC''')
        events = cursor.fetchall()
        for event_row in events:
            # event_row is already a DictRow, so direct dictionary conversion is fine
            event_dict = dict(event_row) 
            
            # Ensure dates are Python date/datetime objects
            # (PostgreSQL driver usually handles this, but good to be robust)
            if event_dict.get('sale_date') and isinstance(event_dict.get('sale_date'), str):
                try:
                    event_dict['sale_date'] = datetime.datetime.strptime(event_dict['sale_date'], '%Y-%m-%d').date()
                except ValueError:
                    # Handle or log cases where date might not be in expected string format
                    print(f"Warning: Could not parse sale_date string: {event_dict.get('sale_date')}")
                    pass 
            
            if event_dict.get('date_recorded') and isinstance(event_dict.get('date_recorded'), str):
                try:
                    event_dict['date_recorded'] = datetime.datetime.fromisoformat(event_dict['date_recorded'])
                except ValueError:
                    print(f"Warning: Could not parse date_recorded string: {event_dict.get('date_recorded')}")
                    pass

            # Fetch associated items for this event
            cursor.execute('''SELECT id, sale_event_id, inventory_item_id, item_type, original_item_name,
                                     original_item_details, quantity_sold, sell_price_per_item,
                                     buy_price_per_item, item_profit_loss
                              FROM sale_items WHERE sale_event_id = %s ORDER BY id ASC''', (event_dict['id'],))
            items_raw = cursor.fetchall()
            # Convert item rows to dictionaries
            event_dict['items'] = [dict(item_row) for item_row in items_raw] 
            sale_events_processed.append(event_dict)
            
    except psycopg2.Error as e:
        print(f"DB Error in get_all_sale_events_with_items: {e}")
    finally:
        if cursor: 
            cursor.close()
        if conn: 
            conn.close()
    return sale_events_processed


    


def add_financial_entry(entry_date, description, category, entry_type, amount, notes):
    """Adds a new financial entry (expense or income) to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO financial_entries (entry_date, description, category, entry_type, amount, notes)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (entry_date, description, category, entry_type, amount, notes))
        new_id = cursor.fetchone()[0]
        conn.commit()
        return new_id
    except psycopg2.Error as e:
        print(f"DB error in add_financial_entry: {e}")
        if conn: conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def get_all_financial_entries():
    """Retrieves all financial entries, ordered by date."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    entries = []
    try:
        cursor.execute("SELECT * FROM financial_entries ORDER BY entry_date DESC, id DESC")
        entries = cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB error in get_all_financial_entries: {e}")
    finally:
        cursor.close()
        conn.close()
    return entries

def delete_financial_entry(entry_id):
    """Deletes a financial entry by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    deleted = False
    try:
        cursor.execute("DELETE FROM financial_entries WHERE id = %s", (entry_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
    except psycopg2.Error as e:
        print(f"DB error in delete_financial_entry for ID {entry_id}: {e}")
        if conn: conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return deleted


if __name__ == '__main__':
    print("Initializing PostgreSQL database...")
    init_db()
    print("Database initialization complete.")