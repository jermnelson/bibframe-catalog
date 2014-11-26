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
import re
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

url_check_re = regex = re.compile(
    r'^(?:http|ftp)s?://' # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
    r'localhost|' # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ...or ipv4
    r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ...or ipv6
    r'(?::\d+)?' # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

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
        if url_check_re.search(str(object_)):
            statement += " <" + str(object_) + "> "
        else:
            statement += """ "{}" """
    if type(object_) == rdflib.Literal:
        if str(object_).find('"') > -1:
            value = """ '''{}''' """.format(object_)
        else:
            value = """ "{}" """.format(object_)
        statement += value
    if type(object_) == rdflib.BNode:
        statement += """ "BNODE:{}" """.format(object_)
    statement += ".\n"
    return statement

def default_graph():
    """Function generates a new rdflib Graph and sets all namespaces as part
    of the graph's context"""
    new_graph = rdflib.Graph()
    for key, value in CONTEXT.items():
        new_graph.namespace_manager.bind(key, value)
    return new_graph

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
        'HeldItem',
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
            repository(flask_fedora_commons.Repository): Fedora Commons Repository
            quiet(boolean): If False, prints status of ingestion
            debug(boolean): Adds additional information for debugging purposes

        """
        self.bf2uris = {}
        self.debug = kwargs.get('debug', False)
        self.uris2uuid = {}
        self.elastic_search = kwargs.get('elastic_search', Elasticsearch())
        if not self.elastic_search.indices.exists('bibframe'):
            self.elastic_search.indices.create('bibframe')
        self.graph = kwargs.get('graph', default_graph())
        self.repository = kwargs.get('repository', Repository())
        self.quiet = kwargs.get('quiet', False)

    def generate_body(self, fedora_uri):
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
                uri = value.get('@id')
                if uri in self.uris2uuid:
                    return self.uris2uuid[uri]
                else:
                    return uri
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
            top_hit = search_result['hits']['hits'][0]
            return top_hit['_source']['fcrepo:hasLocation'][0]


    def exists(self, subject):
        """Method takes a subject, queries Elasticsearch index,
        if present, adds result to bf2uris, always returns boolean

        Args:
            subject(rdflib.Term): Subject, can be literal, BNode, or URI

        Returns:
            boolean
        """
        doc_type = guess_search_doc_type(self.graph, subject)
        # This should be accomplished in a single Elasticseach query
        # instead of potentially five separate queries
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
                if result:
                    return result


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
        self.uris2uuid[str(fcrepo_uri)] = doc_id
        doc_type = guess_search_doc_type(fcrepo_graph, fcrepo_uri)
        body = self.generate_body(fcrepo_uri)
        self.elastic_search.index(
            index='bibframe',
            doc_type=doc_type,
            id=doc_id,
            body=body)

    def ingest(self):
        """Method ingests a BIBFRAME graph into Fedora 4 and Elastic search"""
        start = datetime.datetime.utcnow()
        if self.quiet is False:
            print("Started ingestion at {}".format(start.isoformat()))
        query = self.graph.query("""PREFIX bf: <http://bibframe.org/vocab/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?work
WHERE {
  ?work rdf:type bf:Work .
}""")
        for row in query:
            self.stub(row[0])
        for i, subject_uri in enumerate(
            set([subject for subject in self.graph.subjects()])):
            if not i%10 and i > 0:
                if self.quiet is False:
                    print(".", end="")
            if not i%100:
                if self.quiet is False:
                    print(i, end="")
            self.process_subject(subject_uri)
        end = datetime.datetime.utcnow()
        if self.quiet is False:
            print("Finished ingesting at {}, total time={} minutes for {} subjects".format(
                end.isoformat(),
                (end-start).seconds / 60.0,
                i))

    def process_subject(self, subject):
        """Method takes a subject URI and iterates through the subject's
        predicates and objects, saving them to a the subject's Fedora graph.
        Blank nodes are expanded and saved as properties to the subject
        graph as well. Finally, the graph is serialized as JSON-LD and updated
        in the Elastic Search index.

        Args:
            subject(rdflib.URIRef): Subject URI
        """
        fedora_url = self.exists(subject)
        if fedora_url:
            return fedora_url
        fedora_url = self.repository.create()
        sparql = build_prefixes(self.repository.namespaces)
        sparql += "\nINSERT DATA {\n"
        if self.debug:
            sparql += create_sparql_insert_row(
                OWL.sameAs,
                subject
            )
        for predicate, _object in self.graph.predicate_objects(subject=subject):
            if type(_object) == rdflib.Literal:
                sparql += create_sparql_insert_row(
                    predicate,
                    _object
                )
            elif self.exists(_object):
                object_url = self.exists(_object)
                sparql += create_sparql_insert_row(
                    predicate,
                    rdflib.URIRef(object_url)
                )
            elif _object in self.graph.subjects():
                object_url = self.process_subject(_object)
                try:
                    rdflib.URIRef(object_url)
                except:
                    print("Failed object url={}".format(object_url))
                    print(subject, predicate, _object)

                sparql += create_sparql_insert_row(
                    predicate,
                    rdflib.URIRef(object_url)
                )
            else:
                sparql += create_sparql_insert_row(
                    predicate,
                    _object)
        sparql += "\n}"
        update_fedora_request = urllib.request.Request(
            fedora_url,
            method='PATCH',
            data=sparql.encode(),
            headers={"Content-type": "application/sparql-update"})
        try:
            result = urllib.request.urlopen(update_fedora_request)
            self.index(rdflib.URIRef(fedora_url))
            return fedora_url
        except:
            print("Could NOT process subject {} Error={}".format(
                subject,
                sys.exc_info()[0]))
            print(fedora_url)
            print(sparql)

    def stub(self, subject):
        """Method creates a Fedora Object BIBFRAME stub with minimal

        Args:
            subject(rdflib.URIRef): Subject URI

        Returns:
            string: Fedora URI
        """
        fcrepo_uri = rdflib.URIRef(self.repository.create())
        sparql = build_prefixes(self.repository.namespaces)
        sparql += "\nINSERT DATA {\n"
        if type(subject) == rdflib.URIRef:
            sparql += "<> owl:sameAs <" + str(subject) + "> .\n"
        elif type(subject) == rdflib.BNode:
            sparql += """<> owl:sameAs "{}" .\n""".format(subject)
        for predicate in [
            BF.authorizedAccessPoint,
            BF.label,
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
