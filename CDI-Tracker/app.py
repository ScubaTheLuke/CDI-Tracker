from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify # Added jsonify
import database
import scryfall
import datetime
import sqlite3 # Not strictly needed if all DB interaction is in database.py

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_here_CHANGE_ME_TO_SOMETHING_RANDOM'

# Custom Jinja2 filter for currency formatting
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

# --- API Route for Set Symbol Finder ---
@app.route('/api/all_sets_info')
def api_all_sets_info():
    set_data = scryfall.fetch_all_set_data() # This function needs to be in scryfall.py
    if set_data is not None: # Check if data was successfully fetched (could be empty list)
        return jsonify(set_data)
    else:
        # Return an empty list or an error if fetching failed critically in scryfall.py
        return jsonify({"error": "Failed to fetch set data from Scryfall"}), 500

# --- Main Application Routes ---
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
                print(f"Warning: Could not parse sale_date string: '{current_sale_date_value}'")
                sale['sale_date'] = None
        elif not isinstance(current_sale_date_value, datetime.date):
            if current_sale_date_value is not None:
                 print(f"Warning: sale_date was not a string or date object, but: {current_sale_date_value} (type: {type(current_sale_date_value)})")
            sale['sale_date'] = None
        sales_history_data.append(sale)

    processed_inventory_cards = []
    total_inventory_market_value_cards = 0
    total_buy_cost_of_inventory_cards = 0
    for card_row in inventory_cards_data:
        card = dict(card_row)
        item = {'type': 'single_card', 'original_id': card['id']}
        if card.get('quantity', 0) <= 0:
            continue
        item['display_name'] = card.get('name', 'N/A')
        item['quantity'] = card.get('quantity', 0)
        item['location'] = card.get('location', 'N/A')
        item['buy_price'] = card.get('buy_price')
        item['sell_price'] = card.get('sell_price')
        item['image_uri'] = card.get('image_uri')
        item['set_code'] = card.get('set_code')
        item['collector_number'] = card.get('collector_number')
        item['is_foil'] = bool(card.get('is_foil', 0))
        item['total_buy_cost'] = item['quantity'] * item['buy_price']
        total_buy_cost_of_inventory_cards += item['total_buy_cost']
        current_market_price = None
        if item['is_foil'] and card.get('foil_market_price_usd') is not None:
            current_market_price = card['foil_market_price_usd']
        elif not item['is_foil'] and card.get('market_price_usd') is not None:
            current_market_price = card['market_price_usd']
        item['current_market_price'] = current_market_price
        item_market_value = 0
        if current_market_price is not None:
            item_market_value = item['quantity'] * current_market_price
            total_inventory_market_value_cards += item_market_value
        item['total_market_value'] = item_market_value
        item['market_vs_buy_percentage_display'] = "N/A"
        if current_market_price is not None and item.get('buy_price') is not None:
            if item['buy_price'] > 0:
                percentage_diff = ((current_market_price - item['buy_price']) / item['buy_price']) * 100
                item['market_vs_buy_percentage_display'] = percentage_diff
            elif item['buy_price'] == 0 and current_market_price > 0:
                 item['market_vs_buy_percentage_display'] = "Infinite"
            elif item['buy_price'] == 0 and current_market_price == 0:
                 item['market_vs_buy_percentage_display'] = 0.0
        item['potential_pl_at_asking_price_display'] = "N/A (No asking price)"
        if item.get('sell_price') is not None:
            asking_value = item['quantity'] * item['sell_price']
            potential_pl = asking_value - item['total_buy_cost']
            item['potential_pl_at_asking_price_display'] = potential_pl
        processed_inventory_cards.append(item)

    processed_sealed_products = []
    total_inventory_market_value_sealed = 0
    total_buy_cost_of_inventory_sealed = 0
    for product_row in sealed_products_data:
        product = dict(product_row)
        item = {'type': 'sealed_product', 'original_id': product['id']}
        if product.get('quantity', 0) <= 0:
            continue
        item['display_name'] = product.get('product_name', 'N/A')
        item['quantity'] = product.get('quantity', 0)
        item['location'] = product.get('location', 'N/A')
        item['buy_price'] = product.get('buy_price')
        item['sell_price'] = product.get('sell_price')
        item['image_uri'] = product.get('image_uri')
        item['set_name'] = product.get('set_name')
        item['product_type'] = product.get('product_type')
        item['language'] = product.get('language')
        item['is_collectors_item'] = bool(product.get('is_collectors_item', 0))
        item['total_buy_cost'] = item['quantity'] * item['buy_price']
        total_buy_cost_of_inventory_sealed += item['total_buy_cost']
        item['current_market_price'] = product.get('manual_market_price')
        item_market_value = None
        if item['current_market_price'] is not None:
             item_market_value = item['quantity'] * item['current_market_price']
             total_inventory_market_value_sealed += item_market_value
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
        display_text = ""
        if item['type'] == 'single_card':
            display_text = f"{item['display_name']} ({item.get('set_code','N/A').upper()}-{item.get('collector_number','N/A')}) {'(Foil)' if item.get('is_foil') else ''} - Qty: {item['quantity']} - Loc: {item.get('location', 'N/A')}"
        elif item['type'] == 'sealed_product':
            display_text = f"{item['display_name']} ({item.get('set_name','N/A')} / {item.get('product_type','N/A')}){' (Collector)' if item.get('is_collectors_item') else ''} - Qty: {item['quantity']} - Loc: {item.get('location', 'N/A')}"
        sale_inventory_options.append({
            "id": f"{item['type']}-{item['original_id']}",
            "display": display_text,
            "type": item['type']
        })

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
    quantity_to_open_str = request.form.get('quantity_to_open')
    original_product_name = request.form.get('original_product_name')
    original_buy_price_str = request.form.get('original_buy_price')

    if not quantity_to_open_str:
        flash("Please specify a quantity to open.", "error")
        return redirect(url_for('index', tab='inventoryTab'))
    try:
        quantity_to_open = int(quantity_to_open_str)
        original_buy_price = float(original_buy_price_str)
    except ValueError:
        flash("Invalid quantity or buy price for opening product.", "error")
        return redirect(url_for('index', tab='inventoryTab'))

    if quantity_to_open <= 0:
        flash("Quantity to open must be positive.", "error")
        return redirect(url_for('index', tab='inventoryTab'))

    sealed_product = database.get_sealed_product_by_id(product_id)
    if not sealed_product:
        flash("Sealed product not found.", "error")
        return redirect(url_for('index', tab='inventoryTab'))
    if quantity_to_open > sealed_product['quantity']:
        flash(f"Cannot open {quantity_to_open}. Only {sealed_product['quantity']} in stock.", "error")
        return redirect(url_for('index', tab='inventoryTab'))

    total_cost_opened = original_buy_price * quantity_to_open
    session['open_sealed_data'] = {
        'product_id': product_id,
        'quantity_opened': quantity_to_open,
        'total_cost_opened': total_cost_opened,
        'product_name': original_product_name
    }
    return redirect(url_for('confirm_open_sealed_page_route'))

