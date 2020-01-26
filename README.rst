shelfcache ReadMe
=================

shelfcache is a Python3 package which provides a persistent (on-disk) thread-
and multiprocess-safe key-value caching store on top of the standard library's
`shelve module <https://docs.python.org/3/library/shelve.html>`_.

It also includes a wrapper around `requests.get()` (a popular HTTP library for
Python) which transparently handles retrieving resources from the cache,
validating them (respecting the Cache-Control header), re-fetching stale
resources including using etag and last-modified headers when possible, and
updating cached resources.

But if caching HTTP requests is your main objective, then consider the
CacheControl_ package instead which is more flexible and better tested.

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

.. _CacheControl: https://github.com/ionrock/cachecontrol
.. note:: On Mac OS X, the `flock` placed on the db file by this module interacts
  with gdbm's own lock, causing a deadlock. The current workaround is to not use
  gdbm on Mac OS X (use berkeley db instead) -- one way to do this is to simply
  not install `gdbm` and Python will choose a different implementation; if you use
  homebrew to install python on Mac OS X, remove `gdbm` by running `brew uninstall
  --ignore-dependencies gdbm`

    
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
    A WSGI micro webservice for mixing Atom/RSS feeds. (Version 3.0 of
    FeedMixer moved away from shelfcache to a RAM-only cache)

If you use shelfcache in a project, add a link to it here and give me a pull
request (or just mention it in an issue, and I'll add it)!

.. _FeedMixer: https://github.com/cristoper/feedmixer

Help
----

Feel free to open an issue on Github for help: https://github.com/cristoper/shelfcache/issues

Support the project
-------------------

If this package was useful to you, please consider supporting my work on this and other open-source projects by making a small (a couple $) one-time donation: `donate via PayPal <https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=E78W4LH2NADXE>`_

If you're looking to contract a Python developer, I might be able to help. Contact me, Chris, at dev@orangenoiseproduction.com

License
-------

    The project is licensed under the WTFPL_ license, without warranty of any kind.

.. _WTFPL: http://www.wtfpl.net/about/

