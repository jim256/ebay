# -*- coding: utf-8 -*-
import arrow
import logging
import re
from scrapy.exceptions import DropItem
from twisted.enterprise import adbapi

from ebay_motors.requests import EbayRequest

_DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss'


class EbayListingCleanserPipeline(object):
    """A pipeline to clean the ebay listing to prepare it for persistence."""

    # All mapping keys should be lowercase except for the DEFAULT value
    _TITLE_TYPE_MAPPING = {
        'clean': 'clean',
        'clear': 'clean',
        'DEFAULT': 'Salvage',
    }
    _FUEL_TYPE_MAPPING = {
        'gasoline': 'Gas',
        'diesel': 'Diesel',
        'DEFAULT': 'Other',
    }
    _SELLER_TYPE_MAPPING = {
        'private seller': 'private',
        'dealer': 'dealership',
        'DEFAULT': None,
    }

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    def process_item(self, item, spider):
        """Clean input values and map raw API values to internal DB values."""
        self.logger.debug(f'Processing item {item.get("source_id")}')

        # clean out the 'not specified's
        for name in [k for k, v in item.items() if v and v.lower() == 'not specified']:
            del item[name]

        item['source'] = 'ebay'
        item['date_found'] = arrow.get(EbayRequest.current_run_date).format(_DATE_FORMAT)
        item['date_updated'] = arrow.get(EbayRequest.current_run_date).format(_DATE_FORMAT)

        if item.get('details'):
            item['details'] = self._ascii_only(item['details'])

        if item.get('name'):
            item['name'] = self._ascii_only(item['name'])

        if item.get('num_doors'):
            if not item['num_doors'].isnumeric():
                # e.g. '4 Doors'
                item['num_doors'] = item['num_doors'][0]

        if item.get('num_cylinders'):
            if not item['num_cylinders'].isnumeric():
                # e.g. 'V8' -- strip out all non-numerics
                item['num_cylinders'] = re.sub(r'\D', '', item['num_cylinders'])
            if not item['num_cylinders']:
                item['num_cylinders'] = None

        if item.get('mileage'):
            if not item['mileage'].isnumeric():
                # e.g. 'N/A'
                item['mileage'] = None

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
            # handle weirdness like 'Private Seller1951 chevy styleline deluxe'
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

    def process_item(self, item, spider):
        # run db query in the thread pool
        d = self.dbpool.runInteraction(self._do_upsert, item, spider)
        d.addErrback(self._handle_error, item, spider)
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

    def _handle_error(self, failure, item, spider):
        """Handle occurred on db interaction."""
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
            SELECT price 
            FROM {table}
            WHERE source = %s and source_id = %s;
        ''', (item.get('source'), item.get('source_id')))
        rv = cur.fetchone()
        if rv:
            old_price = rv[0]
            # If the price has decreased, set the item['date_analyzed'] to None
            if item.get('price') and float(item.get('price')) < old_price:
                item['date_analyzed'] = None


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