@app.route('/confirm_open_sealed_page', methods=['GET'])
def confirm_open_sealed_page_route():
    open_data = session.get('open_sealed_data')
    if not open_data:
        flash("No product opening data found. Please start again.", "warning")
        return redirect(url_for('index', tab='inventoryTab'))
    return render_template('confirm_open_sealed.html',
                           product_id=open_data['product_id'],
                           quantity_opened=open_data['quantity_opened'],
                           total_cost_opened=open_data['total_cost_opened'],
                           product_name=open_data['product_name'])

@app.route('/finalize_open_sealed', methods=['POST'])
def finalize_open_sealed_route():
    product_id = request.form.get('product_id', type=int)
    quantity_opened = request.form.get('quantity_opened', type=int)
    total_cost_opened_str = request.form.get('total_cost_opened')
    num_singles_to_add_str = request.form.get('num_singles_to_add')
    product_name = request.form.get('product_name')
    session.pop('open_sealed_data', None)

    if not all([product_id, quantity_opened, total_cost_opened_str, num_singles_to_add_str]):
        flash("Missing data to finalize opening. Please start over.", "error")
        return redirect(url_for('index', tab='inventoryTab'))
    try:
        num_singles_to_add = int(num_singles_to_add_str)
        total_cost_opened = float(total_cost_opened_str)
    except ValueError:
        flash("Invalid number for singles or cost.", "error")
        session['open_sealed_data'] = { # Repopulate session for retry
            'product_id': product_id, 'quantity_opened': quantity_opened,
            'total_cost_opened': total_cost_opened_str, # Keep original string if parsing failed
            'product_name': product_name
        }
        return redirect(url_for('confirm_open_sealed_page_route'))
    if num_singles_to_add <= 0:
        flash("Number of singles to add must be positive.", "error")
        session['open_sealed_data'] = {
            'product_id': product_id, 'quantity_opened': quantity_opened,
            'total_cost_opened': total_cost_opened, 'product_name': product_name
        }
        return redirect(url_for('confirm_open_sealed_page_route'))

    average_buy_price = round(total_cost_opened / num_singles_to_add, 2) if num_singles_to_add > 0 else 0.0
    success, message = database.update_sealed_product_quantity(product_id, -quantity_opened)

    if success:
        flash_message = (f"Opened {quantity_opened} x '{product_name}'. "
                         f"Total cost: {format_currency_with_commas(total_cost_opened)}. "
                         f"Add your {num_singles_to_add} singles. "
                         f"Suggested avg. buy price: {format_currency_with_commas(average_buy_price)} each.")
        flash(flash_message, "success")
        return redirect(url_for('index', tab='addCardTab',
                                suggested_buy_price=average_buy_price,
                                from_pack_name=product_name,
                                from_pack_cost=total_cost_opened,
                                from_pack_qty_opened=quantity_opened))
    else:
        flash(f"Failed to update sealed product inventory: {message}", "error")
        return redirect(url_for('index', tab='inventoryTab'))

