import sqlite3
import datetime

DATABASE_NAME = 'cdi_tracker.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_item_id INTEGER,
            item_type TEXT NOT NULL,
            original_item_name TEXT,
            original_item_details TEXT,
            quantity_sold INTEGER NOT NULL,
            sell_price_per_item REAL NOT NULL,
            buy_price_per_item REAL NOT NULL,
            shipping_cost REAL DEFAULT 0.0,
            profit_loss REAL NOT NULL,
            sale_date DATE NOT NULL,
            notes TEXT,
            date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    _check_and_add_column(cursor, 'cards', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'cards', 'scryfall_id', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'rarity', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'language', 'TEXT')
    _check_and_add_column(cursor, 'sealed_products', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'sales', 'item_type', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'inventory_item_id', 'INTEGER')
    _check_and_add_column(cursor, 'sales', 'original_item_name', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'original_item_details', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'notes', 'TEXT')
    _check_and_add_column(cursor, 'sales', 'shipping_cost', 'REAL DEFAULT 0.0')

    conn.commit()
    conn.close()

def _check_and_add_column(cursor, table_name, column_name, column_type_with_default):
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row['name'] for row in cursor.fetchall()]
        if column_name not in columns:
             cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_with_default}")
             print(f"Added column '{column_name}' to table '{table_name}'.")
    except sqlite3.Error as e:
        print(f"Error checking/adding column '{column_name}' to '{table_name}': {e}")

def get_item_by_id(item_type, item_id):
    if item_type == 'single_card': return get_card_by_id(item_id)
    elif item_type == 'sealed_product': return get_sealed_product_by_id(item_id)
    return None

