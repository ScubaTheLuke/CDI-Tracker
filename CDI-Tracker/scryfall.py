import requests
import time

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"

def get_card_details(set_code, collector_number):
    url = f"{SCRYFALL_API_BASE_URL}/cards/{set_code.lower()}/{collector_number}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1) # Scryfall API courtesy delay
        
        data = response.json()
        card_name = data.get('name')
        
        market_price_usd = None
        foil_market_price_usd = None
        image_uri = None

        if data.get('prices'):
            market_price_usd = data['prices'].get('usd')
            foil_market_price_usd = data['prices'].get('usd_foil')
        
        if data.get('image_uris'):
            image_uri = data['image_uris'].get('small', data['image_uris'].get('normal'))
        elif data.get('card_faces'):
            for face in data['card_faces']:
                if face.get('image_uris'):
                    image_uri = face['image_uris'].get('small', face['image_uris'].get('normal'))
                    break
        
        return {
            "name": card_name,
            "market_price_usd": float(market_price_usd) if market_price_usd else None,
            "foil_market_price_usd": float(foil_market_price_usd) if foil_market_price_usd else None,
            "image_uri": image_uri
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching card data from Scryfall for {set_code}/{collector_number}: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing price for {set_code}/{collector_number}: {e}")
        return None