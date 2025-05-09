import sqlite3
import datetime

DATABASE_NAME = 'cdi_tracker.db'

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    # Enable date/time type detection
    conn = sqlite3.connect(DATABASE_NAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Cards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            is_foil INTEGER NOT NULL DEFAULT 0,
            market_price_usd REAL,
            foil_market_price_usd REAL,
            image_uri TEXT,
            sell_price REAL, -- Asking price
            location TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scryfall_id TEXT,
            UNIQUE(set_code, collector_number, is_foil, location)
        )
    ''')

    # Sealed Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sealed_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            set_name TEXT,
            product_type TEXT,
            language TEXT DEFAULT 'English',
            is_collectors_item INTEGER DEFAULT 0,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            manual_market_price REAL,
            sell_price REAL, -- Asking price
            image_uri TEXT,
            location TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_name, set_name, product_type, language, location, is_collectors_item)
        )
    ''')

    # Sales table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_item_id INTEGER,
            item_type TEXT NOT NULL,
            original_item_name TEXT,
            original_item_details TEXT,
            quantity_sold INTEGER NOT NULL,
            sell_price_per_item REAL NOT NULL,
            buy_price_per_item REAL NOT NULL,
            shipping_cost REAL DEFAULT 0.0,  -- New column for shipping cost
            profit_loss REAL NOT NULL,       -- This will now be NET profit
            sale_date DATE NOT NULL,
            notes TEXT,
            date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Add columns if they don't exist (Simple migration) ---
    _check_and_add_column(cursor, 'cards', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'cards', 'scryfall_id', 'TEXT')
    _check_and_add_column(cursor, 'sealed_products', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'sales', 'item_type', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'inventory_item_id', 'INTEGER')
    _check_and_add_column(cursor, 'sales', 'original_item_name', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'original_item_details', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'notes', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'shipping_cost', 'REAL DEFAULT 0.0') # Add shipping_cost column

    conn.commit()
    conn.close()

