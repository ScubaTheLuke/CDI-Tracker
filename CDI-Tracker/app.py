from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv # Add this import
load_dotenv() # Add this line to load variables from .env

import database


from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import database
import scryfall
import datetime
import os
import requests
import csv
import io
import json
from collections import defaultdict 
import math 
import re 
import sys # For the is_foil hack in CSV import, if kept

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_very_secret_key_here_CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECURE')

ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "YOUR_ROBOFLOW_API_KEY_HERE")
ROBOFLOW_MODEL_ENDPOINT = os.environ.get("ROBOFLOW_MODEL_ENDPOINT", "YOUR_ROBOFLOW_MODEL_INFERENCE_URL_HERE")

ITEMS_PER_PAGE = 50 

def format_currency_with_commas(value):
    if value is None: return "$0.00"
    try:
        num_value = float(value)
        return f"-${abs(num_value):,.2f}" if num_value < 0 else f"${num_value:,.2f}"
    except (ValueError, TypeError): return str(value)
app.jinja_env.filters['currency_commas'] = format_currency_with_commas

@app.route('/api/all_sets_info')
def api_all_sets_info():
    set_data = scryfall.fetch_all_set_data()
    return jsonify(set_data) if set_data else (jsonify({"error": "Failed to fetch set data from Scryfall"}), 500)

