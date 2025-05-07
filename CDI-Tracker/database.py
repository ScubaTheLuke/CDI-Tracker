import sqlite3
import datetime

DATABASE_NAME = 'cdi.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            is_foil INTEGER NOT NULL,
            market_price_usd REAL,
            foil_market_price_usd REAL,
            image_uri TEXT,
            added_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sell_price REAL,
            location TEXT,
            UNIQUE(set_code, collector_number, is_foil, location)
        )
    ''')
    
    columns_to_add = {
        'sell_price': 'REAL',
        'location': 'TEXT'
    }
    
    cursor.execute("PRAGMA table_info(cards)")
    existing_columns = [row['name'] for row in cursor.fetchall()]

    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(f'ALTER TABLE cards ADD COLUMN {col_name} {col_type}')
                print(f"Added {col_name} column to cards table.")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    pass 
                else:
                    print(f"Error adding column {col_name}: {e}")
                    # raise # Optionally re-raise if it's an unexpected error
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT NOT NULL,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            is_foil INTEGER NOT NULL,
            quantity_sold INTEGER NOT NULL,
            buy_price_per_item REAL NOT NULL,
            sell_price_per_item REAL NOT NULL,
            profit_loss REAL NOT NULL,
            sale_date DATETIME NOT NULL,
            inventory_card_id INTEGER, 
            FOREIGN KEY (inventory_card_id) REFERENCES cards(id) ON DELETE SET NULL
        )
    ''')

    conn.commit()
    conn.close()

def add_card(set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, quantity FROM cards 
            WHERE set_code = ? AND collector_number = ? AND is_foil = ? AND location = ?
        ''', (set_code, collector_number, 1 if is_foil else 0, location))
        existing_card = cursor.fetchone()

        if existing_card:
            if existing_card['quantity'] == 0:
                cursor.execute('''
                    UPDATE cards 
                    SET name = ?, quantity = ?, buy_price = ?, 
                        market_price_usd = ?, foil_market_price_usd = ?, image_uri = ?, 
                        sell_price = ?, added_timestamp = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (name, quantity, buy_price, market_price_usd, foil_market_price_usd, 
                      image_uri, sell_price, existing_card['id']))
                conn.commit()
                # print(f"Restocked card ID {existing_card['id']} at location '{location}'.") # Optional debug print
                return True
            else:
                # Card already exists with quantity > 0, this is a true duplicate add attempt for active stock
                # print(f"Card {set_code}-{collector_number} {'(Foil)' if is_foil else ''} at location '{location}' already exists with quantity > 0.") # Optional debug print
                return False 
        else:
            # Card does not exist, proceed with insert
            cursor.execute('''
                INSERT INTO cards (set_code, collector_number, name, quantity, buy_price, is_foil, 
                                 market_price_usd, foil_market_price_usd, image_uri, sell_price, location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (set_code, collector_number, name, quantity, buy_price, 1 if is_foil else 0, 
                  market_price_usd, foil_market_price_usd, image_uri, sell_price, location))
            conn.commit()
            return True
    except sqlite3.Error as e: # Catch any SQLite error during the process
        print(f"Database error in add_card for {set_code}-{collector_number} at '{location}': {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_all_cards():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, set_code, collector_number, name, quantity, buy_price, is_foil, 
               market_price_usd, foil_market_price_usd, image_uri, added_timestamp, sell_price, location
        FROM cards
        WHERE quantity > 0
        ORDER BY name, set_code, collector_number
    ''')
    cards = cursor.fetchall()
    conn.close()
    return cards

def update_card_fields(card_id, new_quantity, new_buy_price, new_sell_price, new_location):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []

    if new_quantity is not None:
        updates.append("quantity = ?")
        params.append(new_quantity)
    if new_buy_price is not None:
        updates.append("buy_price = ?")
        params.append(new_buy_price)
    if new_location is not None: # Location can be empty string
        updates.append("location = ?")
        params.append(new_location)
    
    # sell_price (asking price) can be set to NULL if user clears it
    updates.append("sell_price = ?")
    params.append(new_sell_price) 
    
    if not updates:
        conn.close()
        return True 

    query = f"UPDATE cards SET {', '.join(updates)} WHERE id = ?"
    params.append(card_id)
    
    try:
        cursor.execute(query, tuple(params))
        conn.commit()
    except sqlite3.IntegrityError as e:
        # This might happen if updating location causes a duplicate with the new UNIQUE constraint
        print(f"IntegrityError updating card {card_id}: {e}")
        conn.close()
        return False
    finally:
        if conn: conn.close()
    return True


def update_card_market_data(card_id, market_price_usd, foil_market_price_usd, image_uri):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE cards
        SET market_price_usd = ?, foil_market_price_usd = ?, image_uri = ?
        WHERE id = ?
    ''', (market_price_usd, foil_market_price_usd, image_uri, card_id))
    conn.commit()
    conn.close()

def delete_card(card_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Before deleting a card, consider implications if it's linked in sales table
    # For now, FOREIGN KEY (inventory_card_id) REFERENCES cards(id) ON DELETE SET NULL handles this
    cursor.execute('DELETE FROM cards WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()

def get_card_by_id(card_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, set_code, collector_number, name, quantity, buy_price, is_foil, 
               market_price_usd, foil_market_price_usd, image_uri, added_timestamp, sell_price, location
        FROM cards WHERE id = ?
    ''', (card_id,))
    card = cursor.fetchone()
    conn.close()
    return card

def decrease_card_quantity(card_id, quantity_to_decrease):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cards SET quantity = quantity - ? WHERE id = ?", (quantity_to_decrease, card_id))
    conn.commit()
    conn.close()

def add_sale_record(card_name, set_code, collector_number, is_foil, quantity_sold, buy_price_per_item, sell_price_per_item, sale_date, inventory_card_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    profit_loss = (sell_price_per_item - buy_price_per_item) * quantity_sold
    try:
        cursor.execute('''
            INSERT INTO sales (card_name, set_code, collector_number, is_foil, quantity_sold, buy_price_per_item, sell_price_per_item, profit_loss, sale_date, inventory_card_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (card_name, set_code, collector_number, 1 if is_foil else 0, quantity_sold, buy_price_per_item, sell_price_per_item, profit_loss, sale_date, inventory_card_id))
        conn.commit()
    except Exception as e:
        print(f"Error adding sale record: {e}")
        conn.rollback() # Rollback on error
        return False
    finally:
        conn.close()
    return True

def get_all_sales():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, card_name, set_code, collector_number, is_foil, quantity_sold, 
               buy_price_per_item, sell_price_per_item, profit_loss, sale_date, inventory_card_id
        FROM sales
        ORDER BY sale_date DESC
    ''')
    sales = cursor.fetchall()
    conn.close()
    return sales