def _check_and_add_column(cursor, table_name, column_name, column_type_with_default):
    """Helper to add a column if it doesn't exist."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row['name'] for row in cursor.fetchall()]
        if column_name not in columns:
             cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_with_default}")
             print(f"Added column '{column_name}' to table '{table_name}'.")
    except sqlite3.Error as e:
        print(f"Error checking/adding column '{column_name}' to '{table_name}': {e}")

# --- Generic Getters ---
# (get_item_by_id remains the same)
def get_item_by_id(item_type, item_id):
    if item_type == 'single_card': return get_card_by_id(item_id)
    elif item_type == 'sealed_product': return get_sealed_product_by_id(item_id)
    return None

# --- Card Functions ---
# (add_card, get_all_cards, get_card_by_id, delete_card, update_card_prices_and_image, update_card_fields, update_card_quantity remain the same)
def add_card(set_code, collector_number, name, quantity, buy_price, is_foil,
             market_price_usd, foil_market_price_usd, image_uri, sell_price, location, scryfall_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    is_foil_int = 1 if is_foil else 0
    try:
        cursor.execute('''SELECT id, quantity FROM cards WHERE set_code = ? AND collector_number = ? AND is_foil = ? AND location = ?''', (set_code, collector_number, is_foil_int, location))
        existing_card = cursor.fetchone()
        if existing_card:
            if existing_card['quantity'] <= 0:
                card_id = existing_card['id']
                cursor.execute(''' UPDATE cards SET name = ?, quantity = ?, buy_price = ?, market_price_usd = ?, foil_market_price_usd = ?, image_uri = ?, sell_price = ?, last_updated = ?, scryfall_id = ?, date_added = ? WHERE id = ? ''', (name, quantity, buy_price, market_price_usd, foil_market_price_usd, image_uri, sell_price, timestamp, scryfall_id, timestamp, card_id))
                conn.commit(); return card_id
            else: return None # Indicate already exists and is active
        else:
            cursor.execute(''' INSERT INTO cards (set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, date_added, last_updated, scryfall_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ''', (set_code, collector_number, name, quantity, buy_price, is_foil_int, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, timestamp, timestamp, scryfall_id))
            conn.commit(); return cursor.lastrowid
    except sqlite3.Error as e: print(f"DB error in add_card: {e}"); conn.rollback(); return None
    finally: conn.close()

def get_all_cards():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM cards WHERE quantity > 0 ORDER BY name, set_code, collector_number")
    cards = cursor.fetchall(); conn.close(); return cards

def get_card_by_id(card_id):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,)); card = cursor.fetchone(); conn.close(); return card

def update_card_quantity(card_id, quantity_change):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT quantity FROM cards WHERE id = ?", (card_id,)); result = cursor.fetchone()
        if not result: return False, "Card not found."
        current_quantity = result['quantity']; new_quantity = current_quantity + quantity_change
        if new_quantity < 0: return False, "Not enough quantity."
        cursor.execute("UPDATE cards SET quantity = ?, last_updated = ? WHERE id = ?", (new_quantity, datetime.datetime.now(), card_id)); conn.commit()
        if new_quantity == 0: return (True, "Card quantity zero, entry deleted.") if delete_card(card_id) else (False, "Card quantity zero, delete failed.")
        return True, "Quantity updated."
    except sqlite3.Error as e: print(f"Error update_card_quantity ID {card_id}: {e}"); return False, f"DB error: {e}"
    finally:
         if conn and not getattr(conn, 'closed', True): conn.close()

def delete_card(card_id):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,)); conn.commit(); return cursor.rowcount > 0
    except sqlite3.Error as e: print(f"Error deleting card ID {card_id}: {e}"); return False
    finally: conn.close()

def update_card_prices_and_image(card_id, market_price_usd, foil_market_price_usd, image_uri):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute(''' UPDATE cards SET market_price_usd = ?, foil_market_price_usd = ?, image_uri = ?, last_updated = ? WHERE id = ? ''', (market_price_usd, foil_market_price_usd, image_uri, datetime.datetime.now(), card_id)); conn.commit(); return cursor.rowcount > 0
    except sqlite3.Error as e: print(f"Error updating market data card ID {card_id}: {e}"); return False
    finally: conn.close()

def update_card_fields(card_id, data_to_update):
    conn = get_db_connection(); cursor = conn.cursor(); allowed_fields = {'quantity', 'buy_price', 'sell_price', 'location'}; fields_to_update_sql = []; values = []; new_quantity = None
    for key, value in data_to_update.items():
        if key in allowed_fields:
            sql_value = value if value != '' else None;
            if key == 'sell_price' and sql_value == '': sql_value = None
            if key == 'quantity': new_quantity = int(sql_value) if sql_value is not None else None
            if sql_value is not None or key == 'sell_price': fields_to_update_sql.append(f"{key} = ?"); values.append(sql_value) # Update even if value is None for sell_price
    if not fields_to_update_sql: conn.close(); return False, "No valid data provided."
    values.extend([datetime.datetime.now(), card_id]); sql = f"UPDATE cards SET {', '.join(fields_to_update_sql)}, last_updated = ? WHERE id = ?"
    try:
        cursor.execute(sql, tuple(values)); conn.commit(); updated_rows = cursor.rowcount
        if updated_rows == 0: return False, "Card not found/unchanged."
        if new_quantity == 0: return (True, "Qty zero, entry deleted.") if delete_card(card_id) else (False, "Qty zero, delete failed.")
        return True, "Card updated."
    except sqlite3.IntegrityError as e: print(f"Integrity error update card {card_id}: {e}"); return False, f"Update failed: Unique constraint conflict? ({e})"
    except sqlite3.Error as e: print(f"DB error update card {card_id}: {e}"); return False, f"DB error: {e}"
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

# --- Sealed Product Functions ---
# (add_sealed_product, get_all_sealed_products, get_sealed_product_by_id, delete_sealed_product, update_sealed_product_fields, update_sealed_product_quantity remain the same structure as previously defined for card funcs, just targeting sealed_products table)
def add_sealed_product(product_name, set_name, product_type, language, is_collectors_item,
                       quantity, buy_price, manual_market_price, sell_price, image_uri, location):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    is_collectors_item_int = 1 if is_collectors_item else 0
    try:
        # Try inserting first
        cursor.execute('''
            INSERT INTO sealed_products (product_name, set_name, product_type, language, is_collectors_item,
                                       quantity, buy_price, manual_market_price, sell_price, image_uri, location,
                                       date_added, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_name, set_name, product_type, language, is_collectors_item_int,
              quantity, buy_price, manual_market_price, sell_price, image_uri, location,
              timestamp, timestamp))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # If insert failed due to UNIQUE constraint, check if it's a zero quantity item to restock
        cursor.execute('''
            SELECT id, quantity FROM sealed_products
            WHERE product_name = ? AND set_name = ? AND product_type = ? AND language = ? AND location = ? AND is_collectors_item = ?
        ''', (product_name, set_name, product_type, language, location, is_collectors_item_int))
        existing_product = cursor.fetchone()

        if existing_product and existing_product['quantity'] <= 0:
             # Try to update / restock existing zero-quantity entry
             # Ensure data_to_update only includes fields relevant for restock if needed
             data_for_restock = {
                 'quantity': quantity,
                 'buy_price': buy_price, # Use new buy price
                 'manual_market_price': manual_market_price, # Update optional fields too
                 'sell_price': sell_price,
                 'image_uri': image_uri
                 # Location, name, set, type, lang, collector status are already matched by WHERE clause
             }
             success, _ = update_sealed_product_fields(existing_product['id'], data_for_restock)

             # Corrected if/else block:
             if success:
                 print(f"Restocked sealed product ID {existing_product['id']}")
                 return existing_product['id'] # Return existing ID if restocked
             else:
                 print(f"Failed to restock sealed product ID {existing_product['id']}")
                 return None # Failed to restock
        else:
             # If it exists with quantity > 0, or another integrity error occurred
            print(f"Error: Sealed product '{product_name}' ({set_name}, Type: {product_type}, Lang: {language}, Coll: {is_collectors_item}) in location '{location}' likely already exists with quantity > 0 or another IntegrityError occurred.")
            return None
    except sqlite3.Error as e:
        print(f"Database error adding sealed product: {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def get_all_sealed_products():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM sealed_products WHERE quantity > 0 ORDER BY product_name, set_name")
    products = cursor.fetchall(); conn.close(); return products

def get_sealed_product_by_id(product_id):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM sealed_products WHERE id = ?", (product_id,)); product = cursor.fetchone(); conn.close(); return product

def update_sealed_product_quantity(product_id, quantity_change):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT quantity FROM sealed_products WHERE id = ?", (product_id,)); result = cursor.fetchone()
        if not result: return False, "Sealed product not found."
        current_quantity = result['quantity']; new_quantity = current_quantity + quantity_change
        if new_quantity < 0: return False, "Not enough quantity."
        cursor.execute("UPDATE sealed_products SET quantity = ?, last_updated = ? WHERE id = ?", (new_quantity, datetime.datetime.now(), product_id)); conn.commit()
        if new_quantity == 0: return (True, "Qty zero, entry deleted.") if delete_sealed_product(product_id) else (False, "Qty zero, delete failed.")
        return True, "Quantity updated."
    except sqlite3.Error as e: print(f"Error update_sealed_product_quantity ID {product_id}: {e}"); return False, f"DB error: {e}"
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

def delete_sealed_product(product_id):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM sealed_products WHERE id = ?", (product_id,)); conn.commit(); return cursor.rowcount > 0
    except sqlite3.Error as e: print(f"Error deleting sealed product ID {product_id}: {e}"); return False
    finally: conn.close()

def update_sealed_product_fields(product_id, data_to_update):
    conn = get_db_connection(); cursor = conn.cursor(); allowed_fields = {'product_name', 'set_name', 'product_type', 'language', 'is_collectors_item', 'quantity', 'buy_price', 'manual_market_price', 'sell_price', 'image_uri', 'location'}; fields_to_update_sql = []; values = []; new_quantity = None
    for key, value in data_to_update.items():
        if key in allowed_fields:
            sql_value = value
            if key == 'is_collectors_item': sql_value = 1 if value else 0
            elif key in ['manual_market_price', 'sell_price', 'image_uri'] and value == '': sql_value = None
            if key == 'quantity': new_quantity = int(sql_value) if sql_value is not None else None
            if sql_value is not None or key in ['manual_market_price', 'sell_price', 'image_uri']: fields_to_update_sql.append(f"{key} = ?"); values.append(sql_value) # Allow setting nullables
    if not fields_to_update_sql: conn.close(); return False, "No valid data."
    values.extend([datetime.datetime.now(), product_id]); sql = f"UPDATE sealed_products SET {', '.join(fields_to_update_sql)}, last_updated = ? WHERE id = ?"
    try:
        cursor.execute(sql, tuple(values)); conn.commit(); updated_rows = cursor.rowcount
        if updated_rows == 0: return False, "Product not found/unchanged."
        if new_quantity == 0: return (True, "Qty zero, entry deleted.") if delete_sealed_product(product_id) else (False, "Qty zero, delete failed.")
        return True, "Sealed product updated."
    except sqlite3.IntegrityError as e: print(f"Integrity error update sealed product {product_id}: {e}"); return False, f"Update failed: Unique constraint conflict? ({e})"
    except sqlite3.Error as e: print(f"DB error update sealed product {product_id}: {e}"); return False, f"DB error: {e}"
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

# --- Sales Functions ---
def record_sale(inventory_item_id, item_type, original_item_name, original_item_details,
                quantity_sold, sell_price_per_item, buy_price_per_item, sale_date_str, shipping_cost=0.0, notes=""):
    """Records a sale and attempts to update inventory quantity."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate item_type
    if item_type not in ['single_card', 'sealed_product']:
        print(f"Error: Invalid item_type '{item_type}' for sale record.")
        conn.close()
        return None, "Invalid item type."

    # Ensure shipping_cost is a float
    try:
        ship_cost_float = float(shipping_cost if shipping_cost is not None else 0.0)
    except ValueError:
        print(f"Error: Invalid shipping_cost value '{shipping_cost}'. Must be a number.")
        conn.close()
        return None, "Invalid shipping cost."

    # Calculate NET profit_loss
    gross_profit = (sell_price_per_item - buy_price_per_item) * quantity_sold
    net_profit_loss = gross_profit - ship_cost_float

    try:
        # Validate sale_date_str format ('YYYY-MM-DD')
        datetime.datetime.strptime(sale_date_str, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Invalid sale_date format '{sale_date_str}'. Must be YYYY-MM-DD.")
        conn.close()
        return None, "Invalid sale date format."

    try:
        # Insert Sale Record First
        cursor.execute('''
            INSERT INTO sales (inventory_item_id, item_type, original_item_name, original_item_details,
                               quantity_sold, sell_price_per_item, buy_price_per_item, shipping_cost, profit_loss, sale_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (inventory_item_id, item_type, original_item_name, original_item_details,
              quantity_sold, sell_price_per_item, buy_price_per_item, ship_cost_float, net_profit_loss, sale_date_str, notes))
        sale_id = cursor.lastrowid
        conn.commit() # Commit sale first

        # Now attempt inventory update
        success = False
        message = "Inventory update not attempted."
        if item_type == 'single_card':
            success, message = update_card_quantity(inventory_item_id, -quantity_sold)
        elif item_type == 'sealed_product':
            success, message = update_sealed_product_quantity(inventory_item_id, -quantity_sold)

        if not success:
            # Critical issue: Sale logged but inventory not updated.
            print(f"CRITICAL WARNING: Sale ID {sale_id} recorded, but inventory update FAILED for {item_type} ID {inventory_item_id}: {message}")
            # Attempt to delete the sale record to maintain consistency
            try:
                # Need a new connection if previous functions closed it (delete does)
                conn_del = get_db_connection()
                cursor_del = conn_del.cursor()
                cursor_del.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
                conn_del.commit()
                conn_del.close()
                print(f"Sale record {sale_id} deleted due to inventory update failure.")
                return None, f"Sale rolled back due to inventory update failure: {message}"
            except sqlite3.Error as e_del:
                print(f"CRITICAL ERROR: Failed to delete sale record {sale_id} after inventory update failure: {e_del}")
                # Return the original warning message as sale is still in DB
                return sale_id, f"Sale recorded, but CRITICAL WARNING: Inventory update failed: {message}. Manual correction needed!"

        return sale_id, message # Return sale ID and inventory update message
    except sqlite3.Error as e:
        print(f"Database error during sale record: {e}")
        conn.rollback()
        return None, f"Database error: {e}"
    finally:
        # Ensure connection is closed if it wasn't closed by sub-functions like delete
         if conn and not getattr(conn, 'closed', True):
            conn.close()

def get_all_sales():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Make sure to select the new shipping_cost column
    cursor.execute('''
        SELECT s.id, s.inventory_item_id, s.item_type,
               s.original_item_name, s.original_item_details,
               s.quantity_sold, s.sell_price_per_item, s.buy_price_per_item,
               s.shipping_cost, s.profit_loss, s.sale_date, s.notes, s.date_recorded
        FROM sales s
        ORDER BY s.sale_date DESC, s.date_recorded DESC
    ''')
    sales = cursor.fetchall()
    conn.close()
    return sales

# --- Main execution block (for direct script run) ---
if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    print("Database initialization complete.")