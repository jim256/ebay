# -*- coding: utf-8 -*-
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy.loader


class EbayListingItem(scrapy.Item):
    id = scrapy.Field(serializer=int)  # auto inc - todo: make sure it handles new inserts properly
    name = scrapy.Field()
    source = scrapy.Field()
    source_id = scrapy.Field(serializer=int)
    price = scrapy.Field(serializer=int)
    year = scrapy.Field(serializer=int)
    make = scrapy.Field()
    model = scrapy.Field()
    mileage = scrapy.Field(serializer=int)
    transmission = scrapy.Field()
    num_cylinders = scrapy.Field(serializer=int)
    drive_type = scrapy.Field()
    body_type = scrapy.Field()
    fuel_type = scrapy.Field()
    title_type = scrapy.Field()
    vin = scrapy.Field()
    trim = scrapy.Field()
    color = scrapy.Field()
    city = scrapy.Field()
    state = scrapy.Field()
    country = scrapy.Field()
    url = scrapy.Field()
    date_listed = scrapy.Field()
    date_found = scrapy.Field()
    date_updated = scrapy.Field()
    num_doors = scrapy.Field(serializer=int)
    date_analyzed = scrapy.Field()
    seller_type = scrapy.Field()
    details = scrapy.Field()
    page_views = scrapy.Field(serializer=int)
    favorited = scrapy.Field(serializer=int)


class EbayListingItemLoader(scrapy.loader.ItemLoader):
    pass