def add_card(set_code, collector_number, name, quantity, buy_price, is_foil,
             market_price_usd, foil_market_price_usd, image_uri, sell_price, location,
             scryfall_id, rarity, language):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    is_foil_int = 1 if is_foil else 0
    try:
        current_buy_price = float(buy_price)
    except (ValueError, TypeError):
        print(f"DB Error: Invalid buy_price format '{buy_price}' for card '{name}'. Cannot process.")
        conn.close()
        return None

    try:
        cursor.execute('''SELECT id, quantity FROM cards
                          WHERE set_code = ? AND collector_number = ? AND is_foil = ? AND location = ?
                          AND rarity = ? AND language = ? AND buy_price = ?''',
                       (set_code, collector_number, is_foil_int, location, rarity, language, current_buy_price))
        existing_card_with_same_buy_price = cursor.fetchone()

        if existing_card_with_same_buy_price:
            card_id = existing_card_with_same_buy_price['id']
            new_quantity = existing_card_with_same_buy_price['quantity'] + quantity
            cursor.execute('''UPDATE cards
                              SET quantity = ?, market_price_usd = ?, foil_market_price_usd = ?,
                                  image_uri = ?, sell_price = ?, last_updated = ?, name = ?, scryfall_id = ?
                              WHERE id = ?''', 
                           (new_quantity, market_price_usd, foil_market_price_usd,
                            image_uri, sell_price, timestamp, name, scryfall_id, card_id))
            conn.commit()
            print(f"DB: Updated quantity for existing card ID {card_id} ('{name}', Buy: ${current_buy_price:.2f}) at '{location}' to {new_quantity}.")
            return card_id
        else:
            cursor.execute('''INSERT INTO cards
                              (set_code, collector_number, name, quantity, buy_price, is_foil,
                               market_price_usd, foil_market_price_usd, image_uri, sell_price, location,
                               date_added, last_updated, scryfall_id, rarity, language)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (set_code, collector_number, name, quantity, current_buy_price, is_foil_int,
                            market_price_usd, foil_market_price_usd, image_uri, sell_price, location,
                            timestamp, timestamp, scryfall_id, rarity, language))
            conn.commit()
            new_card_id = cursor.lastrowid
            print(f"DB: Inserted new card ID {new_card_id} ('{name}', Buy: ${current_buy_price:.2f}) at '{location}'.")
            return new_card_id
    except sqlite3.IntegrityError as ie:
        print(f"DB IntegrityError in add_card for {name} ({set_code}-{collector_number}, Buy: ${current_buy_price:.2f}) at '{location}': {ie}")
        conn.rollback()
        return None
    except sqlite3.Error as e:
        print(f"DB error in add_card for {name} ({set_code}-{collector_number}, Buy: ${current_buy_price:.2f}) at '{location}': {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def get_all_cards():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM cards WHERE quantity > 0 ORDER BY name, set_code, collector_number, location, buy_price, rarity, language")
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
    conn = get_db_connection(); cursor = conn.cursor()
    allowed_fields = {'quantity', 'buy_price', 'sell_price', 'location'}
    fields_to_update_sql = []; values_for_sql = [];

    if not data_to_update: # Should be caught by app.py
        conn.close()
        return False, "No changes were submitted to update_card_fields."

    for key, value_from_app in data_to_update.items():
        if key not in allowed_fields:
            print(f"DB Warning: Field '{key}' is not allowed for update in update_card_fields. Skipping.")
            continue
        
        sql_value = value_from_app # Assumes app.py sent correct type (int, float, str, or None for sell_price)

        # sell_price can be None if cleared
        if key == 'sell_price' and value_from_app is None:
            sql_value = None 
        # For other fields, app.py should ensure they are not None if they are required (like location, quantity, buy_price)
        
        fields_to_update_sql.append(f"{key} = ?")
        values_for_sql.append(sql_value)

    if not fields_to_update_sql:
        conn.close()
        return False, "No valid data fields provided for card update."

    fields_to_update_sql.append("last_updated = ?")
    values_for_sql.append(datetime.datetime.now())
    
    sql_set_clause = ", ".join(fields_to_update_sql)
    final_sql_values = tuple(values_for_sql + [card_id])

    sql = f"UPDATE cards SET {sql_set_clause} WHERE id = ?"
    try:
        cursor.execute(sql, final_sql_values); conn.commit(); updated_rows = cursor.rowcount
        if updated_rows == 0: return False, "Card not found or no data changed."
        return True, "Card updated."
    except sqlite3.IntegrityError as e:
        print(f"Integrity error update card {card_id}: {e}. This might happen if changing buy_price creates a duplicate entry based on the unique key (set,cn,foil,loc,rarity,lang,buy_price).");
        return False, f"Update failed: Buy price change creates a duplicate? ({e})"
    except sqlite3.Error as e: print(f"DB error update card {card_id}: {e}"); return False, f"DB error: {e}"
    finally:
        if conn: conn.close()

def add_sealed_product(product_name, set_name, product_type, language, is_collectors_item,
                       quantity, buy_price, manual_market_price, sell_price, image_uri, location):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    is_collectors_item_int = 1 if is_collectors_item else 0
    try:
        current_buy_price = float(buy_price)
    except (ValueError, TypeError):
        print(f"DB Error: Invalid buy_price format '{buy_price}' for sealed product '{product_name}'. Cannot process.")
        conn.close()
        return None

    try:
        cursor.execute('''
            SELECT id, quantity FROM sealed_products
            WHERE product_name = ? AND set_name = ? AND product_type = ? AND language = ? AND location = ? AND is_collectors_item = ? AND buy_price = ?
        ''', (product_name, set_name, product_type, language, location, is_collectors_item_int, current_buy_price))
        existing_product = cursor.fetchone()

        if existing_product:
            product_id = existing_product['id']
            new_quantity = existing_product['quantity'] + quantity
            # Note: buy_price is part of the match, so it's not updated here for an existing lot.
            # If buy_price changes, it should ideally become a new lot or be handled by update_sealed_product_fields.
            cursor.execute('''UPDATE sealed_products 
                              SET quantity = ?, manual_market_price = ?, sell_price = ?, image_uri = ?, last_updated = ?
                              WHERE id = ?''',
                           (new_quantity, manual_market_price, sell_price, image_uri, timestamp, product_id))
            conn.commit()
            print(f"DB: Updated quantity for existing sealed product ID {product_id} at '{location}' to {new_quantity}.")
            return product_id
        else:
            cursor.execute('''
                INSERT INTO sealed_products (product_name, set_name, product_type, language, is_collectors_item,
                                           quantity, buy_price, manual_market_price, sell_price, image_uri, location,
                                           date_added, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_name, set_name, product_type, language, is_collectors_item_int,
                  quantity, current_buy_price, manual_market_price, sell_price, image_uri, location,
                  timestamp, timestamp))
            conn.commit()
            new_product_id = cursor.lastrowid
            print(f"DB: Inserted new sealed product ID {new_product_id} (Buy: ${current_buy_price:.2f}) at '{location}'.")
            return new_product_id
    except sqlite3.IntegrityError as ie:
        print(f"DB IntegrityError adding sealed product '{product_name}' (Buy: ${current_buy_price:.2f}) at '{location}': {ie}")
        conn.rollback()
        return None
    except sqlite3.Error as e:
        print(f"Database error adding sealed product: {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def get_all_sealed_products():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM sealed_products WHERE quantity > 0 ORDER BY product_name, set_name, location, buy_price")
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
        return True, "Quantity updated."
    except sqlite3.Error as e: print(f"Error update_sealed_product_quantity ID {product_id}: {e}"); return False, f"DB error: {e}"
    finally:
        if conn: conn.close()

