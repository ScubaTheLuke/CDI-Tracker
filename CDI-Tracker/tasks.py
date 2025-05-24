from flask import current_app
from database import add_card
from scryfall import get_card_details as fetch_card_data
import csv
import io

def import_cards_from_csv(file_content):
    import csv, io
    from database import add_card
    from scryfall import get_card_details as fetch_card_data


    file = io.StringIO(file_content.decode('utf-8'))
    reader = csv.DictReader(file)
    imported, failed = 0, 0

    for row in reader:
        try:
            set_code = row.get('Set Code', '').strip()
            collector_number = row.get('Card Number', '').strip()
            quantity = int(row.get('Quantity', 1))
            buy_price = float(row.get('Buy Price', 0.0))
            foil = str(row.get('Foil', '')).strip().lower() == 'foil'

            if not set_code or not collector_number:
                print(f"SKIPPING ROW: Missing Set Code or Card Number: {row}")
                failed += 1
                continue

            card_info = fetch_card_data(set_code=set_code, collector_number=collector_number)

            if not card_info:
                print(f"Card not found in Scryfall: {set_code} {collector_number}")
                failed += 1
                continue

            market_price = float(card_info['usd_foil'] if foil else card_info['usd'] or 0.0)

            add_card(
                name=card_info['name'],
                set_code=set_code,
                collector_number=collector_number,
                quantity=quantity,
                buy_price=buy_price,
                market_price=market_price,
                foil=foil
            )
            imported += 1
        except Exception as e:
            print(f"ERROR processing row: {row}")
            print(f"Exception: {e}")
            failed += 1

    print(f"CSV import finished: {imported} imported, {failed} failed.")
    return f"{imported} cards imported, {failed} rows failed."

def register_jobs(rq):
    rq.job(import_cards_from_csv)
