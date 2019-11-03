import arrow
import json
import scrapy

from ebay_motors.items import EbayListingItem
from ebay_motors.requests import EbayRequest


class EbaySpider(scrapy.spiders.Spider):
    """

    """

    name = 'ebay'

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
            # TODO: Determine whether it is better to loop through and spin off all pages at once.
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
                'submodel': item.get(''),
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

        # TODO: check for expired token error and initiate generating a new access_token
        # This can be deferred to a future date if the expected runtime of this
        # synchronization is less than the 2 hour token expiration window.
