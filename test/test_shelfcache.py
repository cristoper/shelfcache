from shelfcache.shelfcache import ShelfCache, Item
import unittest
from unittest.mock import MagicMock, patch
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
    @patch('os.path.exists')
    def test_no_db(self, mock_os_path_exists):
        """
        Test trying to read a non-existing cache database.
        """
        # Report the database file as non-existent:
        mock_os_path_exists.return_value = False

        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        val = sc.get('key')

        self.assertIsNone(val)
        mock_dict.get.assert_not_called()

    @patch('os.path.exists')
    def test_getitem_missing_key(self, mock_os_path_exists):
        """
        Trying to get a non-existent key with __getitem__ should throw a
        KeyError.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

        mock_shelf = make_mock_locked_shelf()

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        with self.assertRaises(KeyError):
            sc['nonkey']

    @patch('os.path.exists')
    def test_get_missing_key(self, mock_os_path_exists):
        """
        Trying to get a non-existent key with get() should return None.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

        mock_shelf = make_mock_locked_shelf()
        mock_dict = mock_shelf.return_value.__enter__.return_value

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)

        val = sc.get('nonkey')
        self.assertIsNone(val)
        mock_dict.get.assert_called_once_with('nonkey')

    @patch('os.path.exists')
    def test_getitem_fresh(self, mock_os_path_exists):
        """
        Get a fresh item with __getitem__.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True
        exp_time = datetime.utcnow() + timedelta(days=1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc['key']
        self.assertEqual('data', data)
        self.assertFalse(exp)

    @patch('os.path.exists')
    def test_get_fresh(self, mock_os_path_exists):
        """
        Get a fresh item with get().
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True
        exp_time = datetime.utcnow() + timedelta(days=1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc.get('key')
        self.assertEqual('data', data)
        self.assertFalse(exp)

    @patch('os.path.exists')
    def test_getitem_stale(self, mock_os_path_exists):
        """
        Get a fresh item with __getitem__.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

        exp_time = datetime.utcnow() + timedelta(days=-1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc['key']
        self.assertEqual('data', data)
        self.assertTrue(exp)

    @patch('os.path.exists')
    def test_get_stale(self, mock_os_path_exists):
        """
        Get a fresh item with get().
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

        exp_time = datetime.utcnow() + timedelta(days=-1)
        test_item = Item(data='data', expire_dt=exp_time)
        test_val = {'key': test_item}

        mock_shelf = make_mock_locked_shelf(test_val)

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        (data, exp) = sc.get('key')
        self.assertEqual('data', data)
        self.assertTrue(exp)


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
    @patch('os.path.exists')
    def test_update_expires(self, mock_os_path_exists):
        """
        Set an item, then ensure its expires date can be updated.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

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
    @patch('os.path.exists')
    def test_delete(self, mock_os_path_exists):
        """
        Set an item and then test that it can be deleted.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

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

    @patch('os.path.exists')
    def test_delitem(self, mock_os_path_exists):
        """
        Set an item and then test that it can be deleted using the del operator
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

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
    @patch('os.path.exists')
    def test_clear(self, mock_os_path_exists):
        """
        Set some items then test that they are all deleted.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

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
    @patch('os.path.exists')
    def test_prune(self, mock_os_path_exists):
        """
        Create some items and then test that the oldest is pruned.
        """
        # so we don't need an actual db file:
        mock_os_path_exists.return_value = True

        mock_shelf = make_mock_locked_shelf()
        tomorrow = datetime.utcnow() + timedelta(days=1)
        yesterday = datetime.utcnow() + timedelta(days=-1)
        today = datetime.utcnow()

        # DUT:
        sc = ShelfCache(db_path='dummy', shelf_t=mock_shelf)
        sc.create_or_update('old', data='old', expire_dt=yesterday)
        sc.create_or_update('new', data='new', expire_dt=tomorrow)

        sc.prune(older_than=today)

        old = sc.get('old')
        new = sc.get('new')

        self.assertIsNone(old)
        self.assertEqual('new', new.data)
