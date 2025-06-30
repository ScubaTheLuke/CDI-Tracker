import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- PostgreSQL Connection Details from your .env ---
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_NAME = os.environ.get('DB_NAME')

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        sslmode='require' # Render usually requires SSL
    )
    return conn

def wipe_all_data():
    """Wipes all data from the application's tables by truncating them."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # List of tables to truncate in dependency order if possible, or use CASCADE
        # Ensure 'sale_items' is before 'sale_events' if not using CASCADE on events,
        # but TRUNCATE ... CASCADE is safer for all.
        tables_to_wipe = [
            "sale_items",
            "sale_events",
            "cards",
            "sealed_products",
            "financial_entries",
            "shipping_supplies_inventory"
        ]

        print("Attempting to wipe data from tables on Render.com...")
        for table_name in tables_to_wipe:
            # TRUNCATE ... RESTART IDENTITY will reset serial IDs (like PRIMARY KEY sequences)
            # CASCADE ensures that any dependent foreign key constraints are handled.
            sql_command = f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;"
            print(f"Executing: {sql_command}")
            cursor.execute(sql_command)
            print(f"Data wiped from '{table_name}'.")

        conn.commit()
        print("Database wipe complete. All tables are now empty.")

    except psycopg2.Error as e:
        print(f"Database error during wipe: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"An unexpected error occurred during wipe: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Starting database wipe script...")
    wipe_all_data()
    print("Script finished.")