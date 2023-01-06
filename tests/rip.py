import unittest
from rip.db import DB
from rip import pred

class TestRipDB(unittest.TestCase):
    def setUp(self):
        self.sub_en = dict(st_type='subtitle', st_lang='en', st_idx=0)
        self.sub_fr = dict(st_type='subtitle', st_lang='fr', st_idx=1, st_out=1)
        self.sub_de = dict(st_type='subtitle', st_lang='de', st_idx=2)
        self.audio_fr = dict(st_type='audio', st_lang='fr', st_idx=3, st_out=2)
        self.audio_en = dict(st_type='audio', st_lang='en', st_idx=4)

        self.coll = [ self.sub_en, self.sub_fr, self.sub_de, 
                      self.audio_fr, self.audio_en ]

        self.db = DB()
        for item in self.coll:
            self.db.append(**item)

    def test_sort(self):
        result = self.db.sort(lambda item: item['st_lang']+item['st_type'])
        expected = [
            self.sub_de, 
            self.audio_en, self.sub_en,
            self.audio_fr, self.sub_fr
        ]
        self.assertEqual(result.as_list(), expected)
        
    def test_get(self):
        """'get' an item based on an unique key
        """
        self.assertEqual(self.db.get(st_lang='de'), self.sub_de)

    def test_all(self):
        """Find all an items based on some keys
        """
        result = [item for item in self.db.all(st_type='audio')]
        self.assertEqual(result, [ self.audio_fr, self.audio_en ])

    def test_filter(self):
        """'filter' according to a predicate
        """
        result = [item for item in self.db.fltr(pred.is_equal('st_type', 'audio'))]
        self.assertEqual(result, [ self.audio_fr, self.audio_en ])

        result = [item for item in self.db.fltr(pred.order_by('st_lang', ['en','fr']))]
        self.assertEqual(result, [ self.sub_en, self.audio_en,
                                   self.sub_fr, self.audio_fr ])

        result = [item for item in self.db.fltr(pred.order_by('st_lang', ['fr','en']))]
        self.assertEqual(result, [ self.sub_fr, self.audio_fr,
                                   self.sub_en, self.audio_en ])


    def test_having(self):
        """Search for item having some property defined (even if None)
        """
        result = [item for item in self.db.fltr(pred.having('st_out'))]
        self.assertEqual(result, [ self.sub_fr, self.audio_fr ])
        

if __name__ == '__main__':
    unittest.main()
