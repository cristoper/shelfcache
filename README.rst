shelfcache ReadMe
=================

shelfcache is a Python3 package which provides a thread- and multiprocess-safe
key-value caching store on top of the standard library's `shelve module
<https://docs.python.org/3/library/shelve.html>`_.

The package include three modules:

- ``shelfcache.py`` - Provides the main `ShelfCache` class::

    >>> from shelfcache import ShelfCache
    >>> cache = ShelfCache('cache.db')
    >>> test_obj = ['any', 'thing', 'that', 'can', 'be', 'pickled']
    >>> cache.create_or_update('key', test_obj)
    >>> retrieved = cache.get('key')
    >>> retrieved.data
    ['any', 'thing', 'that', 'can', 'be', 'pickled']
    >>> retrieved.expired
    False

- ``cache_get.py`` - Provides a transparent persistent cache wrapper around the
  ``get()`` method from the `requests package
  <http://docs.python-requests.org/en/master/>`_ for GETting resources over
  HTTP/HTTPS::

    >>> from shelfcache import cache_get, ShelfCache
    >>> cache = ShelfCache('path/to/cache.db')
    >>> response = cache_get(cache, url='https://hnrss.org/newest')
    >>> response.status_code
    200

- ``locked_shelf.py`` - Provides the locking wrappers around the standard
  library's ``shelve`` module.
    
Installation
------------

Install from this repository with pip::

$ pip3 install git+git://github.com/cristoper/shelfcache.git#egg=shelfcache


Documentation
-------------

https://shelfcache.readthedocs.io/en/latest/

Projects
--------
FeedMixer_
    A WSGI micro webservice for mixing Atom/RSS feeds

If you use shelfcache in a project, add a link to it here and give me a pull
request (or just mention it in an issue, and I'll add it)!

.. _FeedMixer: https://github.com/cristoper/feedmixer

Support
-------

Feel free to open an issue on Github for help: https://github.com/cristoper/shelfcache/issues

License
-------

    The project is licensed under the WTFPL_ license, without warranty of any kind.

.. _WTFPL: http://www.wtfpl.net/about/
