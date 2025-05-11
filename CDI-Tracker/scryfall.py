import requests
import time
import urllib.parse

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"

def get_card_details(card_name=None, set_code=None, collector_number=None):
    url = None
    api_method = "object"
    search_query_for_log = "" # For logging search queries

    set_code_lower = set_code.lower().strip() if set_code else None
    card_name_stripped = card_name.strip() if card_name else None
    collector_number_stripped = collector_number.strip() if collector_number else None

    if set_code_lower and collector_number_stripped:
        url = f"{SCRYFALL_API_BASE_URL}/cards/{set_code_lower}/{collector_number_stripped}"
        api_method = "object"
    elif card_name_stripped and set_code_lower:
        encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
        url = f"{SCRYFALL_API_BASE_URL}/cards/named?exact={encoded_card_name}&set={set_code_lower}"
        api_method = "object"
    elif card_name_stripped and collector_number_stripped:
        encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
        search_query_for_log = f'!"{card_name_stripped}" cn:"{collector_number_stripped}"'
        encoded_query = urllib.parse.quote_plus(search_query_for_log)
        url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true" # include_extras might be useful
        api_method = "list"
    elif card_name_stripped:
        encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
        url = f"{SCRYFALL_API_BASE_URL}/cards/named?exact={encoded_card_name}"
        api_method = "object"
    else:
        print("Error: Insufficient parameters for Scryfall lookup.")
        return None

    try:
        # print(f"DEBUG Scryfall URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1)

        json_data = response.json()
        card_data = None

        if api_method == "object":
            card_data = json_data
        elif api_method == "list":
            if json_data.get("object") == "list" and json_data.get("total_cards", 0) > 0:
                all_prints = json_data.get("data", [])
                if len(all_prints) == 1:
                    card_data = all_prints[0]
                else:
                    # Prioritize non-LIST, non-SLD, non-TOKEN printings, then earliest release
                    deprioritized_set_types = ["the_list", "token", "memorabilia", "funny", "masterpiece"]
                    deprioritized_set_codes = ["sld", "plist"] # SLD for Secret Lair, PLIST is new code for The List

                    # Filter out deprioritized sets if possible
                    preferred_prints = [
                        p for p in all_prints
                        if p.get("set_type") not in deprioritized_set_types and
                           p.get("set", "").lower() not in deprioritized_set_codes
                    ]

                    if preferred_prints:
                        # Sort by release date (oldest first), then by whether it's a digital object (paper preferred)
                        preferred_prints.sort(key=lambda c: (c.get("released_at", "9999-12-31"), c.get("digital", False)))
                        card_data = preferred_prints[0]
                        print(f"Info: Multiple cards ({len(all_prints)}) found for '{search_query_for_log}'. Prioritized: {card_data.get('name')} from {card_data.get('set_name')} ({card_data.get('set').upper()}).")
                    elif all_prints: # If all are from deprioritized sets, take the first one Scryfall returned (often latest)
                        all_prints.sort(key=lambda c: (c.get("released_at", "9999-12-31"), c.get("digital", False))) # Sort anyway
                        card_data = all_prints[0]
                        print(f"Warning: Multiple cards ({len(all_prints)}) found for '{search_query_for_log}'. All appear to be special printings. Using: {card_data.get('name')} from {card_data.get('set_name')} ({card_data.get('set').upper()}).")
                    else: # Should not happen if all_prints was not empty
                        print(f"No suitable card found after filtering for query: '{search_query_for_log}'. URL: {url}")
                        return None
            else:
                print(f"No cards found via search for query: '{search_query_for_log}'. URL: {url}")
                return None

        if not card_data:
            print(f"Could not extract card data from Scryfall response. URL: {url}")
            return None

        name_from_api = card_data.get('name')
        collector_number_from_api = card_data.get('collector_number')
        set_code_from_api = card_data.get('set')
        scryfall_id_from_api = card_data.get('id')
        market_price_usd = None
        foil_market_price_usd = None
        image_uri = None

        if card_data.get('prices'):
            market_price_usd = card_data['prices'].get('usd')
            foil_market_price_usd = card_data['prices'].get('usd_foil')

        image_uris_data = card_data.get('image_uris')
        if not image_uris_data and card_data.get('card_faces'):
            for face in card_data['card_faces']:
                if face.get('image_uris'):
                    image_uris_data = face.get('image_uris'); break
        if image_uris_data:
            image_uri = image_uris_data.get('small', image_uris_data.get('normal'))

        return {
            "name": name_from_api, "collector_number": collector_number_from_api,
            "set_code": set_code_from_api, "id": scryfall_id_from_api,
            "market_price_usd": float(market_price_usd) if market_price_usd else None,
            "foil_market_price_usd": float(foil_market_price_usd) if foil_market_price_usd else None,
            "image_uri": image_uri
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "Unknown"
        print(f"HTTP error {status_code} for Scryfall URL: {url}. Details: {e.response.text if e.response is not None else e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request error for Scryfall URL: {url}. Error: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing price for card. URL: {url}. Error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in get_card_details. URL: {url}. Error: {e}")
        return None
