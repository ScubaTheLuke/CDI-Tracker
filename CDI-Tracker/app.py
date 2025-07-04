from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
load_dotenv()

import database
import scryfall
import datetime
import os
import csv
import io
import json
from collections import defaultdict
import math
import re
import sys

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_very_secret_key_here_CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECURE')

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

@app.route('/')
def index():
    active_tab = request.args.get('tab', 'dashboardTab')
    page = request.args.get('page', 1, type=int)

    query_filter_text = request.args.get('filter_text', '').strip().lower()
    query_filter_type = request.args.get('filter_type', 'all')
    query_filter_location = request.args.get('filter_location', 'all')
    query_filter_set = request.args.get('filter_set', 'all')
    query_filter_foil = request.args.get('filter_foil', 'all')
    query_filter_rarity = request.args.get('filter_rarity', 'all')
    query_filter_card_lang = request.args.get('filter_card_lang', 'all')
    query_filter_condition = request.args.get('filter_condition', 'all')
    # Corrected variable names defined here:
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
    shipping_supplies_data = database.get_all_shipping_supplies()
    shipping_supply_presets = database.get_all_shipping_supply_presets()


    processed_shipping_supplies = []
    total_shipping_supplies_quantity = 0
    total_shipping_supplies_value = 0
    for supply_row in shipping_supplies_data:
        supply = dict(supply_row) # Convert DictRow to dict
        total_shipping_supplies_quantity += supply.get('quantity_on_hand', 0)
        total_shipping_supplies_value += (supply.get('quantity_on_hand', 0) * supply.get('cost_per_unit', 0))

        # Convert date objects to string for JSON serialization
        if isinstance(supply.get('purchase_date'), datetime.date):
            supply['purchase_date'] = supply['purchase_date'].isoformat()
        if isinstance(supply.get('date_added'), datetime.datetime):
            supply['date_added'] = supply['date_added'].isoformat()
        if isinstance(supply.get('last_updated'), datetime.datetime):
            supply['last_updated'] = supply['last_updated'].isoformat()

        processed_shipping_supplies.append(supply)


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
    
    total_supplies_cost_deducted_in_sales_pl = sum(
        event.get('total_supplies_cost_for_sale', 0.0) or 0.0
        for event in sales_events_raw
    )
    app.logger.info(f"DEBUG: Total Shipping Supplies Cost Used in Sales (All Time): ${total_supplies_cost_deducted_in_sales_pl:,.2f}")



    total_cogs = 0.0
    total_gross_sales = 0.0
    for event in sales_events_raw:
        for item_detail in event.get('items', []):
            quantity_sold = item_detail.get('quantity_sold', 0)
            buy_price = item_detail.get('buy_price_per_item', 0.0)
            sell_price = item_detail.get('sell_price_per_item', 0.0)
            total_cogs += (buy_price * quantity_sold)
            total_gross_sales += (sell_price * quantity_sold)

    total_other_income = sum(entry['amount'] for entry in financial_entries if entry['entry_type'] == 'income')
    total_other_expenses = sum(entry['amount'] for entry in financial_entries if entry['entry_type'] == 'expense') # Keep this for ledger display



    net_business_pl = sales_pl + total_other_income - total_other_expenses + total_supplies_cost_deducted_in_sales_pl

    processed_inventory_cards = []
    total_inventory_market_value_cards = 0
    total_buy_cost_of_inventory_cards = 0
    total_single_cards_quantity = 0
    for card_row in inventory_cards_data:
        card = dict(card_row)
        total_single_cards_quantity += card.get('quantity', 0)
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
    total_sealed_products_quantity = 0
    for product_row in sealed_products_data:
        product = dict(product_row)
        total_sealed_products_quantity += product.get('quantity', 0)
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

    processed_shipping_supplies = []
    total_shipping_supplies_quantity = 0
    total_shipping_supplies_value = 0
    for supply_row in shipping_supplies_data:
        supply = dict(supply_row) # Convert DictRow to dict
        total_shipping_supplies_quantity += supply.get('quantity_on_hand', 0)
        total_shipping_supplies_value += (supply.get('quantity_on_hand', 0) * supply.get('cost_per_unit', 0))

        # Convert date objects to string for JSON serialization
        if isinstance(supply.get('purchase_date'), datetime.date):
            supply['purchase_date'] = supply['purchase_date'].isoformat()
        if isinstance(supply.get('date_added'), datetime.datetime):
            supply['date_added'] = supply['date_added'].isoformat()
        if isinstance(supply.get('last_updated'), datetime.datetime):
            supply['last_updated'] = supply['last_updated'].isoformat()

        processed_shipping_supplies.append(supply)

    # 1. Combine all raw inventory items into one list for initial filtering
    all_combined_inventory_items_for_filtering = []
    for item in processed_inventory_cards:
        item['internal_type'] = 'single_card'
        all_combined_inventory_items_for_filtering.append(item)
    for item in processed_sealed_products:
        item['internal_type'] = 'sealed_product'
        all_combined_inventory_items_for_filtering.append(item)
    for item in processed_shipping_supplies:
        item['internal_type'] = 'shipping_supply'
        item['display_name'] = item.get('supply_name', 'N/A') # Ensure display_name for supplies here
        all_combined_inventory_items_for_filtering.append(item)


    # Start with the full combined list
    filtered_inventory_items = all_combined_inventory_items_for_filtering


    # 2. Apply query_filter_type first
    if query_filter_type != 'all':
        filtered_inventory_items = [
            item for item in filtered_inventory_items
            if item.get('internal_type') == query_filter_type
        ]

    # 3. Apply text search filter
    if query_filter_text:
        filtered_inventory_items = [item for item in filtered_inventory_items if
            query_filter_text in str(item.get('display_name', '')).lower() or # Use display_name here
            (item.get('internal_type') == 'single_card' and (query_filter_text in str(item.get('set_code', '')).lower() or query_filter_text in str(item.get('collector_number', '')).lower() or query_filter_text in str(item.get('rarity', '')).lower() or query_filter_text in str(item.get('language', '')).lower())) or
            (item.get('internal_type') == 'sealed_product' and (query_filter_text in str(item.get('set_name', '')).lower() or query_filter_text in str(item.get('product_type', '')).lower() or query_filter_text in str(item.get('language', '')).lower())) or
            (item.get('internal_type') == 'shipping_supply' and (query_filter_text in str(item.get('description', '')).lower() or query_filter_text in str(item.get('unit_of_measure', '')).lower())) or
            query_filter_text in str(item.get('location', '')).lower()
        ]

    # 4. Apply location filter
    if query_filter_location != 'all':
        filtered_inventory_items = [
            item for item in filtered_inventory_items
            if item.get('location') == query_filter_location
        ]

    # 5. Apply set filter (This is the key filter for the user's current problem)
    if query_filter_set != 'all':
        filtered_inventory_items = [
            item for item in filtered_inventory_items
            if (
                item.get('internal_type') == 'single_card' and
                (str(item.get('set_code','')) == query_filter_set or str(item.get('set_name','')) == query_filter_set)
            ) or (
                item.get('internal_type') == 'sealed_product' and
                str(item.get('set_name','')) == query_filter_set
            )
        ]

    # 6. Apply type-specific filters (foil, rarity, condition, collector, language)
    temp_items_after_type_specific_filters = []
    for item_to_check in filtered_inventory_items:
        keep = True
        if item_to_check.get('internal_type') == 'single_card':
            if query_filter_foil != 'all' and item_to_check.get('is_foil') != (query_filter_foil == 'yes'): keep = False
            if query_filter_rarity != 'all' and item_to_check.get('rarity') != query_filter_rarity: keep = False
            if query_filter_card_lang != 'all' and item_to_check.get('language') != query_filter_card_lang: keep = False
            if query_filter_condition != 'all' and item_to_check.get('condition') != query_filter_condition: keep = False
        elif item_to_check.get('internal_type') == 'sealed_product':
            if query_filter_collector != 'all' and item_to_check.get('is_collectors_item') != (query_filter_collector == 'yes'): keep = False
            if query_filter_sealed_lang != 'all' and item_to_check.get('language') != query_filter_sealed_lang: keep = False
        elif item_to_check.get('internal_type') == 'shipping_supply':
            if query_filter_foil != 'all' or query_filter_rarity != 'all' or query_filter_card_lang != 'all' or \
               query_filter_condition != 'all' or query_filter_collector != 'all' or query_filter_sealed_lang != 'all':
                keep = False

        if keep:
            temp_items_after_type_specific_filters.append(item_to_check)
    filtered_inventory_items = temp_items_after_type_specific_filters


    # Prepare for sorting, using 'internal_type' to guide column access
    def get_sort_value(item_to_sort, key):
        if item_to_sort.get('internal_type') == 'shipping_supply':
            if key == 'display_name' or key == 'supply_name': return str(item_to_sort.get('supply_name', '')).lower()
            if key == 'quantity': return item_to_sort.get('quantity_on_hand', 0)
            if key == 'buy_price' or key == 'cost_per_unit': return item_to_sort.get('cost_per_unit', -float('inf'))
            if key == 'location': return str(item_to_sort.get('location', '')).lower()
            if key == 'purchase_date': return str(item_to_sort.get('purchase_date', ''))
            return str(item_to_sort.get(key, '')).lower()
        else: # single_card or sealed_product
            val = item_to_sort.get(key)
            if key == 'set_name_sort':
                s_val = (str(item_to_sort.get('set_code','')) or str(item_to_sort.get('set_name', ''))) if item_to_sort.get('internal_type') == 'single_card' else str(item_to_sort.get('set_name', ''))
                return s_val.lower()
            if isinstance(val, bool): return int(val)
            if isinstance(val, (int, float)): return val if val is not None else (-float('inf') if query_sort_direction == 'asc' else float('inf'))
            return str(val if val is not None else '').lower()

    try:
        filtered_inventory_items.sort(key=lambda i_sort: (get_sort_value(i_sort, query_sort_key), get_sort_value(i_sort, 'display_name')), reverse=(query_sort_direction == 'desc'))
    except TypeError as e:
        print(f"Sorting TypeError for key '{query_sort_key}': {e}. Falling back.");
        filtered_inventory_items.sort(key=lambda i_sort: get_sort_value(i_sort, 'display_name'), reverse=(query_sort_direction == 'desc'))

    total_filtered_item_count = len(filtered_inventory_items)
    total_pages = (total_filtered_item_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_filtered_item_count > 0 else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * ITEMS_PER_PAGE
    paginated_inventory_items_for_display = filtered_inventory_items[offset : offset + ITEMS_PER_PAGE]
    inventory_items_json = json.dumps(paginated_inventory_items_for_display)

    total_buy_cost_of_inventory = total_buy_cost_of_inventory_cards + total_buy_cost_of_inventory_sealed
    total_inventory_market_value = total_inventory_market_value_cards + total_inventory_market_value_sealed        
    all_locations_temp = set(item.get('location') for item in all_combined_inventory_items_for_filtering if item.get('location'))
    all_locations = sorted(list(all_locations_temp))
    all_sets_identifiers_temp = set((item.get('set_code') or item.get('set_name')) for item in all_combined_inventory_items_for_filtering if item.get('internal_type') in ['single_card', 'sealed_product'] and (item.get('set_code') or item.get('set_name')))
    all_sets_identifiers = sorted(list(all_sets_identifiers_temp))
    all_rarities_temp = set(item.get('rarity') for item in all_combined_inventory_items_for_filtering if item.get('internal_type') == 'single_card' and item.get('rarity'))
    all_rarities = sorted(list(all_rarities_temp))
    all_card_languages_temp = set(item.get('language') for item in all_combined_inventory_items_for_filtering if item.get('internal_type') == 'single_card' and item.get('language'))
    all_card_languages = sorted(list(all_card_languages_temp))
    all_sealed_languages_temp = set(item.get('language') for item in all_combined_inventory_items_for_filtering if item.get('internal_type') == 'sealed_product' and item.get('language'))
    all_sealed_languages = sorted(list(all_sealed_languages_temp))
    all_conditions_for_template = ['Mint', 'Near Mint', 'Lightly Played', 'Moderately Played', 'Heavily Played', 'Damaged']


    num_unique_card_inventory_entries = len(processed_inventory_cards)

    sale_inventory_options = []
    temp_sorted_for_sale_options = sorted(all_combined_inventory_items_for_filtering, key=lambda x_sort: x_sort.get('display_name', x_sort.get('supply_name', '')).lower())
    for item_s_opt in temp_sorted_for_sale_options:
        display_text_val = f"{item_s_opt.get('display_name', item_s_opt.get('supply_name', 'N/A'))} "
        if item_s_opt.get('internal_type') == 'single_card':
            condition_str = f"C: {item_s_opt.get('condition','N/A')}, "
            display_text_val += f"({item_s_opt.get('set_code','N/A').upper()}-{item_s_opt.get('collector_number','N/A')}) {'(Foil)' if item_s_opt.get('is_foil') else ''} (R: {item_s_opt.get('rarity','N/A')}, L: {item_s_opt.get('language','N/A')}, {condition_str}BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        elif item_s_opt.get('internal_type') == 'sealed_product':
            display_text_val += f"({item_s_opt.get('set_name','N/A')} / {item_s_opt.get('product_type','N/A')}){' (Collector)' if item_s_opt.get('is_collectors_item') else ''} (L: {item_s_opt.get('language','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        elif item_s_opt.get('internal_type') == 'shipping_supply':
            display_text_val += f"({item_s_opt.get('description','N/A')}) (UOM: {item_s_opt.get('unit_of_measure','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('cost_per_unit'))}) - Qty: {item_s_opt['quantity_on_hand']} - Loc: {item_s_opt.get('location', 'N/A')}"
        sale_inventory_options.append({"id": f"{item_s_opt['internal_type']}-{item_s_opt['id'] if item_s_opt.get('id') else item_s_opt['original_id']}", "display": display_text_val, "type": item_s_opt['internal_type']})

    sale_inventory_options_json = json.dumps(sale_inventory_options)

    shipping_supply_options = []
    temp_sorted_supplies = sorted(processed_shipping_supplies, key=lambda x_sort: x_sort.get('supply_name', '').lower())
    for supply_opt in temp_sorted_supplies:
        display_text_val = f"{supply_opt['supply_name']} ({supply_opt.get('description', 'N/A')}) - Qty: {supply_opt['quantity_on_hand']} {supply_opt['unit_of_measure']} @ {format_currency_with_commas(supply_opt.get('cost_per_unit'))} each"
        shipping_supply_options.append({
            "id": supply_opt['id'],
            "display": display_text_val,
            "cost_per_unit": supply_opt['cost_per_unit'],
            "quantity_on_hand": supply_opt['quantity_on_hand']
        })
    shipping_supply_options_json = json.dumps(shipping_supply_options)

    shipping_supply_presets_json = json.dumps(shipping_supply_presets)


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
                           filter_collector=query_filter_collector, # Corrected variable name
                           filter_sealed_lang=query_filter_sealed_lang, # Corrected variable name
                           sort_key=query_sort_key,
                           sort_dir=query_sort_direction,
                           all_locations=all_locations,
                           all_sets_identifiers=all_sets_identifiers,
                           all_rarities=all_rarities,
                           all_card_languages=all_card_languages,
                           all_sealed_languages=all_sealed_languages,
                           all_conditions=all_conditions_for_template,
                           financial_entries=financial_entries,
                           total_cogs=total_cogs,
                           total_gross_sales=total_gross_sales,
                           shipping_supplies_display_json=json.dumps(processed_shipping_supplies),
                           shipping_supply_options_json=shipping_supply_options_json,
                           shipping_supply_presets_json=shipping_supply_presets_json
                           )

