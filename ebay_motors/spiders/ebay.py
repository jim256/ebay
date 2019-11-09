import json
import os
import scrapy
import scrapy.signals

from ebay_motors.items import EbayListingItem
from ebay_motors.requests import EbayRequest
from ebay_motors import utils


class EbaySpider(scrapy.spiders.Spider):
    """

    """

    name = 'ebay'

    processed = 0
    errors = 0

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        # crawler.signals.connect(spider.spider_opened, signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, scrapy.signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        if not self.errors:
            self.logger.info(f'Updating prior_run_date timestamp file with {EbayRequest.current_run_date}')
            open(self.settings.get('EBAY_SEARCH_TIMESTAMP_PATH'), 'w').write(EbayRequest.current_run_date)
        else:
            self.logger.info('Not updating prior_run_date due to processing errors.')
        self.logger.info(f'\n\n-- EXECUTION STATS --\n'
                         f'Processed: {self.processed}\n'
                         f'Errors: {self.errors}\n')

    def start_requests(self):
        """Entry point for scraping."""

        self.logger.debug(f'Starting search')
        yield EbayRequest.auth(
            self.settings,
            callback=self.parse_auth_and_search,
            errback=self.auth_error)

    def parse_auth_and_search(self, response):
        """Pull out the access token and submit the initial search."""

        # Take the access_token from the auth response and put it on the EbayRequest class
        auth_resp = json.loads(response.text)

        # If `faking` the response, pull out the response content
        if self.settings.get('EBAY_MOCK_SEARCH', False):
            auth_resp = auth_resp.get('data')

        EbayRequest.access_token = auth_resp['access_token']

        if self.settings.get('EBAY_SEARCH_TIMESTAMP_PATH') and \
                os.path.isfile(self.settings['EBAY_SEARCH_TIMESTAMP_PATH']):
            prior_run_date = open(self.settings['EBAY_SEARCH_TIMESTAMP_PATH']).read()
            EbayRequest.prior_run_date = prior_run_date
        self.logger.info(f'Initializing {self.name} spider with prior run date of {EbayRequest.prior_run_date}')

        yield EbayRequest.search(
            self.settings,
            callback=self.parse_results,
            errback=self.search_error)

    def parse_results(self, response):
        """
        Process a page of search results.

        Kick off additional page searches if there are more.
        Initiate detail searches for all items returned.
        """
        search_resp = json.loads(response.text)

        # If `faking` the response, pull out the response content
        if self.settings.get('EBAY_MOCK_SEARCH', False):
            search_resp = search_resp.get('data')

        # Get to the body of the response
        search_resp = search_resp.get('findItemsAdvancedResponse')
        if search_resp:
            search_resp = search_resp[0]
        else:
            self.logger.error(f'No body in response from search: {response.text}')
            return

        # Check status of response
        if search_resp['ack'] and search_resp['ack'][0] in ['Failure', 'PartialFailure']:  # Other values are 'Success', 'Warning'
            self.errors += 1
            self.logger.error(f'Error(s) returned from search: {search_resp["errorMessage"]}')
            return

        # Check pagination
        cur_page = int(search_resp.get('paginationOutput', [{}])[0].get('pageNumber', ['1'])[0])
        total_pages = int(search_resp.get('paginationOutput', [{}])[0].get('totalPages', ['1'])[0])
        self.logger.info(f'Search results contain {total_pages} pages.')
        # If there are more pages, go get them
        if cur_page == 1 and total_pages > 1:
            for page in range(cur_page + 1, total_pages + 1):
                self.logger.debug(f'Requesting page {page} of {total_pages}')
                yield EbayRequest.search(
                    self.settings,
                    page=page,
                    callback=self.parse_results,
                    errback=self.search_error)

        # Take the high level info and process the items in batches
        # eBay currently only supports batches of 20 items
        batch_num = 0
        for batch in utils.batches(search_resp.get('searchResult', [{}])[0].get('item', []), 20):
            batch_num += 1
            self.logger.info(f'Request details for batch {batch_num} of page {cur_page}')
            yield EbayRequest.details(
                self.settings,
                items=batch,
                callback=self.parse_details,
                errback=self.detail_error,
                cb_kwargs={'items': batch})

    def parse_details(self, response, items):
        """

        """
        # If `faking` the response, pull out the response content
        if self.settings.get('EBAY_MOCK_SEARCH', False):
            response = scrapy.Selector(text=json.loads(response.text)['data'], type='xml')
            response.remove_namespaces()
        else:
            response.selector.remove_namespaces()

        # Check status of response
        if response.xpath('/GetMultipleItemsResponse/Ack').get() in ['Failure', 'PartialFailure']:
            # Other values are 'Success', 'Warning'
            self.errors += 1
            self.logger.error(f'Error(s) returned from details: '
                              f'{response.xpath("/GetMultipleItemsResponse/ErrorMessage").get()}')
            return

        for item in items:
            try:
                detail = response.xpath(f'/GetMultipleItemsResponse/Item[ItemID="{item["itemId"][0]}"]')[0]
            except IndexError:
                self.logger.warning(f'Detail records did not contain item `{item["itemId"][0]}`, skipping')
                continue
            yield EbayListingItem({
                'source_id': item.get('itemId', [None])[0],
                'name': item.get('title', [None])[0],
                'url': item.get('viewItemURL', [None])[0],
                'price': item.get('sellingStatus', [{}])[0].get('currentPrice', [{}])[0].get('__value__'),
                'city': item['location'][0].rsplit(',', maxsplit=2)[0] if ',' in item.get('location', [''])[0] else None,
                'state': item['location'][0].rsplit(',', maxsplit=2)[1] if ',' in item.get('location', [''])[0] else None,
                'country': item.get('country', [None])[0],
                'date_listed': item.get('listingInfo', [{}])[0].get('startTime')[0],
                'favorited': item.get('listingInfo', [{}])[0].get('watchCount', [None])[0],

                'bin_price': detail.xpath('ConvertedBuyItNowPrice/text()').get(),
                'page_views': detail.xpath('HitCount/text()').get(),
                'seller_type': detail.xpath('ItemSpecifics/NameValueList[Name="For Sale By"]/Value/text()').get(),
                'details': detail.xpath('Description/text()').get(),
                'year': detail.xpath('ItemSpecifics/NameValueList[Name="Year"]/Value/text()').get(),
                'make': detail.xpath('ItemSpecifics/NameValueList[Name="Make"]/Value/text()').get(),
                'model': detail.xpath('ItemSpecifics/NameValueList[Name="Model"]/Value/text()').get(),
                'submodel': detail.xpath('ItemSpecifics/NameValueList[Name="Sub Model"]/Value/text()').get(),
                'mileage': detail.xpath('ItemSpecifics/NameValueList[Name="Mileage"]/Value/text()').get(),
                'transmission': detail.xpath('ItemSpecifics/NameValueList[Name="Transmission"]/Value/text()').get(),
                'num_cylinders': detail.xpath('ItemSpecifics/NameValueList[Name="Number of Cylinders"]/Value/text()').get(),
                'drive_type': detail.xpath('ItemSpecifics/NameValueList[Name="Drive Type"]/Value/text()').get(),
                'body_type': detail.xpath('ItemSpecifics/NameValueList[Name="Body Type"]/Value/text()').get(),
                'fuel_type': detail.xpath('ItemSpecifics/NameValueList[Name="Fuel Type"]/Value/text()').get(),
                'title_type': detail.xpath('ItemSpecifics/NameValueList[Name="Vehicle Title"]/Value/text()').get(),
                'vin': detail.xpath('ItemSpecifics/NameValueList[Name="VIN"]/Value/text()').get(),
                'trim': detail.xpath('ItemSpecifics/NameValueList[Name="Trim"]/Value/text()').get(),
                'color': detail.xpath('ItemSpecifics/NameValueList[Name="Exterior Color"]/Value/text()').get(),
                'num_doors': detail.xpath('ItemSpecifics/NameValueList[Name="Number of Doors"]/Value/text()').get(),
            })

    def auth_error(self, failure):
        self.errors += 1
        self.logger.error(repr(failure))
        self.logger.error(failure.value.response.body)

    def search_error(self, failure):
        self.errors += 1
        self.logger.error(repr(failure))
        self.logger.error(failure.value.response.body)

        # Check for expired token error and initiate generating a new access_token
        # This can be deferred to a future date if the expected runtime of this
        # synchronization is less than the 2 hour token expiration window.

    def detail_error(self, failure):
        self.errors += 1
        self.logger.error(repr(failure))
        self.logger.error(failure.value.response.body)

        # Check for expired token error and initiate generating a new access_token
        # This can be deferred to a future date if the expected runtime of this
        # synchronization is less than the 2 hour token expiration window.
