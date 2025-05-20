import requests
import time
import urllib.parse

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"

def get_card_details(card_name=None, set_code=None, collector_number=None, lang=None, variant_info_from_app=None):
    url = None
    api_method = "object" # Default, may change to "list" for searches
    
    set_code_lower = set_code.lower().strip() if set_code else None
    card_name_stripped = card_name.strip() if card_name else None # This is the cleaned name from app.py
    collector_number_stripped = collector_number.strip() if collector_number else None
    
    lang_param_suffix = f"&lang={lang}" if lang else "" # For /named endpoint if other params exist
    lang_query_part = f'lang:{lang}' if lang else None # For search q= parameter

    # Determine lookup strategy
    # Strategy 1: Set Code + Collector Number (Most specific, assume CN points to the variant)
    if set_code_lower and collector_number_stripped:
        params = {}
        if lang: params['lang'] = lang 
        # Collector numbers are usually unique for variants. If not, this might need search.
        # For now, try direct first as it's fastest.
        param_string = urllib.parse.urlencode(params)
        url = f"{SCRYFALL_API_BASE_URL}/cards/{set_code_lower}/{collector_number_stripped}"
        if param_string: url += f"?{param_string}"
        api_method = "object"
        print(f"DEBUG Scryfall API Call (Set+CN): {url}")

    # Strategy 2: Name + Set (potentially with variant)
    elif card_name_stripped and set_code_lower:
        if variant_info_from_app: # Force search if variant info is present
            query_parts = [f'!"{card_name_stripped}"', f'set:{set_code_lower}']
            if variant_info_from_app == "borderless": query_parts.append("border:borderless")
            elif variant_info_from_app == "extendedart": query_parts.append("frame:extendedart")
            elif variant_info_from_app == "showcase": query_parts.append("frame:showcase")
            elif variant_info_from_app == "retro": query_parts.append("frame:retro")
            # For DFCs where variant is part of the name, the name itself might be enough if cleaned properly
            elif variant_info_from_app == "innocent traveler" or variant_info_from_app == "olivia, crimson bride":
                 query_parts = [f'"{card_name_stripped}"', f'set:{set_code_lower}'] # Use original name if it was a DFC variant
            if lang_query_part: query_parts.append(lang_query_part)
            if collector_number_stripped: query_parts.append(f'cn:"{collector_number_stripped}"') # Add CN if available

            search_query = " ".join(query_parts)
            encoded_query = urllib.parse.quote_plus(search_query)
            url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true"
            api_method = "list"
            print(f"DEBUG Scryfall API Call (Name+Set+Variant Search): {url}")
        else: # No variant info, try /named endpoint
            encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
            url = f"{SCRYFALL_API_BASE_URL}/cards/named?exact={encoded_card_name}&set={set_code_lower}{lang_param_suffix}"
            api_method = "object"
            print(f"DEBUG Scryfall API Call (Name+Set via /named): {url}")

    # Strategy 3: Name + Collector Number (no set, use search)
    elif card_name_stripped and collector_number_stripped:
        query_parts = [f'!"{card_name_stripped}"', f'cn:"{collector_number_stripped}"']
        if variant_info_from_app:
            if variant_info_from_app == "borderless": query_parts.append("border:borderless")
            elif variant_info_from_app == "extendedart": query_parts.append("frame:extendedart")
            elif variant_info_from_app == "showcase": query_parts.append("frame:showcase")
            elif variant_info_from_app == "retro": query_parts.append("frame:retro")
            elif variant_info_from_app == "innocent traveler" or variant_info_from_app == "olivia, crimson bride":
                 query_parts = [f'"{card_name_stripped}"', f'cn:"{collector_number_stripped}"'] 
        if lang_query_part: query_parts.append(lang_query_part)
        
        search_query = " ".join(query_parts)
        encoded_query = urllib.parse.quote_plus(search_query)
        url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true"
        api_method = "list"
        print(f"DEBUG Scryfall API Call (Name+CN+Variant Search): {url}")
        
    # Strategy 4: Name only (potentially with variant)
    elif card_name_stripped:
        if variant_info_from_app: # Force search
            query_parts = [f'!"{card_name_stripped}"']
            if variant_info_from_app == "borderless": query_parts.append("border:borderless")
            elif variant_info_from_app == "extendedart": query_parts.append("frame:extendedart")
            elif variant_info_from_app == "showcase": query_parts.append("frame:showcase")
            elif variant_info_from_app == "retro": query_parts.append("frame:retro")
            elif variant_info_from_app == "innocent traveler" or variant_info_from_app == "olivia, crimson bride":
                 query_parts = [f'"{card_name_stripped}"']
            if lang_query_part: query_parts.append(lang_query_part)

            search_query = " ".join(query_parts)
            encoded_query = urllib.parse.quote_plus(search_query)
            url = f"{SCRYFALL_API_BASE_URL}/cards/search?q={encoded_query}&unique=cards&include_extras=true"
            api_method = "list"
            print(f"DEBUG Scryfall API Call (Name Only+Variant Search): {url}")
        else: # No variant info, try /named endpoint
            encoded_card_name = urllib.parse.quote_plus(card_name_stripped)
            url = f"{SCRYFALL_API_BASE_URL}/cards/named?exact={encoded_card_name}{lang_param_suffix.replace('&', '?', 1)}" # ensure '?' if no other params
            api_method = "object"
            print(f"DEBUG Scryfall API Call (Name Only via /named): {url}")
    else:
        print("Error: Insufficient parameters for Scryfall lookup.")
        return None

    try:
        if url is None: return None # Should have been caught already
        
        response = requests.get(url)
        # print(f"Scryfall request to URL: {url}")
        # print(f"Scryfall response status: {response.status_code}")
        # if response.status_code != 200: print(f"Scryfall response text: {response.text[:500]}")
        response.raise_for_status()
        time.sleep(0.1) # Be respectful of API limits

        json_data = response.json()
        card_data_to_parse = None # This will hold the single card object chosen

        if api_method == "object":
            card_data_to_parse = json_data
        elif api_method == "list": # Results from a search
            if json_data.get("object") == "list" and json_data.get("total_cards", 0) > 0:
                all_prints_returned = json_data.get("data", [])
                
                if len(all_prints_returned) == 1:
                    card_data_to_parse = all_prints_returned[0]
                else: # Multiple cards returned from search, apply refined sorting
                    # Prioritize exact collector number match if CN was an input
                    # Then, prefer non-digital, then by release date (earliest)
                    # This is a general approach; specific variant flags from Scryfall data could refine this further
                    
                    # Filter out generally unwanted set types first, unless the search was specific for them (e.g. SLD)
                    # This might be too aggressive if a variant search correctly found an SLD card.
                    # For now, we trust a more specific search query.
                    
                    def sort_prints_key(p):
                        cn_match = 0 # Best match
                        if collector_number_stripped and p.get('collector_number') != collector_number_stripped:
                            cn_match = 1 # Lesser match if CN was specified and this one doesn't match
                        
                        is_digital = p.get('digital', False)
                        release_date = p.get('released_at', '9999-12-31')
                        
                        # Prefer paper over digital, then by CN match, then by release date
                        return (is_digital, cn_match, release_date)

                    all_prints_returned.sort(key=sort_prints_key)
                    
                    if all_prints_returned:
                        card_data_to_parse = all_prints_returned[0]
                        print(f"Info: Multiple cards ({json_data.get('total_cards')}) found for search. Prioritized: {card_data_to_parse.get('name')} ({card_data_to_parse.get('set').upper()}-{card_data_to_parse.get('collector_number')})")
                    else: # Should not be reached if total_cards > 0 and data was present
                        print(f"Warning: Search returned cards, but filtering/sorting yielded no candidates. Query: {url}")
                        return None
            else: # No cards found from search
                unquoted_query = urllib.parse.unquote_plus(url.split('q=')[1].split('&')[0]) if 'q=' in url else "N/A"
                print(f"No cards found via search for query: '{unquoted_query}'. URL: {url}")
                return None
        
        if not card_data_to_parse:
            print(f"Could not extract/select a single card data object from Scryfall response. URL: {url}")
            return None

        # Extract details from the chosen card_data_to_parse object
        name_from_api = card_data_to_parse.get('name')
        collector_number_from_api = card_data_to_parse.get('collector_number')
        set_code_from_api = card_data_to_parse.get('set')
        scryfall_id_from_api = card_data_to_parse.get('id')
        rarity_from_api = card_data_to_parse.get('rarity')
        lang_from_api = card_data_to_parse.get('lang') # Language of the card data from Scryfall
        
        market_price_usd = None
        foil_market_price_usd = None
        image_uri = None

        if card_data_to_parse.get('prices'):
            market_price_usd = card_data_to_parse['prices'].get('usd')
            foil_market_price_usd = card_data_to_parse['prices'].get('usd_foil')

        image_uris_data = card_data_to_parse.get('image_uris')
        if not image_uris_data and card_data_to_parse.get('card_faces'): # Handle DFCs
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
        error_details = e.response.text if e.response is not None else str(e)
        try: # Try to parse Scryfall error JSON for a cleaner message
            scryfall_error = e.response.json()
            if 'details' in scryfall_error: error_details = scryfall_error['details']
        except: pass # Ignore if parsing Scryfall error fails
        print(f"HTTP error {status_code} for Scryfall URL: {url}. Details: {error_details}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request error for Scryfall URL: {url}. Error: {e}")
        return None
    except ValueError as e: 
        print(f"Error parsing data (e.g., price) for card. URL: {url}. Error: {e}")
        # Fallback for partial data if main fields are present
        if card_data_to_parse and 'name' in card_data_to_parse and 'collector_number' in card_data_to_parse and 'set' in card_data_to_parse:
            return {
                "name": card_data_to_parse.get('name'), "collector_number": card_data_to_parse.get('collector_number'),
                "set_code": card_data_to_parse.get('set'), "id": card_data_to_parse.get('id'),
                "rarity": card_data_to_parse.get('rarity'), "language": card_data_to_parse.get('lang'),
                "market_price_usd": None, "foil_market_price_usd": None,
                "image_uri": image_uri # May have been set before error
            }
        return None
    except Exception as e:
        print(f"Unexpected error in get_card_details. URL: {url}. Error: {e.__class__.__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_all_set_data(): # Added this function based on its usage in app.py
    """Fetches all set data from Scryfall."""
    url = f"{SCRYFALL_API_BASE_URL}/sets"
    try:
        response = requests.get(url)
        response.raise_for_status()
        time.sleep(0.1) # Respect API rate limits
        set_data = response.json()
        if set_data.get("object") == "list" and "data" in set_data:
            # Filter out unwanted set types if necessary, or return all
            # For example, to exclude tokens:
            # return [s for s in set_data["data"] if s.get("set_type") != "token"]
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