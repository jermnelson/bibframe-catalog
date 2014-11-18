"""
Name:        bibframe
Purpose:     Helper functions for ingesting BIBFRAME graphs into Fedora 4
             supported by Elastic Search

Author:      Jeremy Nelson

Created:     2014/11/02
Copyright:   (c) Jeremy Nelson 2014
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"

import datetime
import json
import rdflib
import sys
import urllib.request
from flask_fedora_commons import build_prefixes, Repository
from elasticsearch import Elasticsearch
from string import Template

CONTEXT = {
    "authz": "http://fedora.info/definitions/v4/authorization#",
    "bf": "http://bibframe.org/vocab/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "fcrepo": "http://fedora.info/definitions/v4/repository#",
    "fedora": "http://fedora.info/definitions/v4/rest-api#",
    "fedoraconfig": "http://fedora.info/definitions/v4/config#",
    "fedorarelsext": "http://fedora.info/definitions/v4/rels-ext#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "image": "http://www.modeshape.org/images/1.0",
    "mads": "http://www.loc.gov/mads/rdf/v1#",
    "mix": "http://www.jcp.org/jcr/mix/1.0",
    "mode": "http://www.modeshape.org/1.0",
    "owl": "http://www.w3.org/2002/07/owl#",
    "nt": "http://www.jcp.org/jcr/nt/1.0",
    "premis": "http://www.loc.gov/premis/rdf/v1#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "schema": "http://schema.org/",
    "sv": "http://www.jcp.org/jcr/sv/1.0",
    "test": "info:fedora/test/",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "xmlns": "http://www.w3.org/2000/xmlns/",
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance"}

for key, value in CONTEXT.items():
    setattr(
        sys.modules[__name__],
        key.upper(),
        rdflib.Namespace(value))


def create_sparql_insert_row(predicate, object_):
    """Function creates a SPARQL update row based on a predicate and object

    Args:
        predicate(rdflib.Term): Predicate
        object_(rdflib.Term): Object

    Returns:
        string
    """
    statement = "<> "
    if str(predicate).startswith(str(RDF)):
        statement += "rdf:" + predicate.split("#")[-1]
    elif str(predicate).startswith(str(BF)):
        statement += "bf:" + predicate.split("/")[-1]
    elif str(predicate).startswith(str(MADS)):
        statement += "mads:" + predicate.split("#")[-1]
    else:
        statement += "<" + str(predicate) + ">"
    if type(object_) == rdflib.URIRef:
        statement += " <" + str(object_) + "> "
    if type(object_) == rdflib.Literal:
        if str(object_).find('"') > -1:
            value = """ '''{}''' """.format(object_)
        else:
            value = """ "{}" """.format(object_)
        statement += value
    statement += ".\n"
    return statement

def default_graph():
    """Function generates a new rdflib Graph and sets all namespaces as part
    of the graph's context"""
    new_graph = rdflib.Graph()
    for key, value in CONTEXT.items():
        new_graph.namespace_manager.bind(key, value)
    return new_graph

def generate_body(fedora_uri):
    """Function takes a Fedora URI, filters the Fedora graph and returns a dict
    for indexing into Elastic search

    Args:
        fedora_uri(string): Fedora URI

    Returns:
        dict: Dictionary of values filtered for Elastic Search indexing
    """
    def get_id_or_value(value):
        if '@value' in value:
            return value.get('@value')
        elif '@id' in value:
            return value.get('@id')
        return value
    def set_or_expand(key, value):
        if key not in body:
            body[key] = []
        if type(value) == list:
            for row in value:
                body[key].append(get_id_or_value(row))
        else:
            body[key] = [get_id_or_value(value),]
    graph = default_graph()
    graph.parse(fedora_uri)
    body = dict()
    bf_json = json.loads(
        graph.serialize(
            format='json-ld',
            context=CONTEXT).decode())
    if '@graph' in bf_json:
        for graph in bf_json.get('@graph'):
            # Index only those graphs that have been created in the
            # repository
            if 'fcrepo:created' in graph:
                for key, val in graph.items():
                    if key in [
                        'fcrepo:lastModified',
                        'fcrepo:created',
                        'fcrepo:uuid']:
                            set_or_expand(key, val)
                    elif key.startswith('@type'):
                        for name in val:
                            if name.startswith('bf:'):
                                set_or_expand('type', name)
                    elif key.startswith('@id'):
                        set_or_expand('fcrepo:hasLocation', val)
                    elif not key.startswith('fcrepo') and not key.startswith('owl'):
                        set_or_expand(key, val)
    return body

