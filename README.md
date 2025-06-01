# CDI-Tracker: Magic: The Gathering Inventory & Business Manager

CDI-Tracker is a web-based application built with Python, Flask, and a PostgreSQL backend. It's designed to help you comprehensively manage your Magic: The Gathering collection and associated business finances. It allows you to track inventory (single cards and sealed products), fetch market values via Scryfall, record multi-item sales, manage other income/expenses, and analyze overall profitability with detailed financial summaries. This application is designed for deployment on cloud platforms.

## Key Features

* **Data Management & Deployment:**
    * Uses a robust **PostgreSQL** database for data storage, suitable for larger collections and scalable deployments.
    * Designed for cloud hosting, with configuration for environment variables for secure database connections.
    * Key item attributes (like `buy_price`, `location`, `language`, `rarity`) are part of `UNIQUE` constraints, allowing different lots of the same card/product if acquired or stored differently.

* **Dashboard Overview (New):**
    * Provides an at-a-glance summary of your business's financial health.
    * Displays key metrics: Total Inventory Buy Cost & Market Value, Realized P/L from Sales (All Time), Net Business P/L (All Time), and Current Month's financial performance.

* **Comprehensive Inventory Management (`Inventory` Tab - Revised):**
    * **Dual System:** Manage both individual Magic cards and sealed products.
    * **Detailed View:** Displays all inventory items in a unified, filterable, and sortable grid.
    * **Server-Side Power:** Filtering, sorting, and pagination are handled server-side for efficient performance with large collections.
    * **Single Card Details:** Fetches card details (name, prices, image, rarity, language) via Scryfall API. Includes tracking for quantity, buy price, asking price, location, foil status.
    * **Sealed Product Details:** Manual entry for product name, set, type, language, quantity, buy price, asking price, manual market price, location, image URL, and collector's status.
    * **Management Actions:** Inline updates to item details, deletion of items, and market data refresh for single cards.
    * **"Open Sealed Product" Workflow:** Designate a sealed product lot as "opened," calculate suggested average buy price for resulting singles, and pre-fill the "Add Single Card" form.

* **Streamlined Item Addition (`Add to Inventory` Tab - New):**
    * Consolidates all methods for adding items into one dedicated tab.
    * **Add Single Card Form:** Flexible card lookup (Set & CN, Set & Name, Name & CN, Name only).
    * **"Find Set by Symbol" Modal:** Visual tool using Scryfall set icons to look up set codes.
    * **Add Sealed Product Form:** For manual entry of sealed items.
    * **CSV Import:** Bulk import single cards with user-defined defaults for buy price, location, etc., using a drag-and-drop interface.

* **Sales Tracking & History (`Sales & History` Tab - Revised):**
    * **Enter New Sale:** Record multi-item sales events, including sale date, multiple items (cards/sealed) with quantities and sell prices, total shipping cost, and overall notes.
    * **Profit/Loss Calculation:** Automatically calculates Net P/L for each sale event based on specific lot buy prices and shipping.
    * **Inventory Adjustment:** Reduces inventory quantities automatically upon sale.
    * **View Sales History:**
        * **Historical Monthly Summaries:** Table summarizing P/L, sales count, and units sold for each past month.
        * **Detailed Event Log:** Expandable list of all individual sale events, showing items sold, prices, and P/L for each item within the event.
    * **Delete Sale Events (New):** Ability to delete entire sale events, which also attempts to revert inventory quantities by adding sold items back to stock.

* **Business Ledger (`Business Ledger` Tab - New/Renamed "Finances"):**
    * Track general business income and expenses not directly related to inventory sales (e.g., platform fees, shipping supplies, software subscriptions).
    * Form to add new financial entries (date, description, category, type (income/expense), amount, notes).
    * Table displaying all recorded ledger entries with delete functionality.

