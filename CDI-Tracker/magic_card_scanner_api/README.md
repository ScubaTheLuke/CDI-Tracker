
# Magic Card Scanner REST API

This REST API provides **Magic The Gathering** card scanning thanks to an **Optical Character Recognition (OCR)** microservice.

You can send the picture of your card and the **Magic Card Scanner OCR** will treat the image to send back the name of the card in the REST API.

After this step, the REST API will call **Scryfall**, an external **Magic The Gathering** REST API which provides the card information (like the set name or the price).

Finally, **Scryfall** will send the card information from the provided card name.

## Install

```
mvn install
```

## Run the app

```
mvn spring-boot:run
```

# REST API

The REST API will run on port `8080` by default.

## Get card information

### Request

`POST /api/scan-magic-card`

This request will show card information from a picture sent to the REST API.

### Example

Sending a picture of the card named **"Liliana of the Dark Realms"** to the REST API as a `form-data` object of type `File`.

![Magic Card](https://i.ibb.co/gwp8BWz/45b5a762-6636-500f-9459-94ee91a0e552.png)

At the end of the microservice processing, the image will be treated and cropped to only get the name of the card :

![Treated Magic Card](https://i.ibb.co/xsG9ncx/qdqdsqsd.png)

The OCR microservice will send back a json with the freshly recognized card name :

### Magic Card Scanner OCR Response

```
{
    "name": "lilianaofthedarkrealms"
}
```

Finally, the REST API will send this **fuzzy** string to the **Scryfall** REST API to get the card information.

### Magic Card Scanner API Response

```
{
    "id": "00cbe506-7332-4d29-9404-b7c6e1e791d8",
    "cardName": "Liliana of the Dark Realms",
    "printName": null,
    "releaseDate": "2013-07-19",
    "lang": "en",
    "images": {
        "small": "https://c1.scryfall.com/file/scryfall-cards/small/front/0/0/00cbe506-7332-4d29-9404-b7c6e1e791d8.jpg?1562825281",
        "normal": "https://c1.scryfall.com/file/scryfall-cards/normal/front/0/0/00cbe506-7332-4d29-9404-b7c6e1e791d8.jpg?1562825281",
        "large": "https://c1.scryfall.com/file/scryfall-cards/large/front/0/0/00cbe506-7332-4d29-9404-b7c6e1e791d8.jpg?1562825281"
    },
    "set": "m14",
    "setName": "Magic 2014",
    "collectionNumber": "102",
    "price": {
        "usd": "19.88",
        "usd_foil": "44.64",
        "eur": "14.99",
        "eur_foil": "19.99",
        "tix": "0.17"
    },
    "purchases": {
        "tcgplayer": "https://shop.tcgplayer.com/product/productsearch?id=69254&utm_campaign=affiliate&utm_medium=api&utm_source=scryfall",
        "cardmarket": "https://www.cardmarket.com/en/Magic/Products/Search?referrer=scryfall&searchString=Liliana+of+the+Dark+Realms&utm_campaign=card_prices&utm_medium=text&utm_source=scryfall",
        "cardhoarder": "https://www.cardhoarder.com/cards/49249?affiliate_id=scryfall&ref=card-profile&utm_campaign=affiliate&utm_medium=card&utm_source=scryfall"
    }
}
```