def guess_search_doc_type(graph, fcrepo_uri):
    """Function takes a graph and attempts to guess the Doc type for ingestion
    into Elastic Search

    Args:
        graph(rdflib.Graph): RDF Graph of Fedora Object
        subject_uri(rdlib.URIRef): Subject of the RDF Graph

    Returns:
        string: Doc type of subject
    """
    doc_type = 'Resource'
    subject_types = [obj for obj in graph.objects(
                subject=fcrepo_uri,
                predicate=rdflib.RDF.type)]
    for class_name in [
        'Work',
        'Annotation',
        'Authority',
        'Person',
        'Place',
        'Provider',
        'Title',
        'Topic',
        'Organization',
        'Instance']:
            if getattr(BF, class_name) in subject_types:
                doc_type = class_name
    return doc_type

class GraphIngester(object):
    """Takes a BIBFRAME graph, extracts all subjects and creates an object in
    Fedora 4 for all triples associated with the subject. The Fedora 4 subject
    graph is then indexed into Elastic Search

    To use

    >> ingester = GraphIngester(graph=bf_graph)
    >> ingester.initalize()
    """

    def __init__(self, **kwargs):
        """Initialized a instance of GraphIngester

        Args:
            es(elasticsearch.ElasticSearch): Instance of Elasticsearch
            graph(rdflib.Graph): BIBFRAM RDF Graph
            repo(flask_fedora_commons.Repository): Fedora Commons Repository

        """
        self.bf2uris = {}
        self.elastic_search = kwargs.get('elastic_search', Elasticsearch())
        self.graph = kwargs.get('graph', default_graph())
        self.repository = kwargs.get('repository', Repository())

    def dedup(self, term, doc_type='Resource'):
        """Method takes a term and attempts to match it againest three
        subject properties that have been indexed into Elastic search, returns
        the first hit if found. This method may need further refinement to
        provide the optimal deduplication for BIBFRAME resources.

        Args:
            term(string): A search term or phrase
            doc_type(string): Doc type to restrict search, defaults to Resource

        Returns:
            string URL of the top-hit for matching the term on a list of
            properties
        """
        if term is None:
            return
        search_result = self.elastic_search.search(
            index="bibframe",
            doc_type=doc_type,
            body={
                "query": {
                    "multi_match": {
                        "query": term,
                        "type": "phrase",
                        "fields": [
                            "bf:authorizedAccessPoint",
                            "mads:authoritativeLabel",
                            "bf:label",
                            "bf:titleValue"]}}})
        if search_result.get('hits').get('total') > 0:
            top_hit = search_result['hits']['hits'][0]['_source']['fcrepo:hasLocation'][0]
            return rdflib.URIRef(top_hit)


    def exists(self, subject):
        """Method takes a subject, queries Elasticsearch index,
        if present, adds result to bf2uris, always returns boolean

        Args:
            subject(rdflib.Term): Subject, can be literal, BNode, or URI

        Returns:
            boolean
        """
        if str(subject) in self.bf2uris:
            return True
        doc_type = guess_search_doc_type(self.graph, subject)
        for predicate in [
            BF.authorizedAccessPoint,
            BF.label,
            MADS.authoritativeLabel,
            BF.titleValue]:
            objects = self.graph.objects(
                subject=subject,
                predicate=predicate)
            for object_value in objects:
                result = self.dedup(str(object_value), doc_type)
                if result is not None:
                    self.repository.insert(result, "owl:sameAs", str(subject))
                    self.bf2uris[str(subject)] = result
                    return True
        return False


    def index(self, fcrepo_uri):
        """Method takes a Fedora Object URIRef, generates JSON-LD
        representation, and then ingests into an Elasticsearch
        instance

        Args:
            fcrepo_uri(rdflib.URIRef): Fedora URI Ref for a BIBFRAME subject

        """
        fcrepo_graph = default_graph().parse(str(fcrepo_uri))
        doc_id = str(fcrepo_graph.value(
                    subject=fcrepo_uri,
                    predicate=FCREPO.uuid))
        doc_type = guess_search_doc_type(fcrepo_graph, fcrepo_uri)
        body = generate_body(fcrepo_uri)
        self.elastic_search.index(
            index='bibframe',
            doc_type=doc_type,
            id=doc_id,
            body=body)

    def ingest(self):
        """Method ingests a BIBFRAME graph into Fedora 4 and Elastic search"""
        start = datetime.datetime.utcnow()
        print("Started ingestion at {}".format(start.isoformat()))
        self.initialize()
        for i, subject_uri in enumerate(
            set([subject for subject in self.graph.subjects()])):
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
            if type(subject_uri) == rdflib.BNode:
                continue
            self.process_subject(subject_uri)
        end = datetime.datetime.utcnow()
        print("Finished ingesting at {}, total time={} minutes for {} subjects".format(
            end.isoformat(),
            (end-start).seconds / 60.0,
            i))

    def initialize(self):
        """Method iterates through all subjects in the BIBFRAME graph,
        creates a Fedora 4 object for all non-BNode subjects, sets some
        default properties for each Fedora 4 object, before indexing into
        Elastic search"""
        print("Initializing all subjects")
        if not self.elastic_search.indices.exists('bibframe'):
            self.elastic_search.indices.create('bibframe')
        for i, subject in enumerate(
            set([subject for subject in self.graph.subjects()])):
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
##            if type(subject) == rdflib.BNode:
##                continue
            if self.exists(subject):
                continue
            self.stub(subject)
        print("Finished adding all subjects to Fedora")


    def process_subject(self, subject):
        """Method takes a subject URI and iteratees through the subject's
        predicates and objects, saving them to a the subject's Fedora graph.
        Blank nodes are expanded and saved as properties to the subject
        graph as well. Finally, the graph is serialized as JSON-LD and updated
        in the Elastic Search index.

        Args:
            subject(rdflib.URIRef): Subject URI
        """
        fedora_uri = self.bf2uris[str(subject)]
        sparql = build_prefixes(self.repository.namespaces)
        sparql += "\nINSERT DATA {\n"
        for predicate, object_ in self.graph.predicate_objects(subject=subject):
            if type(object_) == rdflib.BNode:
                for b_predicate, b_object in self.graph.predicate_objects(
                    subject=object_):
                        if str(b_object) in self.bf2uris:
                            b_object = self.bf2uris.get(str(b_object))
                        sparql += create_sparql_insert_row(
                            b_predicate,
                            b_object)
            else:
                if str(object_) in self.bf2uris:\
                    sparql += create_sparql_insert_row(
                                predicate,
                                self.bf2uris.get(str(object_)))
                else:
                    sparql += create_sparql_insert_row(
                        predicate, object_)
        sparql += "\n}"
        update_fedora_request = urllib.request.Request(
            str(fedora_uri),
            method='PATCH',
            data=sparql.encode(),
            headers={"Content-type": "application/sparql-update"})
        result = urllib.request.urlopen(update_fedora_request)
        self.index(fedora_uri)

    def stub(self, subject):
        """Method creates a Fedora Object BIBFRAME stub with minimal

        Args:
            subject(rdflib.URIRef): Subject URI

        Returns:
            string: Fedora URI
        """
        fcrepo_uri = rdflib.URIRef(self.repository.create())
        self.bf2uris[str(subject)] = fcrepo_uri
        sparql = build_prefixes(self.repository.namespaces)
        sparql += "\nINSERT DATA {\n"
        if type(subject) == rdflib.URIRef:
            sparql += "<> owl:sameAs <" + str(subject) + "> .\n"
        elif type(subject) == rdflib.BNode:
            sparql += """<> owl:sameAs "{}" .\n""".format(subject)
        for predicate in [
            BF.authorizedAccessPoint,
            BF.titleValue,
            MADS.authoritativeLabel]:
                for obj_value in self.graph.objects(subject=subject,
                                                    predicate=predicate):
                    sparql += create_sparql_insert_row(predicate, obj_value)
        for type_of in self.graph.objects(
            subject=subject,
            predicate=rdflib.RDF.type):
                if str(type_of).startswith('http://bibframe'):
                    sparql += "<> rdf:type <" + str(type_of) + "> .\n"
        sparql += "}"
        update_request = urllib.request.Request(
            str(fcrepo_uri),
            data=sparql.encode(),
            method='PATCH',
            headers={'Content-Type': 'application/sparql-update'})
        try:
            result = urllib.request.urlopen(update_request)
            self.index(fcrepo_uri)
        except urllib.request.HTTPError:
            print("Error with {}, SPARQL:\n{}".format(fcrepo_uri, sparql))
            raise ValueError(sparql)
        return fcrepo_uri



def main():
    pass

if __name__ == '__main__':
    main()