* **User Interface:**
    * Responsive, mobile-first design with a hamburger menu for navigation on smaller screens.
    * Collapsible filter section on the inventory tab for better space management on mobile.
    * Dark mode theme inspired by Magic: The Gathering colors.
    * Tabbed interface for clear separation of functionalities: Dashboard, Inventory, Add to Inventory, Sales & History, Business Ledger.

## Project Layout

CDI-Tracker/
├── app.py                     # Main Flask application
├── database.py                # Database logic (PostgreSQL)
├── scryfall.py                # Scryfall API interaction
├── requirements.txt           # Python dependencies
├── render.yaml                # Configuration for deployment on Render (example)
├── static/
│   └── style.css              # CSS for styling
├── templates/
│   ├── index.html             # Main HTML template for the application
│   └── confirm_open_sealed.html # Template for confirming pack opening
└── README.md                  # This file


## Setup and Installation

### Prerequisites

* Python 3.7+
* `pip` (Python package installer)
* A running PostgreSQL server.

### Installation Steps

1.  **Get the Code:**
    * Download or clone the project files.
    * Navigate to the project's root directory in your terminal.

2.  **Create and Activate a Virtual Environment (Highly Recommended):**
    ```bash
    python -m venv venv
    # Windows: venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    (Ensure `requirements.txt` includes `Flask`, `requests`, `psycopg2-binary`, `python-dotenv`).

4.  **Configure Environment Variables:**
    Create a `.env` file in the project root for local development. For production (e.g., on Render), set these in the service's environment settings.
    ```dotenv
    # .env file (Example for local development - use your actual testing DB credentials)
    DB_USER=your_testing_db_user
    DB_PASSWORD=your_testing_db_password
    DB_HOST=your_testing_db_host 
    DB_PORT=5432
    DB_NAME=your_testing_db_name
    FLASK_SECRET_KEY=a_very_long_random_and_secret_string_for_security
    # For Roboflow (Optional)
    # ROBOFLOW_API_KEY=your_roboflow_api_key
    # ROBOFLOW_MODEL_ENDPOINT=your_roboflow_model_inference_url
    ```
    Remember to add `.env` to your `.gitignore` file.

5.  **Initialize the Database:**
    * Ensure your PostgreSQL server is running and you have created databases for testing and production as needed.
    * Make sure your `.env` file (for local) or Render environment variables (for production) are correctly set.
    * Run the initialization script. This will create all necessary tables if they don't exist.
        ```bash
        python database.py
        ```

## Running the Application (Local Development)

1.  Ensure your virtual environment is activated and your `.env` file is configured for your local/testing database.
2.  Run the Flask application:
    ```bash
    python app.py
    ```
3.  Open your web browser and go to: `http://127.0.0.1:10000` (or the port specified in `app.py`).

## Usage Overview (New Tab Structure)

* **Dashboard:** View your main financial summaries and key performance indicators.
* **Inventory:** Browse, filter, sort, update, and manage your existing single cards and sealed products. Initiate opening sealed products from here.
* **Add to Inventory:** Use the forms here to add new single cards, sealed products, or bulk import cards via CSV.
* **Sales & History:** Record new multi-item sales transactions and review detailed history of all past sales, including monthly summaries. Delete sale events if needed.
* **Business Ledger:** Add and track other business-related income and expenses (like fees, supplies, etc.) not directly tied to inventory sales.

## Notes

* The Scryfall API is used for fetching single card data. Be mindful of their API usage guidelines.
* For local development, ensure your `.env` file points to your testing database. For production on Render, ensure your Render environment variables point to your official/production database.
* The integrated camera scanning feature using Roboflow (mentioned in `app.py`) requires Roboflow API key configuration and model endpoint setup as environment variables.
* Deleting sale events attempts to restock inventory but may have limitations if original inventory items have been significantly altered or deleted since the sale.

## Features to Add / Future Enhancements

* Add sort by print finish (e.g., Etched, Gilded) with combo checkboxes in inventory filters.
* More robust error handling and user feedback for inventory restocking during sale event deletion.
* Charts and visualizations on the Dashboard for financial trends.
* User accounts and authentication.
* More detailed reporting features.