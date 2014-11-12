import rdflib
import unittest
import catalog.helpers.bibframe as bibframe

class FunctionsTest(unittest.TestCase):

    def setUp(self):
        pass

    def test_default_graph(self):
        self.assertEqual(1,1)

    def test_create_sparql_insert_row(self):
        row = bibframe.create_sparql_insert_row(
            bibframe.BF.title,
            rdflib.Literal("Test Title"))
        self.assertEqual(
            row,
            """<> bf:title "Test Title" .\n""")

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()