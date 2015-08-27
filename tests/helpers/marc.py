import pymarc
import rdflib
import unittest
import sys
try:
    import bibframe_catalog.catalog.helpers.marc as marc
except ImportError:
    #! Crud hack for development
    import os, sys
    sys.path.append("E:\\2014\\bibframe-catalog")
    import catalog.helpers.marc as marc


class MARCIngesterTest(unittest.TestCase):

    def setUp(self):
        self.record = pymarc.Record()
        self.es = None
        self.repository = None

    def test_init(self):
        ingester = marc.MARCIngester(
            elastic_search=self.es,
            repository=self.repository,
            record=self.record)
        self.assertIsNotNone(ingester)


    def tearDown(self):
        pass
        # self.es.flush()



if __name__ == '__main__':
    unittest.main()