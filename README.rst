===========
Ebay Motors
===========

.. image:: https://img.shields.io/badge/python-3.7%20%7C%203.8-blue
   :alt: Supported Python Versions

.. image:: https://img.shields.io/badge/scrapy-1.7%20%7C%201.8-orange
   :alt: Supported Scrapy Versions

Overview
========

Use the eBay Motors API to sync vehicle listing with a local database.

The ``findItemsAdvanced`` eBay API is used to provide flexibility in searching
and filtering results.  The spider is to be run on a periodic basis to retrieve
all additions and updates to the listings and synchronize them to the local
MySQL database for further processing and analysis.

Requirements
============

* Python 3.7+
* Scrapy 1.7+
* Works on Linux, Windows, Mac OSX

Install
=======

Windows
-------
::

    > cd c:\dev\envs
    > virtualenv --python=python3.7 as_ebay
    > cd c:\dev
    > git clone https://github.com/jim256/as-ebay
    > cd as-ebay
    > c:\dev\envs\as_ebay\Scripts\activate.bat
    > pip install -r requirements.txt
    > deactivate

*Note*:
    If the installation fails due to the `cryptography`, `lxml`, or `mysqlclient` packages, download the appropriate wheel for your platform from:

* https://pypi.org/project/cryptography/#files
* https://pypi.org/project/lxml/#files
* https://pypi.org/project/mysqlclient/#files

or if unavailable there, from:

* https://www.lfd.uci.edu/~gohlke/pythonlibs/

and install with::

    pip install cryptography-2.8-cp37-cp37m-win32.whl

Linux
-----
::

    > cd /opt/envs
    > virtualenv --python=python3.7 as_ebay
    > cd /opt
    > git clone https://github.com/jim256/as-ebay
    > cd as-ebay
    > source /opt/envs/as_ebay/bin/activate
    > pip install -r requirements.txt
    > deactivate

Execute
=======

From Windows command line::

    > cd c:\dev\as-ebay
    > c:\dev\envs\as_ebay\Scripts\python.exe run.py ebay

From Linux command line::

    > cd /opt/as-ebay
    > /opt/envs/as_ebay/bin/python run.py ebay

From cron::

    cd /opt/as-ebay && /opt/envs/as_ebay/bin/python run.py ebay [options]

For available parameters use ``run.py --help``

`Sample common execution command`::

    python run.py ebay --configfile=config.json --loglevel=INFO