@app.route('/add_shipping_supply', methods=['POST'])
def add_shipping_supply_route():
    supply_name = request.form.get('supply_name', '').strip()
    description = request.form.get('description', '').strip()
    unit_of_measure = request.form.get('unit_of_measure', 'unit').strip()
    purchase_date_str = request.form.get('purchase_date')
    quantity_str = request.form.get('quantity')
    total_purchase_amount_str = request.form.get('total_purchase_amount')
    location = request.form.get('location', '').strip()

    if not all([supply_name, purchase_date_str, quantity_str, total_purchase_amount_str]):
        flash('Supply Name, Purchase Date, Quantity, and Total Purchase Amount are required.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    try:
        quantity = int(quantity_str)
        total_purchase_amount = float(total_purchase_amount_str)
        if quantity <= 0 or total_purchase_amount < 0:
            flash('Quantity must be positive; Total Purchase Amount non-negative.', 'error')
            return redirect(url_for('index', tab='addItemsTab'))
    except ValueError:
        flash('Invalid number format for quantity or total purchase amount.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    supply_id = database.add_shipping_supply_batch(
        supply_name=supply_name,
        description=description,
        unit_of_measure=unit_of_measure,
        purchase_date_str=purchase_date_str,
        quantity=quantity,
        total_purchase_amount=total_purchase_amount,
        location=location
    )

    if supply_id:
        flash(f"Shipping supply '{supply_name} ({description})' batch added/updated!", 'success')
    else:
        flash(f"Failed to add/update shipping supply batch. Possible duplicate or DB issue.", 'error')

    return redirect(url_for('index', tab='addItemsTab'))


@app.route('/add_shipping_supply_preset', methods=['POST'])
def add_shipping_supply_preset_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received."}), 400

        preset_name = data.get('name', '').strip()
        preset_description = data.get('description', '').strip()
        items = data.get('items', [])

        if not preset_name:
            return jsonify({"success": False, "message": "Preset name is required."}), 400
        if not items:
            return jsonify({"success": False, "message": "At least one supply item is required for a preset."}), 400

        for item in items:
            if not isinstance(item, dict) or 'supply_id' not in item or 'quantity' not in item:
                return jsonify({"success": False, "message": "Invalid item data in preset. Each item needs 'supply_id' and 'quantity'."}), 400
            try:
                item['supply_id'] = int(item['supply_id'])
                item['quantity'] = int(item['quantity'])
                if item['supply_id'] <= 0 or item['quantity'] <= 0:
                    return jsonify({"success": False, "message": "Supply ID and quantity must be positive integers."}), 400
            except ValueError:
                return jsonify({"success": False, "message": "Supply ID and quantity must be valid integers."}), 400

        preset_id = database.add_shipping_supply_preset(preset_name, preset_description, items)

        if preset_id:
            flash(f"Shipping supply preset '{preset_name}' added successfully!", 'success')
            return jsonify({"success": True, "message": "Preset added!", "preset_id": preset_id})
        else:
            flash(f"Failed to add shipping supply preset '{preset_name}'. Possible duplicate name or DB issue.", 'error')
            return jsonify({"success": False, "message": "Failed to add preset. Possible duplicate name or DB issue."}), 500

    except Exception as e:
        print(f"Error in /add_shipping_supply_preset route: {e}")
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        return jsonify({"success": False, "message": f"An internal error occurred: {str(e)}"}), 500

@app.route('/delete_shipping_supply_preset/<int:preset_id>', methods=['POST'])
def delete_shipping_supply_preset_route(preset_id):
    success = database.delete_shipping_supply_preset(preset_id)
    if success:
        flash('Shipping supply preset deleted successfully.', 'success')
        return jsonify({"success": True, "message": "Preset deleted."})
    else:
        flash('Failed to delete shipping supply preset.', 'error')
        return jsonify({"success": False, "message": "Failed to delete preset."}), 500


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

@app.route('/delete_shipping_supply/<int:supply_id>', methods=['POST'])
def delete_shipping_supply_route(supply_id):
    deleted = database.delete_shipping_supply(supply_id)
    flash('Shipping supply batch deleted!' if deleted else 'Failed to delete shipping supply batch.', 'success' if deleted else 'error')
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

@app.route('/update_shipping_supply/<int:supply_id>', methods=['POST'])
def update_shipping_supply_route(supply_id):
    data_to_update = {}
    original_supply = database.get_shipping_supply_by_id(supply_id)
    if not original_supply:
        flash('Shipping supply batch not found for update.', 'error')
        return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page', 1)))
    try:
        if request.form.get('quantity_on_hand') is not None and request.form.get('quantity_on_hand').strip() != '':
            qty = int(request.form.get('quantity_on_hand'))
            if qty < 0: flash('Quantity must be non-negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if qty != original_supply['quantity_on_hand']: data_to_update['quantity_on_hand'] = qty
        if request.form.get('cost_per_unit') is not None and request.form.get('cost_per_unit').strip() != '':
            cost = float(request.form.get('cost_per_unit'))
            if cost < 0: flash('Cost per unit cannot be negative.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if abs(cost - original_supply['cost_per_unit']) > 1e-9: data_to_update['cost_per_unit'] = cost
        if request.form.get('location') is not None:
            loc = request.form.get('location').strip()
            if not loc: flash('Location cannot be empty.'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))
            if loc != original_supply['location']: data_to_update['location'] = loc
        if request.form.get('description') is not None:
            desc = request.form.get('description').strip()
            if desc != original_supply['description']: data_to_update['description'] = desc
        if request.form.get('unit_of_measure') is not None:
            uom = request.form.get('unit_of_measure').strip()
            if uom != original_supply['unit_of_measure']: data_to_update['unit_of_measure'] = uom
    except ValueError: flash('Invalid number format for update.', 'error'); return redirect(url_for('index', tab='inventoryTab', page=request.args.get('page',1)))

    if not data_to_update: flash('No changes detected to update.', 'warning')
    else:
        success, message = database.update_shipping_supply_fields(supply_id, data_to_update)
        flash(f'Shipping supply details updated! {message}' if success else f'Failed to update. {message}', 'success' if success else 'error')
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

@app.route('/edit_sale_event/<int:sale_event_id>', methods=['GET'])
def edit_sale_event_get_route(sale_event_id):
    sale_event_data = database.get_sale_event_by_id_with_details(sale_event_id)
    if not sale_event_data:
        flash("Sale event not found.", 'error')
        return redirect(url_for('index', tab='salesHistoryTab'))

    # Convert date objects to string for HTML form input
    if isinstance(sale_event_data.get('sale_date'), datetime.date):
        sale_event_data['sale_date'] = sale_event_data['sale_date'].isoformat()

    # Prepare current items for JS pre-population
    current_sale_items = []
    for item in sale_event_data['items']:
        current_sale_items.append({
            'inventory_item_id_with_prefix': f"{item['item_type']}-{item['inventory_item_id']}",
            'quantity_sold': item['quantity_sold'],
            'sell_price_per_item': item['sell_price_per_item'],
            'display_name': item['original_item_name'],
            'display_details': item['original_item_details']
        })
    current_sale_items_json = json.dumps(current_sale_items)

    # Shipping supplies
    current_shipping_supplies_used = {}
    for supply in sale_event_data['shipping_supplies_used']:
        current_shipping_supplies_used[supply['supply_id']] = supply['quantity_used']
    current_shipping_supplies_used_json = json.dumps(current_shipping_supplies_used)


    # Need to pass all options for item lookup as well (cards, sealed, supplies)
    inventory_cards_data = database.get_all_cards()
    sealed_products_data = database.get_all_sealed_products()
    shipping_supplies_data = database.get_all_shipping_supplies()

    all_combined_inventory_items_for_filtering = []
    for item in inventory_cards_data:
        item_copy = dict(item)
        item_copy['internal_type'] = 'single_card'
        item_copy['display_name'] = item_copy.get('name', 'N/A') # Set display_name for cards
        all_combined_inventory_items_for_filtering.append(item_copy)
    for item in sealed_products_data:
        item_copy = dict(item)
        item_copy['internal_type'] = 'sealed_product'
        item_copy['display_name'] = item_copy.get('product_name', 'N/A') # Set display_name for sealed products
        all_combined_inventory_items_for_filtering.append(item_copy)
    for item in shipping_supplies_data:
        item_copy = dict(item)
        item_copy['internal_type'] = 'shipping_supply'
        item_copy['display_name'] = item_copy.get('supply_name', 'N/A') # Ensure display_name for supplies here
        all_combined_inventory_items_for_filtering.append(item_copy)

    sale_inventory_options = []
    temp_sorted_for_sale_options = sorted(all_combined_inventory_items_for_filtering, key=lambda x_sort: x_sort.get('display_name', x_sort.get('supply_name', '')).lower())
    for item_s_opt in temp_sorted_for_sale_options:
        display_text_val = f"{item_s_opt.get('display_name', item_s_opt.get('supply_name', 'N/A'))} "
        if item_s_opt.get('internal_type') == 'single_card':
            condition_str = f"C: {item_s_opt.get('condition','N/A')}, "
            display_text_val += f"({item_s_opt.get('set_code','N/A').upper()}-{item_s_opt.get('collector_number','N/A')}) {'(Foil)' if item_s_opt.get('is_foil') else ''} (R: {item_s_opt.get('rarity','N/A')}, L: {item_s_opt.get('language','N/A')}, {condition_str}BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        elif item_s_opt.get('internal_type') == 'sealed_product':
            display_text_val += f"({item_s_opt.get('set_name','N/A')} / {item_s_opt.get('product_type','N/A')}){' (Collector)' if item_s_opt.get('is_collectors_item') else ''} (L: {item_s_opt.get('language','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        elif item_s_opt.get('internal_type') == 'shipping_supply':
            display_text_val += f"({item_s_opt.get('description','N/A')}) (UOM: {item_s_opt.get('unit_of_measure','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('cost_per_unit'))}) - Qty: {item_s_opt['quantity_on_hand']} - Loc: {item_s_opt.get('location', 'N/A')}"
        sale_inventory_options.append({"id": f"{item_s_opt['internal_type']}-{item_s_opt['id'] if item_s_opt.get('id') else item_s_opt['original_id']}", "display": display_text_val, "type": item_s_opt['internal_type']})

    sale_inventory_options_json = json.dumps(sale_inventory_options)

    shipping_supply_options = []
    temp_sorted_supplies = sorted(shipping_supplies_data, key=lambda x_sort: x_sort.get('supply_name', '').lower())
    for supply_opt in temp_sorted_supplies:
        display_text_val = f"{supply_opt['supply_name']} ({supply_opt.get('description', 'N/A')}) - Qty: {supply_opt['quantity_on_hand']} {supply_opt['unit_of_measure']} @ {format_currency_with_commas(supply_opt.get('cost_per_unit'))} each"
        shipping_supply_options.append({
            "id": supply_opt['id'],
            "display": display_text_val,
            "cost_per_unit": supply_opt['cost_per_unit'],
            "quantity_on_hand": supply_opt['quantity_on_hand']
        })
    shipping_supply_options_json = json.dumps(shipping_supply_options)

    # Need to also pass shipping_supply_presets to edit_sale.html for the presets dropdown
    shipping_supply_presets = database.get_all_shipping_supply_presets()
    shipping_supply_presets_json = json.dumps(shipping_supply_presets)


    return render_template('edit_sale.html',
                           sale_event=sale_event_data,
                           current_sale_items_json=current_sale_items_json,
                           current_shipping_supplies_used_json=current_shipping_supplies_used_json,
                           sale_inventory_options_json=sale_inventory_options_json,
                           shipping_supply_options_json=shipping_supply_options_json,
                           shipping_supply_presets_json=shipping_supply_presets_json, # Pass presets here
                           current_date=datetime.date.today().isoformat()
                           )


@app.route('/edit_sale_event/<int:sale_event_id>', methods=['POST'])
def edit_sale_event_post_route(sale_event_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received."}), 400

        sale_date_str = data.get('sale_date')
        total_shipping_cost_str = data.get('total_shipping_cost', '0.0')
        overall_notes = data.get('notes', '')
        items_data = data.get('items')
        shipping_supplies_data = data.get('shipping_supplies_used', [])

        customer_shipping_charge_str = data.get('customer_shipping_charge', '0.0')
        platform_fee_str = data.get('platform_fee', '0.0')

        if not sale_date_str or not isinstance(items_data, list) or not items_data:
            flash('Missing sale date or items data.', 'error')
            return jsonify({"success": False, "message": "Missing sale date or items list is empty."}), 400

        success, message = database.update_sale_event_details(
            sale_event_id,
            sale_date_str,
            total_shipping_cost_str,
            overall_notes,
            customer_shipping_charge_str,
            platform_fee_str,
            items_data,
            shipping_supplies_data
        )

        if success:
            flash(f"Sale event (ID: {sale_event_id}) updated successfully. {message}", 'success')
            return jsonify({"success": True, "message": f"Sale event (ID: {sale_event_id}) updated."})
        else:
            flash(f"Failed to update sale event. Reason: {message}", 'error')
            return jsonify({"success": False, "message": f"Failed to update sale event. Reason: {message}"}), 400
    except Exception as e:
        print(f"Error in /edit_sale_event POST route: {e}")
        flash(f"An error occurred: {str(e)}", 'error')
        return jsonify({"success": False, "message": f"An internal error occurred: {str(e)}"}), 500


@app.route('/import_csv', methods=['POST'])
def import_csv_route():
    if 'csv_file' not in request.files:
        flash('No CSV file part in the request.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))
    file = request.files['csv_file']
    if file.filename == '':
        flash('No CSV file selected for uploading.', 'error')
        return redirect(url_for('index', tab='addItemsTab'))

    default_buy_price_str = request.form.get('default_buy_price', '0.00')
    default_location = request.form.get('default_location', 'Imported Batch')
    default_asking_price_str = request.form.get('default_asking_price')
    default_language_csv_form = request.form.get('default_language_csv', 'en').strip().lower()
    default_condition_csv_form = request.form.get('default_condition_csv', 'Near Mint').strip()
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

    card_aggregator = defaultdict(lambda: {'quantity': 0, 'details': {}})
    errors_list = []
    skipped_count = 0

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8", errors='replace'), newline=None)
        csv_reader = csv.DictReader(stream)

        if not csv_reader.fieldnames:
             flash('CSV file appears to be empty or has no headers.', 'error')
             return redirect(url_for('index', tab='addItemsTab'))

        # Define flexible column mappings for common variations
        # Keys are internal names, values are lists of possible CSV headers (normalized)
        flexible_headers = {
            'card_name': ['product name', 'name'],
            'quantity': ['total quantity', 'quantity'], # TCGplayer uses "Total Quantity"
            'set_identifier': ['set code', 'set name', 'set'], # Order: prefer code, then name, then generic 'set'
            'collector_number': ['number', 'card number', 'collector number'], # TCGplayer uses "Number"
            'rarity': ['rarity'],
            'language': ['language'],
            'condition': ['condition'],
            'printing': ['printing'], # For old files that might have this explicit column
            'tcg_market_price': ['tcg market price', 'market price'] # TCGplayer specific
        }

        # Create a mapping from our internal flexible name to the actual column name found in the CSV
        actual_csv_header_map = {}
        normalized_incoming_headers = [hdr.lower().replace(' ', '_') for hdr in csv_reader.fieldnames if hdr]

        for internal_name, possible_headers in flexible_headers.items():
            for possible_hdr in possible_headers:
                if possible_hdr in normalized_incoming_headers:
                    actual_csv_header_map[internal_name] = possible_hdr
                    break # Found the first best match for this internal_name
        
        # Check for essential columns based on *any* of their possible names
        # 'card_name' or 'quantity' must be present under any of their flexible names
        has_card_name_col = 'card_name' in actual_csv_header_map
        has_quantity_col = 'quantity' in actual_csv_header_map

        if not has_card_name_col or not has_quantity_col:
             flash(f"CSV missing one or more required columns ('Name'/'Product Name' and 'Quantity'/'Total Quantity'). Found headers: {', '.join(normalized_incoming_headers)}", 'error')
             return redirect(url_for('index', tab='addItemsTab'))


        for row_num, row_raw in enumerate(csv_reader, start=1):
            # Convert row_raw keys to normalized lowercase keys for easy access
            row = {k.lower().replace(' ', '_'): v.strip() if isinstance(v, str) else v for k, v in row_raw.items()}

            # Extract data using the determined actual_csv_header_map
            card_name = row.get(actual_csv_header_map.get('card_name'))
            quantity_str = row.get(actual_csv_header_map.get('quantity'))
            
            # Use the mapped header names to get values from the current row
            set_identifier_from_csv = row.get(actual_csv_header_map.get('set_identifier'))
            collector_number_from_csv = row.get(actual_csv_header_map.get('collector_number'))
            rarity_from_csv = row.get(actual_csv_header_map.get('rarity'))
            language_from_csv = row.get(actual_csv_header_map.get('language'))
            condition_from_csv = row.get(actual_csv_header_map.get('condition'))
            printing_from_csv = row.get(actual_csv_header_map.get('printing'))
            tcg_market_price_from_csv = row.get(actual_csv_header_map.get('tcg_market_price'))


            # --- Validation of per-row required fields ---
            if not all([card_name, quantity_str]):
                errors_list.append(f"Row {row_num}: Missing 'Name' or 'Quantity'. Skipping.")
                skipped_count += 1
                continue

            try:
                quantity = int(quantity_str)
                if quantity <= 0:
                    errors_list.append(f"Row {row_num}: Quantity for '{card_name}' must be positive. Skipping.")
                    skipped_count += 1
                    continue
            except (ValueError, TypeError):
                errors_list.append(f"Row {row_num}: Invalid quantity '{quantity_str}' for '{card_name}'. Skipping.")
                skipped_count += 1
                continue
            
            # --- Determine foil status (more robust) ---
            is_foil = False
            # 1. Check 'Printing' column from older CSVs if available and says 'foil'
            if printing_from_csv and 'foil' in str(printing_from_csv).lower():
                is_foil = True
            # 2. If 'assume_non_foil' is checked in the form, it overrides other detections for mass import
            if assume_non_foil:
                is_foil = False
            # You could add more advanced detection here for TCGplayer's specifics if needed.

            # --- Aggregate cards for stacking ---
            # Use data from CSV, or form defaults if CSV fields are missing/empty
            current_rarity_for_agg = rarity_from_csv.lower() if rarity_from_csv else 'unknown'
            current_language_for_agg = language_from_csv.lower() if language_from_csv else default_language_csv_form
            current_condition_for_agg = condition_from_csv.strip() if condition_from_csv else default_condition_csv_form


            unique_key = (
                card_name.lower(),
                (set_identifier_from_csv.lower() if set_identifier_from_csv else ''), # Can be code or name
                (collector_number_from_csv.lower() if collector_number_from_csv else ''),
                is_foil,
                default_location.lower(), # From form
                default_buy_price,        # From form
                current_condition_for_agg.lower(),
                current_rarity_for_agg.lower(),
                current_language_for_agg.lower()
            )
            
            # Store data for this stack (quantity and other details for Scryfall lookup/DB insert)
            card_aggregator[unique_key]['quantity'] += quantity
            if not card_aggregator[unique_key]['details']:
                 card_aggregator[unique_key]['details'] = {
                     'name': card_name,
                     'set_identifier': set_identifier_from_csv, # Raw identifier from CSV
                     'collector_number': collector_number_from_csv,
                     'rarity': current_rarity_for_agg, # Cleaned rarity
                     'language': current_language_for_agg, # Cleaned language
                     'condition': current_condition_for_agg, # Cleaned condition
                     'is_foil': is_foil, # Foil status determined above
                     'buy_price': default_buy_price, # From form
                     'sell_price': default_asking_price, # From form
                     'location': default_location, # From form
                     'tcg_market_price_csv': float(tcg_market_price_csv) if tcg_market_price_csv else None
                 }

    except Exception as e:
        flash(f'Critical error reading or processing CSV file: {e}', 'error')
        import traceback; traceback.print_exc()
        return redirect(url_for('index', tab='addItemsTab'))

    imported_count = 0
    failed_count = 0

    # --- Process Aggregated Cards and Add to DB ---
    for key, data in card_aggregator.items():
        card_info = data['details']
        total_quantity = data['quantity']

        # --- Scryfall Lookup for comprehensive data (using cleaned data) ---
        card_details = None
        scryfall_card_name = card_info['name']
        scryfall_set_id = card_info['set_identifier'] # Could be set code or set name
        scryfall_collector_number = card_info['collector_number']
        scryfall_language = card_info['language']

        # Scryfall lookup logic (prioritized for best match)
        # Priority 1: Set Identifier + Collector Number + Card Name (most specific)
        if scryfall_set_id and scryfall_collector_number:
            card_details = scryfall.get_card_details(
                card_name=scryfall_card_name,
                set_code=scryfall_set_id, # Scryfall can often resolve set names too
                collector_number=scryfall_collector_number,
                lang=scryfall_language
            )

        # Priority 2: Set Identifier + Card Name (no collector number)
        if not card_details and scryfall_set_id and scryfall_card_name:
            card_details = scryfall.get_card_details(
                card_name=scryfall_card_name,
                set_code=scryfall_set_id,
                lang=scryfall_language
            )
        
        # Priority 3: Card Name + Collector Number (no specific set identifier)
        if not card_details and scryfall_card_name and scryfall_collector_number:
            card_details = scryfall.get_card_details(
                card_name=scryfall_card_name,
                collector_number=scryfall_collector_number,
                lang=scryfall_language
            )

        # Priority 4: Card Name only (least precise)
        if not card_details and scryfall_card_name:
            card_details = scryfall.get_card_details(
                card_name=scryfall_card_name,
                lang=scryfall_language
            )


        if card_details and all(k in card_details for k in ['name', 'collector_number', 'set_code']):
            final_name = card_details['name']
            final_set_code = card_details['set_code'].upper() # Always store set code as uppercase
            final_collector_number = card_details['collector_number']
            final_scryfall_uuid = card_details.get('id')

            # Use Scryfall's rarity/language if available, otherwise use mapped CSV data
            final_rarity = card_details.get('rarity', card_info['rarity']).lower() # Use cleaned rarity from card_info
            final_language = card_details.get('language', card_info['language']).lower() # Use cleaned language from card_info
            final_condition = card_info['condition'] # Use cleaned condition from card_info

            # For image, prefer Scryfall's image_uri
            final_image_uri = card_details.get('image_uri')

            # Market prices from Scryfall (prefer Scryfall's current data)
            final_market_price_usd = card_details.get('market_price_usd')
            final_foil_market_price_usd = card_details.get('foil_market_price_usd')

            # Re-evaluate is_foil based on Scryfall and previous logic
            is_foil_final = card_info['is_foil'] # Start with what was determined from CSV/form
            if not is_foil_final and card_details.get('foil_market_price_usd') is not None and card_details.get('market_price_usd') is None:
                is_foil_final = True # If Scryfall only has foil price, it's likely foil, override non-foil assumption

            card_id = database.add_card(
                set_code=final_set_code,
                collector_number=final_collector_number,
                name=final_name,
                quantity=total_quantity,
                buy_price=card_info['buy_price'],
                is_foil=is_foil_final,
                market_price_usd=final_market_price_usd,
                foil_market_price_usd=final_foil_market_price_usd,
                image_uri=final_image_uri,
                sell_price=card_info['sell_price'],
                location=card_info['location'],
                scryfall_id=final_scryfall_uuid,
                rarity=final_rarity,
                language=final_language,
                condition=final_condition
            )

            if card_id:
                imported_count += 1
            else:
                failed_count += 1
                errors_list.append(f"DB error for '{card_info['name']}' (Set: {card_info.get('set_identifier')}).")
        else:
            failed_count += 1
            errors_list.append(f"Scryfall lookup failed for '{card_info['name']}' (Set: {card_info.get('set_identifier') or 'N/A'}, CN: {card_info.get('collector_number') or 'N/A'}).")

    summary_message = f"CSV Import Finished: {imported_count} unique card stacks processed."
    if failed_count > 0: summary_message += f" {failed_count} failed."
    if skipped_count > 0: summary_message += f" {skipped_count} rows skipped."

    flash_category = 'success' if imported_count > 0 and not errors_list else ('warning' if imported_count > 0 and errors_list else 'error')
    flash(summary_message, flash_category)

    if errors_list:
        [flash(f"Import Error: {err}", 'error') for err in errors_list[:10]]
        if len(errors_list) > 10:
            flash(f"...and {len(errors_list) - 10} more errors (see server console for full list).", 'error')
        print("--- Detailed CSV Import Errors ---\n" + "\n".join(errors_list) + "\n---------------------------------")

    return redirect(url_for('index', tab='addItemsTab'))


# ... (rest of the app.py code) ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


@app.route('/api/all_shipping_supply_presets', methods=['GET'])
def api_all_shipping_supply_presets():
    try:
        presets = database.get_all_shipping_supply_presets()
        # Convert any date/datetime objects within preset items to ISO format for JSON serialization
        for preset in presets:
            if 'items' in preset and isinstance(preset['items'], list):
                for item in preset['items']:
                    # Assuming there might be date/datetime objects if we ever pull more fields
                    # but for now, just a general check. The database.py function already returns
                    # cost_per_unit and quantity as numbers, which is good.
                    pass # No specific date conversion needed for the current item structure
        return jsonify(presets)
    except Exception as e:
        print(f"Error fetching all shipping supply presets via API: {e}")
        return jsonify({"error": "Failed to fetch shipping supply presets."}), 500


@app.route('/mass_edit_inventory', methods=['POST'])
def mass_edit_inventory_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received."}), 400

        filters = data.get('filters', {})
        update_data = data.get('update_data', {})

        if not update_data:
            return jsonify({"success": False, "message": "No update data provided."}), 400

        # Validate update_data to prevent unexpected field updates
        allowed_update_fields = {
            'location', 'sell_price', 'condition', 'buy_price_change_percentage',
            'manual_market_price_change_percentage', 'cost_per_unit_change_percentage',
            'unit_of_measure', 'description'
        }
        for key in update_data.keys():
            if key not in allowed_update_fields:
                return jsonify({"success": False, "message": f"Invalid update field: {key}"}), 400

        # Convert percentage strings to floats
        for key in ['buy_price_change_percentage', 'manual_market_price_change_percentage', 'cost_per_unit_change_percentage']:
            if key in update_data:
                try:
                    update_data[key] = float(update_data[key])
                except ValueError:
                    return jsonify({"success": False, "message": f"Invalid number format for {key}."}), 400

        success, message, updated_count = database.mass_update_inventory_items(filters, update_data)

        if success:
            flash(f"Mass edit successful! {updated_count} items updated. {message}", 'success')
            return jsonify({"success": True, "message": message, "updated_count": updated_count})
        else:
            flash(f"Mass edit failed: {message}", 'error')
            return jsonify({"success": False, "message": message})

    except Exception as e:
        print(f"Error in /mass_edit_inventory route: {e}")
        flash(f"An unexpected error occurred during mass edit: {str(e)}", 'error')
        return jsonify({"success": False, "message": f"An internal error occurred: {str(e)}"}), 500

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
        shipping_supplies_data = data.get('shipping_supplies_used', [])

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
            platform_fee_str,
            shipping_supplies_data
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

@app.route('/edit_sale_event/<int:sale_event_id>', methods=['GET'])
def edit_sale_event_get_route(sale_event_id):
    sale_event_data = database.get_sale_event_by_id_with_details(sale_event_id)
    if not sale_event_data:
        flash("Sale event not found.", 'error')
        return redirect(url_for('index', tab='salesHistoryTab'))

    # Convert date objects to string for HTML form input
    if isinstance(sale_event_data.get('sale_date'), datetime.date):
        sale_event_data['sale_date'] = sale_event_data['sale_date'].isoformat()

    # Prepare current items for JS pre-population
    # Sale items
    current_sale_items = []
    for item in sale_event_data['items']:
        current_sale_items.append({
            'inventory_item_id_with_prefix': f"{item['item_type']}-{item['inventory_item_id']}",
            'quantity_sold': item['quantity_sold'],
            'sell_price_per_item': item['sell_price_per_item'],
            'display_name': item['original_item_name'], # For display in frontend
            'display_details': item['original_item_details'] # For display
        })
    current_sale_items_json = json.dumps(current_sale_items)

    # Shipping supplies
    current_shipping_supplies_used = {}
    for supply in sale_event_data['shipping_supplies_used']:
        current_shipping_supplies_used[supply['supply_id']] = supply['quantity_used']
    current_shipping_supplies_used_json = json.dumps(current_shipping_supplies_used)


    # Need to pass all options for item lookup as well (cards, sealed, supplies)
    inventory_cards_data = database.get_all_cards()
    sealed_products_data = database.get_all_sealed_products()
    shipping_supplies_data = database.get_all_shipping_supplies() # This data contains datetime.date objects

    all_combined_inventory_items_for_filtering = []
    for item in inventory_cards_data:
        item_copy = dict(item)
        item_copy['internal_type'] = 'single_card' # Add a consistent type identifier for filtering
        item_copy['display_name'] = item_copy.get('name', 'N/A')
        all_combined_inventory_items_for_filtering.append(item_copy)
    for item in sealed_products_data:
        item_copy = dict(item)
        item_copy['internal_type'] = 'sealed_product' # Add a consistent type identifier for filtering
        item_copy['display_name'] = item_copy.get('product_name', 'N/A')
        all_combined_inventory_items_for_filtering.append(item_copy)
    for item in shipping_supplies_data:
        item_copy = dict(item)
        item_copy['internal_type'] = 'shipping_supply' # Add a consistent type identifier for filtering
        item_copy['display_name'] = item_copy.get('supply_name', 'N/A')
        all_combined_inventory_items_for_filtering.append(item_copy)

    sale_inventory_options = []
    temp_sorted_for_sale_options = sorted(all_combined_inventory_items_for_filtering, key=lambda x_sort: x_sort.get('display_name', x_sort.get('supply_name', '')).lower())
    for item_s_opt in temp_sorted_for_sale_options:
        display_text_val = f"{item_s_opt.get('display_name', item_s_opt.get('supply_name', 'N/A'))} "
        if item_s_opt.get('internal_type') == 'single_card':
            condition_str = f"C: {item_s_opt.get('condition','N/A')}, "
            display_text_val += f"({item_s_opt.get('set_code','N/A').upper()}-{item_s_opt.get('collector_number','N/A')}) {'(Foil)' if item_s_opt.get('is_foil') else ''} (R: {item_s_opt.get('rarity','N/A')}, L: {item_s_opt.get('language','N/A')}, {condition_str}BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        elif item_s_opt.get('internal_type') == 'sealed_product':
            display_text_val += f"({item_s_opt.get('set_name','N/A')} / {item_s_opt.get('product_type','N/A')}){' (Collector)' if item_s_opt.get('is_collectors_item') else ''} (L: {item_s_opt.get('language','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('buy_price'))}) - Qty: {item_s_opt['quantity']} - Loc: {item_s_opt.get('location', 'N/A')}"
        elif item_s_opt.get('internal_type') == 'shipping_supply':
            display_text_val += f"({item_s_opt.get('description','N/A')}) (UOM: {item_s_opt.get('unit_of_measure','N/A')}, BP: {format_currency_with_commas(item_s_opt.get('cost_per_unit'))}) - Qty: {item_s_opt['quantity_on_hand']} - Loc: {item_s_opt.get('location', 'N/A')}"
        sale_inventory_options.append({"id": f"{item_s_opt['internal_type']}-{item_s_opt['id'] if item_s_opt.get('id') else item_s_opt['original_id']}", "display": display_text_val, "type": item_s_opt['internal_type']})

    sale_inventory_options_json = json.dumps(sale_inventory_options)

    shipping_supply_options = []
    temp_sorted_supplies = sorted(shipping_supplies_data, key=lambda x_sort: x_sort.get('supply_name', '').lower())
    for supply_opt in temp_sorted_supplies:
        display_text_val = f"{supply_opt['supply_name']} ({supply_opt.get('description', 'N/A')}) - Qty: {supply_opt['quantity_on_hand']} {supply_opt['unit_of_measure']} @ {format_currency_with_commas(supply_opt.get('cost_per_unit'))} each"
        shipping_supply_options.append({
            "id": supply_opt['id'],
            "display": display_text_val,
            "cost_per_unit": supply_opt['cost_per_unit'],
            "quantity_on_hand": supply_opt['quantity_on_hand']
        })
    shipping_supply_options_json = json.dumps(shipping_supply_options)


    return render_template('edit_sale.html',
                           sale_event=sale_event_data,
                           current_sale_items_json=current_sale_items_json,
                           current_shipping_supplies_used_json=current_shipping_supplies_used_json,
                           sale_inventory_options_json=sale_inventory_options_json, # For item search
                           shipping_supply_options_json=shipping_supply_options_json, # For shipping supply search
                           current_date=datetime.date.today().isoformat()
                           )


@app.route('/edit_sale_event/<int:sale_event_id>', methods=['POST'])
def edit_sale_event_post_route(sale_event_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received."}), 400

        sale_date_str = data.get('sale_date')
        total_shipping_cost_str = data.get('total_shipping_cost', '0.0')
        overall_notes = data.get('notes', '')
        items_data = data.get('items')
        shipping_supplies_data = data.get('shipping_supplies_used', [])

        customer_shipping_charge_str = data.get('customer_shipping_charge', '0.0')
        platform_fee_str = data.get('platform_fee', '0.0')

        if not sale_date_str or not isinstance(items_data, list) or not items_data:
            flash('Missing sale date or items data.', 'error')
            return jsonify({"success": False, "message": "Missing sale date or items list is empty."}), 400

        success, message = database.update_sale_event_details(
            sale_event_id,
            sale_date_str,
            total_shipping_cost_str,
            overall_notes,
            customer_shipping_charge_str,
            platform_fee_str,
            items_data, # These are the *new* items
            shipping_supplies_data # These are the *new* supplies
        )

        if success:
            flash(f"Sale event (ID: {sale_event_id}) updated successfully. {message}", 'success')
            return jsonify({"success": True, "message": f"Sale event (ID: {sale_event_id}) updated."})
        else:
            flash(f"Failed to update sale event. Reason: {message}", 'error')
            return jsonify({"success": False, "message": f"Failed to update sale event. Reason: {message}"}), 400
    except Exception as e:
        print(f"Error in /edit_sale_event POST route: {e}")
        flash(f"An error occurred: {str(e)}", 'error')
        return jsonify({"success": False, "message": f"An internal error occurred: {str(e)}"}), 500




import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)