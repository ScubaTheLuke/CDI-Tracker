import requests
import time
import urllib.parse

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"

def get_card_details(card_name=None, set_code=None, collector_number=None):
    url = None
    api_method = "object" # "object" for direct card, "list" for search results

    # Clean inputs
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
    elif card_name_stripped and collector_number_stripped: # New: Name + Collector Number
        encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
        # Scryfall search query: exact name and collector number
        search_query = f'!"{encoded_card_name}" cn:"{collector_number_stripped}"'
        # Alternative query for exact name: name:"{card_name_stripped}"
        # search_query = f'name:"{card_name_stripped}" number:"{collector_number_stripped}"' # Could also work
        encoded_query = urllib.parse.quote_plus(search_query)
        url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards" # unique=cards to get printings
        api_method = "list"
    elif card_name_stripped: # Name only lookup
        encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
        url = f"{SCRYFALL_API_BASE_URL}/cards/named?exact={encoded_card_name}"
        api_method = "object"
    else:
        print("Error: Insufficient parameters for Scryfall lookup.")
        return None

    try:
        # print(f"DEBUG Scryfall URL: {url}") # Uncomment for debugging
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1) # Scryfall API courtesy delay

        json_data = response.json()
        card_data = None

        if api_method == "object":
            card_data = json_data
        elif api_method == "list":
            if json_data.get("object") == "list" and json_data.get("total_cards", 0) > 0:
                if json_data["total_cards"] == 1:
                    card_data = json_data["data"][0]
                else:
                    # Multiple cards found for Name + CN, could be ambiguous or different languages
                    # For simplicity, we'll take the first one, but log a warning.
                    # Ideally, we'd prefer an exact match based on language if specified, but Scryfall handles this well.
                    print(f"Warning: Multiple cards ({json_data['total_cards']}) found for Name+CN query '{search_query}'. Using the first result.")
                    card_data = json_data["data"][0]
            else:
                print(f"No cards found via search for Name+CN query: '{search_query if 'search_query' in locals() else 'N/A'}'. URL: {url}")
                return None

        if not card_data:
            print(f"Could not extract card data from Scryfall response. URL: {url}")
            return None

        # Extract details from card_data
        name_from_api = card_data.get('name')
        collector_number_from_api = card_data.get('collector_number')
        set_code_from_api = card_data.get('set') # Key 'set' holds the set code
        scryfall_id_from_api = card_data.get('id') # Scryfall's unique ID for the card print

        market_price_usd = None
        foil_market_price_usd = None
        image_uri = None

        if card_data.get('prices'):
            market_price_usd = card_data['prices'].get('usd')
            foil_market_price_usd = card_data['prices'].get('usd_foil')

        image_uris_data = card_data.get('image_uris')
        if not image_uris_data and card_data.get('card_faces'): # For multi-faced cards
            for face in card_data['card_faces']:
                if face.get('image_uris'):
                    image_uris_data = face.get('image_uris')
                    break

        if image_uris_data:
            image_uri = image_uris_data.get('small', image_uris_data.get('normal'))

        return {
            "name": name_from_api,
            "collector_number": collector_number_from_api,
            "set_code": set_code_from_api, # Return the set code Scryfall found/used
            "id": scryfall_id_from_api, # Return Scryfall ID
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
    except ValueError as e: # For float conversion
        print(f"Error parsing price for card. URL: {url}. Error: {e}")
        return None
    except Exception as e: # Catch-all for other unexpected errors
        print(f"An unexpected error occurred in get_card_details. URL: {url}. Error: {e}")
        return None

# ... (keep existing imports: requests, time, urllib.parse)
# ... (keep SCRYFALL_API_BASE_URL and get_card_details function)

def fetch_all_set_data():
    """Fetches all sets from Scryfall and returns a list of essential details."""
    url = f"{SCRYFALL_API_BASE_URL}/sets"
    sets_info = []
    try:
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1) # API courtesy
        data = response.json()

        if data.get("object") == "list":
            for set_obj in data.get("data", []):
                # We only want sets that typically have cards you'd inventory and have an icon
                if set_obj.get("icon_svg_uri") and set_obj.get("card_count", 0) > 0:
                    # Relevant set types: core, expansion, masters, commander, draft_innovation, etc.
                    # Exclude: token, memorabilia, funny - unless user wants them
                    relevant_types = ["core", "expansion", "masters", "commander", "draft_innovation", 
                                      "starter", "box", "promo", "duel_deck", "from_the_vault", 
                                      "premium_deck", "planechase", "archenemy", "alchemy", "funny",
                                      "masterpiece", "arsenal", "spellbook", "treasure_chest", "jumpstart",
                                      "board_game_deck", "reprint", "battle_royale_box_set", "challenger_deck"]
                                      # "token" and "memorabilia" are often excluded. "funny" is silver-bordered.
                                      # User might want "funny" sets (Un-sets)
                    
                    # Let's be more inclusive initially, can filter more later if needed
                    # For now, just check for icon and card_count.
                    sets_info.append({
                        "code": set_obj.get("code"),
                        "name": set_obj.get("name"),
                        "icon_svg_uri": set_obj.get("icon_svg_uri"),
                        "parent_set_code": set_obj.get("parent_set_code"), # Useful for sub-sets
                        "set_type": set_obj.get("set_type")
                    })
        
        # Sort by name for easier Browse in the modal, could also sort by release date
        sets_info.sort(key=lambda x: x["name"])
        return sets_info
    except requests.exceptions.RequestException as e:
        print(f"Error fetching set data from Scryfall: {e}")
        return [] # Return empty list on error
    except Exception as e:
        print(f"An unexpected error occurred in fetch_all_set_data: {e}")
        return []