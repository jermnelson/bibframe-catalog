import rdflib
import unittest
import sys
sys.path.append("E:\\2014\\bibframe-catalog")
import catalog.helpers.bibframe as bibframe

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

    def test_create_sparql_insert_row(self):
        row = bibframe.create_sparql_insert_row(
            bibframe.BF.title,
            rdflib.Literal("Test Title"))
        self.assertEqual(
            row,
            """<> bf:title "Test Title" .\n""")

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
            'Resource'
        )

    def tearDown(self):
        pass


class GraphIngesterTest(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()

    def test_default_init(self):
        ingester = bibframe.GraphIngester(graph=self.graph)
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
        pass

if __name__ == '__main__':
    unittest.main()