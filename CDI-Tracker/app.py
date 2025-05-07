from flask import Flask, render_template, request, redirect, url_for, flash
import database
import scryfall
import datetime

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_here' 

@app.before_request
def initialize_database():
    database.init_db()

@app.route('/')
def index():
    active_tab = request.args.get('tab', 'inventoryTab') # Default to inventory tab

    inventory_cards_data = database.get_all_cards() # Where quantity > 0
    raw_sales_history_data = database.get_all_sales() # Fetch raw data
    sales_history_data = [] # Prepare a new list for processed data

    for raw_sale_row in raw_sales_history_data:
        sale = dict(raw_sale_row) # Convert SQLite Row to a mutable dictionary
        if isinstance(sale.get('sale_date'), str):
            try:
                # Attempt to parse the string into a date object
                sale['sale_date'] = datetime.datetime.strptime(sale['sale_date'], '%Y-%m-%d').date()
            except ValueError:
                # If parsing fails (e.g., unexpected format or None), leave it as is or handle
                # For template robustness, ensure it can handle None or original string if strftime is conditional
                print(f"Warning: Could not parse sale_date string: {sale.get('sale_date')}")
                # If you want it to be None if unparseable:
                # sale['sale_date'] = None 
        sales_history_data.append(sale)
    
    overall_realized_pl = sum(s['profit_loss'] for s in sales_history_data if s.get('profit_loss') is not None)
    

    processed_inventory_cards = []
    total_inventory_market_value = 0
    total_buy_cost_of_inventory = 0
    
    for card_row in inventory_cards_data:
        card = dict(card_row)
        card['is_foil_bool'] = bool(card['is_foil'])
        
        current_market_price = None
        if card['is_foil_bool'] and card['foil_market_price_usd'] is not None:
            current_market_price = card['foil_market_price_usd']
        elif not card['is_foil_bool'] and card['market_price_usd'] is not None:
            current_market_price = card['market_price_usd']
        card['current_market_price_display'] = current_market_price
        
        card_buy_cost = card['quantity'] * card['buy_price']
        total_buy_cost_of_inventory += card_buy_cost
        card['total_buy_cost'] = card_buy_cost
        
        card_current_market_value = 0
        if current_market_price is not None:
            card_current_market_value = card['quantity'] * current_market_price
            total_inventory_market_value += card_current_market_value
        card['total_current_market_value'] = card_current_market_value
        
        card['market_vs_buy_percentage_display'] = "N/A"
        if current_market_price is not None and card['buy_price'] is not None:
            if card['buy_price'] > 0:
                percentage_diff = ((current_market_price - card['buy_price']) / card['buy_price']) * 100
                card['market_vs_buy_percentage_display'] = percentage_diff
            elif card['buy_price'] == 0 and current_market_price > 0:
                 card['market_vs_buy_percentage_display'] = "Infinite"
            elif card['buy_price'] == 0 and current_market_price == 0:
                 card['market_vs_buy_percentage_display'] = 0.0

        card['potential_pl_at_asking_price_display'] = "N/A (No asking price)"
        if card['sell_price'] is not None: # sell_price is now "Asking Price"
            asking_value = card['quantity'] * card['sell_price']
            potential_pl = asking_value - card_buy_cost
            card['potential_pl_at_asking_price_display'] = potential_pl
        
        processed_inventory_cards.append(card)

    overall_realized_pl = sum(sale['profit_loss'] for sale in sales_history_data)
        
    return render_template('index.html', 
                           inventory_cards=processed_inventory_cards,
                           sales_history=sales_history_data,
                           total_inventory_market_value=total_inventory_market_value, 
                           total_buy_cost_of_inventory=total_buy_cost_of_inventory,
                           overall_realized_pl=overall_realized_pl,
                           active_tab=active_tab,
                           current_date=datetime.date.today().isoformat())


@app.route('/add_card', methods=['POST'])
def add_card_route():
    set_code = request.form.get('set_code')
    collector_number = request.form.get('collector_number')
    quantity = request.form.get('quantity', type=int)
    buy_price = request.form.get('buy_price', type=float)
    is_foil = 'is_foil' in request.form
    location = request.form.get('location', '').strip()
    
    asking_price_str = request.form.get('asking_price')
    asking_price = None
    if asking_price_str:
        try:
            asking_price = float(asking_price_str)
            if asking_price < 0: asking_price = None
        except ValueError:
            asking_price = None

    if not all([set_code, collector_number, quantity, buy_price is not None, location is not None]): # Location is now required
        flash('Missing form data for required fields. Set, Number, Qty, Buy Price, and Location are required.', 'error')
        return redirect(url_for('index', tab='addCardTab'))

    if quantity <= 0 or buy_price < 0:
        flash('Quantity must be positive and buy price cannot be negative.', 'error')
        return redirect(url_for('index', tab='addCardTab'))

    card_details = scryfall.get_card_details(set_code, collector_number)

    if card_details:
        added = database.add_card(
            set_code.upper(), collector_number, card_details['name'],
            quantity, buy_price, is_foil,
            card_details['market_price_usd'], card_details['foil_market_price_usd'],
            card_details['image_uri'], asking_price, location
        )
        if added:
            flash(f"Card {card_details['name']} added to inventory at '{location}'!", 'success')
        else:
            flash(f"Failed to add card. It might already exist at that location or another error occurred.", 'error')
    else:
        flash(f"Could not fetch card details for {set_code.upper()}-{collector_number} from Scryfall.", 'error')
        
    return redirect(url_for('index', tab='addCardTab'))


