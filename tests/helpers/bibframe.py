import os
import rdflib
import unittest
import sys
try:
    import bf_catalog.catalog.helpers.bibframe as bibframe
except ImportError:
    test_directory = os.path.dirname(__file__)
    base_directory = test_directory.split(
        "{0}tests{0}helpers".format(os.path.sep))[0]
    sys.path.append(base_directory)
    import catalog.helpers.bibframe as bibframe
import flask_fedora_commons

LOC_DEMO_COLLECTION_ONE = rdflib.Graph()
LOC_DEMO_COLLECTION_TWO = rdflib.Graph()

LOC2_WORK_63_TURTLE = """@prefix bf: <http://bibframe.org/vocab/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xml: <http://www.w3.org/XML/1998/namespace> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://bibframe.org/resources/sample-lc-2/16736259> a bf:Text,
        bf:Work ;
    bf:authorizedAccessPoint "Howden, Martin. Russell Crowe :the biography",
        "howdenmartinrussellcrowethebiographyengworktext"@x-bf-hash ;
    bf:classification <http://bibframe.org/resources/sample-lc-2/16736259classification19> ;
    bf:classificationLcc <http://id.loc.gov/authorities/classification/PN3018.C76> ;
    bf:creator <http://bibframe.org/resources/sample-lc-2/16736259person12> ;
    bf:derivedFrom <http://bibframe.org/resources/sample-lc-2/16736259.marcxml.xml> ;
    bf:language <http://id.loc.gov/vocabulary/languages/eng> ;
    bf:subject <http://bibframe.org/resources/sample-lc-2/16736259person14>,
        <http://bibframe.org/resources/sample-lc-2/16736259topic15>,
        <http://bibframe.org/resources/sample-lc-2/16736259topic16>,
        <http://id.loc.gov/vocabulary/geographicAreas/u-at> ;
    bf:workTitle <http://bibframe.org/resources/sample-lc-2/16736259title11> .

<http://bibframe.org/resources/sample-lc-2/16736259classification19> a bf:Classification ;
    bf:classificationEdition "22",
        "full" ;
    bf:classificationNumber "791.43028092" ;
    bf:classificationScheme "ddc" ;
    bf:label "791.43028092" .

<http://bibframe.org/resources/sample-lc-2/16736259person12> a bf:Person ;
    bf:authorizedAccessPoint "Howden, Martin." ;
    bf:hasAuthority <http://id.loc.gov/authorities/names/nb2008020278> ;
    bf:label "Howden, Martin." .

<http://bibframe.org/resources/sample-lc-2/16736259person14> a bf:Person ;
    bf:authorizedAccessPoint "Crowe, Russell, 1964-" ;
    bf:hasAuthority <http://id.loc.gov/authorities/names/no97049663> ;
    bf:label "Crowe, Russell, 1964-" .

<http://bibframe.org/resources/sample-lc-2/16736259title11> a bf:Title ;
    bf:subtitle "the biography " ;
    bf:titleValue "Russell Crowe :" .

<http://bibframe.org/resources/sample-lc-2/16736259topic15> a bf:Topic ;
    bf:authorizedAccessPoint "Actors--Australia--Biography" ;
    bf:hasAuthority <http://id.loc.gov/authorities/subjects/sh2009113517> ;
    bf:label "Actors--Australia--Biography" .

<http://bibframe.org/resources/sample-lc-2/16736259topic16> a bf:Topic ;
    bf:authorizedAccessPoint "Motion picture actors and actresses--Australia--Biography" ;
    bf:hasAuthority <http://id.loc.gov/authorities/subjects/sh2010102437> ;
    bf:label "Motion picture actors and actresses--Australia--Biography" .

"""

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
        self.assertTrue(bibframe.URL_CHECK_RE.search("http://www.example.com/"))
        self.assertIsNone(
            bibframe.URL_CHECK_RE.search("http://www.example.com/extra space"))

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


    def test_create_sparql_insert_row_valid_urlref(self):
        valid_url_row = bibframe.create_sparql_insert_row(
            bibframe.BF.instanceOf,
            rdflib.URIRef('http://localhost/Work/678'))
        self.assertEqual(
            valid_url_row,
            """<> bf:instanceOf <http://localhost/Work/678> .\n""")

    def test_create_sparql_insert_row_invalid_urlref(self):
        invalid_url_row =  bibframe.create_sparql_insert_row(
            bibframe.BF.instanceOf,
            rdflib.URIRef('http://catalog/Work 678'))
        self.assertEqual(
            invalid_url_row,
            """<> bf:instanceOf "http://catalog/Work 678" .\n""")
        # This test case comes from loading graph at
        # http://bibframe.org/resources/sample-lc-2/bibframe.rdf
        invalid_loc_row = bibframe.create_sparql_insert_row(
            bibframe.BF.classificationValue,
            rdflib.URIRef('http://id.loc.gov/authorities/classification/HF3224.6 R36'))
        self.assertEqual(
            invalid_loc_row,
            """<> bf:classificationValue "http://id.loc.gov/authorities/classification/HF3224.6 R36" .\n""")


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
        self.graph63 = rdflib.Graph().parse(
            data=LOC2_WORK_63_TURTLE,
            format='turtle')
        self.work63 = rdflib.term.URIRef(
            'http://bibframe.org/resources/sample-lc-2/16736259')
        self.test_artifacts = list()
        self.repository = flask_fedora_commons.Repository()
        self.ingester = bibframe.GraphIngester(
            graph=self.graph63,
            repository=self.repository)

    def test_default_init(self):

        self.assertEqual(
            self.graph63,
            self.ingester.graph
        )
        self.assertEqual(
            self.ingester.repository.base_url,
            'http://localhost:8080'
        )
        self.assertEqual(
            self.ingester.elastic_search.info().get('status'),
            200
        )
        subjects = list(set([s for s in self.graph63.subjects()]))
        self.assertEqual(len(subjects), 7)

    def test_init_subject(self):
        fedora_uri = self.ingester.init_subject(self.work63)
        self.assertIsNotNone(fedora_uri)

        # Test Fedora 4 Container and RDF Content
        fedora_g63 = rdflib.Graph().parse(fedora_uri)
        authorizedAccessPoints = [
            str(object_) for object_ in fedora_g63.objects(
                subject=rdflib.URIRef(fedora_uri),
                predicate=bibframe.BF.authorizedAccessPoint)
        ]
        container_types = [
            str(object_) for object_ in fedora_g63.objects(
                subject=rdflib.URIRef(fedora_uri),
                predicate=bibframe.RDF.type
                )
        ]
        self.assertListEqual(
            sorted(authorizedAccessPoints),
            ["Howden, Martin. Russell Crowe :the biography",
             "howdenmartinrussellcrowethebiographyengworktext"])
        self.assertTrue('http://bibframe.org/vocab/Work' in container_types)
        self.assertTrue('http://bibframe.org/vocab/Text' in container_types)
        # Test Elastic search result
        uuid = fedora_g63.value(subject=rdflib.URIRef(fedora_uri),
                                predicate=bibframe.FCREPO.uuid)
        self.assertIsNotNone(uuid)
        es_result = self.ingester.elastic_search.get_source(
            id=uuid,
            index='bibframe'
        )
        self.assertIsNotNone(es_result)
        self.test_artifacts.append({
            "uuid": uuid,
            "fcrepo_url": fedora_uri,
            "doc_type": bibframe.guess_search_doc_type(
                fedora_g63,
                rdflib.URIRef(fedora_uri))})


    def tearDown(self):
        for row in self.test_artifacts:
            self.repository.delete(row.get('fcrepo_url'))
            self.ingester.elastic_search.delete(
                id=row.get('uuid'),
                doc_type=row.get('doc_type'),
                index='bibframe')

if __name__ == '__main__':
    print("""Loading Library of Congress Demo Collections located at
http://bibframe.org/demos/""")

    unittest.main()
