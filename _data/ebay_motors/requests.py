import arrow
import base64
import scrapy
import urllib.parse
try:
    from scrapy.http import JsonRequest
except ImportError:
    # Handle backward-incompatible class name change in scrapy 1.8
    from scrapy.http import JSONRequest as JsonRequest

import tests
from ebay_motors import utils


class EbayRequest(JsonRequest):
    """Client to access the Ebay API.

    Handles the OAuth2 token exchanges.
    Exposes methods to search and retrieve listings.
    """

    # This is cached at the class level so that all generated requests from
    # multiple concurrent threads can use the value without making this into
    # a singleton object.
    access_token = None

    # Default to last day
    prior_run_date = utils.ebay_date_format(arrow.utcnow().shift(days=-1))
    current_run_date = utils.ebay_date_format(arrow.utcnow())

    @classmethod
    def auth(cls, settings, *args, **kwargs) -> scrapy.Request:
        """OAuth call to get an access token for ebay APIs."""

        # Check if we are `faking` the call to ebay with a canned response for testing
        if settings.get('EBAY_MOCK_SEARCH', False):
            return cls(
                'https://postman-echo.com/post',
                headers={},
                data=tests.load_test_data('auth', settings['EBAY_MOCK_SEARCH']),
                *args, **kwargs,
            )

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
    def search(cls, settings, page: int = 1, *args, **kwargs) -> scrapy.Request:
        # Check if we are `faking` the call to ebay with a canned response for testing
        if settings.get('EBAY_MOCK_SEARCH', False):
            return cls(
                'https://postman-echo.com/post',
                headers={},
                data=tests.load_test_data('search', settings['EBAY_MOCK_SEARCH']),
                *args, **kwargs,
            )

        headers = {
            'Authorization': f'Bearer {cls.access_token}',
            'X-EBAY-SOA-GLOBAL-ID': 'EBAY-MOTOR',
            'X-EBAY-SOA-OPERATION-NAME': 'findItemsAdvanced',
            'X-EBAY-SOA-REQUEST-DATA-FORMAT': 'JSON',
            'X-EBAY-SOA-RESPONSE-DATA-FORMAT': 'JSON',
            'X-EBAY-SOA-SECURITY-APPNAME': settings['EBAY_CLIENT_ID'],
            # 'X-EBAY-SOA-SERVICE-VERSION': '1.0.0',
        }
        body = {
            "findItemsAdvancedRequest": {
                "xmlns": "https://www.ebay.com/marketplace/search/v1/services",
                "categoryId": "6001",  # All vehicle categories
                # "itemFilter": [],
                # "aspectFilters": [],
                "paginationInput": {
                    "entriesPerPage": settings.get('EBAY_SEARCH_PAGESIZE', '100'),
                    "pageNumber": str(page),
                    "sortOrder": "EndTimeSoonest",
                }
            }
        }
        if settings.get('EBAY_SEARCH_ITEM_FILTERS'):
            filters = []
            body['findItemsAdvancedRequest']['itemFilter'] = filters
            for f in settings.get('EBAY_SEARCH_ITEM_FILTERS'):
                if isinstance(f.get('value'), str):
                    f['value'] = f.get('value').format(
                        prior_run_date=cls.prior_run_date,
                        current_run_date=cls.current_run_date,
                        tomorrow=utils.ebay_date_format(arrow.utcnow().shift(days=1).floor('day')),
                        # Add other values here to make them available for replacement in
                        # item filters in settings
                    )
                filters.append(f)
        if settings.get('EBAY_SEARCH_ASPECT_FILTERS'):
            body['findItemsAdvancedRequest']['aspectFilter'] = settings.get('EBAY_SEARCH_ASPECT_FILTERS')

        return cls(
            settings['EBAY_SEARCH_URL'],
            headers=headers,
            data=body,
            *args, **kwargs,
        )

    @classmethod
    def details(cls, settings, items, *args, ** kwargs) -> scrapy.Request:
        # Check if we are `faking` the call to ebay with a canned response for testing
        if settings.get('EBAY_MOCK_SEARCH', False):
            return cls(
                'https://postman-echo.com/post',
                method='POST',
                headers={'Content-Type': 'application/xml'},
                body=tests.load_test_data('details', settings['EBAY_MOCK_SEARCH']),
                *args, **kwargs,
            )

        params = dict(
            callname='GetMultipleItems',
            responseencoding='XML',
            appid=settings['EBAY_CLIENT_ID'],
            siteid='100',  # ebay motors
            version='967',
            ItemID=','.join([i['itemId'][0] for i in items]),
            IncludeSelector='TextDescription, ItemSpecifics',
        )
        return cls(
            settings['EBAY_DETAILS_URL'] + '?' + urllib.parse.urlencode(params),
            method='GET',
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