@app.route('/add_card', methods=['POST'])
def add_card_route():
    set_code_input = request.form.get('set_code', '').strip()
    collector_number_input = request.form.get('collector_number', '').strip()
    card_name_input = request.form.get('card_name', '').strip()
    quantity_str = request.form.get('quantity')
    buy_price_str = request.form.get('buy_price')
    is_foil = 'is_foil' in request.form
    location = request.form.get('location', '').strip()
    asking_price_str = request.form.get('asking_price')

    quantity, buy_price, asking_price = None, None, None
    try:
        if quantity_str: quantity = int(quantity_str)
        if buy_price_str: buy_price = float(buy_price_str)
        if asking_price_str and asking_price_str.strip() != '':
            asking_price = float(asking_price_str)
            if asking_price < 0: asking_price = None
        else:
             asking_price = None
    except ValueError:
        flash('Invalid number format for Quantity, Buy Price, or Asking Price.', 'error')
        return redirect(url_for('index', tab='addCardTab'))

    set_code_for_lookup = set_code_input if set_code_input else None
    collector_number_for_lookup = collector_number_input if collector_number_input else None
    card_name_for_lookup = card_name_input if card_name_input else None

    can_lookup_by_set_and_number = set_code_for_lookup and collector_number_for_lookup
    can_lookup_by_set_and_name = set_code_for_lookup and card_name_for_lookup
    can_lookup_by_name_and_number = card_name_for_lookup and collector_number_for_lookup and not set_code_for_lookup
    can_lookup_by_name_only = card_name_for_lookup and not set_code_for_lookup and not collector_number_for_lookup

    if not (can_lookup_by_set_and_number or can_lookup_by_set_and_name or can_lookup_by_name_and_number or can_lookup_by_name_only):
        flash('For Scryfall lookup, please provide one of the following combinations: (Set & CN), (Set & Name), (Name & CN), or (Name only - Scryfall will pick a printing).', 'error')
        return redirect(url_for('index', tab='addCardTab'))
    if quantity is None or buy_price is None or not location:
        flash('Quantity, Buy Price, and Location are required fields.', 'error')
        return redirect(url_for('index', tab='addCardTab'))
    if quantity <= 0 or buy_price < 0:
        flash('Quantity must be positive and Buy Price cannot be negative.', 'error')
        return redirect(url_for('index', tab='addCardTab'))

    card_details = scryfall.get_card_details(
        card_name=card_name_for_lookup,
        set_code=set_code_for_lookup,
        collector_number=collector_number_for_lookup
    )

    if card_details and card_details.get('name') and card_details.get('collector_number') and card_details.get('set_code'):
        final_set_code = card_details['set_code']
        final_collector_number = card_details['collector_number']
        scryfall_uuid = card_details.get('id')

        card_id_or_none = database.add_card(
            final_set_code.upper(), final_collector_number, card_details['name'],
            quantity, buy_price, is_foil,
            card_details['market_price_usd'], card_details['foil_market_price_usd'],
            card_details['image_uri'], asking_price, location, scryfall_uuid
        )
        if card_id_or_none:
            flash(f"Card '{card_details['name']}' ({final_set_code.upper()}-{final_collector_number}) handled in inventory at '{location}'!", 'success')
        else:
            flash(f"Failed to add/update card. It might already exist with active stock at that location, or another database error occurred.", 'error')
    else:
        flash(f"Could not fetch valid card details from Scryfall. Ensure input is correct. If providing only card name, Scryfall picks the printing.", 'error')
    return redirect(url_for('index', tab='addCardTab'))