@app.route('/record_sale', methods=['POST'])
def record_sale_route():
    inventory_card_id = request.form.get('inventory_card_id', type=int)
    quantity_sold = request.form.get('quantity_sold', type=int)
    sell_price_per_item = request.form.get('sell_price_per_item', type=float)
    sale_date_str = request.form.get('sale_date')

    if not all([inventory_card_id, quantity_sold, sell_price_per_item is not None, sale_date_str]):
        flash('Missing data for recording sale. Please fill all fields.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    if quantity_sold <= 0 or sell_price_per_item < 0:
        flash('Quantity sold must be positive and sell price cannot be negative.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))
    
    try:
        sale_date = datetime.datetime.strptime(sale_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid sale date format. Please use YYYY-MM-DD.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))


    inventory_card = database.get_card_by_id(inventory_card_id)

    if not inventory_card:
        flash('Inventory item not found.', 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    if quantity_sold > inventory_card['quantity']:
        flash(f"Cannot sell {quantity_sold} item(s). Only {inventory_card['quantity']} available in stock for '{inventory_card['name']}' at '{inventory_card['location']}'.", 'error')
        return redirect(url_for('index', tab='enterSaleTab'))

    sale_added = database.add_sale_record(
        card_name=inventory_card['name'],
        set_code=inventory_card['set_code'],
        collector_number=inventory_card['collector_number'],
        is_foil=inventory_card['is_foil'],
        quantity_sold=quantity_sold,
        buy_price_per_item=inventory_card['buy_price'],
        sell_price_per_item=sell_price_per_item,
        sale_date=sale_date,
        inventory_card_id=inventory_card_id
    )

    if sale_added:
        database.decrease_card_quantity(inventory_card_id, quantity_sold)
        flash(f"Successfully recorded sale of {quantity_sold} x {inventory_card['name']}.", 'success')
    else:
        flash('Failed to record sale.', 'error')
    
    return redirect(url_for('index', tab='salesHistoryTab'))


@app.route('/delete_card/<int:card_id>', methods=['POST'])
def delete_card_route(card_id):
    # Consider if there are sales linked to this card_id.
    # The DB constraint is ON DELETE SET NULL for sales.inventory_card_id
    database.delete_card(card_id)
    flash('Inventory card entry deleted successfully!', 'success')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/update_card/<int:card_id>', methods=['POST'])
def update_card_route(card_id):
    original_card = database.get_card_by_id(card_id)
    if not original_card:
        flash('Card not found.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))

    new_quantity_str = request.form.get('quantity')
    new_buy_price_str = request.form.get('buy_price')
    new_asking_price_str = request.form.get('asking_price') # Renamed from sell_price for clarity
    new_location = request.form.get('location', '').strip()


    try:
        new_quantity = int(new_quantity_str) if new_quantity_str else original_card['quantity']
        if new_quantity <= 0: flash('Quantity must be positive.'); return redirect(url_for('index', tab='inventoryTab'))
        
        new_buy_price = float(new_buy_price_str) if new_buy_price_str else original_card['buy_price']
        if new_buy_price < 0: flash('Buy price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab'))

        if new_asking_price_str:
            if new_asking_price_str.strip() == "":
                new_asking_price = None
            else:
                new_asking_price = float(new_asking_price_str)
                if new_asking_price < 0: flash('Asking price cannot be negative if set.'); return redirect(url_for('index', tab='inventoryTab'))
        else: # If field not present or empty string was not intended to clear
            new_asking_price = original_card['sell_price'] # Keep original asking price

        if not new_location and new_location != original_card['location']: # if new_location is empty string but original was not
             flash('Location cannot be empty if it was previously set. Provide a new location or keep original by not submitting field for it implicitly if form allows that behavior (current form will submit empty).'); 
             # This logic might need adjustment based on how empty location updates are handled
             # For now, we assume an empty string is a valid (though perhaps undesirable) location.
             # If location is mandatory, check "if not new_location:"
             pass # allow empty location string for now

    except ValueError:
        flash('Invalid number format for quantity, buy price, or asking price.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))
    
    updated = database.update_card_fields(card_id, new_quantity, new_buy_price, new_asking_price, new_location)
    if updated:
        flash('Card details updated successfully!', 'success')
    else:
        flash('Failed to update card. An identical card might already exist at the new location.', 'error')
    return redirect(url_for('index', tab='inventoryTab'))

@app.route('/refresh_card/<int:card_id>', methods=['POST'])
def refresh_card_route(card_id):
    card = database.get_card_by_id(card_id)
    if not card:
        flash('Card not found for refreshing.', 'error')
        return redirect(url_for('index', tab='inventoryTab'))

    card_details = scryfall.get_card_details(card['set_code'], card['collector_number'])
    if card_details:
        database.update_card_market_data(
            card_id,
            card_details['market_price_usd'],
            card_details['foil_market_price_usd'],
            card_details['image_uri']
        )
        flash(f"Market data for {card_details['name']} refreshed successfully!", 'success')
    else:
        flash(f"Could not refresh market data for {card['set_code']}-{card['collector_number']}.", 'error')
    return redirect(url_for('index', tab='inventoryTab'))


if __name__ == '__main__':
    app.run(debug=True)