@app.route('/api/scan_card_via_roboflow', methods=['POST'])
def scan_card_via_roboflow_route():
    if ROBOFLOW_API_KEY.startswith("YOUR_") or ROBOFLOW_MODEL_ENDPOINT.startswith("YOUR_"):
        print("Warning: Roboflow API key or endpoint not configured on the server with actual values.")
        return jsonify({"error": "Roboflow API key or endpoint not configured on the server."}), 500
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
    active_tab = request.args.get('tab', 'dashboardTab') # Default to dashboardTab
    page = request.args.get('page', 1, type=int)
    
    query_filter_text = request.args.get('filter_text', '').strip().lower()
    query_filter_type = request.args.get('filter_type', 'all')
    query_filter_location = request.args.get('filter_location', 'all')
    query_filter_set = request.args.get('filter_set', 'all')
    query_filter_foil = request.args.get('filter_foil', 'all')
    query_filter_rarity = request.args.get('filter_rarity', 'all')
    query_filter_card_lang = request.args.get('filter_card_lang', 'all')
    query_filter_condition = request.args.get('filter_condition', 'all')
    query_filter_collector = request.args.get('filter_collector', 'all')
    query_filter_sealed_lang = request.args.get('filter_sealed_lang', 'all')
    query_sort_key = request.args.get('sort_key', 'display_name')
    query_sort_direction = request.args.get('sort_dir', 'asc')

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
    financial_entries = database.get_all_financial_entries()
    sales_events_raw = database.get_all_sale_events_with_items()

    sales_history_data_for_json = []
    for event in sales_events_raw:
        event_copy = dict(event) 
        if isinstance(event_copy.get('sale_date'), datetime.date):
            event_copy['sale_date'] = event_copy['sale_date'].isoformat()
        if isinstance(event_copy.get('date_recorded'), datetime.datetime):
            event_copy['date_recorded'] = event_copy['date_recorded'].isoformat()
        
        processed_items = []
        for item_detail in event_copy.get('items', []):
            item_copy = dict(item_detail)
            processed_items.append(item_copy)
        event_copy['items'] = processed_items
        sales_history_data_for_json.append(event_copy)

    current_month_sale_events_count = 0 
    current_month_sealed_sold_quantity = 0 
    current_month_single_cards_sold_quantity = 0 
    current_month_profit_loss = 0.0 

    today_date_obj = datetime.date.today()
    current_month_val = today_date_obj.month
    current_year_val = today_date_obj.year

    historical_monthly_summary_temp = defaultdict(lambda: {
        'profit_loss': 0.0, 'sales_events_count': 0,
        'single_cards_sold': 0, 'sealed_products_sold': 0
    })

    for event in sales_events_raw: 
        sale_date_obj = event.get('sale_date')
        if not isinstance(sale_date_obj, datetime.date): 
            try: sale_date_obj = datetime.date.fromisoformat(str(sale_date_obj))
            except (ValueError, TypeError): continue

        year_month_key = (sale_date_obj.year, sale_date_obj.month)
        
        event_total_profit = event.get('total_profit_loss', 0.0) or 0.0
        historical_monthly_summary_temp[year_month_key]['profit_loss'] += float(event_total_profit)
        historical_monthly_summary_temp[year_month_key]['sales_events_count'] += 1

        for item_detail in event.get('items', []):
            quantity_sold_val = item_detail.get('quantity_sold', 0)
            item_type_val = item_detail.get('item_type')
            if item_type_val == 'single_card' and quantity_sold_val:
                historical_monthly_summary_temp[year_month_key]['single_cards_sold'] += int(quantity_sold_val)
            elif item_type_val == 'sealed_product' and quantity_sold_val:
                historical_monthly_summary_temp[year_month_key]['sealed_products_sold'] += int(quantity_sold_val)

        if sale_date_obj.month == current_month_val and sale_date_obj.year == current_year_val:
            current_month_profit_loss += float(event_total_profit)
            current_month_sale_events_count += 1 
            for item_detail in event.get('items', []):
                quantity_sold_val = item_detail.get('quantity_sold', 0)
                item_type_val = item_detail.get('item_type')
                if item_type_val == 'single_card' and quantity_sold_val:
                    current_month_single_cards_sold_quantity += int(quantity_sold_val)
                elif item_type_val == 'sealed_product' and quantity_sold_val:
                    current_month_sealed_sold_quantity += int(quantity_sold_val)

    historical_monthly_sales_summary = []
    for (year, month), data in historical_monthly_summary_temp.items():
        historical_monthly_sales_summary.append({
            'year': year, 'month': month, 
            'month_name': datetime.date(year, month, 1).strftime('%B %Y'),
            'profit_loss': data['profit_loss'], 
            'sales_count': data['sales_events_count'], 
            'single_cards_sold': data['single_cards_sold'], 
            'sealed_products_sold': data['sealed_products_sold']
        })
    historical_monthly_sales_summary.sort(key=lambda x: (x['year'], x['month']), reverse=True)

    sales_pl = sum(event.get('total_profit_loss', 0.0) or 0.0 for event in sales_events_raw)

    total_other_income = sum(entry['amount'] for entry in financial_entries if entry['entry_type'] == 'income')
    total_other_expenses = sum(entry['amount'] for entry in financial_entries if entry['entry_type'] == 'expense')

    net_business_pl = sales_pl + total_other_income - total_other_expenses
    
    processed_inventory_cards = []
    total_inventory_market_value_cards = 0
    total_buy_cost_of_inventory_cards = 0
    total_single_cards_quantity = 0  # New counter
    for card_row in inventory_cards_data:
        card = dict(card_row)
        total_single_cards_quantity += card.get('quantity', 0)  # Increment counter
        item = {'type': 'single_card', 'original_id': card['id']}
        item['display_name'] = card.get('name', 'N/A')
        item['quantity'] = card.get('quantity', 0)
        item['location'] = card.get('location', 'N/A')
        item['buy_price'] = card.get('buy_price')
        item['sell_price'] = card.get('sell_price')
        item['image_uri'] = card.get('image_uri')
        item['set_code'] = card.get('set_code')
        item['collector_number'] = card.get('collector_number')
        item['is_foil'] = bool(card.get('is_foil', 0))
        item['rarity'] = card.get('rarity', 'N/A')
        item['language'] = card.get('language', 'N/A')
        item['condition'] = card.get('condition', 'N/A')
        item['total_buy_cost'] = (item['quantity'] * item['buy_price']) if item.get('buy_price') is not None else 0
        total_buy_cost_of_inventory_cards += item['total_buy_cost']
        current_market_price = None
        if item['is_foil'] and card.get('foil_market_price_usd') is not None: current_market_price = card['foil_market_price_usd']
        elif not item['is_foil'] and card.get('market_price_usd') is not None: current_market_price = card['market_price_usd']
        item['current_market_price'] = current_market_price
        item_market_value = 0
        if current_market_price is not None: item_market_value = item['quantity'] * current_market_price; total_inventory_market_value_cards += item_market_value
        item['total_market_value'] = item_market_value; item['market_vs_buy_percentage_display'] = "N/A"
        if current_market_price is not None and item.get('buy_price') is not None:
            if item['buy_price'] > 0: item['market_vs_buy_percentage_display'] = ((current_market_price - item['buy_price']) / item['buy_price']) * 100
            elif item['buy_price'] == 0 and current_market_price > 0: item['market_vs_buy_percentage_display'] = "Infinite"
            elif item['buy_price'] == 0 and current_market_price == 0: item['market_vs_buy_percentage_display'] = 0.0
        item['potential_pl_at_asking_price_display'] = "N/A (No asking price)"
        if item.get('sell_price') is not None and item.get('buy_price') is not None: item['potential_pl_at_asking_price_display'] = (item['quantity'] * item['sell_price']) - item['total_buy_cost']
        processed_inventory_cards.append(item)

    processed_sealed_products = []
    total_inventory_market_value_sealed = 0
    total_buy_cost_of_inventory_sealed = 0
    total_sealed_products_quantity = 0  # New counter
    for product_row in sealed_products_data:
        product = dict(product_row)
        total_sealed_products_quantity += product.get('quantity', 0)  # Increment counter
        item = {'type': 'sealed_product', 'original_id': product['id']}
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
        item['total_buy_cost'] = (item['quantity'] * item['buy_price']) if item.get('buy_price') is not None else 0
        total_buy_cost_of_inventory_sealed += item['total_buy_cost']
        item['current_market_price'] = product.get('manual_market_price')
        item_market_value = 0
        if item['current_market_price'] is not None: item_market_value = item['quantity'] * item['current_market_price']; total_inventory_market_value_sealed += item_market_value
        item['total_market_value'] = item_market_value; item['market_vs_buy_percentage_display'] = "N/A (Manual Price)"; item['potential_pl_at_asking_price_display'] = "N/A (No asking price)"
        if item.get('sell_price') is not None and item.get('buy_price') is not None: item['potential_pl_at_asking_price_display'] = (item['quantity'] * item['sell_price']) - item['total_buy_cost']
        processed_sealed_products.append(item)
    
    all_combined_inventory_items_unfiltered = processed_inventory_cards + processed_sealed_products
    all_locations = sorted(list(set(i.get('location') for i in all_combined_inventory_items_unfiltered if i.get('location'))))
    all_sets_identifiers = sorted(list(set( (i.get('set_code') or i.get('set_name')) if i.get('type') == 'single_card' else i.get('set_name') for i in all_combined_inventory_items_unfiltered if (i.get('set_code') or i.get('set_name')) )))
    all_rarities = sorted(list(set(i.get('rarity') for i in all_combined_inventory_items_unfiltered if i.get('type') == 'single_card' and i.get('rarity'))))
    all_card_languages = sorted(list(set(i.get('language') for i in all_combined_inventory_items_unfiltered if i.get('type') == 'single_card' and i.get('language'))))
    all_sealed_languages = sorted(list(set(i.get('language') for i in all_combined_inventory_items_unfiltered if i.get('type') == 'sealed_product' and i.get('language'))))
    all_conditions_for_template = ['Mint', 'Near Mint', 'Lightly Played', 'Moderately Played', 'Heavily Played', 'Damaged']


    filtered_inventory_items = all_combined_inventory_items_unfiltered
    if query_filter_text: filtered_inventory_items = [i for i in filtered_inventory_items if query_filter_text in str(i.get('display_name', '')).lower() or query_filter_text in str(i.get('set_code', '')).lower() or query_filter_text in str(i.get('set_name', '')).lower() or query_filter_text in str(i.get('location', '')).lower() or (i.get('type') == 'single_card' and query_filter_text in str(i.get('collector_number', '')).lower()) or (i.get('type') == 'single_card' and query_filter_text in str(i.get('rarity', '')).lower()) or query_filter_text in str(i.get('language', '')).lower() or (i.get('type') == 'sealed_product' and query_filter_text in str(i.get('product_type', '')).lower())]
    if query_filter_type != 'all': filtered_inventory_items = [i for i in filtered_inventory_items if i.get('type') == query_filter_type]
    if query_filter_location != 'all': filtered_inventory_items = [i for i in filtered_inventory_items if i.get('location') == query_filter_location]
    if query_filter_set != 'all': filtered_inventory_items = [i for i in filtered_inventory_items if (i.get('type') == 'single_card' and (str(i.get('set_code','')) == query_filter_set or str(i.get('set_name','')) == query_filter_set)) or (i.get('type') == 'sealed_product' and str(i.get('set_name','')) == query_filter_set)]
    
    temp_items_after_type_specific_filters = []
    for item_to_check in filtered_inventory_items:
        keep = True
        if item_to_check.get('type') == 'single_card':
            if query_filter_foil != 'all' and item_to_check.get('is_foil') != (query_filter_foil == 'yes'): keep = False
            if query_filter_rarity != 'all' and item_to_check.get('rarity') != query_filter_rarity: keep = False
            if query_filter_card_lang != 'all' and item_to_check.get('language') != query_filter_card_lang: keep = False
            if query_filter_condition != 'all' and item_to_check.get('condition') != query_filter_condition: keep = False
        elif item_to_check.get('type') == 'sealed_product':
            if query_filter_collector != 'all' and item_to_check.get('is_collectors_item') != (query_filter_collector == 'yes'): keep = False
            if query_filter_sealed_lang != 'all' and item_to_check.get('language') != query_filter_sealed_lang: keep = False
        
        if ( (query_filter_type == 'single_card' and item_to_check.get('type') != 'single_card') or \
             (query_filter_type == 'sealed_product' and item_to_check.get('type') != 'sealed_product') ):
            pass 

        if keep: temp_items_after_type_specific_filters.append(item_to_check)
    filtered_inventory_items = temp_items_after_type_specific_filters

    def get_sort_value(item_to_sort, key):
        val = item_to_sort.get(key)
        if key == 'set_name_sort': 
            s_val = (str(item_to_sort.get('set_code','')) or str(item_to_sort.get('set_name', ''))) if item_to_sort.get('type') == 'single_card' else str(item_to_sort.get('set_name', ''))
            return s_val.lower()
        if isinstance(val, bool): return int(val)
        if isinstance(val, (int, float)): return val if val is not None else -float('inf') if query_sort_direction == 'asc' else float('inf')
        return str(val if val is not None else '').lower()

    try: filtered_inventory_items.sort(key=lambda i_sort: (get_sort_value(i_sort, query_sort_key), get_sort_value(i_sort, 'display_name')), reverse=(query_sort_direction == 'desc'))
    except TypeError as e: print(f"Sorting TypeError for key '{query_sort_key}': {e}. Falling back."); filtered_inventory_items.sort(key=lambda i_sort: get_sort_value(i_sort, 'display_name'), reverse=(query_sort_direction == 'desc'))
    
    total_filtered_item_count = len(filtered_inventory_items)
    total_pages = (total_filtered_item_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_filtered_item_count > 0 else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * ITEMS_PER_PAGE
    paginated_inventory_items_for_display = filtered_inventory_items[offset : offset + ITEMS_PER_PAGE]
    inventory_items_json = json.dumps(paginated_inventory_items_for_display)
    
    total_buy_cost_of_inventory = total_buy_cost_of_inventory_cards + total_buy_cost_of_inventory_sealed
    total_inventory_market_value = total_inventory_market_value_cards + total_inventory_market_value_sealed
    num_unique_card_inventory_entries = len(processed_inventory_cards) 

    sale_inventory_options = []
    temp_sorted_for_sale_options = sorted(all_combined_inventory_items_unfiltered, key=lambda x_sort: x_sort.get('display_name', '').lower())
    for item_s_opt in temp_sorted_for_sale_options:
        display_text_val = f"{item_s_opt['display_name']} "
        if item_s_opt['type'] == 'single_card': 
            condition_str = f"C: {item_s_opt.get('condition','N/A')}, "
            display_text_val += f"({item_s_opt.get('set_code','N/A').upper()}-{item_s_opt.get('collector_number','N/A')}) {'(Foil)' if item_s_opt.get('is_foil') else ''} (R: {item_s_opt.get('rarity','N/A')}, L: {item_s_opt.get('language','N/A')}, {condition_str}BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        else: 
            display_text_val += f"({item_s_opt.get('set_name','N/A')} / {item_s_opt.get('product_type','N/A')}){' (Collector)' if item_s_opt.get('is_collectors_item') else ''} (L: {item_s_opt.get('language','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        sale_inventory_options.append({"id": f"{item_s_opt['type']}-{item_s_opt['original_id']}", "display": display_text_val, "type": item_s_opt['type']})
    sale_inventory_options_json = json.dumps(sale_inventory_options)

    return render_template('index.html',
                           inventory_items_json=inventory_items_json,
                           sales_history_json=json.dumps(sales_history_data_for_json),
                           sale_inventory_options_json=sale_inventory_options_json,
                           total_inventory_market_value=total_inventory_market_value,
                           total_buy_cost_of_inventory=total_buy_cost_of_inventory,
                           total_single_cards_quantity=total_single_cards_quantity,
                           total_sealed_products_quantity=total_sealed_products_quantity,
                           sales_pl=sales_pl,
                           net_business_pl=net_business_pl,
                           num_unique_card_inventory_entries=num_unique_card_inventory_entries,
                           current_month_sales_count=current_month_sale_events_count,
                           current_month_sealed_sold_quantity=current_month_sealed_sold_quantity,
                           current_month_single_cards_sold_quantity=current_month_single_cards_sold_quantity,
                           current_month_profit_loss=current_month_profit_loss,
                           current_month_name=today_date_obj.strftime("%B"),
                           historical_monthly_sales_summary=historical_monthly_sales_summary,
                           active_tab=active_tab,
                           current_date=datetime.date.today().isoformat(),
                           suggested_buy_price=suggested_buy_price,
                           from_pack_details=from_pack_details,
                           current_page=page, total_pages=total_pages,
                           filter_text=query_filter_text, 
                           filter_type=query_filter_type, 
                           filter_location=query_filter_location, 
                           filter_set=query_filter_set, 
                           filter_foil=query_filter_foil, 
                           filter_rarity=query_filter_rarity, 
                           filter_card_lang=query_filter_card_lang, 
                           filter_condition=query_filter_condition, 
                           filter_collector=query_filter_collector, 
                           filter_sealed_lang=query_filter_sealed_lang, 
                           sort_key=query_sort_key, 
                           sort_dir=query_sort_direction,
                           all_locations=all_locations, 
                           all_sets_identifiers=all_sets_identifiers, 
                           all_rarities=all_rarities, 
                           all_card_languages=all_card_languages, 
                           all_sealed_languages=all_sealed_languages, 
                           all_conditions=all_conditions_for_template,
                           financial_entries=financial_entries
                           )



@app.route('/record_multi_item_sale', methods=['POST'])
def record_multi_item_sale_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received."}), 400

        sale_date_str = data.get('sale_date')
        total_shipping_cost_str = data.get('total_shipping_cost', '0.0') 
        overall_notes = data.get('notes', '')
        items_data = data.get('items')

        customer_shipping_charge_str = data.get('customer_shipping_charge', '0.0')
        platform_fee_str = data.get('platform_fee', '0.0')

        if not sale_date_str or not isinstance(items_data, list) or not items_data:
            flash('Missing sale date or items data.', 'error') 
            return jsonify({"success": False, "message": "Missing sale date or items list is empty."}), 400

        sale_event_id, message = database.record_multi_item_sale(
            sale_date_str, 
            total_shipping_cost_str, 
            overall_notes, 
            items_data,
            customer_shipping_charge_str, 
            platform_fee_str
        )

        if sale_event_id:
            flash(f"Sale event (ID: {sale_event_id}) recorded. {message}", 'success')
            return jsonify({"success": True, "message": f"Sale event (ID: {sale_event_id}) recorded.", "sale_event_id": sale_event_id})
        else:
            flash(f"Failed to record sale event. Reason: {message}", 'error')
            return jsonify({"success": False, "message": f"Failed to record sale event. Reason: {message}"}), 400
    except Exception as e:
        print(f"Error in /record_multi_item_sale route: {e}")
        flash(f"An error occurred: {str(e)}", 'error')
        return jsonify({"success": False, "message": f"An internal error occurred: {str(e)}"}), 500

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
    except (ValueError, TypeError) : 
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
    if not all([product_id, quantity_opened is not None, total_cost_opened_str, num_singles_to_add_str]): 
        flash("Missing data to finalize opening.", "error")
        return redirect(url_for('index', tab='inventoryTab'))
    try: 
        num_singles_to_add = int(num_singles_to_add_str)
        total_cost_opened = float(total_cost_opened_str)
    except ValueError: 
        flash("Invalid number for singles or cost.", "error")
        session['open_sealed_data'] = {'product_id': product_id, 'quantity_opened': quantity_opened, 'total_cost_opened': total_cost_opened_str, 'product_name': product_name}
        return redirect(url_for('confirm_open_sealed_page_route'))
    if num_singles_to_add <= 0: 
        flash("Number of singles to add must be positive.", "error")
        session['open_sealed_data'] = {'product_id': product_id, 'quantity_opened': quantity_opened, 'total_cost_opened': total_cost_opened, 'product_name': product_name}
        return redirect(url_for('confirm_open_sealed_page_route'))
    
    average_buy_price = round(total_cost_opened / num_singles_to_add, 2) if num_singles_to_add > 0 else 0.0
    success, message = database.update_sealed_product_quantity(product_id, -quantity_opened)
    if success: 
        flash_message = (f"Opened {quantity_opened} x '{product_name}'. Cost: {format_currency_with_commas(total_cost_opened)}. "
                         f"Add {num_singles_to_add} singles. Avg. buy price: {format_currency_with_commas(average_buy_price)} each.")
        flash(flash_message, "success")
        return redirect(url_for('index', tab='addItemsTab', suggested_buy_price=average_buy_price, 
                        from_pack_name=product_name, from_pack_cost=total_cost_opened, 
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
    rarity_input = request.form.get('rarity', '').strip()
    language_input = request.form.get('language', 'en').strip()
    condition_input = request.form.get('condition', 'Near Mint').strip()

    try:
        quantity = int(quantity_str) if quantity_str else None
        buy_price = float(buy_price_str) if buy_price_str else None
        asking_price = float(asking_price_str) if asking_price_str and asking_price_str.strip() != '' else None
        if asking_price is not None and asking_price < 0: asking_price = None
    except (ValueError, TypeError): 
        flash('Invalid number format.', 'error'); return redirect(url_for('index', tab='addItemsTab'))

    if buy_price is None: flash('Buy Price is required.', 'error'); return redirect(url_for('index', tab='addItemsTab'))
    
    set_code_for_lookup = set_code_input or None
    collector_number_for_lookup = collector_number_input or None
    card_name_for_lookup = card_name_input or None
    language_for_lookup = language_input if language_input and language_input != "" else None

    if not ( (set_code_for_lookup and collector_number_for_lookup) or \
             (set_code_for_lookup and card_name_for_lookup) or \
             (card_name_for_lookup and collector_number_for_lookup and not set_code_for_lookup) or \
             (card_name_for_lookup and not set_code_for_lookup and not collector_number_for_lookup) ): 
        flash('Lookup requires: (Set & CN), (Set & Name), (Name & CN), or (Name only).', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    if quantity is None or not location: 
        flash('Quantity and Location required.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    if quantity <= 0 or buy_price < 0: 
        flash('Quantity must be positive; Buy Price non-negative.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    card_details = scryfall.get_card_details(card_name=card_name_for_lookup, set_code=set_code_for_lookup, collector_number=collector_number_for_lookup, lang=language_for_lookup)
    if card_details and all(k in card_details for k in ['name', 'collector_number', 'set_code']):
        final_set_code = card_details['set_code']; final_collector_number = card_details['collector_number']
        scryfall_uuid = card_details.get('id')
        final_rarity = card_details.get('rarity', rarity_input if rarity_input else 'unknown').lower()
        final_language = card_details.get('language', language_input if language_input else 'en').lower()
        
        card_id = database.add_card( 
            final_set_code.upper(), final_collector_number, card_details['name'], quantity, buy_price, is_foil, 
            card_details['market_price_usd'], card_details['foil_market_price_usd'], 
            card_details['image_uri'], asking_price, location, scryfall_uuid, 
            final_rarity, final_language, condition_input
        )
        if card_id:
            flash(f"Successfully handled '{card_details['name']}' [{condition_input}].", 'success')
        else:
            flash(f"Failed to add/update card '{card_details['name']}'. Check server logs.", 'error')
    else: flash(f"Could not fetch valid card details from Scryfall for the provided input.", 'error')
    return redirect(url_for('index', tab='addItemsTab'))

@app.route('/add_sealed_product', methods=['POST'])
def add_sealed_product_route():
    product_name = request.form.get('product_name', '').strip()
    set_name = request.form.get('set_name', '').strip()
    product_type = request.form.get('product_type', '').strip()
    language = request.form.get('language', 'en').strip()
    is_collectors_item = 'is_collectors_item' in request.form
    quantity_str = request.form.get('quantity')
    buy_price_str = request.form.get('buy_price')
    manual_market_price_str = request.form.get('manual_market_price')
    asking_price_str = request.form.get('asking_price')
    image_uri = request.form.get('image_uri', '').strip()
    location = request.form.get('location', '').strip()

    if not all([product_name, set_name, product_type, location]): 
        flash('Product Name, Set Name, Product Type, and Location are required.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    try:
        quantity = int(quantity_str) if quantity_str else None
        buy_price = float(buy_price_str) if buy_price_str else None
        manual_market_price = float(manual_market_price_str) if manual_market_price_str and manual_market_price_str.strip() != '' else None
        if manual_market_price is not None and manual_market_price < 0 : manual_market_price = None
        asking_price = float(asking_price_str) if asking_price_str and asking_price_str.strip() != '' else None
        if asking_price is not None and asking_price < 0: asking_price = None
    except ValueError: 
        flash('Invalid number format.', 'error'); return redirect(url_for('index', tab='addItemsTab'))

    if quantity is None or buy_price is None: 
        flash('Quantity and Buy Price are required.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    if quantity <= 0 or buy_price < 0: 
        flash('Quantity must be positive; Buy Price non-negative.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    
    product_id = database.add_sealed_product(
        product_name=product_name, set_name=set_name, product_type=product_type, language=language, 
        is_collectors_item=is_collectors_item, quantity=quantity, buy_price=buy_price, 
        manual_market_price=manual_market_price, sell_price=asking_price, 
        image_uri=image_uri if image_uri else None, location=location
    )
    if product_id: flash(f"Sealed product '{product_name}' (BP: {format_currency_with_commas(buy_price)}) added/updated!", 'success')
    else: flash(f"Failed to add/update sealed product. Possible duplicate or DB issue.", 'error')
    return redirect(url_for('index', tab='addItemsTab'))

@app.route('/delete_card/<int:card_id>', methods=['POST'])
def delete_card_route(card_id):
    deleted = database.delete_card(card_id)
    flash('Card entry deleted!' if deleted else 'Failed to delete card entry.', 'success' if deleted else 'error')
    return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page', 1)))

@app.route('/delete_sealed_product/<int:product_id>', methods=['POST'])
def delete_sealed_product_route(product_id):
    deleted = database.delete_sealed_product(product_id)
    flash('Sealed product entry deleted!' if deleted else 'Failed to delete sealed product.', 'success' if deleted else 'error')
    return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page', 1)))


@app.route('/delete_sale_event/<int:event_id>', methods=['POST'])
def delete_sale_event_route(event_id):
    success, message = database.delete_sale_event(event_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('index', tab='salesHistoryTab')) 




@app.route('/add_financial_entry', methods=['POST'])
def add_financial_entry_route():
    try:
        entry_date = request.form.get('entry_date')
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        entry_type = request.form.get('entry_type')
        amount_str = request.form.get('amount')
        notes = request.form.get('notes', '').strip()

        if not all([entry_date, description, entry_type, amount_str]):
            flash('Date, Description, Type, and Amount are required.', 'error')
            return redirect(url_for('index', tab='businessLedgerTab'))

        amount = float(amount_str)
        if amount <= 0:
            flash('Amount must be positive.', 'error')
            return redirect(url_for('index', tab='businessLedgerTab'))

        new_id = database.add_financial_entry(entry_date, description, category, entry_type, amount, notes)
        if new_id:
            flash(f"Financial entry '{description}' added successfully.", 'success')
        else:
            flash('Failed to add financial entry.', 'error')

    except (ValueError, TypeError):
        flash('Invalid amount format. Please enter a valid number.', 'error')
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'error')

    return redirect(url_for('index', tab='businessLedgerTab'))

@app.route('/delete_financial_entry/<int:entry_id>', methods=['POST'])
def delete_financial_entry_route(entry_id):
    deleted = database.delete_financial_entry(entry_id)
    if deleted:
        flash('Financial entry deleted successfully.', 'success')
    else:
        flash('Failed to delete financial entry.', 'error')
    return redirect(url_for('index', tab='businessLedgerTab'))

@app.route('/update_card/<int:card_id>', methods=['POST'])
def update_card_route(card_id):
    data_to_update = {}
    original_card = database.get_card_by_id(card_id)
    if not original_card: flash('Card not found for update.', 'error'); return redirect(url_for('index', tab='inventoryTab'))
    try:
        if request.form.get('quantity') is not None and request.form.get('quantity').strip() != '': 
            qty = int(request.form.get('quantity'))
            if qty < 0: flash('Quantity must be non-negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if qty != original_card['quantity']: data_to_update['quantity'] = qty
        if request.form.get('buy_price') is not None and request.form.get('buy_price').strip() != '': 
            price = float(request.form.get('buy_price'))
            if price < 0: flash('Buy price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if abs(price - original_card['buy_price']) > 1e-9 : data_to_update['buy_price'] = price
        if request.form.get('asking_price') is not None:
            ask_price_str = request.form.get('asking_price').strip()
            ask_price = float(ask_price_str) if ask_price_str != '' else None
            if ask_price is not None and ask_price < 0: flash('Asking price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if ask_price != original_card['sell_price']: data_to_update['sell_price'] = ask_price
        if request.form.get('location') is not None:
            location = request.form.get('location').strip()
            if not location: flash('Location cannot be empty.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if location != original_card['location']: data_to_update['location'] = location
        if request.form.get('condition') is not None:
            condition = request.form.get('condition').strip()
            if condition != original_card['condition']: data_to_update['condition'] = condition
    except ValueError: flash('Invalid number format for update.', 'error'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))

    if not data_to_update: flash('No changes detected to update.', 'warning')
    else:
        success, message = database.update_card_fields(card_id, data_to_update)
        flash(f'Card details updated! {message}' if success else f'Failed to update card. {message}', 'success' if success else 'error')
    return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page', 1)))

@app.route('/update_sealed_product/<int:product_id>', methods=['POST'])
def update_sealed_product_route(product_id):
    data_to_update = {}
    original_product = database.get_sealed_product_by_id(product_id)
    if not original_product: flash('Product not found for update.', 'error'); return redirect(url_for('index', tab='inventoryTab'))
    try:
        if request.form.get('quantity') is not None and request.form.get('quantity').strip() != '':
            qty = int(request.form.get('quantity'));
            if qty < 0: flash('Quantity must be non-negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if qty != original_product['quantity']: data_to_update['quantity'] = qty
        if request.form.get('buy_price') is not None and request.form.get('buy_price').strip() != '':
            price = float(request.form.get('buy_price'));
            if price < 0: flash('Buy price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if abs(price - original_product['buy_price']) > 1e-9: data_to_update['buy_price'] = price
        if request.form.get('manual_market_price') is not None:
            mkt_str = request.form.get('manual_market_price').strip(); mkt_price = float(mkt_str) if mkt_str != '' else None;
            if mkt_price is not None and mkt_price < 0: flash('Market Price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if mkt_price != original_product['manual_market_price']: data_to_update['manual_market_price'] = mkt_price
        if request.form.get('asking_price') is not None:
            ask_str = request.form.get('asking_price').strip(); ask_price = float(ask_str) if ask_str != '' else None;
            if ask_price is not None and ask_price < 0: flash('Asking price cannot be negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if ask_price != original_product['sell_price']: data_to_update['sell_price'] = ask_price
        if request.form.get('location') is not None:
            loc = request.form.get('location').strip();
            if not loc: flash('Location cannot be empty.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if loc != original_product['location']: data_to_update['location'] = loc
        if request.form.get('image_uri') is not None:
            img_uri = request.form.get('image_uri').strip(); img_uri = img_uri if img_uri else None;
            if img_uri != original_product['image_uri']: data_to_update['image_uri'] = img_uri
        if request.form.get('language') is not None:
            lang = request.form.get('language').strip();
            if lang != original_product['language']: data_to_update['language'] = lang
        is_collectors_item_form = 'is_collectors_item' in request.form
        if is_collectors_item_form != bool(original_product['is_collectors_item']): data_to_update['is_collectors_item'] = is_collectors_item_form
    except ValueError: flash('Invalid number format for update.', 'error'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
    if not data_to_update: flash('No changes detected to update.', 'warning')
    else:
        success, message = database.update_sealed_product_fields(product_id, data_to_update)
        flash(f'Sealed product details updated! {message}' if success else f'Failed to update. {message}', 'success' if success else 'error')
    return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page', 1)))

@app.route('/refresh_card/<int:card_id>', methods=['POST'])
def refresh_card_route(card_id):
    card = database.get_card_by_id(card_id)
    if not card: flash('Card not found for refreshing.', 'error'); return redirect(url_for('index', tab='inventoryTab'))
    card_lang = card['language'] if 'language' in card and card['language'] else None
    card_details = scryfall.get_card_details(set_code=card['set_code'], collector_number=card['collector_number'], lang=card_lang)
    if card_details:
        updated = database.update_card_prices_and_image(card_id, card_details['market_price_usd'], card_details['foil_market_price_usd'], card_details['image_uri'])
        flash('Market data refreshed successfully!' if updated else 'Failed to update market data in DB.', 'success' if updated else 'error')
    else: flash(f"Could not fetch refresh data from Scryfall for {card['set_code']}-{card['collector_number']}.", 'error')
    return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page', 1)))


@app.route('/import_csv', methods=['POST'])
def import_csv_route():
    if 'csv_file' not in request.files:
        flash('No CSV file part in the request.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    file = request.files['csv_file']
    if file.filename == '':
        flash('No CSV file selected for uploading.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    # Get default values from form
    default_buy_price_str = request.form.get('default_buy_price', '0.00')
    default_location = request.form.get('default_location', 'Imported Batch')
    default_asking_price_str = request.form.get('default_asking_price')
    default_language_csv = request.form.get('default_language_csv', 'en').strip().lower()
    default_condition_csv = request.form.get('default_condition_csv', 'Near Mint').strip()
    assume_non_foil = 'assume_non_foil' in request.form
    
    try:
        default_buy_price = float(default_buy_price_str)
        default_asking_price = float(default_asking_price_str) if default_asking_price_str and default_asking_price_str.strip() != '' else None
    except (ValueError, TypeError):
        flash('Invalid default price format.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    if not default_location.strip():
        flash('Default location cannot be empty.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    if not file or not file.filename.endswith('.csv'):
        flash('Invalid file type. Please upload a CSV file.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    # --- Aggregation Logic ---
    card_aggregator = defaultdict(lambda: {'quantity': 0, 'details': {}})
    errors_list = []
    skipped_count = 0

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8", errors='replace'), newline=None)
        csv_reader = csv.DictReader(stream)
        
        if not csv_reader.fieldnames:
             flash('CSV file appears to be empty or has no headers.', 'error')
             return redirect(url_for('index', tab='addItemsTab'))
        
        # Normalize headers to be more forgiving
        csv_reader.fieldnames = [hdr.lower().strip().replace(' ', '_') for hdr in csv_reader.fieldnames if hdr]

        for row_num, row_raw in enumerate(csv_reader, start=1):
            row = {k: v.strip() if isinstance(v, str) else v for k, v in row_raw.items()}

            card_name = row.get('name')
            set_code = row.get('set_code') or row.get('set')
            collector_number = row.get('card_number') or row.get('collector_number')
            quantity_str = row.get('quantity')
            printing_str = row.get('printing', 'normal').lower()
            
            if not all([card_name, quantity_str]):
                errors_list.append(f"Row {row_num}: Missing required 'Name' or 'Quantity' column. Skipping.")
                skipped_count += 1
                continue
            
            try:
                quantity = int(quantity_str)
                if quantity <= 0:
                    errors_list.append(f"Row {row_num}: Quantity for '{card_name}' must be positive. Skipping.")
                    skipped_count += 1
                    continue
            except (ValueError, TypeError):
                errors_list.append(f"Row {row_num}: Invalid quantity for '{card_name}'. Skipping.")
                skipped_count += 1
                continue
            
            is_foil = not assume_non_foil and 'foil' in printing_str

            # Create a unique key based on the most specific data available
            unique_key = (card_name, set_code, collector_number, is_foil, default_location, default_buy_price, default_condition_csv)
            
            card_aggregator[unique_key]['quantity'] += quantity
            if not card_aggregator[unique_key]['details']:
                 card_aggregator[unique_key]['details'] = {
                     'name': card_name, 'set_code': set_code, 'collector_number': collector_number,
                     'is_foil': is_foil, 'buy_price': default_buy_price, 'sell_price': default_asking_price, 
                     'location': default_location, 'language': default_language_csv, 'condition': default_condition_csv,
                     'rarity': row.get('rarity')
                 }

    except Exception as e:
        flash(f'Critical error reading or processing CSV file: {e}', 'error')
        import traceback; traceback.print_exc()
        return redirect(url_for('index', tab='addItemsTab'))

    # --- Process the aggregated data with robust lookup ---
    imported_count = 0
    failed_count = 0
    
    for key, data in card_aggregator.items():
        card_info = data['details']
        total_quantity = data['quantity']
        
        # --- NEW ROBUST LOOKUP SEQUENCE ---
        card_details = None
        # Attempt 1: Most specific (Set + CN). This is fast.
        if card_info.get('set_code') and card_info.get('collector_number'):
            card_details = scryfall.get_card_details(set_code=card_info['set_code'], collector_number=card_info['collector_number'], lang=card_info['language'])
        
        # Attempt 2: Fallback to Name + Set (e.g., for promos without a CN)
        if not card_details and card_info.get('name') and card_info.get('set_code'):
             card_details = scryfall.get_card_details(card_name=card_info['name'], set_code=card_info['set_code'], lang=card_info['language'])

        # Attempt 3: Final fallback to just the Name. This will find *a* version of the card.
        if not card_details and card_info.get('name'):
            card_details = scryfall.get_card_details(card_name=card_info['name'], lang=card_info['language'])
        
        if card_details and all(k in card_details for k in ['name', 'collector_number', 'set_code']):
            final_rarity = card_details.get('rarity', card_info.get('rarity', 'unknown')).lower()
            final_language = card_details.get('language', card_info['language']).lower()
            
            card_id = database.add_card(
                set_code=card_details['set_code'].upper(), collector_number=card_details['collector_number'], 
                name=card_details['name'], quantity=total_quantity, buy_price=card_info['buy_price'], 
                is_foil=card_info['is_foil'], market_price_usd=card_details['market_price_usd'], 
                foil_market_price_usd=card_details['foil_market_price_usd'], image_uri=card_details['image_uri'], 
                sell_price=card_info['sell_price'], location=card_info['location'], 
                scryfall_id=card_details.get('id'), rarity=final_rarity, language=final_language, 
                condition=card_info['condition']
            )

            if card_id:
                imported_count += 1
            else:
                failed_count += 1
                errors_list.append(f"DB error for '{card_info['name']}' ({card_info.get('set_code')}).")
        else:
            failed_count += 1
            errors_list.append(f"Scryfall lookup failed for '{card_info['name']}' ({card_info.get('set_code') or 'N/A'}-{card_info.get('collector_number') or 'N/A'}).")

    # --- Final Flash Messaging ---
    summary_message = f"CSV Import Finished: {imported_count} unique card stacks processed."
    if failed_count > 0: summary_message += f" {failed_count} failed."
    if skipped_count > 0: summary_message += f" {skipped_count} rows skipped."
    
    flash_category = 'success' if imported_count > 0 and not errors_list else ('warning' if imported_count > 0 and errors_list else 'error')
    flash(summary_message, flash_category)
    
    if errors_list:
        [flash(err, 'error') for err in errors_list[:10]]
        if len(errors_list) > 10:
            flash(f"...and {len(errors_list) - 10} more errors (see server console for full list).", 'error')
        print("--- Detailed CSV Import Errors ---\n" + "\n".join(errors_list) + "\n---------------------------------")
        
    return redirect(url_for('index', tab='addItemsTab'))


import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)