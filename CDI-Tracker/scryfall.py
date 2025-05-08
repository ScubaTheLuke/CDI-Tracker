import requests
import time
import urllib.parse

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"

def get_card_details(set_code, collector_number=None, card_name=None):
    url = None
    set_code_lower = set_code.lower() if set_code else None

    if card_name and set_code_lower:
        encoded_card_name = urllib.parse.quote_plus(card_name)
        url = f"{SCRYFALL_API_BASE_URL}/cards/named?exact={encoded_card_name}&set={set_code_lower}"
    elif collector_number and set_code_lower:
        url = f"{SCRYFALL_API_BASE_URL}/cards/{set_code_lower}/{collector_number}"
    else:
        print("Error: Insufficient parameters for Scryfall lookup. Provide (Set Code and Card Name) or (Set Code and Collector Number).")
        return None

    try:
        response = requests.get(url)
        response.raise_for_status() 
        time.sleep(0.1) 
        
        data = response.json()
        
        name_from_api = data.get('name')
        collector_number_from_api = data.get('collector_number')
        
        market_price_usd = None
        foil_market_price_usd = None
        image_uri = None

        if data.get('prices'):
            market_price_usd = data['prices'].get('usd')
            foil_market_price_usd = data['prices'].get('usd_foil')
        
        image_uris_data = data.get('image_uris')
        if not image_uris_data and data.get('card_faces'):
            for face in data['card_faces']:
                if face.get('image_uris'):
                    image_uris_data = face.get('image_uris')
                    break 
        
        if image_uris_data:
            image_uri = image_uris_data.get('small', image_uris_data.get('normal'))
        
        return {
            "name": name_from_api,
            "collector_number": collector_number_from_api,
            "market_price_usd": float(market_price_usd) if market_price_usd else None,
            "foil_market_price_usd": float(foil_market_price_usd) if foil_market_price_usd else None,
            "image_uri": image_uri
        }
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Card not found on Scryfall (404 Error). URL: {url}. Check input details.")
        else:
            print(f"HTTP error fetching card data from Scryfall. Status: {e.response.status_code}. URL: {url}. Response: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request error fetching card data from Scryfall. URL: {url}. Error: {e}")
        return None
    except ValueError as e: 
        print(f"Error parsing price for card. URL: {url}. Error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_card_details. URL: {url}. Error: {e}")
        return None