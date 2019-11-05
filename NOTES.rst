Notes
=====

`run.py`

- This is the starting point for execution.  It provides access to common scrapy parameters, sets up custom log rotation, and implements the config file and command line overrides for the project settings.
- The simplest form of execution is ``run.py spidername``

`settings.py`

- Most parameters that control scrapy execution live here.  Additionally, this houses the default values for the EBay API authentication and execution as well as the MySQL connection information.

`spiders.ebay.py`

- `EbaySpider` is the spider itself.
- `start_requests()` is the entry point, which initiates the EBay OAuth sequence with `requests.EbayRequest.auth()`.
- `parse_auth_and_search()` retrieves the API access_token, looks up the prior run date to use a search parameter, and initiates the search with `requests.EbayRequest.search()`.
- `parse_results()` checks whether there are additional pages of results, and initiates the next search(es).  Then it breaks up the returned items into batches of 20 since that's the most where we can get details at a time, and initiates the detail retrieval with `requests.EbayRequest.details()`.  `parse_results()` is called once for each page of 100 search results.
- `parse_details()` matches up the initial search results to the returned details and populates an `items.EbayListingItem` for each.  The items then go through the `pipelines.EbayListingCleanserPipeline.process_item()` call for cleansing and data mapping and to the `pipelines.MySQLExportPipeline._do_upsert()` call for persistence.  `parse_details()` is called once for each batch of 20 detail results.

`requests.py`

- `EbayRequest` is the JsonRequest subclass that handles communication with the EBay API.
- `auth()` performs the OAuth sequence with the credentials from the settings/config.
- `search()` executes the ``findItemsAdvanced`` API method with support for pagination and search item filters from the settings/config.  This also supports returning mocked responses for testing.
- `details()` executes the ``GetMultipleItems`` API method for the ItemIDs returned from the `search()`.  This also supports returning mocked responses for testing.

`items.py`

- `EbayListingItem` is the model for incoming items from the EBay API.  The fields defined on this model match the target MySQL schema.
- `serializer` attributes are specified for fields that have special data types.
- `exclude_insert` and `exclude_update` attributes are specified to control how the fields are used during the upsert process.  Any field with both of these is available for cleansing/mapping/processing but does not get persisted.

`pipelines.py`

- `EbayListingCleanserPipeline` applies any custom cleansing or mapping rules.  Mapping dictionaries are used to provide direct mappings for fields where that applies to facilitate maintenance.
- `MySQLExportPipeline` is a generic pipeline implementation that creates a pool of database connections, calls an internal `_do_upsert()` method for each incoming item, and returns that item for other pipeline processing.  It supports an overridable `_pre_process()` method for subclasses to provide logic specific to their needs.
- `EbayMySQLExportPipeline` is the EBay-specific subclass with all of the unique pre-processing logic.


Points of Configuration
-----------------------

These are the most common places where changes would be made to tweak the execution for the content of the items searched or the data mapping/cleansing from the Ebay API to the MySQL table.

`lastrun.txt`

- This contains the timestamp of the prior execution.  it is update at the end of each run.  You can modify it to control a run if you need to execute with a different reference date.

`settings.py`

- EBAY_SEARCH_ITEM_FILTERS

`pipelines.py`

- EbayListingCleanserPipeline
    - Mapping dictionaries
    - process_item() rules

`spiders/ebay.py`

- parse_details() where the EbayListingItem is created from the API responses

