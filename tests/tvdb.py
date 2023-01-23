import unittest
from rip import tvdb

class TestTvdb(unittest.TestCase):
    def setUp(self):
        pass

    def test_search(self):
        """ The search function return an array of matches
        """
        SERIES = "Wacky Races"
        expected = [
            {'id': 'wacky-races', 'title': 'Wacky Races'},
            {'id': 'wacky-races-2017', 'title': 'Wacky Races (2017)'},
        ]

        provider = tvdb.TVDB()
        actual = provider.search(SERIES)
        self.assertListEqual(actual, expected)

if __name__ == '__main__':
    unittest.main()
