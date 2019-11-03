# -*- coding: utf-8 -*-
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy.loader


class EbayListingItem(scrapy.Item):
    id = scrapy.Field(serializer=int, exclude_insert=True, exclude_update=True)  # auto inc
    name = scrapy.Field()
    source = scrapy.Field(exclude_update=True)
    source_id = scrapy.Field(serializer=int, exclude_update=True)
    price = scrapy.Field(serializer=int)
    year = scrapy.Field(serializer=int)
    make = scrapy.Field()
    model = scrapy.Field()
    submodel = scrapy.Field(exclude_insert=True, exclude_update=True)
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
    date_updated = scrapy.Field(exclude_insert=True)
    num_doors = scrapy.Field(serializer=int)
    date_analyzed = scrapy.Field(exclude_insert=True)
    seller_type = scrapy.Field()
    details = scrapy.Field()
    page_views = scrapy.Field(serializer=int)
    favorited = scrapy.Field(serializer=int)


class EbayListingItemLoader(scrapy.loader.ItemLoader):
    pass
