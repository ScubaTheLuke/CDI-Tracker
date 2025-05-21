import requests
import time
import urllib.parse

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"

def get_card_details(card_name=None, set_code=None, collector_number=None, lang=None, variant_info_from_app=None):
    url = None
    api_method = "object" 
    
    original_set_input = set_code # Preserve original input for search query if it's a name
    set_code_cleaned_for_path = set_code.lower().strip() if set_code else None # For direct path usage
    card_name_cleaned = card_name.strip() if card_name else None
    collector_number_cleaned = collector_number.strip() if collector_number else None
    
    # Heuristic: Scryfall set codes are typically short (2-5 chars) and don't contain spaces.
    is_likely_actual_set_code = bool(
        set_code_cleaned_for_path and 
        len(set_code_cleaned_for_path) <= 5 and 
        ' ' not in set_code_cleaned_for_path
    )

    # --- Determine URL and API Method ---

    # Priority 1: Actual Set Code (short form) + Collector Number
    if is_likely_actual_set_code and collector_number_cleaned:
        url = f"{SCRYFALL_API_BASE_URL}/cards/{set_code_cleaned_for_path}/{collector_number_cleaned}"
        # Scryfall ignores 'lang' for this endpoint, so we don't add it.
        api_method = "object"
        print(f"DEBUG Scryfall API Call (Direct SetCode+CN): {url}")
    
    # Priority 2: Name + Set (original_set_input could be a code or full name) + Collector Number (optional)
    # This will now primarily use search, which is more flexible for set names and variants.
    elif card_name_cleaned and original_set_input:
        query_parts = [f'!"{card_name_cleaned}"'] # Exact name match
        query_parts.append(f'set:"{original_set_input.strip()}"') # Use quotes for set names with spaces

        if collector_number_cleaned:
            query_parts.append(f'cn:"{collector_number_cleaned}"')
        
        if variant_info_from_app:
            if variant_info_from_app == "borderless": query_parts.append("border:borderless")
            elif variant_info_from_app == "extendedart": query_parts.append("frame:extendedart")
            elif variant_info_from_app == "showcase": query_parts.append("frame:showcase")
            elif variant_info_from_app == "retro": query_parts.append("frame:retro")
            # For DFCs where variant is part of the name, the cleaned name might be sufficient
            # or the original full name might be needed if scryfall_lookup_name was too aggressive.
            # This part of variant logic is from app.py's responsibility to pass correct name.

        if lang: query_parts.append(f'lang:{lang}')
        
        search_query = " ".join(query_parts)
        encoded_query = urllib.parse.quote_plus(search_query)
        url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true"
        api_method = "list"
        print(f"DEBUG Scryfall API Call (Search Name+Set[+CN/+Variant]): {url}")

    # Priority 3: Name + Collector Number (no set specified)
    elif card_name_cleaned and collector_number_cleaned:
        query_parts = [f'!"{card_name_cleaned}"', f'cn:"{collector_number_cleaned}"']
        if variant_info_from_app:
            if variant_info_from_app == "borderless": query_parts.append("border:borderless")
            elif variant_info_from_app == "extendedart": query_parts.append("frame:extendedart")
            elif variant_info_from_app == "showcase": query_parts.append("frame:showcase")
            elif variant_info_from_app == "retro": query_parts.append("frame:retro")
        if lang: query_parts.append(f'lang:{lang}')
        
        search_query = " ".join(query_parts)
        encoded_query = urllib.parse.quote_plus(search_query)
        url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true"
        api_method = "list"
        print(f"DEBUG Scryfall API Call (Search Name+CN[+Variant]): {url}")

    # Priority 4: Name only
    elif card_name_cleaned:
        query_parts = [f'!"{card_name_cleaned}"']
        if variant_info_from_app:
            if variant_info_from_app == "borderless": query_parts.append("border:borderless")
            elif variant_info_from_app == "extendedart": query_parts.append("frame:extendedart")
            elif variant_info_from_app == "showcase": query_parts.append("frame:showcase")
            elif variant_info_from_app == "retro": query_parts.append("frame:retro")
        if lang: query_parts.append(f'lang:{lang}')
        
        search_query = " ".join(query_parts)
        # Using unique=cards to get distinct cards, include_extras for variant data
        encoded_query = urllib.parse.quote_plus(search_query)
        url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true"
        api_method = "list"
        print(f"DEBUG Scryfall API Call (Search Name Only[+Variant]): {url}")
    
    else:
        print("Error: Insufficient parameters for Scryfall lookup.")
        return None

    # --- Request Execution and Response Parsing ---
    try:
        if url is None: return None
        
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1) 

        json_data = response.json()
        card_data_to_parse = None 

        if api_method == "object":
            card_data_to_parse = json_data
        elif api_method == "list": 
            if json_data.get("object") == "list" and json_data.get("total_cards", 0) > 0:
                all_prints_returned = json_data.get("data", [])
                
                if len(all_prints_returned) == 1:
                    card_data_to_parse = all_prints_returned[0]
                else: 
                    # Refined sorting for multiple search results
                    def sort_prints_key(p):
                        cn_match_score = 0 # Best (0) if CN matches or no CN was searched
                        if collector_number_cleaned and p.get('collector_number') != collector_number_cleaned:
                            cn_match_score = 1 # Lower preference if CN was searched and this doesn't match
                        
                        is_digital = p.get('digital', False)
                        release_date = p.get('released_at', '9999-12-31')
                        
                        # Prioritize: non-digital, then collector number match, then earliest release
                        return (is_digital, cn_match_score, release_date)

                    all_prints_returned.sort(key=sort_prints_key)
                    
                    if all_prints_returned:
                        card_data_to_parse = all_prints_returned[0]
                        print(f"Info: Multiple cards ({json_data.get('total_cards')}) found for search. Prioritized: {card_data_to_parse.get('name')} ({card_data_to_parse.get('set').upper()}-{card_data_to_parse.get('collector_number')}) Release: {card_data_to_parse.get('released_at')}")
                    else:
                        print(f"Warning: Search returned cards, but filtering/sorting yielded no candidates. Query: {url}")
                        return None
            else: 
                unquoted_query = urllib.parse.unquote_plus(url.split('q=')[1].split('&')[0]) if 'q=' in url else "N/A"
                print(f"No cards found via search for query: '{unquoted_query}'. URL: {url}")
                return None
        
        if not card_data_to_parse:
            print(f"Could not extract/select a single card data object from Scryfall response. URL: {url}")
            return None

        name_from_api = card_data_to_parse.get('name')
        collector_number_from_api = card_data_to_parse.get('collector_number')
        set_code_from_api = card_data_to_parse.get('set')
        scryfall_id_from_api = card_data_to_parse.get('id')
        rarity_from_api = card_data_to_parse.get('rarity')
        lang_from_api = card_data_to_parse.get('lang') 
        
        market_price_usd = None
        foil_market_price_usd = None
        image_uri = None

        if card_data_to_parse.get('prices'):
            market_price_usd = card_data_to_parse['prices'].get('usd')
            foil_market_price_usd = card_data_to_parse['prices'].get('usd_foil')

        image_uris_data = card_data_to_parse.get('image_uris')
        if not image_uris_data and card_data_to_parse.get('card_faces'): 
            for face in card_data_to_parse['card_faces']:
                if face.get('image_uris'):
                    image_uris_data = face.get('image_uris'); break
        if image_uris_data:
            image_uri = image_uris_data.get('small', image_uris_data.get('normal', image_uris_data.get('large')))

        return {
            "name": name_from_api, "collector_number": collector_number_from_api,
            "set_code": set_code_from_api, "id": scryfall_id_from_api,
            "rarity": rarity_from_api, "language": lang_from_api,
            "market_price_usd": float(market_price_usd) if market_price_usd else None,
            "foil_market_price_usd": float(foil_market_price_usd) if foil_market_price_usd else None,
            "image_uri": image_uri
        }

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "Unknown"
        error_details_str = str(e)
        if e.response is not None:
            try: scryfall_error = e.response.json(); error_details_str = scryfall_error.get('details', e.response.text)
            except ValueError: error_details_str = e.response.text[:500] # Show beginning of text if not JSON
        print(f"HTTP error {status_code} for Scryfall URL: {url}. Details: {error_details_str}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request error for Scryfall URL: {url}. Error: {e}")
        return None
    except ValueError as e: 
        print(f"Error parsing data (e.g., price) for card. URL: {url}. Error: {e}")
        if card_data_to_parse and 'name' in card_data_to_parse: # Attempt to return partial if possible
            return { "name": card_data_to_parse.get('name'), "collector_number": card_data_to_parse.get('collector_number'), "set_code": card_data_to_parse.get('set'), "id": card_data_to_parse.get('id'), "rarity": card_data_to_parse.get('rarity'), "language": card_data_to_parse.get('lang'), "market_price_usd": None, "foil_market_price_usd": None, "image_uri": card_data_to_parse.get('image_uris', {}).get('small') }
        return None
    except Exception as e:
        print(f"Unexpected error in get_card_details. URL: {url}. Error: {e.__class__.__name__}: {e}")
        import traceback; traceback.print_exc()
        return None

def fetch_all_set_data():
    url = f"{SCRYFALL_API_BASE_URL}/sets"
    try:
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1)
        set_data = response.json()
        if set_data.get("object") == "list" and "data" in set_data:
            return sorted(set_data["data"], key=lambda s: s.get("name", "").lower())
        else:
            print("Failed to parse set data from Scryfall or no data found.")
            return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching all sets: {e.response.status_code} - {e.response.text if e.response is not None else e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request error fetching all sets: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching all sets: {e}")
        return None