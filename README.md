# CDI-Tracker: Magic: The Gathering Inventory & Sales Manager

CDI-Tracker is a web-based application built with Python and Flask, designed to help you manage your Magic: The Gathering collection, including both single cards and sealed products. It allows you to track your inventory, buy prices (differentiating lots by buy price), current market values (for singles via Scryfall), sales, shipping costs, and overall profitability.

## Features

* **Dual Inventory System:** Manage both individual Magic cards and sealed products. Each item acquired at a different `buy_price` is treated as a distinct lot.
* **Single Card Management:**
    * Add cards using various methods:
        * Set Code + Collector Number
        * Set Code + Card Name
        * Card Name + Collector Number (Scryfall determines the set)
        * Card Name only (Scryfall determines the most likely printing)
    * Automatically fetches card details (name, collector number, set code, market prices for foil/non-foil, card image, **rarity, language**) from the Scryfall API.
    * Track quantity, **buy price (unique per lot)**, user-defined asking price, physical location, **language, rarity,** and foil status.
    * Calculates and displays "Market Price vs. Buy Price %" and "Potential P/L at Asking Price" for each lot.
    * "Find Set by Symbol" modal: A visual tool to look up set codes using Scryfall's set icon SVGs.
    * Allows refreshing market data from Scryfall for existing cards.
    * Allows updating card details, including `buy_price` (if the change doesn't conflict with another existing lot's unique attributes).
* **Sealed Product Management:**
    * Manually enter details for sealed products: Product Name, Set Name, Product Type (Booster Pack, Box, Bundle, Precon, etc.), Language.
    * Track quantity, **buy price (unique per lot)**, user-defined asking price, manually entered market price, physical location, and an optional "Collector's Item" status.
    * Allows manual entry of an image URL.
    * Allows updating sealed product details, including `buy_price` (if the change doesn't conflict with another existing lot's unique attributes).
* **"Open Sealed Product" Workflow:**
    * Designate sealed products (a specific lot) from your inventory as "opened."
    * Specify how many single cards you will add from the opened product(s).
    * The system calculates a **suggested average buy price** for these singles based on the original cost of the specific sealed product lot.
    * The "Add Single Card" form is pre-filled with this suggested buy price.
* **Sales Tracking & Profitability:**
    * Record sales for both single cards and sealed products (specific lots).
    * Input quantity sold, sell price per item, sale date, notes, and shipping cost.
    * Calculates **Net Profit/Loss** for each sale, factoring in the specific lot's buy price and the shipping cost.
* **CSV Import for Single Cards:**
    * Import card collections from a CSV file.
    * Expected columns: 'Quantity', 'Name', 'Set', 'Card Number', 'Set Code', 'Printing', **'Rarity', 'Language'**.
    * Uses a default `buy_price` for the entire import batch (each card in the CSV will be associated with this buy price for that import). If this creates new lots or adds to existing lots with the same buy price, it's handled accordingly.
    * Allows setting default location, asking price, and language for imported cards.
    * Handles "LIST" set codes by attempting a more general Scryfall lookup.
* **Comprehensive Inventory View:**
    * Displays all inventory items (singles and sealed, including distinct lots by buy price) in a unified, sortable, and filterable view.
    * **Client-Side Sorting:** Sort inventory by Name, Set, Location, Quantity, Buy Price, Market Price, Rarity (Cards), Language, Collector Number (Cards), Product Type (Sealed).
    * Advanced client-side filtering by text search (name, set, location, etc.), item type, location, set, foil status, rarity, language (for cards), and collector's item status, language (for sealed).
* **Financial Overview:**
    * Calculates and displays:
        * Total Inventory Buy Cost.
        * Total Inventory Market Value (Scryfall for singles, manual for sealed).
        * Overall Realized Net Profit/Loss from all recorded sales.
* **User Interface:**
    * Tabbed interface for: Add Single Card, Add Sealed Product, Enter Sale, View Inventory, View Sales History, Import CSV.
    * Dark mode theme with Magic: The Gathering inspired colors.
    * Language input fields are dropdowns for common MTG languages.
    * Responsive search bar for selecting items (specific lots) from inventory when recording a sale.
    * Monetary values formatted with dollar signs and commas.
    * Positive P/L and percentage values colored green; negative values red.
* **Data Management:**
    * Uses an SQLite database (`cdi_tracker.db`) for local data storage.
    * `buy_price` is part of the unique key, allowing different lots of the same item if acquired at different prices.
    * Handles aggregation of quantities if an item with the exact same unique attributes (including `buy_price`) is added again.

## Project Layout
CDI-Tracker/
├── app.py                     # Main Flask application
├── database.py                # Database logic (SQLite)
├── scryfall.py                # Scryfall API interaction
├── requirements.txt           # Python dependencies
├── static/
│   └── style.css              # CSS for styling
├── templates/
│   ├── index.html             # Main HTML template for the application
│   └── confirm_open_sealed.html # Template for confirming pack opening details
├── cdi_tracker.db             # SQLite database file (auto-created)
└── README.md                  # This file

## Setup and Installation

### Prerequisites

* Python 3.7+
* `pip` (Python package installer, usually comes with Python)
* Git (optional, for version control)

### Installation Steps

1.  **Get the Code:**
    * If cloned from GitHub: `git clone <repository_url>` and `cd CDI-Tracker`
    * If you have the files directly, navigate to the `CDI-Tracker/` root directory.

2.  **Create and Activate a Virtual Environment (Highly Recommended):**
    ```bash
    python -m venv venv
    ```
    Activate:
    * Windows: `venv\Scripts\activate`
    * macOS/Linux: `source venv/bin/activate`

3.  **Create `requirements.txt` file:**
    In the project root, create a file named `requirements.txt` with the following content:
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
    * **Important:** If you are updating from a version where `buy_price` was not part of the `UNIQUE` key in the database tables, you will need to allow the database to be recreated with the new schema. The simplest way is to **backup your existing `cdi_tracker.db` (if it has data you want to save/migrate manually) and then delete it.**
    * Run `database.py` directly to create/update the `cdi_tracker.db` file with the latest schema:
        ```bash
        python database.py
        ```
    The application will also attempt to initialize the DB on first run if the file is missing.

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

* **Add Single Card:** For individual cards. Input details including Set Code, Name, Collector Number, **Rarity**, **Language** (dropdown), Quantity, **Buy Price**, Location, etc. Scryfall API fetches additional card data. Different buy prices will create distinct inventory lots.
* **Add Sealed Product:** Manually input details for sealed items, including **Language** (dropdown) and **Buy Price**. Different buy prices create distinct lots.
* **Enter Sale:** Record sales of specific items/lots from your inventory.
* **View Inventory:** See all your items, including distinct lots for items acquired at different buy prices. Use filters and sorting (by Name, Set, Quantity, Buy Price, etc.) to manage your view. Update item details (including `buy_price`, which may fail if it creates a conflict with another lot).
* **View Sales History:** Review past sales and their net profitability.
* **Import CSV:** Bulk import single cards. Ensure your CSV includes **'Rarity'** and **'Language'** columns. A default `buy_price` specified on the import form will be used for all cards in that batch.

## Notes

* The Scryfall API is used for fetching single card data. Please be mindful of their rate limits.
* Market prices for sealed products are entered manually.
* The `cdi_tracker.db` file contains all your inventory and sales data. Consider adding this to your `.gitignore` if you don't want to commit personal data to a public repository.
* The integrated camera scanning feature was explored but removed due to complexity and reliability concerns.

---