def delete_sealed_product(product_id):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM sealed_products WHERE id = ?", (product_id,)); conn.commit(); return cursor.rowcount > 0
    except sqlite3.Error as e: print(f"Error deleting sealed product ID {product_id}: {e}"); return False
    finally: conn.close()

def update_sealed_product_fields(product_id, data_to_update_from_app):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # These are the fields that app.py is expected to send if they are changed.
    # product_name, set_name, product_type are part of the unique key (with lang, loc, collector, buy_price)
    # and generally shouldn't be changed via this update mechanism as it might imply a new item/lot.
    # If they were to be updatable, they'd need careful handling regarding the UNIQUE constraint.
    allowed_fields_for_update = {
        'quantity', 'buy_price', 'manual_market_price', 
        'sell_price', 'location', 'image_uri', 'language', 'is_collectors_item'
    }

    fields_to_set_in_sql = []
    values_for_sql_query = []

    # This check should ideally be handled by app.py before calling this DB function.
    if not data_to_update_from_app:
        conn.close()
        # This message indicates app.py called with an empty dict, which it shouldn't.
        return False, "No changes were submitted to the database function."

    for field_key, new_value in data_to_update_from_app.items():
        if field_key not in allowed_fields_for_update:
            print(f"DB Warning: Field '{field_key}' is not an allowed field for updating sealed products. Skipping.")
            continue

        current_sql_value = new_value # new_value from app.py should be of the correct Python type (int, float, str, bool, or None for clearable fields)

        # Convert Python bool to SQLite integer for 'is_collectors_item'
        if field_key == 'is_collectors_item':
            current_sql_value = 1 if new_value else 0
        
        # Add the field and its value to our lists for building the SQL query
        fields_to_set_in_sql.append(f"{field_key} = ?")
        values_for_sql_query.append(current_sql_value)

    # If data_to_update_from_app was not empty, but all fields were skipped (e.g., not in allowed_fields_for_update),
    # then fields_to_set_in_sql will be empty.
    if not fields_to_set_in_sql:
        conn.close()
        # This is the error message the user is seeing. It means app.py sent data,
        # but this loop didn't find any of it to be valid for updating.
        return False, "No valid data fields provided for update."

    # Always update the 'last_updated' timestamp when any other valid field is being updated.
    fields_to_set_in_sql.append("last_updated = ?")
    values_for_sql_query.append(datetime.datetime.now()) # SQLite Python driver handles datetime objects

    # Construct the SET part of the SQL query
    sql_set_clause = ", ".join(fields_to_set_in_sql)
    
    # Add the product_id for the WHERE clause to the end of the values list
    final_sql_values_tuple = tuple(values_for_sql_query + [product_id])

    sql_query_string = f"UPDATE sealed_products SET {sql_set_clause} WHERE id = ?"
    
    try:
        cursor.execute(sql_query_string, final_sql_values_tuple)
        conn.commit()
        updated_rows = cursor.rowcount
        if updated_rows == 0:
            # This could happen if product_id is incorrect or if, by some chance,
            # all submitted values were identical to DB values (though app.py tries to prevent this).
            return False, "Sealed product not found or data was identical, resulting in no actual change in the database."
        return True, "Sealed product updated successfully."
    except sqlite3.IntegrityError as e:
        # This typically occurs if changing buy_price (or other unique-constrained fields)
        # creates a conflict with an existing record.
        print(f"DB IntegrityError on updating sealed_product ID {product_id}: {e}")
        return False, f"Update failed. This might be due to a conflict with an existing item (e.g., changing buy price to one that already exists for this item's other attributes). Error: {e}"
    except sqlite3.Error as e:
        print(f"DB general error on updating sealed_product ID {product_id}: {e}")
        return False, f"A database error occurred: {e}"
    finally:
        if conn:
            conn.close()


