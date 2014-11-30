import rdflib
import unittest
import sys
import catalog.helpers.bibframe as bibframe
import flask_fedora_commons

LOC_DEMO_COLLECTION_ONE = rdflib.Graph()
LOC_DEMO_COLLECTION_TWO = rdflib.Graph()

class FunctionsTest(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.work_uri = rdflib.URIRef('http://catalog.test/1234')
        self.instance_uri = rdflib.URIRef('http://catalog.test/5678')
        self.graph.add((self.work_uri, rdflib.RDF.type, bibframe.BF.Work))
        self.graph.add(
            (self.instance_uri, rdflib.RDF.type, bibframe.BF.Instance))

    def test_default_graph(self):
        self.assertEqual(1,1)

    def test_create_sparql_insert_row_bnode(self):
        row = bibframe.create_sparql_insert_row(
            bibframe.BF.provider,
            rdflib.BNode("67788999"))
        self.assertEqual(
            row,
            """<> bf:provider "BNODE:67788999" .\n""")

    def test_URL_CHECK_RE(self):
        self.assert_(bibframe.URL_CHECK_RE.search("http://www.example.com/"))

    def test_create_sparql_insert_row_literal(self):
        row = bibframe.create_sparql_insert_row(
            bibframe.BF.title,
            rdflib.Literal("Test Title"))
        self.assertEqual(
            row,
            """<> bf:title "Test Title" .\n""")
        row = bibframe.create_sparql_insert_row(
            bibframe.BF.title,
            rdflib.Literal(""" The "Best" Test Title"""))
        self.assertEqual(
            row,
            """<> bf:title ''' The "Best" Test Title''' .\n""")


    def test_guess_search_doc_type(self):
        self.assertEqual(
            bibframe.guess_search_doc_type(
                self.graph,
                self.work_uri
            ),
            'Work'
        )
        self.assertEqual(
            bibframe.guess_search_doc_type(
                self.graph,
                self.instance_uri
            ),
            'Instance'
        )
        held_item = rdflib.URIRef('http://catalog.test/90123')
        self.graph.add((held_item, rdflib.RDF.type, bibframe.BF.HeldItem))
        self.assertEqual(
            bibframe.guess_search_doc_type(
                self.graph,
                held_item
            ),
            'HeldItem'
        )

    def tearDown(self):
        pass


class GraphIngesterTest(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.test_urls = list()
        self.repository = flask_fedora_commons.Repository()

    def test_default_init(self):
        ingester = bibframe.GraphIngester(graph=self.graph,
                                          repository=self.repository)
        self.assertEqual(
            self.graph,
            ingester.graph
        )
        self.assertEqual(
            ingester.repository.base_url,
            'http://localhost:8080'
        )
        self.assertEqual(
            ingester.elastic_search.info().get('status'),
            200
        )

    def tearDown(self):
        for url in self.test_urls:
            self.repository.delete(url)

if __name__ == '__main__':
    print("""Loading Library of Congress Demo Collections located at
http://bibframe.org/demos/""")
    
    unittest.main()
