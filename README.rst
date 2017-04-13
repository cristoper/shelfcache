feedfetch
========

feedfetch is a Python package which provides a thread- and multiprocess-safe caching wrapper around the `Universal Feed Parser`_.

Usage is as simple as initializing with a path where the database file should be created, and then calling the fetch method with the URL to fetch:

>>> from feedfetch import FeedCache
>>> cache = FeedCache('cache.db')
>>> feed = cache.fetch('https://hnrss.org/newest')
>>> for entry in feed.entries:
>>>     # Process feed, etc
>>>     print(entry.title)
>>>
>>> # Fetching a second time will be much faster as it will likely be
>>> # returned from cache:
>>> feed = cache.fetch('https://hnrss.org/newest')

.. _Universal Feed Parser: https://pypi.python.org/pypi/feedparser

Documentation
-------------

TODO: see rtd

Installation
------------

TODO:

    pip install github...


Contribute
----------

- Issue Tracker: github.com/$project/$project/issues
- Source Code: github.com/$project/$project

Support
-------

Feel free to open an issue on Github for help.

License
-------

    The project is licensed under the WTFPL_ license, without warranty of any kind.

.. _WTFPL: http://www.wtfpl.net/about/
