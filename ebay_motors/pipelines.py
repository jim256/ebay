# -*- coding: utf-8 -*-
import arrow
import logging
import MySQLdb._exceptions
import re
import typing
from scrapy.exceptions import DropItem
from twisted.enterprise import adbapi

from ebay_motors.requests import EbayRequest

_DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss'


class EbayListingCleanserPipeline(object):
    """A pipeline to clean the ebay listing to prepare it for persistence."""

    # All mapping keys should be lowercase except for the DEFAULT value
    _TITLE_TYPE_MAPPING = {
        'clean': 'Clean',
        'clear': 'Clean',
        'DEFAULT': 'Salvage',
    }
    _FUEL_TYPE_MAPPING = {
        'gasoline': 'Gas',
        'diesel': 'Diesel',
        'DEFAULT': 'Other',
    }
    _SELLER_TYPE_MAPPING = {
        'private seller': 'Private',
        'dealer': 'Dealership',
        'DEFAULT': None,
    }

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    def process_item(self, item, spider):
        """Clean input values and map raw API values to internal DB values."""
        self.logger.debug(f'Processing item {item.get("source_id")}')

        item['source'] = 'ebay'
        item['date_found'] = arrow.get(EbayRequest.current_run_date).format(_DATE_FORMAT)
        item['date_updated'] = arrow.get(EbayRequest.current_run_date).format(_DATE_FORMAT)
        item['url'] = f'ebay.com/itm/{item.get("source_id")}'

        # clean out the 'not specified's
        for name in [k for k, v in item.items() if v and v.lower() in ['not specified', '--']]:
            del item[name]

        # enforce numeric fields
        numeric_fields = [name for name in item if item.fields[name].get('serializer') is int]
        for name in numeric_fields:
            if item.get(name):
                item[name] = self._ensure_numeric(item[name])

        if item.get('details'):
            item['details'] = self._ascii_only(item['details'])

        if item.get('name'):
            item['name'] = self._ascii_only(item['name'])

        if item.get('transmission'):
            item['transmission'] = item['transmission'].title()

        if item.get('mileage'):
            try:
                if item['mileage'] < 300 and (item.get('year', 9999) or 9999) < arrow.utcnow().year - 1:
                    item['mileage'] *= 1000
                elif item['mileage'] > 1000000:
                    while item['mileage'] > 1000000:
                        item['mileage'] /= 10
            except:
                pass

        if item.get('body_type'):
            body_type = item['body_type'].lower()
            if re.search(r'sports?[\s/]*utility|cross|suv', body_type):
                body_type = 'SUV'
            elif re.search(r'truck|pick[\s-]*up|(crew|regular|extended|quad|double|super)\s*cab|super\s*crew|(short|flat)\s*bed', body_type):
                body_type = 'Truck'
            elif re.search(r'sedan|compact|4dr|4\s*door', body_type):
                body_type = 'Sedan'
            elif 'coupe' in body_type:
                body_type = 'Coupe'
            elif 'convert' in body_type:
                body_type = 'Convertible'
            elif 'van' in body_type:
                body_type = 'Van'
            elif 'hatch' in body_type or 'wagon' in body_type:
                body_type = 'Hatchback'
            item['body_type'] = body_type.title()

        if item.get('drive_type'):
            drive_type = item['drive_type'].lower()
            m = re.search(r'awd|fwd|rwd|4wd', drive_type)
            if m:
                drive_type = m.group().upper()
            elif 'four wheel drive' in drive_type:
                drive_type = '4WD'
            elif re.search(r'4(?!dr)', drive_type):  # eliminate false positive on 4DR
                drive_type = '4WD'
            elif 'all' in drive_type:
                drive_type = 'AWD'
            elif 'front' in drive_type:
                drive_type = 'FWD'
            elif 'rear' in drive_type:
                drive_type = 'RWD'
            elif re.search(r'2', drive_type):  # eliminate false positive on 2DR with r'2(?!dr)'
                # Some of these body types don't necessarily mean RWD,
                # perhaps worth revisiting at some point
                rwd_body_types = re.compile(r'truck|pickup|coupe|cpe|convertible')
                if item.get('body_type'):
                    if rwd_body_types.search(item['body_type'].lower()):
                        drive_type = 'RWD'
                    else:
                        drive_type = 'FWD'
                else:
                    if rwd_body_types.search(drive_type):
                        drive_type = 'RWD'
                    else:
                        drive_type = '2WD'
            item['drive_type'] = drive_type

        if item.get('title_type'):
            item['title_type'] = self._map_field(self._TITLE_TYPE_MAPPING, item.get('title_type'))
            if item.get('details'):
                # Sometimes title type is "clean" even though the description says it is salvage - prefer description
                if any(x in item.get('details', '').lower()
                       for x in ["salvage", "branded", "buyback", "lemon", "rebuilt", "reconstructed", "rebuildable"]):
                    title_type = 'Salvage'
                    if title_type != item['title_type']:
                        self.logger.debug(f'Changed {item["title_type"]} to Salvage')
                    item['title_type'] = title_type

        if item.get('fuel_type'):
            item['fuel_type'] = self._map_field(self._FUEL_TYPE_MAPPING, item.get('fuel_type'))

        if item.get('seller_type'):
            # handle weirdness like 'Private Seller1951 chevy styleline deluxe' in the seller_type field
            seller_type = [key for key in self._SELLER_TYPE_MAPPING if item['seller_type'].lower().startswith(key)]
            if seller_type:
                item['seller_type'] = seller_type[0]
            item['seller_type'] = self._map_field(self._SELLER_TYPE_MAPPING, item['seller_type'])

        if not item.get('trim'):
            item['trim'] = item.get('submodel')

        if item.get('date_listed'):
            # Standardize the date format from Ebay to ours for MySQL
            try:
                item['date_listed'] = arrow.get(item.get('date_listed')).format(_DATE_FORMAT)
            except:
                self.logger.warning(f'Could not parse `date_listed` value of {item.get("date_listed")}')

        if item.get('bin_price'):
            # Override current price with BuyItNow price if there is one
            item['price'] = item.get('bin_price')

        return item

    def _map_field(self, mapping: dict, value):
        """Lookup the input `value` in the given `mapping`.
        Try for a DEFAULT if the value is missing and fall back to
        the original value if there is no DEFAULT.
        """
        return mapping.get(value.lower() if value else '', mapping.get('DEFAULT', value))

    def _ascii_only(self, text: str) -> str:
        """Replace all non-ascii characters with spaces."""
        return ''.join([char if ord(char) < 128 else ' ' for char in text])

    def _ensure_numeric(self, text: str) -> typing.Optional[int]:
        """Ensure the string is numeric."""
        try:
            return int(float(text))
        except:
            pass
        try:
            return int(float(re.search(r'(\d+(?:\.\d+)?|\.\d+)', text).group(1)))
        except:
            pass
        # If it isn't numeric and doesn't contain numbers to extract, return None
        return None