@app.route('/add_sealed_product', methods=['POST'])
def add_sealed_product_route():
    product_name = request.form.get('product_name', '').strip()
    set_name = request.form.get('set_name', '').strip()
    product_type = request.form.get('product_type', '').strip()
    language = request.form.get('language', 'English').strip()
    is_collectors_item = 'is_collectors_item' in request.form
    quantity_str = request.form.get('quantity')
    buy_price_str = request.form.get('buy_price')
    manual_market_price_str = request.form.get('manual_market_price')
    asking_price_str = request.form.get('asking_price')
    image_uri = request.form.get('image_uri', '').strip()
    location = request.form.get('location', '').strip()

    if not all([product_name, set_name, product_type, location]):
        flash('Product Name, Set Name, Product Type, and Location are required.', 'error')
        return redirect(url_for('index', tab='addSealedProductTab'))

    quantity, buy_price, manual_market_price, asking_price = None, None, None, None
    try:
        if quantity_str: quantity = int(quantity_str)
        if buy_price_str: buy_price = float(buy_price_str)
        if manual_market_price_str and manual_market_price_str.strip() != '':
            manual_market_price = float(manual_market_price_str)
            if manual_market_price < 0: manual_market_price = None
        if asking_price_str and asking_price_str.strip() != '':
            asking_price = float(asking_price_str)
            if asking_price < 0: asking_price = None
    except ValueError:
        flash('Invalid number format for Quantity or Price fields.', 'error')
        return redirect(url_for('index', tab='addSealedProductTab'))

    if quantity is None or buy_price is None:
         flash('Quantity and Buy Price are required.', 'error')
         return redirect(url_for('index', tab='addSealedProductTab'))
    if quantity <= 0 or buy_price < 0:
        flash('Quantity must be positive and Buy Price cannot be negative.', 'error')
        return redirect(url_for('index', tab='addSealedProductTab'))

    product_id = database.add_sealed_product(
        product_name=product_name, set_name=set_name, product_type=product_type, language=language,
        is_collectors_item=is_collectors_item, quantity=quantity, buy_price=buy_price,
        manual_market_price=manual_market_price, sell_price=asking_price,
        image_uri=image_uri if image_uri else None, location=location
    )
    if product_id:
        flash(f"Sealed product '{product_name}' added successfully!", 'success')
    else:
        flash(f"Failed to add sealed product. It might already exist with the same details at that location.", 'error')
    return redirect(url_for('index', tab='addSealedProductTab'))

