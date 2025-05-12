# CDI-Tracker: Magic: The Gathering Inventory & Sales Manager

CDI-Tracker is a web-based application built with Python and Flask, designed to help you manage your Magic: The Gathering collection, including both single cards and sealed products. It allows you to track your inventory, differentiate lots by buy price and other attributes, fetch current market values for singles via Scryfall, record sales and shipping costs, and analyze overall profitability with detailed monthly and all-time financial summaries.

## Key Features

* **Dual Inventory System:**
    * Manage both individual Magic cards and sealed products.
    * Each item acquired with a unique combination of identifying attributes (including `buy_price`, `location`, `language`, `rarity` for cards; `buy_price`, `location`, `language`, `product_type`, `is_collectors_item` for sealed) is treated as a distinct lot in the inventory.

* **Single Card Management:**
    * **Flexible Card Addition:**
        * Set Code + Collector Number
        * Set Code + Card Name
        * Card Name + Collector Number (Scryfall determines the set)
        * Card Name only (Scryfall determines the most likely printing)
    * **Scryfall API Integration:** Automatically fetches card details such as name, collector number, set code, market prices (USD for non-foil and foil), card image URI, rarity, and language.
    * **Detailed Tracking:** Track quantity, buy price (per lot), user-defined asking price, physical location, language (dropdown), rarity, and foil status.
    * **"Find Set by Symbol" Modal:** A visual tool utilizing Scryfall's set icon SVGs to easily look up set codes.
    * **Data Refresh:** Allows refreshing market prices and image URI from Scryfall for existing cards in the inventory.
    * **Updates:** Modify card details including quantity, buy price, asking price, and location. Changing attributes that are part of the unique key (like `buy_price`) may result in a new lot if it doesn't conflict with an existing one.

* **Sealed Product Management:**
    * **Manual Entry:** Input details for sealed products: Product Name, Set Name, Product Type (Booster Pack, Box, Bundle, Precon, etc.), Language (dropdown).
    * **Detailed Tracking:** Track quantity, buy price (per lot), user-defined asking price, manually entered market price, physical location, image URL, and an optional "Collector's Item" status.
    * **Updates:** Modify sealed product details including quantity, buy price, market price, asking price, location, image URL, language, and collector's item status.

* **"Open Sealed Product" Workflow:**
    * Designate a specific lot of sealed products from your inventory as "opened."
    * Specify the number of single cards you will add from the opened product(s).
    * The system calculates a suggested average buy price for these singles based on the original cost of the specific sealed product lot.
    * The "Add Single Card" form is then pre-filled with this suggested average buy price and details of the opened pack.

* **Sales Tracking & Profitability:**
    * Record sales for specific lots of both single cards and sealed products.
    * Input quantity sold, sell price per item, sale date, notes, and shipping cost.
    * Automatically calculates Net Profit/Loss for each sale, factoring in the specific lot's buy price and the shipping cost.
    * Reduces inventory quantity upon sale.

* **CSV Import for Single Cards:**
    * Bulk import single card collections from a CSV file.
    * **Expected columns (case-insensitive):** 'Quantity', 'Name', 'Set' (Set Name), 'Card Number' (Collector Number), 'Set Code', 'Printing' (e.g., "Foil", "Normal"), 'Rarity', 'Language' (2-letter code).
    * Uses a user-specified default `buy_price` for the entire import batch.
    * Allows setting default location, asking price, and language for imported cards.
    * Scryfall is used to fetch full card details based on the provided CSV data.

* **Comprehensive Inventory View (`View Inventory` Tab):**
    * Displays all inventory items (singles and sealed, including distinct lots) in a unified grid.
    * **Client-Side Filtering:** Advanced filtering by text search (name, set, location, collector number, rarity, language, product type), item type, location, set, foil status (cards), rarity (cards), language (cards/sealed), and collector's item status (sealed).
    * **Client-Side Sorting:** Sort inventory by Name, Set, Location, Quantity, Buy Price, Market Price, Rarity (Cards), Language, Collector Number (Cards), Product Type (Sealed) in ascending or descending order.
    * **Financial Summary:** Displays key metrics:
        * Total Inventory Buy Cost.
        * Total Inventory Market Value (Scryfall for singles, manual for sealed).
        * Overall Realized Net Profit/Loss (All Time).
        * Current Month's Realized Profit/Loss.
        * Current Month's Total Sales Transactions.
        * Current Month's Total Single Cards Sold (Units).
        * Current Month's Total Sealed Products Sold (Units).
    * Allows inline updates to item details and deletion of items.