class MySQLExportPipeline(object):
    """A pipeline to store the item in a MySQL database.
    This implementation uses Twisted's asynchronous database API.

    Adapted from: https://github.com/rmax/dirbot-mysql
    """

    key_field = 'id'

    def __init__(self, dbpool, *args, **kwargs):
        self.dbpool = dbpool
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    @classmethod
    def from_settings(cls, settings):
        # Only process items if requested to do so
        if not settings.get('MYSQL_ENABLED', False):
            log = logging.getLogger(cls.__name__)
            log.info(f'MySQL export is disabled.  Feeds are going to {settings["FEED_URI"]}')
            return None

        dbargs = dict(
            host=settings['MYSQL_HOST'],
            db=settings['MYSQL_DBNAME'],
            user=settings['MYSQL_USER'],
            passwd=settings['MYSQL_PASSWD'],
            charset='utf8',
            use_unicode=True,
        )
        dbpool = adbapi.ConnectionPool('MySQLdb', **dbargs)
        return cls(dbpool)

    def process_item(self, item, spider, retrying=False):
        spider.processed += 1
        # run db query in the thread pool
        d = self.dbpool.runInteraction(self._do_upsert, item, spider)
        d.addErrback(self._handle_error, item, spider, retrying=retrying)
        # at the end return the item in case of success or failure
        d.addBoth(lambda _: item)
        # return the deferred instead the item. This makes the engine to
        # process next item (according to CONCURRENT_ITEMS setting) after this
        # operation (deferred) has finished.
        return d

    def _pre_process(self, cur, item, spider):
        """Perform any additional changes on item prior to storing it.
        This is intended to be overridden as needed.
        """
        pass

    def _do_upsert(self, cur, item, spider):
        """Perform an insert or update."""

        self._pre_process(cur, item, spider)

        # Adapt this [insert...on duplicate key update] approach from the following
        # https://chartio.com/resources/tutorials/how-to-insert-if-row-does-not-exist-upsert-in-mysql/
        # http://www.mysqltutorial.org/mysql-insert-or-update-on-duplicate-key-update/
        # https://pynative.com/python-mysql-execute-parameterized-query-using-prepared-statement/
        # In order to take advantage of this approach, there needs to be not only a composite
        # index on (source, source_id) but also a unique index on the same combination.

        # Loop through field specs to generate the parameterized query
        sets = ', '.join([f'@{name} = %s' for name in item])
        params = tuple(item.values())
        insert_fields = ', '.join([name for name in item if not item.fields[name].get('exclude_insert', False)])
        insert_values = ', '.join([f'@{name}' for name in item if not item.fields[name].get('exclude_insert', False)])
        updates = ', '.join([f'{name} = @{name}'
                             for name in item if not item.fields[name].get('exclude_update', False)])
        table = spider.settings['MYSQL_EBAY_TABLE']
        query = f'''
            SET {sets};
            INSERT INTO {table}
                ({insert_fields})
            VALUES
                ({insert_values})
            ON DUPLICATE KEY UPDATE
                {updates};
        '''

        cur.execute(query, params)
        # If rows affected == 1, it was a new insert
        # If rows affected == 2, it was an update
        # If rows affected == 0, nothing was changed
        self.logger.debug(f'Stored item {item.get("source_id")} to database')

    def _handle_error(self, failure, item, spider, retrying):
        """Handle occurred on db interaction."""
        try:
            # Check for deadlock
            if failure.type is MySQLdb._exceptions.OperationalError and failure.value.args[0] == 1213:
                if not retrying:
                    spider.logger.debug('Got a database deadlock...retrying transaction.')
                    return self.process_item(item, spider, retrying=True)
                else:
                    spider.logger.debug('Retried database transaction and got another deadlock.')
        except Exception as e:
            spider.logger.warning(f'Failure in database retry logic: {e}')
        spider.errors += 1
        self.logger.error(f'Error writing to the database: {failure}')


