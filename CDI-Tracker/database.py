import psycopg2
import psycopg2.extras
import datetime
import os
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
    cursor.execute("DROP TABLE IF EXISTS sales")

    print("Attempting to create shipping_supply_presets table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shipping_supply_presets (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    print("shipping_supply_presets table creation attempted.")

    print("Attempting to create shipping_preset_items table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shipping_preset_items (
            id SERIAL PRIMARY KEY,
            preset_id INTEGER NOT NULL,
            supply_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (preset_id) REFERENCES shipping_supply_presets (id) ON DELETE CASCADE,
            FOREIGN KEY (supply_id) REFERENCES shipping_supplies_inventory (id) ON DELETE CASCADE,
            UNIQUE(preset_id, supply_id) -- A supply can only be in a preset once
        );
    ''')
    print("shipping_preset_items table creation attempted.")


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
            condition TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scryfall_id TEXT,
            UNIQUE(set_code, collector_number, is_foil, location, rarity, language, buy_price, condition)
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
        total_shipping_cost REAL DEFAULT 0.0, -- Your postage cost + supplies cost for the sale
        notes TEXT,
        total_profit_loss REAL,
        date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        customer_shipping_charge REAL DEFAULT 0.0, -- What customer paid for shipping
        platform_fee REAL DEFAULT 0.0,           -- Platform fees for the sale
        total_supplies_cost_for_sale REAL DEFAULT 0.0 -- NEW: Cost of shipping supplies used for this specific sale
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

    # NEW TABLE: shipping_supplies_inventory
    print("Attempting to create shipping_supplies_inventory table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shipping_supplies_inventory (
            id SERIAL PRIMARY KEY,
            supply_name TEXT NOT NULL,
            description TEXT,
            unit_of_measure TEXT NOT NULL DEFAULT 'unit',
            purchase_date DATE NOT NULL,
            quantity_on_hand INTEGER NOT NULL,
            cost_per_unit REAL NOT NULL,
            location TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(supply_name, description, unit_of_measure, cost_per_unit, location) -- Removed purchase_date from UNIQUE
        );
    ''')
    print("shipping_supplies_inventory table creation attempted.")

    # NEW TABLE: sale_event_shipping_supplies
    print("Attempting to create sale_event_shipping_supplies table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_event_shipping_supplies (
            id SERIAL PRIMARY KEY,
            sale_event_id INTEGER NOT NULL,
            supply_id INTEGER NOT NULL,
            quantity_used INTEGER NOT NULL,
            cost_per_unit_snapshot REAL NOT NULL, -- Snapshot cost at time of sale
            supply_name_snapshot TEXT,
            supply_description_snapshot TEXT,
            FOREIGN KEY (sale_event_id) REFERENCES sale_events (id) ON DELETE CASCADE,
            FOREIGN KEY (supply_id) REFERENCES shipping_supplies_inventory (id) ON DELETE RESTRICT
        );
    ''')
    print("sale_event_shipping_supplies table creation attempted.")


    # This block fixes the constraint on EXISTING databases.
    try:
        print("Checking for old unique constraint on 'cards' table...")
        # Check if the OLD constraint exists by its specific name from the error log
        cursor.execute("""
            SELECT 1 FROM pg_constraint WHERE conname = 'cards_set_code_collector_number_is_foil_location_rarity_lan_key';
        """)
        if cursor.fetchone():
            print("Dropping old unique constraint...")
            cursor.execute("ALTER TABLE cards DROP CONSTRAINT cards_set_code_collector_number_is_foil_location_rarity_lan_key;")
            print("Old constraint dropped.")
        else:
            print("Old constraint not found, skipping drop.")

        # Check if the NEW constraint exists before trying to add it
        print("Checking for new unique constraint on 'cards' table...")
        cursor.execute("""
            SELECT 1 FROM pg_constraint WHERE conname = 'cards_unique_attributes_with_condition_key';
        """)
        if not cursor.fetchone():
            print("Adding new unique constraint with condition...")
            cursor.execute("""
                ALTER TABLE cards ADD CONSTRAINT cards_unique_attributes_with_condition_key
                UNIQUE (set_code, collector_number, is_foil, location, rarity, language, buy_price, condition);
            """)
            print("New constraint added.")
        else:
            print("New constraint already exists.")

        # --- Handle unique constraint for shipping_supplies_inventory ---
        print("Checking and updating unique constraint on 'shipping_supplies_inventory' table...")
        # A bit more complex for existing tables, you'd usually drop the old one and add the new one.
        # This checks for a constraint matching the OLD signature (with purchase_date)
        # and attempts to remove it if found.
        # Then, it attempts to add the NEW one (without purchase_date).
        cursor.execute("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'shipping_supplies_inventory'::regclass AND contype = 'u'
            AND conkey = ARRAY(
                SELECT attnum FROM pg_attribute
                WHERE attrelid = 'shipping_supplies_inventory'::regclass
                AND attname IN ('supply_name', 'description', 'unit_of_measure', 'purchase_date', 'cost_per_unit', 'location')
                ORDER BY attnum
            );
        """)
        old_ssi_constraint = cursor.fetchone()
        if old_ssi_constraint:
            print(f"Dropping old shipping_supplies_inventory unique constraint: {old_ssi_constraint[0]}...")
            cursor.execute(f"ALTER TABLE shipping_supplies_inventory DROP CONSTRAINT {old_ssi_constraint[0]};")
            print("Old shipping_supplies_inventory constraint dropped.")
        else:
            print("Old shipping_supplies_inventory unique constraint (with purchase_date) not found, skipping drop.")

        # Now, try to add the new one (without purchase_date) if it doesn't already exist by its desired key columns
        cursor.execute("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'shipping_supplies_inventory'::regclass AND contype = 'u'
            AND conkey = ARRAY(
                SELECT attnum FROM pg_attribute
                WHERE attrelid = 'shipping_supplies_inventory'::regclass
                AND attname IN ('supply_name', 'description', 'unit_of_measure', 'cost_per_unit', 'location')
                ORDER BY attnum
            );
        """)
        new_ssi_constraint_exists = cursor.fetchone()
        if not new_ssi_constraint_exists:
            print("Adding new shipping_supplies_inventory unique constraint (without purchase_date)...")
            cursor.execute("""
                ALTER TABLE shipping_supplies_inventory ADD CONSTRAINT shipping_supplies_unique_attrs
                UNIQUE (supply_name, description, unit_of_measure, cost_per_unit, location);
            """)
            print("New shipping_supplies_inventory constraint added.")
        else:
            print(f"New shipping_supplies_inventory unique constraint ({new_ssi_constraint_exists[0]}) already exists.")

        conn.commit()
    except psycopg2.Error as e:
        print(f"Error during constraint update: {e}")
        conn.rollback()

    print("Checking and adding columns if they don't exist...")
    _check_and_add_column(cursor, 'cards', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'cards', 'scryfall_id', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'rarity', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'language', 'TEXT')
    _check_and_add_column(cursor, 'cards', 'condition', 'TEXT')
    _check_and_add_column(cursor, 'sealed_products', 'last_updated', 'TIMESTAMP')
    _check_and_add_column(cursor, 'sale_events', 'total_supplies_cost_for_sale', 'REAL DEFAULT 0.0')
    _check_and_add_column(cursor, 'sale_events', 'customer_shipping_charge', 'REAL DEFAULT 0.0')
    _check_and_add_column(cursor, 'sale_events', 'platform_fee', 'REAL DEFAULT 0.0')
    print("All column checks attempted.")

    # NEW: Check and add columns for shipping_supplies_inventory if needed (e.g., if schema evolves)
    _check_and_add_column(cursor, 'shipping_supplies_inventory', 'description', 'TEXT')
    _check_and_add_column(cursor, 'shipping_supplies_inventory', 'unit_of_measure', 'TEXT DEFAULT \'unit\'')
    _check_and_add_column(cursor, 'shipping_supplies_inventory', 'location', 'TEXT')


    print("Attempting to commit final changes...")
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

def add_card(set_code, collector_number, name, quantity, buy_price, is_foil, market_price_usd, foil_market_price_usd, image_uri, sell_price, location, scryfall_id, rarity, language, condition):
    """
    Adds a new card to the inventory or updates the quantity if an identical card is found.
    An identical card is one that matches on all unique constraint fields.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    timestamp = datetime.datetime.now()
    is_foil_db_val = 1 if is_foil else 0
    card_id = None

    try:
        # Check if an identical card already exists
        cursor.execute(
            """SELECT id, quantity FROM cards
               WHERE set_code = %s AND collector_number = %s AND is_foil = %s AND location = %s
               AND rarity = %s AND language = %s AND buy_price = %s AND condition = %s""",
            (set_code, collector_number, is_foil_db_val, location, rarity, language, buy_price, condition)
        )
        existing_card = cursor.fetchone()

        if existing_card:
            # Card exists, so update its quantity
            new_quantity = existing_card['quantity'] + quantity
            cursor.execute(
                """UPDATE cards
                   SET quantity = %s, last_updated = %s,
                       market_price_usd = %s, foil_market_price_usd = %s, image_uri = %s,
                       sell_price = %s, name = %s, scryfall_id = %s
                   WHERE id = %s""",
                (new_quantity, timestamp, market_price_usd, foil_market_price_usd, image_uri,
                 sell_price, name, scryfall_id, existing_card['id'])
            )
            card_id = existing_card['id']
            print(f"SUCCESS (Updated): Added {quantity} x {name} ({set_code.upper()}) [{condition}] to existing stack.")
        else:
            # Card does not exist, so insert a new row
            cursor.execute(
                """INSERT INTO cards (set_code, collector_number, name, quantity, buy_price, is_foil,
                                     market_price_usd, foil_market_price_usd, image_uri, sell_price,
                                     location, date_added, last_updated, scryfall_id, rarity, language, condition)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (set_code, collector_number, name, quantity, buy_price, is_foil_db_val,
                 market_price_usd, foil_market_price_usd, image_uri, sell_price,
                 location, timestamp, timestamp, scryfall_id, rarity, language, condition)
            )
            card_id = cursor.fetchone()['id']
            print(f"SUCCESS (Inserted): Added {quantity} x {name} ({set_code.upper()}) [{condition}] to inventory.")

        conn.commit()
        return card_id

    except psycopg2.Error as e:
        print(f"DB Error in add_card for {name}: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def add_shipping_supply_batch(supply_name, description, unit_of_measure, purchase_date_str, quantity, total_purchase_amount, location):
    """
    Adds a new batch of shipping supplies to inventory or updates an existing identical batch.
    Calculates cost_per_unit from total_purchase_amount and quantity.
    An identical batch matches on name, description, unit_of_measure, cost_per_unit, and location.
    Automatically adds an expense entry to the financial ledger for the total purchase amount.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    timestamp = datetime.datetime.now()
    supply_batch_id = None

    try:
        purchase_date_obj = datetime.datetime.strptime(purchase_date_str, '%Y-%m-%d').date()

        calculated_cost_per_unit = round(float(total_purchase_amount) / quantity, 2) if quantity > 0 else 0.0

        # Check if an identical batch already exists (now using calculated_cost_per_unit and WITHOUT purchase_date)
        cursor.execute(
            """SELECT id, quantity_on_hand FROM shipping_supplies_inventory
               WHERE supply_name = %s AND description = %s AND unit_of_measure = %s
               AND cost_per_unit = %s AND location = %s""",
            (supply_name, description, unit_of_measure, calculated_cost_per_unit, location)
        )
        existing_batch = cursor.fetchone()

        if existing_batch:
            # Batch exists, so update its quantity
            new_quantity = existing_batch['quantity_on_hand'] + quantity
            cursor.execute(
                """UPDATE shipping_supplies_inventory
                   SET quantity_on_hand = %s, last_updated = %s
                   WHERE id = %s""",
                (new_quantity, timestamp, existing_batch['id'])
            )
            supply_batch_id = existing_batch['id']
            print(f"SUCCESS (Updated): Added {quantity} x {supply_name} ({description}) to existing batch. New Qty: {new_quantity}")
        else:
            # Batch does not exist, so insert a new row
            cursor.execute(
                """INSERT INTO shipping_supplies_inventory (supply_name, description, unit_of_measure, purchase_date,
                                                             quantity_on_hand, cost_per_unit, location, date_added, last_updated)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (supply_name, description, unit_of_measure, purchase_date_obj,
                 quantity, calculated_cost_per_unit, location, timestamp, timestamp)
            )
            supply_batch_id = cursor.fetchone()['id']
            print(f"SUCCESS (Inserted): Added new batch of {quantity} x {supply_name} ({description}) at {calculated_cost_per_unit} per unit.")

        # Automatic ledger entry for the purchase
        if supply_batch_id:
            entry_description = f"Purchase: {supply_name} ({description}) - {quantity} units"
            entry_category = "Shipping Supplies"
            entry_type = "expense"
            entry_amount = float(total_purchase_amount)
            notes = f"Auto-generated from adding supply batch ID {supply_batch_id}"

            cursor.execute("""
                INSERT INTO financial_entries (entry_date, description, category, entry_type, amount, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (purchase_date_obj, entry_description, entry_category, entry_type, entry_amount, notes))
            print(f"SUCCESS: Added financial entry for shipping supply purchase: {entry_description} - ${entry_amount}")


        conn.commit()
        return supply_batch_id

    except psycopg2.IntegrityError as ie:
        print(f"DB IntegrityError in add_shipping_supply_batch for {supply_name}: {ie}")
        if conn: conn.rollback()
        return None
    except psycopg2.Error as e:
        print(f"DB Error in add_shipping_supply_batch for {supply_name}: {e}")
        if conn: conn.rollback()
        return None
    except ValueError as e:
        print(f"Value Error in add_shipping_supply_batch (e.g., date parsing or quantity/total_purchase_amount): {e}")
        if conn: conn.rollback()
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def add_shipping_supply_preset(preset_name, preset_description, items):
    """
    Adds a new shipping supply preset.
    :param preset_name: Name of the preset.
    :param preset_description: Description of the preset.
    :param items: A list of dictionaries, each with 'supply_id' and 'quantity'.
    :return: The ID of the new preset, or None if failed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    preset_id = None
    try:
        cursor.execute(
            "INSERT INTO shipping_supply_presets (name, description) VALUES (%s, %s) RETURNING id",
            (preset_name, preset_description)
        )
        preset_id = cursor.fetchone()[0]

        for item in items:
            cursor.execute(
                "INSERT INTO shipping_preset_items (preset_id, supply_id, quantity) VALUES (%s, %s, %s)",
                (preset_id, item['supply_id'], item['quantity'])
            )
        conn.commit()
        print(f"SUCCESS: Added shipping supply preset '{preset_name}' (ID: {preset_id}).")
        return preset_id
    except psycopg2.Error as e:
        print(f"DB Error in add_shipping_supply_preset for {preset_name}: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_all_shipping_supply_presets():
    """
    Retrieves all shipping supply presets with their associated items.
    :return: A list of preset dictionaries.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    presets = []
    try:
        cursor.execute("SELECT id, name, description FROM shipping_supply_presets ORDER BY name ASC")
        raw_presets = cursor.fetchall()

        for preset_row in raw_presets:
            preset_dict = dict(preset_row)
            cursor.execute(
                """SELECT
                    spi.supply_id,
                    spi.quantity,
                    ssi.supply_name,
                    ssi.description,
                    ssi.unit_of_measure,
                    ssi.cost_per_unit,
                    ssi.quantity_on_hand as current_stock
                FROM shipping_preset_items spi
                JOIN shipping_supplies_inventory ssi ON spi.supply_id = ssi.id
                WHERE spi.preset_id = %s
                ORDER BY ssi.supply_name ASC""",
                (preset_dict['id'],)
            )
            preset_dict['items'] = [dict(item) for item in cursor.fetchall()]
            presets.append(preset_dict)
    except psycopg2.Error as e:
        print(f"DB Error in get_all_shipping_supply_presets: {e}")
        return [] # Ensure an empty list is returned on error
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return presets

def delete_shipping_supply_preset(preset_id):
    """
    Deletes a shipping supply preset and its associated items.
    :param preset_id: The ID of the preset to delete.
    :return: True if deleted, False otherwise.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    deleted = False
    try:
        cursor.execute("DELETE FROM shipping_preset_items WHERE preset_id = %s", (preset_id,))
        cursor.execute("DELETE FROM shipping_supply_presets WHERE id = %s", (preset_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
    except psycopg2.Error as e:
        print(f"DB Error in delete_shipping_supply_preset for ID {preset_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return deleted


def get_all_shipping_supplies():
    """Retrieves all shipping supply batches with quantity > 0, ordered by name and purchase date."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    supplies = []
    try:
        cursor.execute("SELECT * FROM shipping_supplies_inventory WHERE quantity_on_hand > 0 ORDER BY supply_name, description, purchase_date ASC")
        supplies = cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB error in get_all_shipping_supplies: {e}")
    finally:
        cursor.close()
        conn.close()
    return supplies

def get_shipping_supply_by_id(supply_id):
    """Retrieves a single shipping supply batch by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    supply = None
    try:
        cursor.execute("SELECT * FROM shipping_supplies_inventory WHERE id = %s", (supply_id,))
        supply = cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB error in get_shipping_supply_by_id for ID {supply_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return supply

def delete_shipping_supply(supply_id):
    """Deletes a shipping supply batch by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    deleted = False
    try:
        cursor.execute("DELETE FROM shipping_supplies_inventory WHERE id = %s", (supply_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
    except psycopg2.Error as e:
        print(f"DB error in delete_shipping_supply for ID {supply_id}: {e}")
        if conn: conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return deleted

def update_shipping_supply_fields(supply_id, data_to_update_from_app):
    """
    Updates fields of a specific shipping supply batch.
    Expected fields: quantity_on_hand, cost_per_unit, location, description, unit_of_measure.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    allowed_fields_for_update = {'quantity_on_hand', 'cost_per_unit', 'location', 'description', 'unit_of_measure'}
    fields_to_set_in_sql = []
    values_for_sql_query = []

    if not data_to_update_from_app:
        conn.close()
        return False, "No changes were submitted."

    for field_key, new_value in data_to_update_from_app.items():
        if field_key not in allowed_fields_for_update:
            print(f"DB Warning: Field '{field_key}' not allowed for update_shipping_supply_fields.")
            continue

        fields_to_set_in_sql.append(f"{field_key} = %s")
        values_for_sql_query.append(new_value)

    if not fields_to_set_in_sql:
        conn.close()
        return False, "No valid data fields for shipping supply update."

    fields_to_set_in_sql.append("last_updated = %s")
    values_for_sql_query.append(datetime.datetime.now())
    sql_set_clause = ", ".join(fields_to_set_in_sql)
    final_sql_values_tuple = tuple(values_for_sql_query + [supply_id])
    sql_query_string = f"UPDATE shipping_supplies_inventory SET {sql_set_clause} WHERE id = %s"

    try:
        cursor.execute(sql_query_string, final_sql_values_tuple)
        conn.commit()
        updated_rows = cursor.rowcount
        return (True, "Shipping supply batch updated successfully.") if updated_rows > 0 else (False, "Shipping supply batch not found or data identical.")
    except psycopg2.IntegrityError as e:
        print(f"DB IntegrityError update shipping_supply {supply_id}: {e}")
        if conn: conn.rollback()
        return False, f"Update failed (integrity): {e}"
    except psycopg2.Error as e:
        print(f"DB error update shipping_supply {supply_id}: {e}")
        if conn: conn.rollback()
        return False, f"DB error: {e}"
    finally:
        cursor.close()
        conn.close()

def mass_update_inventory_items(filters, update_data):
    """
    Performs a mass update on inventory items (cards, sealed products, or shipping supplies)
    based on provided filters and update data.

    :param filters: A dictionary of filter criteria (e.g., {'item_type': 'single_card', 'location': 'Box 1'}).
                    Expected keys: item_type, filter_text, filter_location, filter_set, filter_foil,
                                   filter_rarity, filter_card_lang, filter_condition, filter_collector,
                                   filter_sealed_lang.
    :param update_data: A dictionary of fields to update and their new values
                        (e.g., {'location': 'New Box', 'buy_price_change_percentage': 10}).
                        Special keys: 'buy_price_change_percentage', 'manual_market_price_change_percentage'.
    :return: Tuple (success_boolean, message, count_updated)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    updated_count = 0
    messages = []
    
    item_type = filters.get('item_type', 'all')

    tables_to_update = []
    if item_type == 'all':
        tables_to_update = ['cards', 'sealed_products', 'shipping_supplies_inventory']
    elif item_type == 'single_card':
        tables_to_update = ['cards']
    elif item_type == 'sealed_product':
        tables_to_update = ['sealed_products']
    elif item_type == 'shipping_supply':
        tables_to_update = ['shipping_supplies_inventory']
    else:
        return False, "Invalid item type specified for mass update.", 0

    try:
        for table_name in tables_to_update:
            where_clauses = []
            where_values = []
            set_clauses = []
            set_values = []

            # --- Construct WHERE clauses based on filters ---
            if filters.get('filter_text'):
                search_term = f"%{filters['filter_text']}%"
                if table_name == 'cards':
                    where_clauses.append("(LOWER(name) LIKE %s OR LOWER(set_code) LIKE %s OR LOWER(location) LIKE %s OR LOWER(collector_number) LIKE %s OR LOWER(rarity) LIKE %s OR LOWER(language) LIKE %s)")
                    where_values.extend([search_term, search_term, search_term, search_term, search_term, search_term])
                elif table_name == 'sealed_products':
                    where_clauses.append("(LOWER(product_name) LIKE %s OR LOWER(set_name) LIKE %s OR LOWER(location) LIKE %s OR LOWER(product_type) LIKE %s OR LOWER(language) LIKE %s)")
                    where_values.extend([search_term, search_term, search_term, search_term, search_term])
                elif table_name == 'shipping_supplies_inventory':
                    where_clauses.append("(LOWER(supply_name) LIKE %s OR LOWER(description) LIKE %s OR LOWER(location) LIKE %s OR LOWER(unit_of_measure) LIKE %s)")
                    where_values.extend([search_term, search_term, search_term, search_term])

            if filters.get('filter_location') and filters['filter_location'] != 'all':
                if table_name in ['cards', 'sealed_products', 'shipping_supplies_inventory']:
                    where_clauses.append("LOWER(location) = LOWER(%s)")
                    where_values.append(filters['filter_location'])

            # Type-specific filters (only apply if the table matches the filter context)
            if table_name == 'cards':
                if filters.get('filter_set') and filters['filter_set'] != 'all':
                    # CORRECTED LINE: Only reference set_code for the 'cards' table
                    where_clauses.append("LOWER(set_code) = LOWER(%s)")
                    where_values.append(filters['filter_set'])
                if filters.get('filter_foil') != 'all':
                    is_foil_val = 1 if filters['filter_foil'] == 'yes' else 0
                    where_clauses.append("is_foil = %s")
                    where_values.append(is_foil_val)
                if filters.get('filter_rarity') and filters['filter_rarity'] != 'all':
                    where_clauses.append("LOWER(rarity) = LOWER(%s)")
                    where_values.append(filters['filter_rarity'])
                if filters.get('filter_card_lang') and filters['filter_card_lang'] != 'all':
                    where_clauses.append("LOWER(language) = LOWER(%s)")
                    where_values.append(filters['filter_card_lang'])
                if filters.get('filter_condition') and filters['filter_condition'] != 'all':
                    where_clauses.append("LOWER(condition) = LOWER(%s)")
                    where_values.append(filters['filter_condition'])
            
            if table_name == 'sealed_products':
                if filters.get('filter_set') and filters['filter_set'] != 'all':
                    where_clauses.append("LOWER(set_name) = LOWER(%s)")
                    where_values.append(filters['filter_set'])
                if filters.get('filter_collector') != 'all':
                    is_collector_val = 1 if filters['filter_collector'] == 'yes' else 0
                    where_clauses.append("is_collectors_item = %s")
                    where_values.append(is_collector_val)
                if filters.get('filter_sealed_lang') and filters['filter_sealed_lang'] != 'all':
                    where_clauses.append("LOWER(language) = LOWER(%s)")
                    where_values.append(filters['filter_sealed_lang'])

            # No specific filter for shipping supplies beyond general text and location, as per current design.

            # Ensure we only update items that have a quantity > 0
            if table_name in ['cards', 'sealed_products']:
                 where_clauses.append("quantity > 0")
            elif table_name == 'shipping_supplies_inventory':
                 where_clauses.append("quantity_on_hand > 0")

            # --- Construct SET clauses based on update_data ---
            for field, value in update_data.items():
                if field == 'location':
                    set_clauses.append("location = %s")
                    set_values.append(value)
                elif field == 'sell_price': # Applicable to cards and sealed
                    if table_name in ['cards', 'sealed_products']:
                        set_clauses.append("sell_price = %s")
                        set_values.append(value)
                elif field == 'condition': # Applicable to cards only
                    if table_name == 'cards':
                        set_clauses.append("condition = %s")
                        set_values.append(value)
                elif field == 'buy_price_change_percentage': # Applicable to cards and sealed
                    if table_name in ['cards', 'sealed_products']:
                        # Ensure buy_price is not NULL to avoid errors
                        set_clauses.append("buy_price = COALESCE(buy_price, 0) * (1 + %s / 100.0)")
                        set_values.append(value)
                elif field == 'manual_market_price_change_percentage': # Applicable to sealed only
                    if table_name == 'sealed_products':
                        # Ensure manual_market_price is not NULL
                        set_clauses.append("manual_market_price = COALESCE(manual_market_price, 0) * (1 + %s / 100.0)")
                        set_values.append(value)
                elif field == 'cost_per_unit_change_percentage': # Applicable to shipping supplies only
                    if table_name == 'shipping_supplies_inventory':
                         set_clauses.append("cost_per_unit = COALESCE(cost_per_unit, 0) * (1 + %s / 100.0)")
                         set_values.append(value)
                elif field == 'unit_of_measure': # Applicable to shipping supplies only
                    if table_name == 'shipping_supplies_inventory':
                        set_clauses.append("unit_of_measure = %s")
                        set_values.append(value)
                elif field == 'description': # Applicable to shipping supplies only
                    if table_name == 'shipping_supplies_inventory':
                        set_clauses.append("description = %s")
                        set_values.append(value)
                # Add more fields as needed

            if not set_clauses: # If no valid fields to update for this table, skip.
                continue
            
            # Always update last_updated timestamp
            set_clauses.append("last_updated = CURRENT_TIMESTAMP")

            sql_query = f"UPDATE {table_name} SET {', '.join(set_clauses)}"
            if where_clauses:
                sql_query += f" WHERE {' AND '.join(where_clauses)}"
            
            cursor.execute(sql_query, set_values + where_values)
            rows_affected = cursor.rowcount
            updated_count += rows_affected
            messages.append(f"Updated {rows_affected} items in {table_name} table.")

        conn.commit()
        return True, "Mass update completed. " + " ".join(messages), updated_count

    except psycopg2.Error as e:
        print(f"DB Error during mass update: {e}")
        if conn:
            conn.rollback()
        return False, f"Database error during mass update: {e}", 0
    except Exception as e:
        print(f"Unexpected error during mass update: {e}")
        if conn:
            conn.rollback()
        return False, f"An unexpected error occurred during mass update: {e}", 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def delete_sale_event(sale_event_id):
    """
    Deletes a sale event and its associated items.
    Attempts to add the sold quantities of inventory items (cards/sealed) and
    used shipping supplies back to their respective inventories.
    All operations are performed in a single transaction.
    Returns a tuple: (success_boolean, message_string)
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) # Use DictCursor for easier item access

    try:
        # Start a transaction (implicitly handled by psycopg2, committed or rolled back explicitly)

        # Check if the sale event itself exists before proceeding with detailed operations
        cursor.execute("SELECT id FROM sale_events WHERE id = %s FOR UPDATE", (sale_event_id,)) # Use FOR UPDATE to lock row
        event_exists = cursor.fetchone()

        if not event_exists:
            conn.rollback() # Ensure no partial operations
            return False, f"Sale event ID {sale_event_id} not found or already deleted."

        restocking_messages = []

        # 1. Get all *inventory items* (cards/sealed products) from the sale event
        cursor.execute("""
            SELECT inventory_item_id, item_type, quantity_sold, original_item_name
            FROM sale_items
            WHERE sale_event_id = %s
        """, (sale_event_id,))
        items_sold = cursor.fetchall()

        # 2. Get all *shipping supplies* used in this sale event
        cursor.execute("""
            SELECT supply_id, quantity_used, cost_per_unit_snapshot, supply_name_snapshot, supply_description_snapshot
            FROM sale_event_shipping_supplies
            WHERE sale_event_id = %s
        """, (sale_event_id,))
        supplies_used = cursor.fetchall()

        # 3. Restock inventory items (cards/sealed products)
        for item in items_sold:
            inventory_id = item['inventory_item_id']
            item_type = item['item_type']
            quantity_to_restock = item['quantity_sold']
            item_name_for_msg = item['original_item_name']

            if inventory_id is None:
                restocking_messages.append(f"Warning: Sold item '{item_name_for_msg}' had no inventory ID linked; cannot restock.")
                continue

            success_restock, msg_restock = _update_inventory_item_quantity_with_cursor(
                cursor, item_type, inventory_id, quantity_to_restock
            )
            if not success_restock:
                conn.rollback() # Rollback the whole transaction if any restock fails
                return False, f"Failed to restock '{item_name_for_msg}' (Inv ID: {inventory_id}): {msg_restock}. Sale event not deleted."
            restocking_messages.append(f"Restocked {quantity_to_restock} of '{item_name_for_msg}'.")

        # 4. Restock shipping supplies
        for supply in supplies_used:
            supply_id = supply['supply_id']
            quantity_to_restock = supply['quantity_used']
            supply_name_for_msg = supply['supply_name_snapshot']
            supply_desc_for_msg = supply['supply_description_snapshot']

            # Retrieve current quantity and lock the row
            cursor.execute("SELECT quantity_on_hand FROM shipping_supplies_inventory WHERE id = %s FOR UPDATE", (supply_id,))
            current_supply_qty_row = cursor.fetchone()
            if not current_supply_qty_row:
                conn.rollback()
                return False, f"Failed to restock shipping supply '{supply_name_for_msg}' (ID: {supply_id}): Supply not found in inventory. Sale event not deleted."

            new_supply_quantity = current_supply_qty_row['quantity_on_hand'] + quantity_to_restock
            cursor.execute(
                "UPDATE shipping_supplies_inventory SET quantity_on_hand = %s, last_updated = %s WHERE id = %s",
                (new_supply_quantity, datetime.datetime.now(), supply_id)
            )
            restocking_messages.append(f"Restocked {quantity_to_restock} of '{supply_name_for_msg} ({supply_desc_for_msg})'.")


        # 5. Delete the records from sale_event_shipping_supplies for this event
        cursor.execute("DELETE FROM sale_event_shipping_supplies WHERE sale_event_id = %s", (sale_event_id,))

        # 6. Delete the sale items records for this event
        cursor.execute("DELETE FROM sale_items WHERE sale_event_id = %s", (sale_event_id,))

        # 7. Delete the sale event record
        cursor.execute("DELETE FROM sale_events WHERE id = %s", (sale_event_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            return False, f"Sale event ID {sale_event_id} could not be deleted (was it already deleted?)."

        conn.commit() # Commit all changes if everything succeeded
        final_message = f"Sale event ID {sale_event_id} deleted. " + " ".join(restocking_messages)
        return True, final_message

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"DB error in delete_sale_event for event ID {sale_event_id}: {e}")
        return False, f"Database error during sale event deletion: {e}"
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Unexpected error in delete_sale_event for event ID {sale_event_id}: {e}")
        import traceback # For more detailed error info in logs
        traceback.print_exc()
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
        cursor.execute("SELECT * FROM cards WHERE quantity > 0 ORDER BY name, set_code, collector_number, location, buy_price, rarity, language, condition")
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
    allowed_fields = {'quantity', 'buy_price', 'sell_price', 'location', 'condition'}
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
        cursor.execute(f"SELECT quantity FROM {table_name} WHERE id = %s FOR UPDATE", (item_id,))
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
                           customer_shipping_charge_str, platform_fee_str, shipping_supplies_data):
    conn = get_db_connection()
    cursor = conn.cursor() # Use a plain cursor here for DML that doesn't need DictCursor
    sale_event_id = None
    total_items_profit_loss = 0.0
    total_shipping_supplies_cost = 0.0 # This will be the sum of snapshot costs

    try:
        sale_date_obj = datetime.datetime.strptime(sale_date_str, '%Y-%m-%d').date()
        our_postage_cost = float(total_shipping_cost_str if total_shipping_cost_str and total_shipping_cost_str.strip() != '' else 0.0)
        customer_shipping_charge = float(customer_shipping_charge_str if customer_shipping_charge_str and customer_shipping_charge_str.strip() != '' else 0.0)
        platform_fee = float(platform_fee_str if platform_fee_str and platform_fee_str.strip() != '' else 0.0)

    except ValueError as e:
        print(f"DB Error: Invalid date/shipping/fee format: {e}")
        if conn: conn.close()
        return None, f"Invalid date/shipping/fee: {e}"

    try:
        # Step 1: Insert into sale_events first to get sale_event_id
        # We will update total_profit_loss later after calculating it
        # and total_supplies_cost_for_sale after iterating through supplies.
        cursor.execute('''INSERT INTO sale_events (sale_date, total_shipping_cost, notes, customer_shipping_charge, platform_fee)
                          VALUES (%s, %s, %s, %s, %s) RETURNING id''',
                       (sale_date_obj, our_postage_cost, overall_notes, customer_shipping_charge, platform_fee))
        result = cursor.fetchone()
        if result: sale_event_id = result[0]
        else: raise Exception("Failed to create sale event.") # Should always return an ID

        print(f"DB: Created sale_event ID {sale_event_id}")

        # Step 2: Deduct shipping supplies from inventory and record in new table
        # Using a separate cursor with DictCursor capabilities for reading supply details
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as supply_read_cursor:
            for supply_data in shipping_supplies_data:
                supply_id = supply_data.get('supply_item_id')
                quantity_used = supply_data.get('quantity_used')

                if not all([supply_id, quantity_used is not None]):
                    raise ValueError(f"Missing/invalid shipping supply data: {supply_data}")

                quantity_used = int(quantity_used)
                if quantity_used <= 0:
                    raise ValueError(f"Quantity used for supply {supply_id} must be positive.")

                # Get current supply details for snapshot and stock check
                supply_read_cursor.execute("SELECT quantity_on_hand, cost_per_unit, supply_name, description FROM shipping_supplies_inventory WHERE id = %s FOR UPDATE", (supply_id,))
                supply_batch = supply_read_cursor.fetchone() # Fetches as DictRow

                if not supply_batch:
                    raise ValueError(f"Shipping supply ID {supply_id} not found.")

                if supply_batch['quantity_on_hand'] < quantity_used:
                    raise ValueError(f"Not enough '{supply_batch['supply_name']} ({supply_batch['description']})' in stock (Have: {supply_batch['quantity_on_hand']}, Need: {quantity_used}).")

                cost_of_this_supply = supply_batch['cost_per_unit'] * quantity_used
                total_shipping_supplies_cost += cost_of_this_supply

                # Update quantity in inventory (using the main transaction cursor)
                cursor.execute(
                    "UPDATE shipping_supplies_inventory SET quantity_on_hand = %s, last_updated = %s WHERE id = %s",
                    (supply_batch['quantity_on_hand'] - quantity_used, datetime.datetime.now(), supply_id)
                )
                print(f"DB (sale transaction): Deducted {quantity_used} of supply ID {supply_id}. New Qty: {supply_batch['quantity_on_hand'] - quantity_used}")

                # NEW: Record used supplies in sale_event_shipping_supplies table
                cursor.execute('''
                    INSERT INTO sale_event_shipping_supplies (sale_event_id, supply_id, quantity_used, cost_per_unit_snapshot, supply_name_snapshot, supply_description_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (sale_event_id, supply_id, quantity_used, supply_batch['cost_per_unit'], supply_batch['supply_name'], supply_batch['description']))
                print(f"DB: Recorded usage of {quantity_used}x Supply ID {supply_id} for Sale {sale_event_id}")


        # Step 3: Process inventory items (cards/sealed products)
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as item_read_cursor:
            for item_data in items_data_from_app:
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
                item_read_cursor.execute(f"SELECT * FROM {table_name_for_read} WHERE id = %s FOR UPDATE", (inventory_item_id_int,))
                original_item_db_row = item_read_cursor.fetchone()

                if not original_item_db_row:
                    raise ValueError(f"Inv item not found: {item_type} id {inventory_item_id_int}")
                if quantity_sold > original_item_db_row['quantity']:
                    name_key = 'name' if item_type == 'single_card' else 'product_name'
                    raise ValueError(f"Not enough stock for {original_item_db_row[name_key]}. Have: {original_item_db_row['quantity']}")

                buy_price_per_item = float(original_item_db_row['buy_price'])
                item_profit_loss = (sell_price_per_item - buy_price_per_item) * quantity_sold
                total_items_profit_loss += item_profit_loss

                original_item_name_snapshot = ""
                original_item_details_snapshot = ""
                if item_type == 'single_card':
                    original_item_name_snapshot = original_item_db_row['name']
                    rarity_str = (original_item_db_row.get('rarity') if original_item_db_row.get('rarity') is not None else 'N/A')
                    lang_str = (original_item_db_row.get('language') if original_item_db_row.get('language') is not None else 'N/A')
                    condition_str = (original_item_db_row.get('condition') if original_item_db_row.get('condition') is not None else 'N/A')
                    original_item_details_snapshot = f"{original_item_db_row['set_code']}-{original_item_db_row['collector_number']} {'(Foil)' if original_item_db_row['is_foil'] else ''} (R: {rarity_str.capitalize()}, L: {lang_str.upper()}, C: {condition_str})"
                elif item_type == 'sealed_product':
                    original_item_name_snapshot = original_item_db_row['product_name']
                    lang_str_sealed = (original_item_db_row.get('language') if original_item_db_row.get('language') is not None else 'N/A')
                    original_item_details_snapshot = f"{original_item_db_row['set_name']} - {original_item_db_row['product_type']} {'(Collector)' if original_item_db_row['is_collectors_item'] else ''} (L: {lang_str_sealed.upper()})"

                cursor.execute('''INSERT INTO sale_items (sale_event_id, inventory_item_id, item_type, original_item_name, original_item_details, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                               (sale_event_id, inventory_item_id_int, item_type, original_item_name_snapshot, original_item_details_snapshot, quantity_sold, sell_price_per_item, buy_price_per_item, item_profit_loss))

                # Use the helper function to update inventory quantity
                success_inv_update, msg_inv_update = _update_inventory_item_quantity_with_cursor(cursor, item_type, inventory_item_id_int, -quantity_sold)
                if not success_inv_update:
                    raise Exception(f"Inv update failed: {msg_inv_update}")

        # Final Update to sale_events: Calculate total_profit_loss and update total_supplies_cost_for_sale
        final_event_profit_loss = total_items_profit_loss + customer_shipping_charge - our_postage_cost - total_shipping_supplies_cost - platform_fee

        cursor.execute('''UPDATE sale_events SET total_profit_loss = %s, total_supplies_cost_for_sale = %s WHERE id = %s''', (final_event_profit_loss, total_shipping_supplies_cost, sale_event_id))
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
                                 customer_shipping_charge, platform_fee, total_supplies_cost_for_sale
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