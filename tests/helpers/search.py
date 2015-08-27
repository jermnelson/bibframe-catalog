import rdflib
import unittest
import sys

from elasticsearch import Elasticsearch

try:
    import bibframe_catalog.catalog.helpers.search as search
except ImportError:
     #! Crud hack for development
    import os, sys
    sys.path.append("E:\\2014\\bibframe-catalog")
    import catalog.helpers.search as search


class KeywordFunctionTest(unittest.TestCase):

    def setUp(self):
        self.es = Elasticsearch()


    def test_keyword_search(self):
        self.assertIsNotNone(search.keyword_search(self.es, "Test"))

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()