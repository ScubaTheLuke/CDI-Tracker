import sqlite3
import datetime
# No 'import sys' needed at the top level

DATABASE_NAME = 'cdi_tracker.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000") 
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # For development, dropping the old sales table if schema changes.
    # In production, use migrations.
    cursor.execute("DROP TABLE IF EXISTS sales") 
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
        CREATE TABLE IF NOT EXISTS sale_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date DATE NOT NULL,
            total_shipping_cost REAL DEFAULT 0.0,
            notes TEXT,
            total_profit_loss REAL, 
            date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn = get_db_connection()
    cursor = conn.cursor()
    item = None
    if item_type == 'single_card':
        cursor.execute("SELECT * FROM cards WHERE id = ?", (item_id,))
        item = cursor.fetchone()
    elif item_type == 'sealed_product':
        cursor.execute("SELECT * FROM sealed_products WHERE id = ?", (item_id,))
        item = cursor.fetchone()
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
    try:
        cursor.execute('''SELECT id, quantity FROM cards WHERE set_code = ? AND collector_number = ? AND is_foil = ? AND location = ? AND rarity = ? AND language = ? AND buy_price = ?''', (set_code, collector_number, is_foil_int, location, rarity, language, current_buy_price))
        existing = cursor.fetchone()
        if existing: 
            card_id, new_qty = existing['id'], existing['quantity'] + quantity
            cursor.execute('''UPDATE cards SET quantity = ?, market_price_usd = ?, foil_market_price_usd = ?, image_uri = ?, sell_price = ?, last_updated = ?, name = ?, scryfall_id = ? WHERE id = ?''', (new_qty, market_price_usd, foil_market_price_usd, image_uri, sell_price, timestamp, name, scryfall_id, card_id))
        else: 
            cursor.execute('''INSERT INTO cards (set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, date_added, last_updated, scryfall_id, rarity, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (set_code, collector_number, name, quantity, current_buy_price, is_foil_int, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, timestamp, timestamp, scryfall_id, rarity, language))
            card_id = cursor.lastrowid
        conn.commit()
        return card_id
    except sqlite3.IntegrityError as ie: print(f"DB IntegrityError in add_card for {name}: {ie}"); conn.rollback(); return None
    except sqlite3.Error as e: print(f"DB error add_card for {name}: {e}"); conn.rollback(); return None
    finally: conn.close()

def get_all_cards(): 
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("SELECT * FROM cards WHERE quantity > 0 ORDER BY name, set_code, collector_number, location, buy_price, rarity, language"); cards = cursor.fetchall(); conn.close(); return cards

def get_card_by_id(card_id): 
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,)); card = cursor.fetchone(); conn.close(); return card

def update_card_quantity(card_id, quantity_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT quantity FROM cards WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        if not result:
            return False, "Card not found."
        current_quantity = result['quantity']
        new_quantity = current_quantity + quantity_change
        if new_quantity < 0:
            return False, "Not enough quantity in stock to remove."
        cursor.execute("UPDATE cards SET quantity = ?, last_updated = ? WHERE id = ?", 
                       (new_quantity, datetime.datetime.now(), card_id))
        conn.commit()
        return True, f"Card quantity updated to {new_quantity}."
    except sqlite3.Error as e:
        print(f"DB error in update_card_quantity for ID {card_id}: {e}")
        if conn: conn.rollback()
        return False, f"Database error during quantity update: {e}"
    finally:
        if conn: conn.close()

def delete_card(card_id): 
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,)); conn.commit(); deleted = cursor.rowcount > 0; conn.close(); return deleted

def update_card_prices_and_image(card_id, market_price_usd, foil_market_price_usd, image_uri): 
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute(''' UPDATE cards SET market_price_usd = ?, foil_market_price_usd = ?, image_uri = ?, last_updated = ? WHERE id = ? ''', (market_price_usd, foil_market_price_usd, image_uri, datetime.datetime.now(), card_id)); conn.commit(); updated = cursor.rowcount > 0; conn.close(); return updated

def update_card_fields(card_id, data_to_update):
    conn = get_db_connection(); cursor = conn.cursor(); allowed_fields = {'quantity', 'buy_price', 'sell_price', 'location'}; fields_to_update_sql = []; values_for_sql = []
    if not data_to_update: conn.close(); return False, "No changes were submitted."
    for key, value_from_app in data_to_update.items():
        if key not in allowed_fields: print(f"DB Warning: Field '{key}' not allowed in update_card_fields."); continue
        fields_to_update_sql.append(f"{key} = ?"); values_for_sql.append(value_from_app)
    if not fields_to_update_sql: conn.close(); return False, "No valid data fields for card update."
    fields_to_update_sql.append("last_updated = ?"); values_for_sql.append(datetime.datetime.now()); sql_set_clause = ", ".join(fields_to_update_sql); final_sql_values = tuple(values_for_sql + [card_id]); sql = f"UPDATE cards SET {sql_set_clause} WHERE id = ?"
    try:
        cursor.execute(sql, final_sql_values); conn.commit(); updated_rows = cursor.rowcount
        return (True, "Card updated successfully.") if updated_rows > 0 else (False, "Card not found or no data changed.")
    except sqlite3.IntegrityError as e: print(f"Integrity error update card {card_id}: {e}"); conn.rollback(); return False, f"Update failed (integrity): {e}"
    except sqlite3.Error as e: print(f"DB error update card {card_id}: {e}"); conn.rollback(); return False, f"DB error: {e}"
    finally: conn.close()

def add_sealed_product(product_name, set_name, product_type, language, is_collectors_item, quantity, buy_price, manual_market_price, sell_price, image_uri, location):
    conn = get_db_connection(); cursor = conn.cursor(); timestamp = datetime.datetime.now(); is_collectors_int = 1 if is_collectors_item else 0
    try: current_buy_price = float(buy_price)
    except (ValueError, TypeError): conn.close(); return None
    try:
        cursor.execute('''SELECT id, quantity FROM sealed_products WHERE product_name = ? AND set_name = ? AND product_type = ? AND language = ? AND location = ? AND is_collectors_item = ? AND buy_price = ?''', (product_name, set_name, product_type, language, location, is_collectors_int, current_buy_price))
        existing = cursor.fetchone()
        if existing: 
            prod_id, new_qty = existing['id'], existing['quantity'] + quantity
            cursor.execute('''UPDATE sealed_products SET quantity = ?, manual_market_price = ?, sell_price = ?, image_uri = ?, last_updated = ? WHERE id = ?''', (new_qty, manual_market_price, sell_price, image_uri, timestamp, prod_id))
        else: 
            cursor.execute('''INSERT INTO sealed_products (product_name, set_name, product_type, language, is_collectors_item, quantity, buy_price, manual_market_price, sell_price, image_uri, location, date_added, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (product_name, set_name, product_type, language, is_collectors_int, quantity, current_buy_price, manual_market_price, sell_price, image_uri, location, timestamp, timestamp))
            prod_id = cursor.lastrowid
        conn.commit(); return prod_id
    except sqlite3.IntegrityError as ie: print(f"DB IntegrityError add_sealed: {ie}"); conn.rollback(); return None
    except sqlite3.Error as e: print(f"DB error add_sealed: {e}"); conn.rollback(); return None
    finally: conn.close()

def get_all_sealed_products(): conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("SELECT * FROM sealed_products WHERE quantity > 0 ORDER BY product_name, set_name, location, buy_price"); prods = cursor.fetchall(); conn.close(); return prods

def get_sealed_product_by_id(product_id): conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("SELECT * FROM sealed_products WHERE id = ?", (product_id,)); prod = cursor.fetchone(); conn.close(); return prod

def update_sealed_product_quantity(product_id, quantity_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT quantity FROM sealed_products WHERE id = ?", (product_id,))
        result = cursor.fetchone()
        if not result:
            return False, "Sealed product not found."
        current_quantity = result['quantity']
        new_quantity = current_quantity + quantity_change
        if new_quantity < 0:
            return False, "Not enough quantity in stock to remove."
        cursor.execute("UPDATE sealed_products SET quantity = ?, last_updated = ? WHERE id = ?", 
                       (new_quantity, datetime.datetime.now(), product_id))
        conn.commit()
        return True, f"Sealed product quantity updated to {new_quantity}."
    except sqlite3.Error as e:
        print(f"DB error in update_sealed_product_quantity for ID {product_id}: {e}")
        if conn: conn.rollback()
        return False, f"Database error during quantity update: {e}"
    finally:
        if conn: conn.close()

def delete_sealed_product(product_id): conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("DELETE FROM sealed_products WHERE id = ?", (product_id,)); conn.commit(); deleted = cursor.rowcount > 0; conn.close(); return deleted

def update_sealed_product_fields(product_id, data_to_update_from_app):
    conn = get_db_connection(); cursor = conn.cursor(); allowed_fields_for_update = {'quantity', 'buy_price', 'manual_market_price', 'sell_price', 'location', 'image_uri', 'language', 'is_collectors_item'}; fields_to_set_in_sql = []; values_for_sql_query = []
    if not data_to_update_from_app: conn.close(); return False, "No changes were submitted."
    for field_key, new_value in data_to_update_from_app.items():
        if field_key not in allowed_fields_for_update: print(f"DB Warning: Field '{field_key}' not allowed for update."); continue
        current_sql_value = 1 if new_value else 0 if field_key == 'is_collectors_item' else new_value
        fields_to_set_in_sql.append(f"{field_key} = ?"); values_for_sql_query.append(current_sql_value)
    if not fields_to_set_in_sql: conn.close(); return False, "No valid data fields for update."
    fields_to_set_in_sql.append("last_updated = ?"); values_for_sql_query.append(datetime.datetime.now()); sql_set_clause = ", ".join(fields_to_set_in_sql); final_sql_values_tuple = tuple(values_for_sql_query + [product_id]); sql_query_string = f"UPDATE sealed_products SET {sql_set_clause} WHERE id = ?"
    try:
        cursor.execute(sql_query_string, final_sql_values_tuple); conn.commit(); updated_rows = cursor.rowcount
        return (True, "Sealed product updated successfully.") if updated_rows > 0 else (False, "Sealed product not found or data identical.")
    except sqlite3.IntegrityError as e: print(f"DB IntegrityError update sealed_product {product_id}: {e}"); conn.rollback(); return False, f"Update failed (integrity): {e}"
    except sqlite3.Error as e: print(f"DB error update sealed_product {product_id}: {e}"); conn.rollback(); return False, f"DB error: {e}"
    finally: conn.close()

def _update_inventory_item_quantity_with_cursor(cursor, item_type, item_id, quantity_change):
    table_name = 'cards' if item_type == 'single_card' else 'sealed_products'
    try:
        cursor.execute(f"SELECT quantity FROM {table_name} WHERE id = ?", (item_id,))
        result = cursor.fetchone()
        if not result: return False, f"{item_type.replace('_', ' ').capitalize()} not found."
        new_quantity = result['quantity'] + quantity_change
        if new_quantity < 0: return False, "Not enough stock to sell/remove."
        cursor.execute(f"UPDATE {table_name} SET quantity = ?, last_updated = ? WHERE id = ?", (new_quantity, datetime.datetime.now(), item_id))
        print(f"DB (cursor op): Updated {table_name} ID {item_id} quantity to {new_quantity}")
        return True, f"{item_type.replace('_', ' ').capitalize()} quantity updated."
    except sqlite3.Error as e: print(f"DB error in _update_inventory_item_quantity_with_cursor for {table_name} ID {item_id}: {e}"); return False, f"DB error during quantity update: {e}"

def record_multi_item_sale(sale_date_str, total_shipping_cost_str, overall_notes, items_data_from_app):
    conn = get_db_connection(); cursor = conn.cursor(); sale_event_id = None; total_event_profit_loss_calculated = 0.0
    try:
        sale_date_obj = datetime.datetime.strptime(sale_date_str, '%Y-%m-%d').date()
        total_shipping_cost = float(total_shipping_cost_str if total_shipping_cost_str and total_shipping_cost_str.strip() != '' else 0.0)
    except ValueError as e: print(f"DB Error: Invalid date/shipping format: {e}"); conn.close(); return None, f"Invalid date/shipping: {e}"
    try:
        cursor.execute('''INSERT INTO sale_events (sale_date, total_shipping_cost, notes) VALUES (?, ?, ?)''', (sale_date_obj, total_shipping_cost, overall_notes))
        sale_event_id = cursor.lastrowid; print(f"DB: Created sale_event ID {sale_event_id}")
        for item_data in items_data_from_app:
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
            original_item_db_row = get_item_by_id(item_type, inventory_item_id_int) 
            if not original_item_db_row: raise ValueError(f"Inv item not found: {item_type} id {inventory_item_id_int}")
            if quantity_sold > original_item_db_row['quantity']: name_key = 'name' if item_type == 'single_card' else 'product_name'; raise ValueError(f"Not enough stock for {original_item_db_row[name_key]}. Have: {original_item_db_row['quantity']}")
            buy_price_per_item = float(original_item_db_row['buy_price']); item_profit_loss = (sell_price_per_item - buy_price_per_item) * quantity_sold; total_event_profit_loss_calculated += item_profit_loss
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
            cursor.execute('''INSERT INTO sale_items (sale_event_id, inventory_item_id, item_type, original_item_name, original_item_details, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (sale_event_id, inventory_item_id_int, item_type, original_item_name_snapshot, original_item_details_snapshot, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss))
            success_inv_update, msg_inv_update = _update_inventory_item_quantity_with_cursor(cursor, item_type, inventory_item_id_int, -quantity_sold)
            if not success_inv_update: raise Exception(f"Inv update failed: {msg_inv_update}")
        final_event_profit_loss = total_event_profit_loss_calculated - total_shipping_cost
        cursor.execute('''UPDATE sale_events SET total_profit_loss = ? WHERE id = ?''', (final_event_profit_loss, sale_event_id))
        conn.commit(); print(f"DB: Committed sale_event ID {sale_event_id}")
        return sale_event_id, "Sale event recorded successfully."
    except Exception as e: print(f"DB Error in record_multi_item_sale: {e}"); conn.rollback(); return None, str(e)
    finally: conn.close()

def get_all_sale_events_with_items():
    conn = get_db_connection(); cursor = conn.cursor(); sale_events_processed = []
    try:
        cursor.execute('''SELECT id, sale_date, total_shipping_cost, notes, total_profit_loss, date_recorded FROM sale_events ORDER BY sale_date DESC, id DESC''')
        events = cursor.fetchall()
        for event_row in events:
            event_dict = dict(event_row)
            cursor.execute('''SELECT id, sale_event_id, inventory_item_id, item_type, original_item_name, original_item_details, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss FROM sale_items WHERE sale_event_id = ? ORDER BY id ASC''', (event_dict['id'],))
            items_raw = cursor.fetchall(); event_dict['items'] = [dict(item_row) for item_row in items_raw]
            # Ensure date types are correctly handled if they are strings (though PARSE_DECLTYPES should handle this)
            if isinstance(event_dict.get('sale_date'), str): event_dict['sale_date'] = datetime.datetime.strptime(event_dict['sale_date'], '%Y-%m-%d').date()
            if isinstance(event_dict.get('date_recorded'), str): event_dict['date_recorded'] = datetime.datetime.fromisoformat(event_dict['date_recorded'])
            sale_events_processed.append(event_dict)
    except sqlite3.Error as e: print(f"DB Error get_all_sale_events: {e}")
    finally: conn.close()
    return sale_events_processed

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    print("Database initialization complete.")