* **Sales History View (`View Sales History` Tab):**
    * **Historical Monthly Summaries:** A table summarizing for each past month:
        * Total Profit/Loss for the month.
        * Total Sales Transactions for the month.
        * Total Single Cards Sold (Units) for the month.
        * Total Sealed Products Sold (Units) for the month.
    * **Detailed Sales Log:** Lists all individual sales transactions with details including item name, specifics, quantities, prices, shipping, and net P/L.

* **User Interface:**
    * Tabbed interface for: Add Single Card, Add Sealed Product, Enter Sale, View Inventory, View Sales History, Import CSV.
    * Dark mode theme inspired by Magic: The Gathering colors.
    * Language input fields are dropdowns for common MTG languages.
    * Responsive search bar for selecting items from inventory when recording a sale.
    * Monetary values formatted with dollar signs and commas (e.g., $1,234.56).
    * Positive Profit/Loss and percentage values colored green; negative values red.

* **Data Management:**
    * Uses an SQLite database (`cdi_tracker.db`) for local data storage.
    * Key item attributes (like `buy_price`, `location`, `language`, `rarity`, `is_foil` for cards) are part of the `UNIQUE` constraints in the database, allowing different lots of the same card/product if acquired or stored differently.

## Project Layout

CDI-Tracker/
├── app.py                     # Main Flask application
├── database.py                # Database logic (SQLite)
├── scryfall.py                # Scryfall API interaction
├── requirements.txt           # Python dependencies (User needs to create this)
├── static/
│   └── style.css              # CSS for styling
├── templates/
│   ├── index.html             # Main HTML template for the application
│   └── confirm_open_sealed.html # Template for confirming pack opening details
├── cdi_tracker.db             # SQLite database file (auto-created on first run or via database.py)
└── README.md                  # This file


## Setup and Installation

### Prerequisites

* Python 3.7+
* `pip` (Python package installer, usually comes with Python)

### Installation Steps

1.  **Get the Code:**
    * Download or clone the project files into a directory named `CDI-Tracker`.
    * Navigate to the `CDI-Tracker/` root directory in your terminal.

2.  **Create and Activate a Virtual Environment (Highly Recommended):**
    ```bash
    python -m venv venv
    ```
    Activate:
    * Windows: `venv\Scripts\activate`
    * macOS/Linux: `source venv/bin/activate`

3.  **Create `requirements.txt` file:**
    In the project root (`CDI-Tracker/`), create a file named `requirements.txt` with the following content:
    ```
    Flask
    requests
    ```

4.  **Install Dependencies:**
    With the virtual environment activated:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Initialize/Update the Database:**
    The application uses an SQLite database (`cdi_tracker.db`).
    * The application will attempt to initialize the database schema on its first run if the `cdi_tracker.db` file is missing.
    * Alternatively, you can manually create/update the `cdi_tracker.db` file with the latest schema by running:
        ```bash
        python database.py
        ```
    * **Important:** If you are updating from a version with a different database schema (e.g., changes to `UNIQUE` constraints), it's often simplest to backup your existing `cdi_tracker.db` (if it has data you want to save/migrate manually) and then delete it to allow `database.py` or the app to create a fresh one with the new schema.

## Running the Application

1.  Ensure your virtual environment is activated.
2.  Navigate to the project's root directory (`CDI-Tracker/`).
3.  Run the Flask application:
    ```bash
    python app.py
    ```
4.  Open your web browser and go to: `http://127.0.0.1:5000/`

## Usage Overview

The application is organized into tabs:

* **Add Single Card:** Add individual cards. Scryfall API fetches details. Unique lots are created based on attributes like buy price, location, language, rarity, and foil status.
* **Add Sealed Product:** Manually input details for sealed items. Unique lots are created based on attributes like buy price, location, language, product type, and collector's status.
* **Enter Sale:** Record sales of specific items/lots from your inventory using a searchable dropdown.
* **View Inventory:** View, filter, and sort all inventory. Update item details or delete items. This tab also shows key financial summaries.
* **View Sales History:** Review past sales with monthly summaries and a detailed log of all transactions.
* **Import CSV:** Bulk import single cards from a CSV file.

## Notes

* The Scryfall API is used for fetching single card data. Please be mindful of their API usage guidelines and rate limits (the app includes a small delay between calls).
* Market prices for sealed products are entered and updated manually.
* The `cdi_tracker.db` file contains all your inventory and sales data. Back it up regularly if it contains important information. Consider adding this file to your `.gitignore` if you are using Git and don't want to commit personal data to a repository.
* The integrated camera scanning feature using Roboflow (mentioned in `app.py`) is present in the Python code but requires Roboflow API key configuration and model endpoint setup. Its reliability would depend on the model and configuration.

## Features to Add

* Add sort by print with combos available using checkboxes