class EbayMySQLExportPipeline(MySQLExportPipeline):
    """
    Pipeline for MySQL storage with overrides for EBay-specific logic.
    """

    key_field = 'source_id'

    def _pre_process(self, cur, item, spider):
        # Tap the table to see if the row is already there to get the `price`
        table = spider.settings['MYSQL_EBAY_TABLE']
        cur.execute(f'''
            SELECT price, date_analyzed 
            FROM {table}
            WHERE source = %s and source_id = %s;
        ''', (item.get('source'), item.get('source_id')))
        rv = cur.fetchone()
        if rv:
            old_price = rv[0]
            # If the price has decreased, set the item['date_analyzed'] to None
            if item.get('price') and float(item.get('price')) < old_price:
                item['date_analyzed'] = None
            else:
                item['date_analyzed'] = rv[1]


class ItemEaterPipeline(object):
    """A pipeline to drop all documents and prevent further pipeline processing."""

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    def process_item(self, item, spider):
        """Drop the item."""
        raise DropItem(f'Ate item')


class ItemMessageFilter(logging.Filter):
    """Suppress the default warning when an item is dropped from the pipeline.

    Works with ItemEaterPipeline."""
    def filter(self, record):
        if record.msg.startswith('Dropped:'):
            return False
        return True
logging.getLogger('scrapy.core.scraper').addFilter(ItemMessageFilter())
