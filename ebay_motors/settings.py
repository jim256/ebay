# -*- coding: utf-8 -*-
import pathlib

project_dir = pathlib.Path(__file__).parent.parent.absolute()


BOT_NAME = 'ebay_motors'
SPIDER_MODULES = ['ebay_motors.spiders']
NEWSPIDER_MODULE = 'ebay_motors.spiders'

DEFAULT_REQUEST_HEADERS = {
  'Accept': 'application/json',
}

ITEM_PIPELINES = {
   'ebay_motors.pipelines.EbayListingCleanserPipeline': 300,
   'ebay_motors.pipelines.EbayMySQLExportPipeline': 310,
   'ebay_motors.pipelines.ItemEaterPipeline': 320,
}

MYSQL_ENABLED = True
MYSQL_HOST = ''
MYSQL_DBNAME = ''
MYSQL_USER = ''
MYSQL_PASSWD = ''
MYSQL_EBAY_TABLE = 'cars'

EBAY_CLIENT_ID = ''
EBAY_CLIENT_SECRET = ''
EBAY_RU_NAME = ''
EBAY_AUTH_URL = 'https://api.ebay.com/identity/v1/oauth2/token'
EBAY_AUTH_SCOPES = 'https://api.ebay.com/oauth/api_scope'
EBAY_SEARCH_TIMESTAMP_PATH = project_dir / 'lastrun.txt'
EBAY_SEARCH_URL = 'https://svcs.ebay.com/services/search/FindingService/v1'
# https://developer.ebay.com/Devzone/finding/CallRef/types/ItemFilterType.html
EBAY_SEARCH_ITEM_FILTERS = [
    {'name': 'ListingType', 'value': ["AuctionWithBIN", "Classified", "FixedPrice"]},
]
EBAY_SEARCH_PAGESIZE = '100'  # number of items per page in search results 1..100
EBAY_DETAILS_URL = 'http://open.api.ebay.com/shopping'

# SUPPORTED EBAY ITEM FILTER TYPES
# 'AvailableTo',
# 'BestOfferOnly',
# 'CharityOnly',
# 'Condition',
# 'Currency',
# 'EndTimeFrom',
# 'EndTimeTo',
# 'ExcludeAutoPay',
# 'ExcludeCategory',
# 'ExcludeSeller',
# 'ExpeditedShippingType',
# 'FeaturedOnly',
# 'FeedbackScoreMax',
# 'FeedbackScoreMin',
# 'FreeShippingOnly',
# 'GetItFastOnly',
# 'HideDuplicateItems',
# 'ListedIn',
# 'ListingType',
# 'LocalPickupOnly',
# 'LocalSearchOnly',
# 'LocatedIn',
# 'LotsOnly',
# 'MaxBids',
# 'MaxDistance',
# 'MaxHandlingTime',
# 'MaxPrice',
# 'MaxQuantity',
# 'MinBids',
# 'MinPrice',
# 'MinQuantity',
# 'ModTimeFrom',
# 'PaymentMethod',
# 'ReturnsAcceptedOnly',
# 'Seller',
# 'SellerBusinessType',
# 'TopRatedSellerOnly',
# 'ValueBoxInventory',
# 'WorldOfGoodOnly',

RETRY_ENABLED = False

#SPIDER_MIDDLEWARES = {
#    'ebay_motors.middlewares.EbayMotorsSpiderMiddleware': 543,
#}
#DOWNLOADER_MIDDLEWARES = {
#    'ebay_motors.middlewares.EbayMotorsDownloaderMiddleware': 543,
#}

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS = 32
# Configure a delay for requests for the same website (default: 0)
#DOWNLOAD_DELAY = 3

#AUTOTHROTTLE_ENABLED = True
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# Enable and configure HTTP caching (disabled by default)
#HTTPCACHE_ENABLED = False
#HTTPCACHE_DIR = 'httpcache'
#HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_IGNORE_HTTP_CODES = []
