import base64
import logging
import scrapy
import urllib.parse
try:
    from scrapy.http import JsonRequest
except ImportError:
    # Handle backward-incompatible class name change in scrapy 1.8
    from scrapy.http import JSONRequest as JsonRequest


class EbayRequest(JsonRequest):
    """Client to access the Ebay API.

    Handles the OAuth2 token exchanges, refreshing as needed.
    Exposes methods to search and retrieve listings.
    """

    # This is cached at the class level so that all generated requests from
    # multiple concurrent threads can use the value without making this into
    # a singleton object.
    access_token = None

    @classmethod
    def auth(cls, settings, *args, **kwargs) -> scrapy.Request:
        """OAuth call to get an access token for ebay APIs."""
        basic_auth = base64.encodebytes(
            f'{settings["EBAY_CLIENT_ID"]}:{settings["EBAY_CLIENT_SECRET"]}'.encode()).decode().replace('\n', '')
        return scrapy.FormRequest(
            settings['EBAY_AUTH_URL'],
            method='POST',
            headers={
                'Authorization': f'Basic {basic_auth}',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            formdata={
                'grant_type': 'client_credentials',
                'scopes': settings['EBAY_AUTH_SCOPES'],
                'redirect_uri': settings['EBAY_RU_NAME'],
            },
            *args, **kwargs,
        )

    @classmethod
    def search_json(cls, settings, page: int = 1, *args, **kwargs):
        # Check if we are `faking` the call to ebay with a canned response for testing
        if settings.get('EBAY_MOCK_SEARCH', False):
            return cls(
                'https://postman-echo.com/post',
                headers={},
                data=_mocked_search_response,
                *args, **kwargs,
            )

        headers = {
            'Authorization': f'Bearer {cls.access_token}',
            'X-EBAY-SOA-GLOBAL-ID': 'EBAY-MOTOR',
            'X-EBAY-SOA-OPERATION-NAME': 'findItemsAdvanced',
            'X-EBAY-SOA-REQUEST-DATA-FORMAT': 'JSON',
            'X-EBAY-SOA-RESPONSE-DATA-FORMAT': 'JSON',
            'X-EBAY-SOA-SECURITY-APPNAME': settings['EBAY_APP_NAME'],
            # 'X-EBAY-SOA-SERVICE-VERSION': '1.0.0',
        }
        body = {
            "findItemsAdvancedRequest": {
                "xmlns": "https://www.ebay.com/marketplace/search/v1/services",
                "categoryId": "6001",  # All vehicle categories
                "paginationInput": {
                    "entriesPerPage": "100",  # 1..100
                    "pageNumber": str(page),
                    "sortOrder": "EndTimeSoonest",
                }
            }
        }
        if settings.get('EBAY_SEARCH_ITEM_FILTERS'):
            body['findItemsAdvancedRequest']['itemFilter'] = settings.get('EBAY_SEARCH_ITEM_FILTERS')

        return cls(
            settings['EBAY_SEARCH_URL'],
            headers=headers,
            data=body,
            *args, **kwargs,
        )

    def notes(self):
        # itemFilter: ListingType = AuctionWithBIN, Classified, and FixedPrice
        # aspectFilter: minYear, maxYear, make, model, minMileage, maxMileage, titleType
        # https://developer.ebay.com/Devzone/finding/CallRef/findItemsAdvanced.html#sampleaspectFilter
        body = {
          "findItemsAdvancedRequest": {
            "xmlns": "https://www.ebay.com/marketplace/search/v1/services",
            "categoryId": "6001",  # All vehicle categories
            "itemFilter": [
              {
                "name": "ListingType",
                "value": "AuctionWithBIN"
              },
                {
                    "name": "ListingType",
                    "value": "Classified"
                },
                {
                    "name": "ListingType",
                    "value": "FixedPrice"
                },
                {
                    "name": "MaxPrice",
                    "value": "75.00",
                    "paramName": "Currency",
                    "paramValue": "USD"
                },
                {
                    "name": "MinPrice",
                    "value": "50.00",
                    "paramName": "Currency",
                    "paramValue": "USD"
                }
            ],
            "aspectFilter": {
                "aspectName": "Megapixels",
               "aspectValueName": "5.0 to 5.9 MP"
              },
              "paginationInput": {
                  "entriesPerPage": "100",  # 1..100
                  "pageNumber": "1",
                  "sortOrder": "EndTimeSoonest",
              },
          }
        }


_mocked_search_response = {
    'ack': 'Success',
    'paginationOutput': {
        'pageNumber': '1',
        'totalPages': '1',
    },
    'searchResult': {
        'item': [
            {
                'itemId': '1',
                'title': 'title_1',
                'viewItemURL': 'url_1',
                'sellingStatus': {
                    'currentPrice': {
                        '#text': '1.0',
                    }
                },
                'location': 'CINCINNATI,OH,USA',
                'country': 'US',
                'listingInfo': {
                    'startTime': '2019-11-02 12:00:00',
                },
            },
            {
                'itemId': '2',
                'title': 'title_2',
                'viewItemURL': 'url_2',
                'sellingStatus': {
                    'currentPrice': {
                        '#text': '2.0',
                    }
                },
                'location': 'CINCINNATI,OH,USA',
                'country': 'US',
                'listingInfo': {
                    'startTime': '2019-11-02 12:00:00',
                },
            }
        ]
    }
}
