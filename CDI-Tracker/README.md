# CDI-Tracker

A Flask web application to track your Magic: The Gathering card inventory, fetch market prices from Scryfall, and calculate potential profits.

## Project Layout

CDI-Tracker/
├── app.py               # Flask app
├── scryfall.py          # Handles Scryfall API calls
├── database.py          # Handles SQLite logic
├── templates/
│   └── index.html       # Frontend UI
├── static/
│   └── style.css        # Optional styles
├── cdi.db               # SQLite DB (auto-created)
└── README.md            # This file


## Setup

1.  **Clone the repository (or create the files as provided).**

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install Flask requests
    ```

4.  **Run the application:**
    ```bash
    python app.py
    ```

5.  Open your web browser and go to `http://127.0.0.1:5000/`.

## Features

* Add cards to your inventory with set code, collector number, quantity, buy price, and foil status.
* Automatically fetches card name, market price (USD for non-foil and foil), and card image from the Scryfall API.
* Displays your current inventory, including:
    * Card details and image.
    * Total buy cost for each entry.
    * Current market value for each entry.
    * Profit/Loss for each entry.
* Calculates total inventory buy cost, total current market value, and overall profit/loss.
* Allows deleting cards from the inventory.
* Allows updating the quantity and buy price of existing cards.
* Allows refreshing card market data (prices, image) from Scryfall for an existing entry.
* Basic styling and user feedback messages.

## Flow

1.  User enters card details (Set code, Collector Number, Quantity, Buy Price, Foil flag) into the web form.
2.  The Flask backend (`app.py`) receives the data.
3.  `scryfall.py` is called to hit the Scryfall API (e.g., `https://api.scryfall.com/cards/{set_code}/{collector_number}`).
4.  Scryfall API returns card name, market prices, image URI, etc.
5.  `database.py` saves the user's input and the fetched Scryfall data to the local `cdi.db` SQLite database.
6.  The main page (`index.html`) displays the current inventory, profits, values, etc., by querying the database.

## Notes

* The Scryfall API has a rate limit (around 10 requests per second). This application includes a small delay (100ms) per request to be polite to the API.
* Ensure `app.py` has a unique `app.secret_key` if deploying in a more public context.
* Error handling for API calls and database interactions is included.



add shipping cost dropdown in make sale secion with values of .80  4.39   .25
add input for sealed product (booster pack, booster box, dual decks, pre con-checkmark to tell if there is a collector version of each sealed product) track finance, name, location, quantity, market average on tcg? 
add filter to the invintory view