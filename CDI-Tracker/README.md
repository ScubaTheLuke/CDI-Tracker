# CDI-Tracker: Magic: The Gathering Inventory & Sales Manager

CDI-Tracker is a web-based application built with Python and Flask, designed to help you manage your Magic: The Gathering collection, including both single cards and sealed products. It allows you to track your inventory, buy prices, current market values (for singles via Scryfall), sales, shipping costs, and overall profitability.

## Features

* **Dual Inventory Tracking:** Manage both individual Magic cards and sealed products (booster packs, boxes, decks, etc.).
* **Single Card Management:**
    * Add cards using Set Code + Collector Number, Set Code + Card Name, or Card Name only.
    * Automatically fetches card details (name, collector number, set code, market prices for foil/non-foil, card image) from the Scryfall API.
    * Tracks quantity, buy price, user-defined asking price, physical location, and foil status.
    * Calculates and displays "Market Price vs. Buy Price %" and "Potential P/L at Asking Price."
    * Allows refreshing market data from Scryfall.
* **Sealed Product Management:**
    * Manually enter details for sealed products: Product Name, Set Name, Product Type (Booster Pack, Box, Bundle, Precon, etc.), Language.
    * Tracks quantity, buy price, user-defined asking price, manually entered market price, physical location, and an optional "Collector's Item" status.
    * Allows manual entry of an image URL.
* **Sales Tracking:**
    * Record sales for both single cards and sealed products.
    * Input quantity sold, sell price per item, sale date, and shipping cost (from a predefined dropdown).
    * Calculates Net Profit/Loss for each sale, factoring in buy price and shipping cost.
* **Comprehensive Inventory View:**
    * Displays all inventory items (singles and sealed) in a unified view.
    * Advanced client-side filtering by text search (name, set, location, etc.), item type, location, set, foil status (for cards), and collector's item status (for sealed).
* **Financial Overview:**
    * Calculates and displays:
        * Total Inventory Buy Cost.
        * Total Inventory Market Value (Scryfall for singles, manual for sealed).
        * Overall Realized Net Profit/Loss from all recorded sales.
* **User Interface:**
    * Tabbed interface for easy navigation: Add Single Card, Add Sealed Product, Enter Sale, View Inventory, View Sales History.
    * Dark mode theme with Magic: The Gathering inspired colors.
    * Responsive search bar for selecting items when recording a sale.
* **Data Management:**
    * Uses an SQLite database (`cdi_tracker.db`) for local data storage.
    * Handles restocking of items that were previously sold out.

## Project Layout

CDI-Tracker/
├── app.py               # Main Flask application
├── database.py          # Database logic (SQLite)
├── scryfall.py          # Scryfall API interaction
├── requirements.txt     # Python dependencies (you'll need to create this)
├── static/
│   └── style.css        # CSS for styling
├── templates/
│   └── index.html       # Main HTML template
├── cdi_tracker.db       # SQLite database file (auto-created)
└── README.md            # This file


## Setup and Installation

### Prerequisites

* Python 3.x
* `pip` (Python package installer, usually comes with Python)
* Git (for cloning the repository)

### Installation Steps

1.  **Clone the Repository (if applicable):**
    If your code is on GitHub, clone it to your local machine:
    ```bash
    git clone [https://github.com/YOUR_USERNAME/CDI-Tracker.git](https://github.com/YOUR_USERNAME/CDI-Tracker.git)
    cd CDI-Tracker
    ```
    If you have the files locally, navigate to the project's root directory (`CDI-Tracker/`).

2.  **Create and Activate a Virtual Environment (Recommended):**
    This keeps your project dependencies isolated.
    ```bash
    python -m venv venv
    ```
    Activate the environment:
    * Windows: `venv\Scripts\activate`
    * macOS/Linux: `source venv/bin/activate`
    Your terminal prompt should now indicate you're in the `(venv)`.

3.  **Create and Install Dependencies:**
    Your project depends on Flask and Requests.
    * First, create a `requirements.txt` file in your project root with the following content:
        ```
        Flask
        requests
        ```
    * Then, install the dependencies:
        ```bash
        pip install -r requirements.txt
        ```

4.  **Initialize the Database:**
    The application uses an SQLite database. The tables will be created automatically when the application first starts or if you run `database.py` directly once.
    * To ensure the schema is up-to-date, especially after pulling changes or making significant modifications to `database.py`, you can run:
        ```bash
        python database.py
        ```
        This will create `cdi_tracker.db` if it doesn't exist and attempt to add any new columns to existing tables. Check the terminal output for any messages.
    * Alternatively, `app.py` calls `database.init_db()` before the first request, which will also create tables if they don't exist.

## Running the Application

1.  Ensure your virtual environment is activated.
2.  Navigate to the project's root directory (`CDI-Tracker/`) if you aren't already there.
3.  Run the Flask application:
    ```bash
    python app.py
    ```
4.  Open your web browser and go to: `http://127.0.0.1:5000/`

## Usage Overview

The application features a tabbed interface:

* **Add Single Card:** Input details for individual Magic cards. Set Code and (Collector Number or Card Name) are used to fetch data from Scryfall. Other details like quantity, buy price, location, and foil status are also recorded.
* **Add Sealed Product:** Manually input details for sealed items like booster packs, boxes, precon decks, etc. This includes Product Name, Set Name, Product Type, Collector's Item status, quantity, buy price, manual market price, asking price, and location.
* **Enter Sale:** Select an item from your current inventory (both singles and sealed products appear in a responsive search bar) and record the quantity sold, sell price per item, sale date, and shipping cost. The system calculates net P/L for this sale.
* **View Inventory:** Displays a combined list of all your single cards and sealed products. Use the filter controls (text search, item type, location, set, foil status, collector's item) to narrow down the view. You can update item details or delete entries from here.
* **View Sales History:** Shows a chronological list of all recorded sales, including item details, quantities, prices, shipping costs, and the net P/L for each sale.

## Notes

* The Scryfall API is used for fetching single card data. Please be mindful of their rate limits (the app includes a small delay).
* Market prices and images for sealed products are entered manually as readily available free APIs for this specific data for new users are currently restricted.
* The `cdi_tracker.db` file contains all your inventory and sales data. It's generally recommended to add this file to your `.gitignore` if you don't want to commit your personal data to a public Git repository. The application will create it if it's missing.

---