# -*- coding: utf-8 -*-
import arrow
import logging
from twisted.enterprise import adbapi

_DATE_FORMAT = 'MM/DD/YYYY HH:mm:ss'


class EbayListingCleanserPipeline(object):
    """A pipeline to clean the ebay listing to prepare it for persistence."""

    # All mapping keys should be lowercase except for the DEFAULT value
    _TITLE_TYPE_MAPPING = {
        'clean title': 'clean',
        'not specified': None,
        'DEFAULT': 'Salvage',
    }
    _FUEL_TYPE_MAPPING = {
        'gasoline': 'Gas',
        'diesel': 'Diesel',
        'not specified': None,
        '_DEFAULT': 'Other',
    }

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    def process_item(self, item, spider):
        self.logger.debug(f'Processing {item}')
        item['source'] = 'ebay'
        item['date_found'] = arrow.utcnow().format(_DATE_FORMAT)
        if 'details' in item:
            item['details'] = self.ascii_only(item['details'])
        if 'name' in item:
            item['name'] = self.ascii_only(item['name'])
        if 'title_type' in item:
            item['title_type'] = self.map_field(self._TITLE_TYPE_MAPPING, item.get('title_type'))
            # Sometimes title type is "clean" even though the description says it is salvage - prefer description
            if any(x in item['details'].lower()
                   for x in ["salvage", "branded", "buyback", "lemon", "rebuilt", "reconstructed", "rebuildable"]):
                title_type = 'Salvage'
                if title_type != item['title_type']:
                    self.logger.debug(f'Changed {item["title_type"]} to Salvage')
                item['title_type'] = title_type
        if 'fuel_type' in item:
            item['fuel_type'] = self.map_field(self._FUEL_TYPE_MAPPING, item.get('fuel_type'))
        return item

    def map_field(self, mapping: dict, value):
        """Lookup the input `value` in the given `mapping`.
        Try for a DEFAULT if the value is missing and fall back to
        the original value if there is no DEFAULT.
        """
        return mapping.get(value.lower() if value else '', mapping.get('DEFAULT', value))

    def ascii_only(self, text: str) -> str:
        """Replace all non-ascii characters with spaces."""
        return ''.join([char if ord(char) < 128 else ' ' for char in text])


class MySQLExportPipeline(object):
    """A pipeline to store the item in a MySQL database.
    This implementation uses Twisted's asynchronous database API.

    Adapted from: https://github.com/rmax/dirbot-mysql
    """

    def __init__(self, dbpool, *args, **kwargs):
        self.dbpool = dbpool
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)

    @classmethod
    def from_settings(cls, settings):
        # Only process items if requested to do so
        if settings['FEED_URI'] is None or settings['FEED_URI'].lower() != 'mysql':
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

    def _do_upsert(self, conn, item, spider):
        """Perform an insert or update."""
        id = item['id']
        now = arrow.utcnow().format(_DATE_FORMAT)

        # TODO: adapt this [insert...on duplicate key update] approach
        # https://chartio.com/resources/tutorials/how-to-insert-if-row-does-not-exist-upsert-in-mysql/
        query = '''
            SET @id = 1,
                @title = 'In Search of Lost Time',
                @author = 'Marcel Proust',
                @year_published = 1913;
            INSERT INTO books
                (id, title, author, year_published)
            VALUES
                (@id, @title, @author, @year_published)
            ON DUPLICATE KEY UPDATE
                title = @title,
                author = @author,
                year_published = @year_published;
        '''

        rv = conn.execute(query)
        # Check the return value to validate the insert/update
        self.logger.debug(f'Stored item {id} to database.')

    def _handle_error(self, failure, item, spider):
        """Handle occurred on db interaction."""
        # do nothing, just log
        self.logger.error(failure)
