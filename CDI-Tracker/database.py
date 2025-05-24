import psycopg2
import psycopg2.extras
import datetime
import os # Recommended for handling connection details securely

# --- PostgreSQL Connection Details ---
# It is recommended to use environment variables for security.
DB_USER = os.environ.get('DB_USER', 'vscode')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'your_postgres_password')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
# The database name will be the same as the username by default
DB_NAME = os.environ.get('DB_NAME', DB_USER)

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    return conn

def init_db():
    """Initializes the database schema for PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # For development, dropping the old sales table if schema changes.
    # In production, use migrations.
    cursor.execute("DROP TABLE IF EXISTS sales") # This line was in the original file
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_events (
            id SERIAL PRIMARY KEY,
            sale_date DATE NOT NULL,
            total_shipping_cost REAL DEFAULT 0.0,
            notes TEXT,
            total_profit_loss REAL,
            date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
    _check_and_add_column(cursor, 'cards', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'cards', 'scryfall_id', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'rarity', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'language', 'TEXT')
    _check_and_add_column(cursor, 'sealed_products', 'last_updated', 'TIMESTAMP')
    conn.commit()
    cursor.close()
    conn.close()

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
        # Rollback in case of error within a larger transaction
        cursor.connection.rollback()


def get_item_by_id(item_type, item_id):
    conn = get_db_connection()
    # Use DictCursor to get results as dictionaries
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    item = None
    table_name = 'cards' if item_type == 'single_card' else 'sealed_products'
    try:
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (item_id,))
        item = cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB error in get_item_by_id for {item_type} ID {item_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return item

def add_card(set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, scryfall_id, rarity, language):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    is_foil_int = 1 if is_foil else 0
    try:
        current_buy_price = float(buy_price)
    except (ValueError, TypeError):
        print(f"DB Error: Invalid buy_price format '{buy_price}' for card '{name}'.")
        conn.close(); return None
    
    card_id = None
    try:
        # Use DictCursor for this specific query to read by name
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as check_cursor:
             check_cursor.execute('''SELECT id, quantity FROM cards WHERE set_code = %s AND collector_number = %s AND is_foil = %s AND location = %s AND rarity = %s AND language = %s AND buy_price = %s''', (set_code, collector_number, is_foil_int, location, rarity, language, current_buy_price))
             existing = check_cursor.fetchone()

        if existing:
            card_id, new_qty = existing['id'], existing['quantity'] + quantity
            cursor.execute('''UPDATE cards SET quantity = %s, market_price_usd = %s, foil_market_price_usd = %s, image_uri = %s, sell_price = %s, last_updated = %s, name = %s, scryfall_id = %s WHERE id = %s''', (new_qty, market_price_usd, foil_market_price_usd, image_uri, sell_price, timestamp, name, scryfall_id, card_id))
        else:
            cursor.execute('''INSERT INTO cards (set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, date_added, last_updated, scryfall_id, rarity, language) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''', (set_code, collector_number, name, quantity, current_buy_price, is_foil_int, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, timestamp, timestamp, scryfall_id, rarity, language))
            card_id = cursor.fetchone()[0]
        conn.commit()
        return card_id
    except psycopg2.IntegrityError as ie: print(f"DB IntegrityError in add_card for {name}: {ie}"); conn.rollback(); return None
    except psycopg2.Error as e: print(f"DB error add_card for {name}: {e}"); conn.rollback(); return None
    finally: cursor.close(); conn.close()

# The remaining functions would be converted in a similar pattern.
# Below are a few key examples.

def get_all_cards():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM cards WHERE quantity > 0 ORDER BY name, set_code, collector_number, location, buy_price, rarity, language")
        cards = cursor.fetchall()
        return cards
    except psycopg2.Error as e:
        print(f"DB error in get_all_cards: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

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
        if conn: cursor.close(); conn.close()

def record_multi_item_sale(sale_date_str, total_shipping_cost_str, overall_notes, items_data_from_app):
    conn = get_db_connection()
    cursor = conn.cursor()
    sale_event_id = None
    total_event_profit_loss_calculated = 0.0

    try:
        sale_date_obj = datetime.datetime.strptime(sale_date_str, '%Y-%m-%d').date()
        total_shipping_cost = float(total_shipping_cost_str if total_shipping_cost_str and total_shipping_cost_str.strip() != '' else 0.0)
    except ValueError as e:
        print(f"DB Error: Invalid date/shipping format: {e}"); conn.close(); return None, f"Invalid date/shipping: {e}"

    try:
        # Start transaction
        cursor.execute('''INSERT INTO sale_events (sale_date, total_shipping_cost, notes) VALUES (%s, %s, %s) RETURNING id''', (sale_date_obj, total_shipping_cost, overall_notes))
        sale_event_id = cursor.fetchone()[0]
        print(f"DB: Created sale_event ID {sale_event_id}")

        # Use a DictCursor for reading item data within the transaction
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as item_cursor:
            for item_data in items_data_from_app:
                # ... (parsing logic remains the same)
                inventory_id_with_prefix = item_data.get('inventory_item_id_with_prefix'); quantity_sold_str = item_data.get('quantity_sold'); sell_price_per_item_str = item_data.get('sell_price_per_item'); item_type = None; inventory_item_id_int = None
                if inventory_id_with_prefix and '-' in inventory_id_with_prefix:
                    parts = inventory_id_with_prefix.split('-', 1); item_type_prefix = parts[0]
                    try: 
                        inventory_item_id_int = int(parts[1])
                        if item_type_prefix == 'single_card': item_type = 'single_card'
                        elif item_type_prefix == 'sealed_product': item_type = 'sealed_product'
                    except ValueError: raise ValueError(f"Invalid inv item ID format: {inventory_id_with_prefix}")
                if not all([item_type, inventory_item_id_int is not None]): raise ValueError(f"Missing/invalid item identifier: {inventory_id_with_prefix}")
                quantity_sold = int(quantity_sold_str); sell_price_per_item = float(sell_price_per_item_str)
                if quantity_sold <= 0 or sell_price_per_item < 0: raise ValueError("Qty/Sell Price invalid.")
                
                # Fetch original item within the same transaction
                table_name = 'cards' if item_type == 'single_card' else 'sealed_products'
                item_cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (inventory_item_id_int,))
                original_item_db_row = item_cursor.fetchone()

                if not original_item_db_row: raise ValueError(f"Inv item not found: {item_type} id {inventory_item_id_int}")
                if quantity_sold > original_item_db_row['quantity']: name_key = 'name' if item_type == 'single_card' else 'product_name'; raise ValueError(f"Not enough stock for {original_item_db_row[name_key]}. Have: {original_item_db_row['quantity']}")
                
                buy_price_per_item = float(original_item_db_row['buy_price']); item_profit_loss = (sell_price_per_item - buy_price_per_item) * quantity_sold; total_event_profit_loss_calculated += item_profit_loss
                
                # ... (snapshot logic remains the same)
                original_item_name_snapshot = ""; original_item_details_snapshot = ""
                if item_type == 'single_card':
                    original_item_name_snapshot = original_item_db_row['name']
                    rarity_str = (original_item_db_row['rarity'] if 'rarity' in original_item_db_row.keys() and original_item_db_row['rarity'] is not None else 'N/A')
                    lang_str = (original_item_db_row['language'] if 'language' in original_item_db_row.keys() and original_item_db_row['language'] is not None else 'N/A')
                    original_item_details_snapshot = f"{original_item_db_row['set_code']}-{original_item_db_row['collector_number']} {'(Foil)' if original_item_db_row['is_foil'] else ''} (R: {rarity_str.capitalize()}, L: {lang_str.upper()})"
                elif item_type == 'sealed_product':
                    original_item_name_snapshot = original_item_db_row['product_name']
                    lang_str_sealed = (original_item_db_row['language'] if 'language' in original_item_db_row.keys() and original_item_db_row['language'] is not None else 'N/A')
                    original_item_details_snapshot = f"{original_item_db_row['set_name']} - {original_item_db_row['product_type']} {'(Collector)' if original_item_db_row['is_collectors_item'] else ''} (L: {lang_str_sealed.upper()})"

                # Use the main cursor for writes
                cursor.execute('''INSERT INTO sale_items (sale_event_id, inventory_item_id, item_type, original_item_name, original_item_details, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''', (sale_event_id, inventory_item_id_int, item_type, original_item_name_snapshot, original_item_details_snapshot, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss))
                
                # Update quantity within the same transaction
                new_quantity = original_item_db_row['quantity'] - quantity_sold
                cursor.execute(f"UPDATE {table_name} SET quantity = %s, last_updated = %s WHERE id = %s", (new_quantity, datetime.datetime.now(), inventory_item_id_int))

        final_event_profit_loss = total_event_profit_loss_calculated - total_shipping_cost
        cursor.execute('''UPDATE sale_events SET total_profit_loss = %s WHERE id = %s''', (final_event_profit_loss, sale_event_id))
        
        conn.commit() # Commit transaction
        print(f"DB: Committed sale_event ID {sale_event_id}")
        return sale_event_id, "Sale event recorded successfully."
    except Exception as e:
        print(f"DB Error in record_multi_item_sale: {e}")
        conn.rollback() # Rollback on any error
        return None, str(e)
    finally:
        cursor.close()
        conn.close()

# The remaining functions for 'sealed_products' and 'sale_events' would follow the same conversion logic.
# Ensure all '?' are replaced with '%s', `cursor.lastrowid` is replaced with `RETURNING id`,
# and error handling uses `psycopg2.Error`.

if __name__ == '__main__':
    print("Initializing PostgreSQL database...")
    init_db()
    print("Database initialization complete.")