from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import database
import scryfall
import datetime
import os
import requests
import csv
import io

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_very_secret_key_here_CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECURE')

ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "YOUR_ROBOFLOW_API_KEY_HERE")
ROBOFLOW_MODEL_ENDPOINT = os.environ.get("ROBOFLOW_MODEL_ENDPOINT", "YOUR_ROBOFLOW_MODEL_INFERENCE_URL_HERE")

def format_currency_with_commas(value):
    if value is None:
        return "$0.00"
    try:
        num_value = float(value)
        if num_value < 0:
            return "-${:,.2f}".format(abs(num_value))
        return "${:,.2f}".format(num_value)
    except (ValueError, TypeError):
        return str(value)
app.jinja_env.filters['currency_commas'] = format_currency_with_commas

@app.before_request
def initialize_database():
    database.init_db()

@app.route('/api/all_sets_info')
def api_all_sets_info():
    set_data = scryfall.fetch_all_set_data()
    if set_data is not None:
        return jsonify(set_data)
    else:
        return jsonify({"error": "Failed to fetch set data from Scryfall"}), 500

@app.route('/api/scan_card_via_roboflow', methods=['POST'])
def scan_card_via_roboflow_route():
    if ROBOFLOW_API_KEY == "YOUR_ROBOFLOW_API_KEY_HERE" or ROBOFLOW_MODEL_ENDPOINT == "YOUR_ROBOFLOW_MODEL_INFERENCE_URL_HERE":
        print("Warning: Roboflow API key or endpoint not configured on the server.")
        if "YOUR_ROBOFLOW_API_KEY_HERE" in ROBOFLOW_API_KEY or "YOUR_ROBOFLOW_MODEL_INFERENCE_URL_HERE" in ROBOFLOW_MODEL_ENDPOINT:
             return jsonify({"error": "Roboflow API key or endpoint not configured on the server with actual values."}), 500
    if 'card_image' not in request.files:
        return jsonify({"error": "No image file provided ('card_image' key missing)."}), 400
    image_file = request.files['card_image']
    if image_file.filename == '':
        return jsonify({"error": "No image selected."}), 400
    try:
        roboflow_url_with_key = f"{ROBOFLOW_MODEL_ENDPOINT}?api_key={ROBOFLOW_API_KEY}&format=json"
        files_for_roboflow = {"file": (image_file.filename, image_file.read(), image_file.mimetype)}
        print(f"Proxying to Roboflow: {roboflow_url_with_key.split('?')[0]}?api_key=HIDDEN&format=json")
        response = requests.post(roboflow_url_with_key, files=files_for_roboflow)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error calling Roboflow API: {http_err} - Response: {http_err.response.text}")
        return jsonify({"error": f"Roboflow API returned an error: {http_err.response.status_code}", "details": http_err.response.text}), http_err.response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Error calling Roboflow API: {e}")
        return jsonify({"error": f"Failed to connect to Roboflow API: {str(e)}"}), 503
    except Exception as e:
        print(f"An unexpected error occurred during Roboflow proxy: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/')
def index():
    active_tab = request.args.get('tab', 'inventoryTab')
    suggested_buy_price = request.args.get('suggested_buy_price', type=float)
    from_pack_details = None
    if request.args.get('from_pack_name'):
        from_pack_details = {
            "name": request.args.get('from_pack_name'),
            "cost": request.args.get('from_pack_cost', type=float),
            "qty_opened": request.args.get('from_pack_qty_opened', type=int)
        }
    inventory_cards_data = database.get_all_cards()
    sealed_products_data = database.get_all_sealed_products()
    sales_history_raw = database.get_all_sales()
    sales_history_data = []
    for raw_sale_row in sales_history_raw:
        sale = dict(raw_sale_row)
        current_sale_date_value = sale.get('sale_date')
        if isinstance(current_sale_date_value, str):
            try:
                sale['sale_date'] = datetime.datetime.strptime(current_sale_date_value, '%Y-%m-%d').date()
            except ValueError:
                sale['sale_date'] = None
        elif not isinstance(current_sale_date_value, datetime.date):
            sale['sale_date'] = None
        sales_history_data.append(sale)
    processed_inventory_cards = []
    total_inventory_market_value_cards = 0
    total_buy_cost_of_inventory_cards = 0
    for card_row in inventory_cards_data:
        card = dict(card_row); item = {'type': 'single_card', 'original_id': card['id']}
        if card.get('quantity', 0) <= 0: continue
        item['display_name'] = card.get('name', 'N/A'); item['quantity'] = card.get('quantity', 0); item['location'] = card.get('location', 'N/A'); item['buy_price'] = card.get('buy_price'); item['sell_price'] = card.get('sell_price'); item['image_uri'] = card.get('image_uri')
        item['set_code'] = card.get('set_code'); item['collector_number'] = card.get('collector_number'); item['is_foil'] = bool(card.get('is_foil', 0))
        item['rarity'] = card.get('rarity', 'N/A'); item['language'] = card.get('language', 'N/A') # Added
        item['total_buy_cost'] = item['quantity'] * item['buy_price']; total_buy_cost_of_inventory_cards += item['total_buy_cost']
        current_market_price = None
        if item['is_foil'] and card.get('foil_market_price_usd') is not None: current_market_price = card['foil_market_price_usd']
        elif not item['is_foil'] and card.get('market_price_usd') is not None: current_market_price = card['market_price_usd']
        item['current_market_price'] = current_market_price
        item_market_value = 0;
        if current_market_price is not None: item_market_value = item['quantity'] * current_market_price; total_inventory_market_value_cards += item_market_value
        item['total_market_value'] = item_market_value
        item['market_vs_buy_percentage_display'] = "N/A"
        if current_market_price is not None and item.get('buy_price') is not None:
            if item['buy_price'] > 0: percentage_diff = ((current_market_price - item['buy_price']) / item['buy_price']) * 100; item['market_vs_buy_percentage_display'] = percentage_diff
            elif item['buy_price'] == 0 and current_market_price > 0: item['market_vs_buy_percentage_display'] = "Infinite"
            elif item['buy_price'] == 0 and current_market_price == 0: item['market_vs_buy_percentage_display'] = 0.0
        item['potential_pl_at_asking_price_display'] = "N/A (No asking price)"
        if item.get('sell_price') is not None:
            asking_value = item['quantity'] * item['sell_price']
            potential_pl = asking_value - item['total_buy_cost']
            item['potential_pl_at_asking_price_display'] = potential_pl
        processed_inventory_cards.append(item)
    processed_sealed_products = []; total_inventory_market_value_sealed = 0; total_buy_cost_of_inventory_sealed = 0
    for product_row in sealed_products_data:
        product = dict(product_row); item = {'type': 'sealed_product', 'original_id': product['id']}
        if product.get('quantity', 0) <= 0: continue
        item['display_name'] = product.get('product_name', 'N/A'); item['quantity'] = product.get('quantity', 0); item['location'] = product.get('location', 'N/A'); item['buy_price'] = product.get('buy_price'); item['sell_price'] = product.get('sell_price'); item['image_uri'] = product.get('image_uri')
        item['set_name'] = product.get('set_name'); item['product_type'] = product.get('product_type'); item['language'] = product.get('language'); item['is_collectors_item'] = bool(product.get('is_collectors_item', 0))
        item['total_buy_cost'] = item['quantity'] * item['buy_price']; total_buy_cost_of_inventory_sealed += item['total_buy_cost']
        item['current_market_price'] = product.get('manual_market_price')
        item_market_value = None
        if item['current_market_price'] is not None: item_market_value = item['quantity'] * item['current_market_price']; total_inventory_market_value_sealed += item_market_value
        item['total_market_value'] = item_market_value
        item['market_vs_buy_percentage_display'] = "N/A (Manual Price)"
        item['potential_pl_at_asking_price_display'] = "N/A (No asking price)"
        if item.get('sell_price') is not None:
            asking_value = item['quantity'] * item['sell_price']
            potential_pl = asking_value - item['total_buy_cost']
            item['potential_pl_at_asking_price_display'] = potential_pl
        processed_sealed_products.append(item)
    combined_inventory_items = processed_inventory_cards + processed_sealed_products
    combined_inventory_items.sort(key=lambda x: x.get('display_name', '').lower())
    total_buy_cost_of_inventory = total_buy_cost_of_inventory_cards + total_buy_cost_of_inventory_sealed
    total_inventory_market_value = total_inventory_market_value_cards + total_inventory_market_value_sealed
    overall_realized_pl = sum(s['profit_loss'] for s in sales_history_data if s.get('profit_loss') is not None)
    sale_inventory_options = []
    for item in combined_inventory_items:
        display_text = "";
        if item['type'] == 'single_card': display_text = f"{item['display_name']} ({item.get('set_code','N/A').upper()}-{item.get('collector_number','N/A')}) {'(Foil)' if item.get('is_foil') else ''} (R: {item.get('rarity','N/A')}, L: {item.get('language','N/A')}) - Qty: {item['quantity']} - Loc: {item.get('location', 'N/A')}" # Added Rarity/Lang
        elif item['type'] == 'sealed_product': display_text = f"{item['display_name']} ({item.get('set_name','N/A')} / {item.get('product_type','N/A')}){' (Collector)' if item.get('is_collectors_item') else ''} (L: {item.get('language','N/A')}) - Qty: {item['quantity']} - Loc: {item.get('location', 'N/A')}" # Added Lang
        sale_inventory_options.append({"id": f"{item['type']}-{item['original_id']}", "display": display_text, "type": item['type']})
    return render_template('index.html',
                           inventory_items=combined_inventory_items,
                           sale_inventory_options=sale_inventory_options,
                           sales_history=sales_history_data,
                           total_inventory_market_value=total_inventory_market_value,
                           total_buy_cost_of_inventory=total_buy_cost_of_inventory,
                           overall_realized_pl=overall_realized_pl,
                           active_tab=active_tab,
                           current_date=datetime.date.today().isoformat(),
                           suggested_buy_price=suggested_buy_price,
                           from_pack_details=from_pack_details)

@app.route('/initiate_open_sealed/<int:product_id>', methods=['POST'])
def initiate_open_sealed_route(product_id):
    quantity_to_open_str = request.form.get('quantity_to_open'); original_product_name = request.form.get('original_product_name'); original_buy_price_str = request.form.get('original_buy_price')
    if not quantity_to_open_str: flash("Please specify a quantity to open.", "error"); return redirect(url_for('index', tab='inventoryTab'))
    try: quantity_to_open = int(quantity_to_open_str); original_buy_price = float(original_buy_price_str)
    except ValueError: flash("Invalid quantity or buy price for opening product.", "error"); return redirect(url_for('index', tab='inventoryTab'))
    if quantity_to_open <= 0: flash("Quantity to open must be positive.", "error"); return redirect(url_for('index', tab='inventoryTab'))
    sealed_product = database.get_sealed_product_by_id(product_id)
    if not sealed_product: flash("Sealed product not found.", "error"); return redirect(url_for('index', tab='inventoryTab'))
    if quantity_to_open > sealed_product['quantity']: flash(f"Cannot open {quantity_to_open}. Only {sealed_product['quantity']} in stock.", "error"); return redirect(url_for('index', tab='inventoryTab'))
    total_cost_opened = original_buy_price * quantity_to_open
    session['open_sealed_data'] = {'product_id': product_id, 'quantity_opened': quantity_to_open, 'total_cost_opened': total_cost_opened, 'product_name': original_product_name}
    return redirect(url_for('confirm_open_sealed_page_route'))

@app.route('/confirm_open_sealed_page', methods=['GET'])
def confirm_open_sealed_page_route():
    open_data = session.get('open_sealed_data')
    if not open_data: flash("No product opening data found. Please start again.", "warning"); return redirect(url_for('index', tab='inventoryTab'))
    return render_template('confirm_open_sealed.html', product_id=open_data['product_id'], quantity_opened=open_data['quantity_opened'], total_cost_opened=open_data['total_cost_opened'], product_name=open_data['product_name'])

@app.route('/finalize_open_sealed', methods=['POST'])
def finalize_open_sealed_route():
    product_id = request.form.get('product_id', type=int); quantity_opened = request.form.get('quantity_opened', type=int); total_cost_opened_str = request.form.get('total_cost_opened'); num_singles_to_add_str = request.form.get('num_singles_to_add'); product_name = request.form.get('product_name'); session.pop('open_sealed_data', None)
    if not all([product_id, quantity_opened, total_cost_opened_str, num_singles_to_add_str]): flash("Missing data to finalize opening.", "error"); return redirect(url_for('index', tab='inventoryTab'))
    try: num_singles_to_add = int(num_singles_to_add_str); total_cost_opened = float(total_cost_opened_str)
    except ValueError: flash("Invalid number for singles or cost.", "error"); session['open_sealed_data'] = {'product_id': product_id, 'quantity_opened': quantity_opened, 'total_cost_opened': total_cost_opened_str, 'product_name': product_name}; return redirect(url_for('confirm_open_sealed_page_route'))
    if num_singles_to_add <= 0: flash("Number of singles to add must be positive.", "error"); session['open_sealed_data'] = {'product_id': product_id, 'quantity_opened': quantity_opened, 'total_cost_opened': total_cost_opened, 'product_name': product_name}; return redirect(url_for('confirm_open_sealed_page_route'))
    average_buy_price = round(total_cost_opened / num_singles_to_add, 2) if num_singles_to_add > 0 else 0.0
    success, message = database.update_sealed_product_quantity(product_id, -quantity_opened)
    if success: flash_message = (f"Opened {quantity_opened} x '{product_name}'. Cost: {format_currency_with_commas(total_cost_opened)}. Add {num_singles_to_add} singles. Avg. buy price: {format_currency_with_commas(average_buy_price)} each."); flash(flash_message, "success"); return redirect(url_for('index', tab='addCardTab', suggested_buy_price=average_buy_price, from_pack_name=product_name, from_pack_cost=total_cost_opened, from_pack_qty_opened=quantity_opened))
    else: flash(f"Failed to update sealed product inventory: {message}", "error"); return redirect(url_for('index', tab='inventoryTab'))

@app.route('/add_card', methods=['POST'])
def add_card_route():
    set_code_input = request.form.get('set_code', '').strip(); collector_number_input = request.form.get('collector_number', '').strip(); card_name_input = request.form.get('card_name', '').strip(); quantity_str = request.form.get('quantity'); buy_price_str = request.form.get('buy_price'); is_foil = 'is_foil' in request.form; location = request.form.get('location', '').strip(); asking_price_str = request.form.get('asking_price')
    rarity_input = request.form.get('rarity', '').strip() # Added
    language_input = request.form.get('language', '').strip() # Added

    quantity, buy_price, asking_price = None, None, None
    try:
        if quantity_str: quantity = int(quantity_str)
        if buy_price_str: buy_price = float(buy_price_str)
        if asking_price_str and asking_price_str.strip() != '': asking_price = float(asking_price_str); asking_price = asking_price if asking_price >= 0 else None
        else: asking_price = None
    except ValueError: flash('Invalid number format.', 'error'); return redirect(url_for('index', tab='addCardTab'))

    set_code_for_lookup = set_code_input if set_code_input else None; collector_number_for_lookup = collector_number_input if collector_number_input else None; card_name_for_lookup = card_name_input if card_name_input else None
    language_for_lookup = language_input if language_input else None # Scryfall uses 'lang' parameter

    can_lookup_by_set_and_number = set_code_for_lookup and collector_number_for_lookup; can_lookup_by_set_and_name = set_code_for_lookup and card_name_for_lookup; can_lookup_by_name_and_number = card_name_for_lookup and collector_number_for_lookup and not set_code_for_lookup; can_lookup_by_name_only = card_name_for_lookup and not set_code_for_lookup and not collector_number_for_lookup
    if not (can_lookup_by_set_and_number or can_lookup_by_set_and_name or can_lookup_by_name_and_number or can_lookup_by_name_only): flash('Lookup requires: (Set & CN), (Set & Name), (Name & CN), or (Name only).', 'error'); return redirect(url_for('index', tab='addCardTab'))
    if quantity is None or buy_price is None or not location: flash('Quantity, Buy Price, and Location required.', 'error'); return redirect(url_for('index', tab='addCardTab'))
    if quantity <= 0 or buy_price < 0: flash('Quantity must be positive; Buy Price non-negative.', 'error'); return redirect(url_for('index', tab='addCardTab'))

    # Pass language_for_lookup to Scryfall
    card_details = scryfall.get_card_details(card_name=card_name_for_lookup, set_code=set_code_for_lookup, collector_number=collector_number_for_lookup, lang=language_for_lookup)

    if card_details and all(k in card_details for k in ['name', 'collector_number', 'set_code']):
        final_set_code = card_details['set_code']; final_collector_number = card_details['collector_number']; scryfall_uuid = card_details.get('id')
        # Use rarity and language from Scryfall response primarily
        final_rarity = card_details.get('rarity', rarity_input if rarity_input else 'unknown').lower()
        final_language = card_details.get('language', language_input if language_input else 'en').lower()

        card_id_or_none = database.add_card(
            final_set_code.upper(), final_collector_number, card_details['name'], quantity, buy_price, is_foil,
            card_details['market_price_usd'], card_details['foil_market_price_usd'],
            card_details['image_uri'], asking_price, location, scryfall_uuid,
            final_rarity, final_language # Added
        )
        if card_id_or_none: flash(f"Card '{card_details['name']}' ({final_set_code.upper()}-{final_collector_number}, R: {final_rarity}, L: {final_language}) handled in inventory at '{location}'!", 'success')
        else: flash(f"Failed to add/update card. Already exists with these details (Set, CN, Foil, Loc, Rarity, Lang)?", 'error')
    else: flash(f"Could not fetch valid card details from Scryfall.", 'error')
    return redirect(url_for('index', tab='addCardTab'))

@app.route('/add_sealed_product', methods=['POST'])
def add_sealed_product_route():
    product_name = request.form.get('product_name', '').strip(); set_name = request.form.get('set_name', '').strip(); product_type = request.form.get('product_type', '').strip(); language = request.form.get('language', 'English').strip(); is_collectors_item = 'is_collectors_item' in request.form; quantity_str = request.form.get('quantity'); buy_price_str = request.form.get('buy_price'); manual_market_price_str = request.form.get('manual_market_price'); asking_price_str = request.form.get('asking_price'); image_uri = request.form.get('image_uri', '').strip(); location = request.form.get('location', '').strip()
    if not all([product_name, set_name, product_type, location]): flash('Product Name, Set Name, Product Type, and Location are required.', 'error'); return redirect(url_for('index', tab='addSealedProductTab'))
    quantity, buy_price, manual_market_price, asking_price = None, None, None, None
    try:
        if quantity_str: quantity = int(quantity_str)
        if buy_price_str: buy_price = float(buy_price_str)
        if manual_market_price_str and manual_market_price_str.strip() != '': manual_market_price = float(manual_market_price_str); manual_market_price = manual_market_price if manual_market_price >= 0 else None
        if asking_price_str and asking_price_str.strip() != '': asking_price = float(asking_price_str); asking_price = asking_price if asking_price >= 0 else None
    except ValueError: flash('Invalid number format.', 'error'); return redirect(url_for('index', tab='addSealedProductTab'))
    if quantity is None or buy_price is None: flash('Quantity and Buy Price are required.', 'error'); return redirect(url_for('index', tab='addSealedProductTab'))
    if quantity <= 0 or buy_price < 0: flash('Quantity must be positive; Buy Price non-negative.', 'error'); return redirect(url_for('index', tab='addSealedProductTab'))
    product_id = database.add_sealed_product(product_name=product_name, set_name=set_name, product_type=product_type, language=language, is_collectors_item=is_collectors_item, quantity=quantity, buy_price=buy_price, manual_market_price=manual_market_price, sell_price=asking_price, image_uri=image_uri if image_uri else None, location=location)
    if product_id: flash(f"Sealed product '{product_name}' added!", 'success')
    else: flash(f"Failed to add sealed product. Already exists?", 'error')
    return redirect(url_for('index', tab='addSealedProductTab'))

@app.route('/record_sale', methods=['POST'])
def record_sale_route():
    item_id_with_prefix = request.form.get('inventory_card_id')
    quantity_sold_str = request.form.get('quantity_sold')
    sell_price_per_item_str = request.form.get('sell_price_per_item')
    sale_date_str = request.form.get('sale_date')
    notes = request.form.get('sale_notes', '')
    shipping_cost_str = request.form.get('shipping_cost')

    item_type = None
    inventory_item_id = None

    if item_id_with_prefix and item_id_with_prefix.strip() and '-' in item_id_with_prefix:
        parts = item_id_with_prefix.strip().split('-', 1)
        item_type_prefix = parts[0].strip()

        print(f"DEBUG record_sale_route: item_type_prefix = {repr(item_type_prefix)}") # Using repr for clarity

        try:
            inventory_item_id = int(parts[1])
            # Corrected comparison for item_type_prefix
            if item_type_prefix == 'single_card': # Was 'card'
                item_type = 'single_card'
            elif item_type_prefix == 'sealed_product':
                item_type = 'sealed_product'
            else:
                print(f"DEBUG record_sale_route: item_type_prefix '{item_type_prefix}' did not match 'single_card' or 'sealed_product'")
        except ValueError:
            inventory_item_id = None
            print(f"DEBUG record_sale_route: ValueError converting '{parts[1]}' to int for inventory_item_id")
    else:
        print(f"DEBUG record_sale_route: item_id_with_prefix '{item_id_with_prefix}' is invalid or missing '-'")


    quantity_sold = None
    sell_price_per_item = None
    shipping_cost = None

    try:
        if quantity_sold_str and quantity_sold_str.strip():
            quantity_sold = int(quantity_sold_str)
        if sell_price_per_item_str and sell_price_per_item_str.strip():
            sell_price_per_item = float(sell_price_per_item_str)
        if shipping_cost_str is not None and shipping_cost_str.strip() != '':
            shipping_cost = float(shipping_cost_str)
        else:
            shipping_cost = 0.0
    except ValueError:
        flash('Invalid number format for Quantity, Sell Price, or Shipping Cost.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    # Debug prints before the all() check
    print(f"--- Pre-validation values for sale ---")
    print(f"item_type: {repr(item_type)}")
    print(f"inventory_item_id: {repr(inventory_item_id)}")
    print(f"quantity_sold: {repr(quantity_sold)}")
    print(f"sell_price_per_item: {repr(sell_price_per_item)}")
    print(f"sale_date_str: {repr(sale_date_str)}")
    print(f"shipping_cost: {repr(shipping_cost)}")
    print(f"------------------------------------")


    if not all([item_type,
                inventory_item_id is not None,
                quantity_sold is not None,
                sell_price_per_item is not None,
                sale_date_str and sale_date_str.strip() != '',
                shipping_cost is not None]):
        flash('Missing or invalid data for sale. Check item selection, quantity, prices, date, and shipping.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    if quantity_sold <= 0 or sell_price_per_item < 0 or shipping_cost < 0:
        flash('Quantity sold must be positive; Sell Price and Shipping Cost cannot be negative.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    original_item = database.get_item_by_id(item_type, inventory_item_id)
    if not original_item:
        flash('Inventory item not found.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    if quantity_sold > original_item['quantity']:
        flash(f"Cannot sell {quantity_sold}. Only {original_item['quantity']} available for '{original_item['name'] if item_type == 'single_card' else original_item['product_name']}'.", 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    original_item_name = "N/A"; original_item_details = "N/A"; buy_price_per_item = None
    if item_type == 'single_card':
        original_item_name = original_item['name']
        original_item_details = f"{original_item['set_code']}-{original_item['collector_number']} {'(Foil)' if original_item['is_foil'] else ''} (R: {original_item.get('rarity','N/A')}, L: {original_item.get('language','N/A')})" # Added R/L
        buy_price_per_item = original_item['buy_price']
    elif item_type == 'sealed_product':
        original_item_name = original_item['product_name']
        original_item_details = f"{original_item['set_name']} - {original_item['product_type']} {'(Collector)' if original_item['is_collectors_item'] else ''} (L: {original_item.get('language','N/A')})" # Added L
        buy_price_per_item = original_item['buy_price']

    if buy_price_per_item is None:
        flash('Could not determine buy price for the item being sold.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    sale_id, message = database.record_sale(
        inventory_item_id=inventory_item_id, item_type=item_type,
        original_item_name=original_item_name, original_item_details=original_item_details,
        quantity_sold=quantity_sold, sell_price_per_item=sell_price_per_item,
        buy_price_per_item=buy_price_per_item, sale_date_str=sale_date_str,
        shipping_cost=shipping_cost, notes=notes
    )
    if sale_id:
        flash(f"Sale recorded (ID: {sale_id}). Inventory: {message}", 'success')
    else:
        flash(f"Failed to record sale. Reason: {message}", 'error')
    return redirect(url_for('index', tab='salesHistoryTab'))


@app.route('/delete_card/<int:card_id>', methods=['POST'])
def delete_card_route(card_id):
    deleted = database.delete_card(card_id)
    if deleted:
        flash('Card entry deleted!', 'success')
    else:
        flash('Failed to delete card entry.', 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/delete_sealed_product/<int:product_id>', methods=['POST'])
def delete_sealed_product_route(product_id):
    deleted = database.delete_sealed_product(product_id)
    if deleted:
        flash('Sealed product entry deleted!', 'success')
    else:
        flash('Failed to delete sealed product.', 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/update_card/<int:card_id>', methods=['POST'])
def update_card_route(card_id):
    data_to_update = {}
    original_card = database.get_card_by_id(card_id)
    if not original_card:
        flash('Card not found for update.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))
    try:
        quantity_str = request.form.get('quantity')
        buy_price_str = request.form.get('buy_price')
        asking_price_str = request.form.get('asking_price')
        location_str = request.form.get('location')
        # Rarity and Language are generally fixed for a printing, so not making them updatable here by default
        # If they need to be updatable, add form fields and logic similar to other fields.

        if quantity_str is not None and quantity_str.strip() != '':
            qty = int(quantity_str)
            if qty < 0:
                flash('Quantity must be non-negative.')
                return redirect(url_for('index', tab='inventoryTab'))
            if qty != original_card['quantity']:
                data_to_update['quantity'] = qty
        if buy_price_str is not None and buy_price_str.strip() != '':
            price = float(buy_price_str)
            if price < 0:
                flash('Buy price cannot be negative.')
                return redirect(url_for('index', tab='inventoryTab'))
            if price != original_card['buy_price']:
                data_to_update['buy_price'] = price
        if asking_price_str is not None:
            ask_price = None
            if asking_price_str.strip() != '':
                ask_price = float(asking_price_str)
                if ask_price < 0:
                    flash('Asking price cannot be negative.')
                    return redirect(url_for('index', tab='inventoryTab'))
            if ask_price != original_card['sell_price']:
                data_to_update['sell_price'] = ask_price
        if location_str is not None:
            location = location_str.strip()
            if not location:
                flash('Location cannot be empty.')
                return redirect(url_for('index', tab='inventoryTab'))
            if location != original_card['location']:
                data_to_update['location'] = location
    except ValueError:
        flash('Invalid number format for quantity or price fields.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))

    if not data_to_update:
         flash('No changes detected to update.', 'warning')
         return redirect(url_for('index', tab='inventoryTab'))

    success, message = database.update_card_fields(card_id, data_to_update)
    if success:
        flash(f'Card details updated! Info: {message}', 'success')
    else:
        flash(f'Failed to update card. Reason: {message}', 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/update_sealed_product/<int:product_id>', methods=['POST'])
def update_sealed_product_route(product_id):
    data_to_update = {}
    original_product = database.get_sealed_product_by_id(product_id)
    if not original_product:
        flash('Product not found for update.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))
    try:
        quantity_str = request.form.get('quantity')
        buy_price_str = request.form.get('buy_price')
        manual_market_price_str = request.form.get('manual_market_price')
        asking_price_str = request.form.get('asking_price')
        location_str = request.form.get('location')
        image_uri_str = request.form.get('image_uri')
        language_str = request.form.get('language') # Added for sealed products
        is_collectors_item_form = 'is_collectors_item' in request.form

        if quantity_str is not None and quantity_str.strip() != '':
            qty = int(quantity_str)
            if qty < 0: flash('Quantity must be non-negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if qty != original_product['quantity']: data_to_update['quantity'] = qty
        if buy_price_str is not None and buy_price_str.strip() != '':
            price = float(buy_price_str)
            if price < 0: flash('Buy price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if price != original_product['buy_price']: data_to_update['buy_price'] = price
        if manual_market_price_str is not None:
            mkt_price = None if manual_market_price_str.strip() == '' else float(manual_market_price_str)
            if mkt_price is not None and mkt_price < 0: flash('Market Price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if mkt_price != original_product['manual_market_price']: data_to_update['manual_market_price'] = mkt_price
        if asking_price_str is not None:
            ask_price = None if asking_price_str.strip() == '' else float(asking_price_str)
            if ask_price is not None and ask_price < 0: flash('Asking price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if ask_price != original_product['sell_price']: data_to_update['sell_price'] = ask_price
        if location_str is not None:
            location = location_str.strip()
            if not location: flash('Location cannot be empty.'); return redirect(url_for('index', tab='inventoryTab'))
            if location != original_product['location']: data_to_update['location'] = location
        if image_uri_str is not None:
             img_uri = image_uri_str.strip() if image_uri_str.strip() else None
             if img_uri != original_product['image_uri']: data_to_update['image_uri'] = img_uri
        if language_str is not None: # Added for sealed products language update
            lang = language_str.strip()
            if not lang: flash('Language cannot be empty for sealed products.'); return redirect(url_for('index', tab='inventoryTab'))
            if lang != original_product['language']: data_to_update['language'] = lang
        if is_collectors_item_form != bool(original_product['is_collectors_item']):
             data_to_update['is_collectors_item'] = is_collectors_item_form
    except ValueError:
        flash('Invalid number format for quantity or price fields.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))

    if not data_to_update:
         flash('No changes detected to update.', 'warning')
         return redirect(url_for('index', tab='inventoryTab'))

    success, message = database.update_sealed_product_fields(product_id, data_to_update)
    if success:
        flash(f'Sealed product details updated! Info: {message}', 'success')
    else:
        flash(f'Failed to update sealed product. Reason: {message}', 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/refresh_card/<int:card_id>', methods=['POST'])
def refresh_card_route(card_id):
    card = database.get_card_by_id(card_id)
    if not card:
        flash('Card not found for refreshing.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))
    # Pass existing language of the card to ensure Scryfall fetches that specific version if needed
    card_details = scryfall.get_card_details(set_code=card['set_code'], collector_number=card['collector_number'], lang=card.get('language'))
    if card_details:
        updated = database.update_card_prices_and_image(
            card_id, card_details['market_price_usd'],
            card_details['foil_market_price_usd'], card_details['image_uri']
            # Rarity and language are not typically "refreshed" as they are static for a printing
        )
        if updated:
            flash(f"Market data for {card_details['name']} refreshed successfully!", 'success')
        else:
            flash(f"Failed to update market data in DB for {card['set_code']}-{card['collector_number']}.", 'error')
    else:
        flash(f"Could not fetch refresh data from Scryfall for {card['set_code']}-{card['collector_number']}.", 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/import_csv', methods=['POST'])
def import_csv_route():
    if 'csv_file' not in request.files:
        flash('No CSV file part in the request.', 'error')
        return redirect(url_for('index', tab='importCsvTab'))

    file = request.files['csv_file']
    if file.filename == '':
        flash('No CSV file selected for uploading.', 'error')
        return redirect(url_for('index', tab='importCsvTab'))

    default_buy_price_str = request.form.get('default_buy_price', '0.00')
    default_location = request.form.get('default_location', 'Imported Batch')
    default_asking_price_str = request.form.get('default_asking_price')
    assume_non_foil = 'assume_non_foil' in request.form
    # Default language if not specified in CSV, can be a form field too
    default_language_csv = request.form.get('default_language_csv', 'en').strip().lower()


    try:
        default_buy_price = float(default_buy_price_str)
        default_asking_price = None
        if default_asking_price_str and default_asking_price_str.strip() != '':
            default_asking_price = float(default_asking_price_str)
            if default_asking_price < 0: default_asking_price = None
    except ValueError:
        flash('Invalid default buy price or asking price format.', 'error')
        return redirect(url_for('index', tab='importCsvTab'))

    if not default_location.strip():
        flash('Default location cannot be empty.', 'error')
        return redirect(url_for('index', tab='importCsvTab'))

    if file and file.filename.endswith('.csv'):
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8", errors='replace'), newline=None)
            csv_reader = csv.DictReader(stream)

            imported_count = 0
            failed_count = 0
            skipped_count = 0
            errors_list = []

            expected_headers = {
                'quantity': 'Quantity',
                'name': 'Name',
                'set_name_csv': 'Set',
                'collector_number_csv': 'Card Number',
                'set_code_csv': 'Set Code',
                'printing': 'Printing',
                'rarity_csv': 'Rarity', # Added
                'language_csv': 'Language' # Added
            }

            if csv_reader.fieldnames:
                 csv_reader.fieldnames = [header.lower().strip() for header in csv_reader.fieldnames if header]
            else:
                flash('CSV file appears to be empty or has no headers.', 'error')
                return redirect(url_for('index', tab='importCsvTab'))


            for row_num, row_raw in enumerate(csv_reader, start=1):
                row = {k.lower().strip() if k else f"unknown_header_{i}": v.strip() if v else "" for i, (k, v) in enumerate(row_raw.items())}

                card_name = row.get(expected_headers['name'].lower())
                set_code_from_csv = row.get(expected_headers['set_code_csv'].lower())
                collector_number_from_csv = row.get(expected_headers['collector_number_csv'].lower())
                quantity_str = row.get(expected_headers['quantity'].lower())
                printing_csv = row.get(expected_headers['printing'].lower(), 'normal').lower()
                set_name_from_csv = row.get(expected_headers['set_name_csv'].lower())
                rarity_from_csv = row.get(expected_headers['rarity_csv'].lower()) # Added
                language_from_csv = row.get(expected_headers['language_csv'].lower(), default_language_csv).lower() # Added, with default

                if not all([card_name, (set_code_from_csv or set_name_from_csv), collector_number_from_csv, quantity_str]):
                    errors_list.append(f"Row {row_num}: Missing Name, Set, CN, or Qty. Skipping.")
                    skipped_count += 1
                    continue

                try:
                    quantity = int(quantity_str)
                    if quantity <= 0:
                        errors_list.append(f"Row {row_num}: Invalid qty '{quantity_str}' for '{card_name}'. Skipping.")
                        skipped_count +=1
                        continue
                except ValueError:
                    errors_list.append(f"Row {row_num}: Invalid qty format '{quantity_str}' for '{card_name}'. Skipping.")
                    skipped_count += 1
                    continue

                is_foil = False
                if not assume_non_foil and 'foil' in printing_csv:
                    is_foil = True

                card_details = None
                # Pass language from CSV to Scryfall lookup
                if set_code_from_csv and set_code_from_csv.upper() == "LIST":
                    print(f"CSV Import (Row {row_num}): Detected 'LIST' set for '{card_name}' CN '{collector_number_from_csv}'. Trying Name+CN lookup first (Lang: {language_from_csv}).")
                    card_details = scryfall.get_card_details(card_name=card_name, collector_number=collector_number_from_csv, lang=language_from_csv)

                if not card_details and set_code_from_csv :
                     card_details = scryfall.get_card_details(card_name=card_name, set_code=set_code_from_csv, collector_number=collector_number_from_csv, lang=language_from_csv)

                if not card_details and set_name_from_csv:
                    print(f"CSV Import (Row {row_num}): Lookup with TCG Set Code '{set_code_from_csv}' failed for '{card_name}'. Trying with TCG Set Name '{set_name_from_csv}' (Lang: {language_from_csv}).")
                    card_details = scryfall.get_card_details(card_name=card_name, set_code=set_name_from_csv, collector_number=collector_number_from_csv, lang=language_from_csv)

                if not card_details:
                    print(f"CSV Import (Row {row_num}): Lookup with Set info failed for '{card_name}' CN '{collector_number_from_csv}'. Trying Name+CN only (Lang: {language_from_csv}).")
                    card_details = scryfall.get_card_details(card_name=card_name, collector_number=collector_number_from_csv, lang=language_from_csv)


                if card_details and all(k in card_details for k in ['name', 'collector_number', 'set_code']):
                    final_set_code = card_details['set_code']
                    final_collector_number = card_details['collector_number']
                    scryfall_uuid = card_details.get('id')
                    # Prioritize Scryfall's rarity and language, fallback to CSV if Scryfall's is missing (though unlikely for these fields)
                    final_rarity = card_details.get('rarity', rarity_from_csv if rarity_from_csv else 'unknown').lower()
                    final_language = card_details.get('language', language_from_csv if language_from_csv else default_language_csv).lower()

                    card_id = database.add_card(
                        set_code=final_set_code.upper(),
                        collector_number=final_collector_number,
                        name=card_details['name'],
                        quantity=quantity,
                        buy_price=default_buy_price,
                        is_foil=is_foil,
                        market_price_usd=card_details['market_price_usd'],
                        foil_market_price_usd=card_details['foil_market_price_usd'],
                        image_uri=card_details['image_uri'],
                        sell_price=default_asking_price,
                        location=default_location,
                        scryfall_id=scryfall_uuid,
                        rarity=final_rarity, # Added
                        language=final_language # Added
                    )
                    if card_id:
                        imported_count += 1
                    else:
                        errors_list.append(f"Row {row_num}: Failed to add/update '{card_details['name']}' (R: {final_rarity}, L: {final_language}) in DB.")
                        failed_count += 1
                else:
                    errors_list.append(f"Row {row_num}: Scryfall lookup failed for '{card_name}' (SetCSV: {set_code_from_csv or set_name_from_csv}, CN: {collector_number_from_csv}, LangCSV: {language_from_csv}). Skipping.")
                    failed_count += 1

            summary_message = f"CSV Import: {imported_count} processed."
            if failed_count > 0: summary_message += f" {failed_count} failed."
            if skipped_count > 0: summary_message += f" {skipped_count} skipped."

            if errors_list:
                flash(summary_message + " Some errors.", 'warning' if imported_count > 0 else 'error')
                for err in errors_list[:10]: # Show first 10 errors
                    flash(err, 'error')
                if len(errors_list) > 10:
                    flash(f"...and {len(errors_list) - 10} more errors (see server console for full list).", 'error')
                print("--- CSV Import Errors ---")
                for err in errors_list: print(err)
                print("-------------------------")
            else:
                flash(summary_message, 'success')

        except Exception as e:
            print(f"Error processing CSV: {e}")
            flash(f'Error processing CSV: {e}', 'error')
            import traceback
            traceback.print_exc()
        return redirect(url_for('index', tab='importCsvTab'))
    else:
        flash('Invalid file type. Please upload a CSV file.', 'error')
        return redirect(url_for('index', tab='importCsvTab'))

if __name__ == '__main__':
    app.run(debug=True)