@app.route('/record_sale', methods=['POST'])
def record_sale_route():
    item_id_with_prefix = request.form.get('inventory_card_id')
    quantity_sold_str = request.form.get('quantity_sold')
    sell_price_per_item_str = request.form.get('sell_price_per_item')
    sale_date_str = request.form.get('sale_date')
    notes = request.form.get('sale_notes', '')
    shipping_cost_str = request.form.get('shipping_cost')

    item_type, inventory_item_id = None, None
    if item_id_with_prefix and '-' in item_id_with_prefix:
        parts = item_id_with_prefix.split('-', 1)
        item_type_prefix = parts[0]
        try:
            inventory_item_id = int(parts[1])
            if item_type_prefix == 'card': item_type = 'single_card'
            elif item_type_prefix == 'sealed_product': item_type = 'sealed_product'
        except ValueError: inventory_item_id = None

    quantity_sold, sell_price_per_item, shipping_cost = None, None, None
    try:
        if quantity_sold_str: quantity_sold = int(quantity_sold_str)
        if sell_price_per_item_str: sell_price_per_item = float(sell_price_per_item_str)
        if shipping_cost_str is not None and shipping_cost_str.strip() != '':
            shipping_cost = float(shipping_cost_str)
        else:
            shipping_cost = 0.0
    except ValueError:
        flash('Invalid number format for Quantity, Sell Price, or Shipping Cost.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    if not all([item_type, inventory_item_id is not None, quantity_sold is not None, sell_price_per_item is not None, sale_date_str, shipping_cost is not None]):
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
        original_item_details = f"{original_item['set_code']}-{original_item['collector_number']} {'(Foil)' if original_item['is_foil'] else ''}"
        buy_price_per_item = original_item['buy_price']
    elif item_type == 'sealed_product':
        original_item_name = original_item['product_name']
        original_item_details = f"{original_item['set_name']} - {original_item['product_type']} {'(Collector)' if original_item['is_collectors_item'] else ''}"
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
        flash('Card entry deleted successfully!', 'success')
    else:
        flash('Failed to delete card entry.', 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/delete_sealed_product/<int:product_id>', methods=['POST'])
def delete_sealed_product_route(product_id):
    deleted = database.delete_sealed_product(product_id)
    if deleted:
        flash('Sealed product entry deleted successfully!', 'success')
    else:
        flash('Failed to delete sealed product entry.', 'error')
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

        if quantity_str is not None and quantity_str.strip() != '':
            qty = int(quantity_str)
            if qty < 0: flash('Quantity must be non-negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if qty != original_card['quantity']: data_to_update['quantity'] = qty
        if buy_price_str is not None and buy_price_str.strip() != '':
            price = float(buy_price_str)
            if price < 0: flash('Buy price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if price != original_card['buy_price']: data_to_update['buy_price'] = price
        if asking_price_str is not None:
            ask_price = None if asking_price_str.strip() == '' else float(asking_price_str)
            if ask_price is not None and ask_price < 0: flash('Asking price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab'))
            if ask_price != original_card['sell_price']: data_to_update['sell_price'] = ask_price
        if location_str is not None:
            location = location_str.strip()
            if not location: flash('Location cannot be empty.'); return redirect(url_for('index', tab='inventoryTab'))
            if location != original_card['location']: data_to_update['location'] = location
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
    card_details = scryfall.get_card_details(set_code=card['set_code'], collector_number=card['collector_number'])
    if card_details:
        updated = database.update_card_prices_and_image(
            card_id, card_details['market_price_usd'],
            card_details['foil_market_price_usd'], card_details['image_uri']
        )
        if updated:
            flash(f"Market data for {card_details['name']} refreshed successfully!", 'success')
        else:
            flash(f"Failed to update market data in DB for {card['set_code']}-{card['collector_number']}.", 'error')
    else:
        flash(f"Could not fetch refresh data from Scryfall for {card['set_code']}-{card['collector_number']}.", 'error')
    return redirect(url_for('index', tab='inventoryTab'))

if __name__ == '__main__':
    app.run(debug=True)
