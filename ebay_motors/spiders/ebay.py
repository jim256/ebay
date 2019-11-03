import arrow
import base64
import json
import logging
import scrapy
import urllib.parse
try:
    from scrapy.http import JsonRequest
except ImportError:
    # Handle backward-incompatible class name change in scrapy 1.8
    from scrapy.http import JSONRequest as JsonRequest

from ebay_motors.items import EbayListingItem


class EbaySpider(scrapy.spiders.Spider):
    """

    """

    name = 'ebay'

    # handle_httpstatus_list = [500]

    def start_requests(self):
        self.logger.debug(f'Starting search')

        # TODO: lookup prior run timestamp to set start_date for this run
        prior_run_date = arrow.get().shift(hours=-1)  # hacked for now to be last hour
        self.logger.debug(f'Initializing {self.name} spider with prior run date of {prior_run_date}')
        # self.settings.set('PRIOR_RUN_DATE', prior_run_date)

        yield EbayRequest.auth(
            self.settings,
            callback=self.parse_auth_and_search,
            errback=self.auth_error)

    def parse_auth_and_search(self, response):
        # Take the access_token from the auth response and put it on the EbayRequest class
        auth_resp = json.loads(response.text)
        EbayRequest.access_token = auth_resp['access_token']
        yield EbayRequest.search_json(
            self.settings,
            callback=self.parse_results,
            errback=self.search_error)

    def parse_results(self, response):
        search_resp = json.loads(response.text)
        # Check status of response
        if search_resp['ack'] in ['Failure', 'PartialFailure']:  # Other values are 'Success', 'Warning'
            self.logger.error(f'Error(s) returned from search: {search_resp["errorMessage"]}')
            return
        # Check pagination
        cur_page = int(search_resp.get('paginationOutput', {}).get('pageNumber', '1'))
        total_pages = int(search_resp.get('paginationOutput', {}).get('totalPages', '1'))
        # If there are more pages, go get them
        if cur_page < total_pages:
            self.logger.debug(f'Requesting page {cur_page + 1} of {total_pages}')
            yield EbayRequest.search_json(
                self.settings,
                page=cur_page + 1,
                callback=self.parse_results,
                errback=self.search_error)

        # Loop through all the items and yield them for persistence
        for item in search_resp['searchResult']['item']:
            yield EbayListingItem({
                'source_id': item.get('itemId'),
                'name': item.get('title'),
                'url': item.get('viewItemURL'),
                'price': item.get('sellingStatus', {}).get('currentPrice', {}).get('#text'),
                'city': item.get('location').rsplit(',', maxsplit=2)[0] if ',' in item.get('location', '') else None,
                'state': item.get('location').rsplit(',', maxsplit=2)[1] if ',' in item.get('location', '') else None,
                'country': item.get('country'),
                'date_listed': item.get('listingInfo', {}).get('startTime'),
                'seller_type': item.get(''),
                'details': item.get(''),
                'page_views': item.get(''),
                'favorited': item.get(''),

                'year': item.get(''),
                'make': item.get(''),
                'model': item.get(''),
                'mileage': item.get(''),
                'transmission': item.get(''),
                'num_cylinders': item.get(''),
                'drive_type': item.get(''),
                'body_type': item.get(''),
                'fuel_type': item.get(''),
                'title_type': item.get(''),
                'vin': item.get(''),
                'trim': item.get(''),
                'color': item.get(''),
                'num_doors': item.get(''),
            })

    def auth_error(self, failure):
        self.logger.error(repr(failure))
        self.logger.error(failure.value.response.body)

    def search_error(self, failure):
        self.logger.error(repr(failure))
        self.logger.error(failure.value.response.body)


class EbayRequest(JsonRequest):
    """Client to access the Ebay API.

    Handles the OAuth2 token exchanges, refreshing as needed.
    Exposes methods to search and retrieve listings.
    """

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
        headers = {
            'Authorization': f'Bearer {cls.access_token}',
            'X-EBAY-SOA-GLOBAL-ID': 'EBAY-MOTOR',
            'X-EBAY-SOA-OPERATION-NAME': 'findItemsAdvanced',
            'X-EBAY-SOA-REQUEST-DATA-FORMAT': 'JSON',
            'X-EBAY-SOA-RESPONSE-DATA-FORMAT': 'JSON',
            'X-EBAY-SOA-SECURITY-APPNAME': settings['DEVID'],  # TODO: verify this is the right value -- it's not
            # 'X-EBAY-SOA-SERVICE-VERSION': '1.0.0',
        }
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
                ],
                "paginationInput": {
                    "entriesPerPage": "100",  # 1..100
                    "pageNumber": str(page),
                    "sortOrder": "EndTimeSoonest",
                }
            }
        }
        return cls(
            settings['EBAY_FIND_URL'],
            headers=headers,
            data=body,
            *args, **kwargs,
        )

    @classmethod
    def search_get(cls, settings):
        log = logging.getLogger(cls.__name__)
        log.debug(f'Searching ebay as {settings.get("EBAY_DEVID")}')

        # https://developer.ebay.com/Devzone/finding/Concepts/MakingACall.html#StandardURLParameters
        # https://developer.ebay.com/Devzone/finding/Concepts/SiteIDToGlobalID.html
        headers = {
            'Authorization': f'Bearer {cls.access_token}',
        }
        search_criteria = {
            'OPERATION-NAME': 'findItemsAdvanced',
            'SERVICE-NAME': 'FindingService',
            'SERVICE-VERSION': '1.0.0',
            'GLOBAL-ID': 'EBAY-US',
            'SECURITY-APPNAME': settings['EBAY_DEVID'],
            'RESPONSE-DATA-FORMAT': 'JSON',
            'REST-PAYLOAD': None,
            # &Standard input fields
            # 'paginationInput': '',
            # 'sortOrder': '',
            # 'itemFilter': '',
            # 'aspectFilter': '',
            # 'outputSelector': '',
            # &Call-specific input fields
        }

        # Note: If the spider is running for longer than the access_token
        # is valid (typically 2 hours), subsequent search calls could fail
        #
        # Return a deferred to the actual call
        return cls(
            settings,
            f'{settings.get("EBAY_FIND_URL")}?{urllib.parse.urlencode(search_criteria)}',
            method='GET',
            headers=headers,
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

        _ITEM_FILTERS = [
        'AvailableTo',
        'BestOfferOnly',
        'CharityOnly',
        'Condition',
        'Currency',
        'EndTimeFrom',
        'EndTimeTo',
        'ExcludeAutoPay',
        'ExcludeCategory',
        'ExcludeSeller',
        'ExpeditedShippingType',
        'FeaturedOnly',
        'FeedbackScoreMax',
        'FeedbackScoreMin',
        'FreeShippingOnly',
        'GetItFastOnly',
        'HideDuplicateItems',
        'ListedIn',
        'ListingType',
        'LocalPickupOnly',
        'LocalSearchOnly',
        'LocatedIn',
        'LotsOnly',
        'MaxBids',
        'MaxDistance',
        'MaxHandlingTime',
        'MaxPrice',
        'MaxQuantity',
        'MinBids',
        'MinPrice',
        'MinQuantity',
        'ModTimeFrom',
        'PaymentMethod',
        'ReturnsAcceptedOnly',
        'Seller',
        'SellerBusinessType',
        'TopRatedSellerOnly',
        'ValueBoxInventory',
        'WorldOfGoodOnly',
    ]
