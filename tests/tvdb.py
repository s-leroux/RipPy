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

    def test_episodes(self):
        self.maxDiff = None
        SERIES_ID = "wacky-races"
        expected =  \
            {0: {1: {'title': 'Japanese Opening'},
                 2: {'title': 'Rear View Mirror: A Look Back at Wacky Races'},
                 3: {'title': 'Spin-Out Spin-Offs'},
                 4: {'title': 'On-Screen Pop-Up Factoids - See-Saw to Arkansas'},
                 5: {'title': 'On-Screen Pop-Up Factoids - Creepy Trip To Lemon Twist'},
                 6: {'title': 'Unknown'},
                 7: {'title': 'Unknown'},
                 8: {'title': 'Unknown'},
                 9: {'title': 'Wacky Races Forever (pilot)'},
                 10: {'title': 'Commercial Break Bumper: Propeller'},
                 11: {'title': 'Commercial Break Bumper: Cannonball'},
                 12: {'title': 'Commentary: Ballpoint, Penn or Bust'},
                 13: {'title': 'Commentary: Fast Track to Hackensack'},
                 14: {'title': 'Commentary: The Ski Resort Road Race'},
                 15: {'title': 'Commentary: Overseas Hi-Way Race'}},
             1: {1: {'title': 'See-Saw to Arkansas'},
                 2: {'title': 'Creepy Trip to Lemon Twist'},
                 3: {'title': 'Why Oh Why Wyoming'},
                 4: {'title': 'Beat the Clock to Yellow Rock'},
                 5: {'title': 'Mish Mash Missouri Dash'},
                 6: {'title': 'Idaho a Go Go'},
                 7: {'title': 'The Baja-Ha-Ha Race'},
                 8: {'title': 'Real Gone Ape'},
                 9: {'title': 'Scout Scatter'},
                 10: {'title': 'Free Wheeling to Wheeling'},
                 11: {'title': 'By Rollercoaster to Upsan Downs'},
                 12: {'title': 'The Speedy Arkansas Traveller'},
                 13: {'title': 'The Zippy Mississippi Race'},
                 14: {'title': 'Traffic Jambalaya'},
                 15: {'title': 'Hot Race at Chillicothe'},
                 16: {'title': 'The Wrong Lumber Race'},
                 17: {'title': 'Rhode Island Road Race'},
                 18: {'title': 'The Great Cold Rush Race'},
                 19: {'title': 'Wacky Race to Ripsaw'},
                 20: {'title': 'Oils Well That Ends Well'},
                 21: {'title': "Whizzin' to Washington"},
                 22: {'title': 'The Dipsy Doodle Desert Derby'},
                 23: {'title': 'Eeny, Miny Missouri Go!'},
                 24: {'title': 'The Super Silly Swamp Sprint'},
                 25: {'title': 'The Dopey Dakota Derby'},
                 26: {'title': 'Dash to Delaware'},
                 27: {'title': 'Speeding for Smogland'},
                 28: {'title': 'Race Rally to Raleigh'},
                 29: {'title': 'Ballpoint, Penn. or Bust!'},
                 30: {'title': 'Fast Track to Hackensack'},
                 31: {'title': 'The Ski Resort Road Race'},
                 32: {'title': 'Overseas Hi-Way Race'},
                 33: {'title': 'Race to Racine'},
                 34: {'title': 'The Carlsbad or Bust Bash'}}}

        provider = tvdb.TVDB()
        actual = provider.episodes(SERIES_ID)
        self.assertDictEqual(actual, expected)

if __name__ == '__main__':
    unittest.main()
