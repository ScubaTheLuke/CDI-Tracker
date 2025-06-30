# CDI Tracker

CDI Tracker is a Flask-based web application designed to help Magic: The Gathering (MTG) card dealers and enthusiasts manage their inventory, track sales, monitor financial performance, and keep a business ledger. It integrates with the Scryfall API for card data and prices, and uses a PostgreSQL database for persistent storage.

## Table of Contents

-   [Features](#features)
-   [Key Changes / Recent Updates](#key-changes--recent-updates)
-   [Project Structure](#project-structure)
-   [Setup and Installation](#setup-and-installation)
    -   [Prerequisites](#prerequisites)
    -   [Database Setup (PostgreSQL)](#database-setup-postgresql)
    -   [Application Setup](#application-setup)
-   [Usage](#usage)
-   [Customization](#customization)
-   [Contributing](#contributing)
-   [License](#license)

## Features

* **Dashboard Overview:** Real-time financial insights including:
    * Total Inventory Buy Cost & Market Value
    * Total Quantity of Single Cards and Sealed Products
    * All-Time Gross Sales, Cost of Goods Sold (COGS), and Realized Profit/Loss from Sales
    * Comprehensive Net Business Profit/Loss (All Time)
    * Current Month's Sales Performance
    * Total Cost of Shipping Supplies Used in Sales (visible in terminal logs)
* **Inventory Management:**
    * Detailed listing of single cards, sealed products, and shipping supplies.
    * Filtering and sorting capabilities for inventory.
    * Mass edit functionality for filtered inventory items.
    * Actions: Delete items, refresh market data (for cards), open sealed products into singles.
* **Add to Inventory:**
    * Forms for adding single cards (with Scryfall lookup for details/prices).
    * Forms for adding sealed products.
    * Forms for adding shipping supply batches (automatically creates ledger expense entries).
    * CSV import for bulk card additions.
* **Sales & History:**
    * Record multi-item sales, including customer shipping charges, platform fees, and actual postage costs, and shipping supplies used.
    * View monthly sales summaries.
    * Detailed sales event history with profit/loss per event and item.
    * Option to delete sale events (restocks items automatically).
* **Business Ledger:**
    * Record general business income and expenses.
    * View all financial entries.
    * Delete individual financial entries.
* **Theme Switch:** Toggle between a custom Dark Mode and a "Classic Mode" (original theme colors). Your preference is saved locally.
* **Responsive Design:** Optimized for various screen sizes, from desktop to mobile.

## Key Changes / Recent Updates

This section highlights the significant modifications and improvements made to the application:

1.  **Refined Net Business P/L Calculation:**
    * **Goal:** Ensure the "Net Business P/L (All Time)" accurately reflects all ledger income and expenses, *without double-counting* the cost of shipping supplies.
    * **Implementation:**
        * The `sale_events` table in `database.py` now explicitly stores `total_supplies_cost_for_sale`.
        * The `record_multi_item_sale` and `get_all_sale_events_with_items` functions in `database.py` were updated to handle this new column.
        * In `app.py`, the `net_business_pl` calculation now *adds back* the `total_supplies_cost_deducted_in_sales_pl` (cost of supplies used in sales events). This cancels out the deduction already applied within the `sales_pl` calculation, ensuring the overall `net_business_pl` reflects the supply cost only once (from their original purchase in the ledger).
    * **Impact:** `Realized P/L from Sales (All Time)` and `P/L from Sales (Current Month)` remain unchanged, continuing to deduct shipping supplies used in sales. Only `Net Business P/L (All Time)` is adjusted as intended.

2.  **Shipping Supplies Cost Logging (Terminal):**
    * Added a `print()` statement in `app.py` (within the `index()` function) to output the "Total Shipping Supplies Cost Used in Sales (All Time)" directly to the Flask server's terminal. This provides quick debug/overview without modifying the UI.

3.  **Dynamic Theme Switching:**
    * **CSS (`style.css`):**
        * The main `:root` now defines a new, modern **Dark Mode** color palette.
        * A new CSS class, `.classic-mode`, was introduced to redefine the CSS variables with your original color palette, enabling a "Classic Mode" theme.
        * Scryfall set symbol images now dynamically adjust their `filter` property (invert colors) based on the active theme, ensuring visibility in both dark and light backgrounds.
    * **HTML/JavaScript (`index.html`):**
        * A toggle switch (`<input type="checkbox">`) was added to the header.
        * JavaScript was implemented to:
            * Read and save theme preferences to `localStorage` for persistence.
            * Apply the appropriate CSS class (`.classic-mode` or none) to the `<body>` element on page load.
            * Handle the toggle event to instantly switch themes.
            * Adjust the Scryfall set symbol image filters in the modal when the theme changes.

## Project Structure


.
├── app.py                  # Main Flask application, routes, and business logic.
├── database.py             # PostgreSQL database connection and CRUD operations.
├── scryfall.py             # Scryfall API integration for card data.
├── requirements.txt        # Python dependencies.
├── static/
│   └── style.css           # Global CSS styles and theme definitions.
├── templates/
│   ├── index.html          # Main application dashboard and tabs.
│   └── confirm_open_sealed.html # Confirmation page for opening sealed products.
└── .env.example            # Example for environment variables (DB credentials).


## Setup and Installation

### Prerequisites

* Python 3.x
* PostgreSQL database server
* `pip` (Python package installer)

### Database Setup (PostgreSQL)

1.  **Create a PostgreSQL Database:**
    Open your PostgreSQL client (e.g., `psql` or pgAdmin) and create a new database.
    ```sql
    CREATE DATABASE cdi_tracker;
    ```

2.  **Create a Database User (Optional, but Recommended):**
    ```sql
    CREATE USER cdi_user WITH PASSWORD 'your_secure_password';
    GRANT ALL PRIVILEGES ON DATABASE cdi_tracker TO cdi_user;
    ```

3.  **Configure Environment Variables:**
    Create a file named `.env` in the root directory of your project (same level as `app.py`).
    ```
    FLASK_SECRET_KEY='a_very_secret_random_string_for_flask_sessions'
    DB_USER='cdi_user'
    DB_PASSWORD='your_secure_password'
    DB_HOST='localhost'
    DB_PORT='5432'
    DB_NAME='cdi_tracker'
    # For production, ensure sslmode='require' is appropriate for your DB setup.
    ```
    Replace `your_secure_password` and other values as per your PostgreSQL setup.

4.  **Initialize Database Schema:**
    Navigate to your project's root directory in the terminal and run the `database.py` script. This will create the necessary tables.
    ```bash
    python database.py
    ```
    * **Important:** If you have existing data and run this after some schema changes, it will attempt to add new columns. If you are developing and want to completely reset, you might need to manually `DROP TABLE`s in PostgreSQL or use `TRUNCATE` before running `database.py` again.

### Application Setup

1.  **Clone the Repository (if applicable) or download the files.**

2.  **Install Python Dependencies:**
    Navigate to your project's root directory in the terminal.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Flask Application:**
    ```bash
    python app.py
    ```
    The application should now be running, typically accessible at `http://127.0.0.1:10000/` or `http://localhost:10000/`.

## Usage

* **Navigation:** Use the tabs at the top to navigate between Dashboard, Inventory, Add Items, Sales & History, and Business Ledger.
* **Add Items:** Use the forms on the "Add to Inventory" tab to add single cards, sealed products, or shipping supplies. You can also import cards via CSV.
* **Record Sales:** On the "Sales & History" tab, use the "Record a New Multi-Item Sale" form to track sales, including items sold and shipping supplies used.
* **Manage Inventory:** The "Inventory" tab allows you to view, filter, sort, and mass-edit your items.
* **Track Finances:** The "Business Ledger" lets you log general income and expenses. The "Dashboard" provides summary financial metrics.
* **Theme Toggle:** Use the switch in the top-right corner to change between Dark Mode and Classic Mode.

## Customization

* **Colors:** Modify the `--bg-*`, `--text-*`, `--border-color`, and `--mtg-*` CSS variables in `style.css` (both in `:root` and `body.classic-mode`) to customize the application's theme.
* **Database:** Adjust PostgreSQL connection details in your `.env` file.
* **Scryfall API:** The `scryfall.py` module handles external API calls; no configuration is typically needed unless Scryfall changes its base URL.

## Contributing

If you have suggestions for features, bug fixes, or improvements, feel free to propose them!

## License

[Specify your project's license here, e.g., MIT, Apache 2.0, etc.]
