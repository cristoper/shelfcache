from shelfcache.shelfcache import ShelfCache, Item
import unittest
from unittest.mock import MagicMock
from shelfcache.locked_shelf import RWShelf
from datetime import datetime, timedelta


def make_mock_locked_shelf(wrapped_dict=None):
    """
    Helper function to create a mocked RWShelf instance which wraps a regular
    dictionary.
    """
    if wrapped_dict is None:
        wrapped_dict = {}
    mock_shelf = MagicMock(spec=RWShelf)
    mock_dict = MagicMock(wraps=wrapped_dict)

    # wraps doesn't seem to actually wrap these magic methods:
    mock_dict.__setitem__.side_effect = wrapped_dict.__setitem__
    mock_dict.__delitem__.side_effect = wrapped_dict.__delitem__
    mock_shelf.return_value.__enter__.return_value = mock_dict
    return mock_shelf


class TestGet(unittest.TestCase):
    def test_no_db(self):
        """
        Test trying to read a non-existing cache database.
        """
        mock_shelf = make_mock_locked_shelf()

        def file_not_found(*args, **kwargs):
            raise FileNotFoundError

        mock_shelf.side_effect = file_not_found
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        val = sc.get('key')
        self.assertIsNone(val)
        mock_dict.get.assert_not_called()

    def test_getitem_missing_key(self):
        """
        Trying to get a non-existent key with __getitem__ should throw a
        KeyError.
        """
        mock_shelf = make_mock_locked_shelf()

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        with self.assertRaises(KeyError):
            sc['nonkey']

    def test_get_missing_key(self):
        """
        Trying to get a non-existent key with get() should return None.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        val = sc.get('nonkey')
        self.assertIsNone(val)
        mock_dict.get.assert_called_once_with('nonkey')

    def test_getitem_fresh(self):
        """
        Get a fresh item with __getitem__.
        """
        exp_time = datetime.utcnow() + timedelta(days=1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc['key']
        self.assertEqual('data', data)
        self.assertFalse(exp)

    def test_get_fresh(self):
        """
        Get a fresh item with get().
        """
        exp_time = datetime.utcnow() + timedelta(days=1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc.get('key')
        self.assertEqual('data', data)
        self.assertFalse(exp)

    def test_getitem_stale(self):
        """
        Get a fresh item with __getitem__.
        """
        exp_time = datetime.utcnow() + timedelta(days=-1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc['key']
        self.assertEqual('data', data)
        self.assertTrue(exp)

    def test_get_stale(self):
        """
        Get a fresh item with get().
        """
        exp_time = datetime.utcnow() + timedelta(days=-1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc.get('key')
        self.assertEqual('data', data)
        self.assertTrue(exp)


class TestGetItem(unittest.TestCase):
    def test_no_db(self):
        """
        Test trying to read a non-existing cache database.
        """
        mock_shelf = make_mock_locked_shelf()

        def file_not_found(*args, **kwargs):
            raise FileNotFoundError

        mock_shelf.side_effect = file_not_found
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        val = sc.get_item('key')
        self.assertIsNone(val)
        mock_dict.get.assert_not_called()

    def test_get_item_missing_key(self):
        """
        Trying to get a non-existent key with get() should return None.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        val = sc.get_item('nonkey')
        self.assertIsNone(val)
        mock_dict.get.assert_called_once_with('nonkey')

    def test_get_item_fresh(self):
        """
        Get a fresh item with get().
        """
        exp_time = datetime.utcnow() + timedelta(days=1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        item = sc.get_item('key')
        self.assertEqual('data', item.data)
        self.assertEqual(exp_time, item.expire_dt)


class TestSet(unittest.TestCase):
    def test_setitem(self):
        """
        Setting item with __setitem__ should never expire.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc['key'] = 'val'
        item = mock_dict.get('key')
        data, exp = item.data, item.expire_dt

        self.assertEqual('val', data)
        self.assertIsNone(exp)

    def test_create_or_update_dt(self):
        """
        Check that key and expire_dt is set with set() passing a datetime
        object.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value
        tomorrow = datetime.utcnow() + timedelta(days=1)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc.create_or_update('key', data='val', expire_dt=tomorrow)
        item = mock_dict.get('key')
        data, exp = item.data, item.expire_dt

        self.assertEqual('val', data)
        self.assertEqual(exp, tomorrow)

    def test_create_or_update_updates(self):
        """
        Check that updating an existing item with create_or_update will update
        the updated_dt.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        # create
        sc.create_or_update('key', data='original')
        item = mock_dict.get('key')
        data, created, updated = item.data, item.created_dt, item.updated_dt
        self.assertEqual('original', data)
        self.assertEqual(created, updated)

        # update
        sc.create_or_update('key', data='new')
        item = mock_dict.get('key')
        data, created, updated = item.data, item.created_dt, item.updated_dt
        self.assertEqual('new', data)
        self.assertTrue(created < updated)

    def test_create_or_update_seconds(self):
        """
        Check that key and expire_dt is set with set() passing seconds.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc.create_or_update('key', data='val', exp_seconds=10)
        item = mock_dict.get('key')
        data, exp, created = item.data, item.expire_dt, item.created_dt
        future = created + timedelta(seconds=10)

        self.assertEqual('val', data)
        self.assertEqual(exp, future)

    def test_create_or_update_seconds_neg1(self):
        """
        Check that passing -1 to exp_seconds results in item having no expiry
        datetime.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc.create_or_update('key', data='val', exp_seconds=-1)
        item = mock_dict.get('key')
        data, exp = item.data, item.expire_dt

        self.assertEqual('val', data)
        self.assertIsNone(exp)


class TestUpdateExpires(unittest.TestCase):
    def test_update_expires(self):
        """
        Set an item, then ensure its expires date can be updated.
        """
        wrapped_dict = {}
        mock_shelf = make_mock_locked_shelf(wrapped_dict)
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        # Set some data
        sc['key'] = 'val'
        item = mock_dict.get('key')
        old_exp = item.expire_dt
        self.assertIsNone(old_exp)

        # Update expires
        tomorrow = datetime.utcnow() + timedelta(days=1)
        sc.update_expires('key', tomorrow)
        item = mock_dict.get('key')
        data, new_exp = item.data, item.expire_dt

        self.assertEqual('val', data)
        self.assertEqual(tomorrow, new_exp)


class TestDel(unittest.TestCase):
    def test_delete(self):
        """
        Set an item and then test that it can be deleted.
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        # create item
        sc['key'] = 'val'
        item = mock_dict.get('key')
        data = item.data
        self.assertEqual('val', data)

        # delete item
        sc.delete('key')
        val = sc.get('key')
        self.assertIsNone(val)

    def test_delitem(self):
        """
        Set an item and then test that it can be deleted using the del operator
        """
        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        # create item
        sc['key'] = 'val'
        item = mock_dict.get('key')
        data = item.data
        self.assertEqual('val', data)

        # delete item
        del sc['key']
        val = sc.get('key')
        self.assertIsNone(val)


class TestClear(unittest.TestCase):
    def test_clear(self):
        """
        Set some items then test that they are all deleted.
        """
        wrapped_dict = {}
        mock_shelf = make_mock_locked_shelf(wrapped_dict)
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        # Set some data
        sc['key'] = 'val'
        sc['key2'] = 'val2'
        item1 = mock_dict.get('key')
        item2 = mock_dict.get('key2')
        d1 = item1.data
        d2 = item2.data
        self.assertEqual('val', d1)
        self.assertEqual('val2', d2)

        # Clear
        sc.clear()

        item1 = mock_dict.get('key')
        item2 = mock_dict.get('key2')
        self.assertIsNone(item1)
        self.assertIsNone(item2)


class TestPrune(unittest.TestCase):
    def test_prune_old(self):
        """
        Create some items and then test that the oldest is pruned.
        """
        mock_shelf = make_mock_locked_shelf()

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc.create_or_update('old', data='old')
        today = datetime.utcnow()
        sc.create_or_update('new', data='new')

        sc.prune_old(older_than=today)

        old = sc.get('old')
        new = sc.get('new')

        self.assertIsNone(old)
        self.assertEqual('new', new.data)

    def test_prune_expired(self):
        """
        Create some items and then test that the expired one is pruned.
        """
        mock_shelf = make_mock_locked_shelf()
        tomorrow = datetime.utcnow() + timedelta(days=1)
        yesterday = datetime.utcnow() + timedelta(days=-1)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc.create_or_update('old', data='old', expire_dt=yesterday)
        sc.create_or_update('new', data='new', expire_dt=tomorrow)

        sc.prune_expired()

        old = sc.get('old')
        new = sc.get('new')

        self.assertIsNone(old)
        self.assertEqual('new', new.data)