def record_sale(inventory_item_id, item_type, original_item_name, original_item_details,
                quantity_sold, sell_price_per_item, buy_price_per_item, sale_date_str, shipping_cost=0.0, notes=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    if item_type not in ['single_card', 'sealed_product']:
        conn.close(); return None, "Invalid item type."
    try: ship_cost_float = float(shipping_cost if shipping_cost is not None else 0.0)
    except ValueError: conn.close(); return None, "Invalid shipping cost."
    try: buy_price_per_item_float = float(buy_price_per_item)
    except (ValueError, TypeError): conn.close(); return None, "Invalid buy price for item sold."

    gross_profit = (sell_price_per_item - buy_price_per_item_float) * quantity_sold
    net_profit_loss = gross_profit - ship_cost_float
    try: sale_date_obj = datetime.datetime.strptime(sale_date_str, '%Y-%m-%d').date() # Store as date object
    except ValueError: conn.close(); return None, "Invalid sale date format."

    try:
        cursor.execute('''
            INSERT INTO sales (inventory_item_id, item_type, original_item_name, original_item_details,
                               quantity_sold, sell_price_per_item, buy_price_per_item, shipping_cost, profit_loss, sale_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (inventory_item_id, item_type, original_item_name, original_item_details,
              quantity_sold, sell_price_per_item, buy_price_per_item_float, ship_cost_float, net_profit_loss, sale_date_obj, notes))
        sale_id = cursor.lastrowid
        conn.commit()
        
        success_inventory_update = False
        inventory_message = "Inventory update not attempted for this item type."

        if item_type == 'single_card': 
            success_inventory_update, inventory_message = update_card_quantity(inventory_item_id, -quantity_sold)
        elif item_type == 'sealed_product': 
            success_inventory_update, inventory_message = update_sealed_product_quantity(inventory_item_id, -quantity_sold)
        
        if not success_inventory_update:
            # Critical: Sale recorded but inventory update failed. Attempt to roll back sale.
            print(f"CRITICAL WARNING: Sale ID {sale_id} recorded, but inventory update FAILED for {item_type} ID {inventory_item_id}: {inventory_message}")
            try:
                # Re-establish connection for rollback if needed, or use existing if transactionally sound
                # For simplicity here, assume a new connection for the delete operation if the original conn was closed by update_x_quantity
                conn_del = get_db_connection(); cursor_del = conn_del.cursor()
                cursor_del.execute("DELETE FROM sales WHERE id = ?", (sale_id,)); conn_del.commit(); conn_del.close()
                print(f"Sale record {sale_id} has been rolled back due to inventory update failure.")
                return None, f"Sale rolled back. Reason: Inventory update failed: {inventory_message}"
            except sqlite3.Error as e_del:
                print(f"CRITICAL ERROR: Failed to delete sale record {sale_id} after inventory update failure: {e_del}. MANUAL INTERVENTION REQUIRED.")
                # Return sale_id but with a critical warning, as sale is in DB but inventory is not updated.
                return sale_id, f"Sale recorded (ID: {sale_id}), but CRITICAL: Inventory update failed: {inventory_message}. Manual correction needed!"
        
        return sale_id, f"Inventory updated: {inventory_message}"
    except sqlite3.Error as e:
        print(f"Database error during sale record: {e}"); conn.rollback() # Rollback if insert into sales failed
        return None, f"Database error: {e}"
    finally:
         if conn and not getattr(conn, 'closed', True): conn.close()


def get_all_sales():
    conn = get_db_connection(); cursor = conn.cursor()
    # Fetches sales, ensuring date types are handled by PARSE_DECLTYPES
    cursor.execute('''
        SELECT s.id, s.inventory_item_id, s.item_type,
               s.original_item_name, s.original_item_details,
               s.quantity_sold, s.sell_price_per_item, s.buy_price_per_item,
               s.shipping_cost, s.profit_loss, s.sale_date, s.notes, s.date_recorded
        FROM sales s
        ORDER BY s.sale_date DESC, s.date_recorded DESC ''')
    sales = cursor.fetchall(); conn.close(); return sales

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    print("Database initialization complete.")
