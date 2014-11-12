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


def default_graph():
    """Function generates a new rdflib Graph and sets all namespaces as part
    of the graph's context"""
    new_graph = rdflib.Graph()
    for key, value in CONTEXT.items():
        new_graph.namespace_manager.bind(key, value)
    return new_graph

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
    if str(predicate).startswith(str(BF)):
        statement += "bf:" + predicate.split("/")[-1]
    if str(predicate).startswith(str(MADS)):
        statement += "mads:" + predicate.split("#")[-1]
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

    def dedup(self, term):
        """Method takes a term and attempts to match it againest three
        subject properties that have been indexed into Elastic search, returns
        the first hit if found. This method may need further refinement to
        provide the optimal deduplication for BIBFRAME resources.

        Args:
            term(string): A search term or phrase

        Returns:
            string URL of the top-hit for matching the term on a list of
            properties
        """
        if term is None:
            return
        search_result = self.elastic_search.search(
            index="bibframe",
            body={
                "query": {
                    "multi_match": {
                        "query": term,
                        "type": "phrase",
                        "fields": [
                            "bf:authorizedAccessPoint",
                            "mads:authoritativeLabel",
                            "bf:label"]}}})
        if search_result.get('hits').get('total') > 0:
            top_hit = search_result['hits']['hits'][0]['_source']['owl:sameAs']
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
        for predicate in [
            BF.authorizedAccessPoint,
            MADS.authoritativeLabel,
            BF.label]:
            object_value = self.graph.value(
                subject=subject,
                predicate=predicate)
            if object_value is not None:
                result = self.dedup(str(object_value))
                if result is not None:
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
        doc_type = 'Resource'
        subject_types = [obj for obj in self.graph.objects(
                subject=fcrepo_uri,
                predicate=rdflib.RDF.type)]
        for class_name in [
            'Work',
            'Annotation',
            'Authority',
            'Instance']:
                if getattr(BF, class_name) in subject_types:
                    doc_type = class_name.split('/')[-1]
        body = json.loads(fcrepo_graph.serialize(
                format='json-ld',
                context=CONTEXT).decode())
        if '@context' in body:
            body.pop('@context')
        body['owl:sameAs'] = str(fcrepo_uri)
        self.elastic_search.index(
            index='bibframe',
            doc_type=doc_type,
            id=str(fcrepo_graph.value(
                    subject=fcrepo_uri,
                    predicate=FCREPO.uuid)),
            body=body)

    def ingest(self):
        """Method ingests a BIBFRAME graph into Fedora 4 and Elastic search"""
        start = datetime.datetime.utcnow()
        print("Started ingestion at {}".format(start.isoformat()))
        self.initialize()
        for i, subject_uri in enumerate(self.bf2uris.keys()):
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
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
        for i, subject in enumerate(
            set([subject for subject in self.graph.subjects()])):
            if type(subject) == rdflib.BNode:
                continue
            if self.exists(subject):
                continue
            self.stub(subject)
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
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
        new_graph = default_graph()
##        if not str(subject) in self.bf2uris:
##            # Failed to find internal, now try SPARQL search
##            sparql_template = Template("""SELECT ?fedora_uri
##                WHERE {
##                    ?fedora_uri <http://www.w3.org/2002/07/owl#sameAs> <$subject>
##                }""")
##            raw_result = self.repository.sparql(
##                sparql_template.substitute(subject=str(subject)),
##                "application/sparql-results+json")
##            json_result = json.loads(raw_result)
##            if len(json_result['results']['bindings']) > 0:
##                first_row =json_result['results']['bindings'][0]
##                fedora_uri = first_row['fedora_url']['value']
##                self.bf2uris[str(subject)] = fedora_uri
##            else:
##                raise ValueError("Fedora URI not found {}".format(subject))
##        else:
        fedora_uri = self.bf2uris[str(subject)]
        sparql = build_prefixes(self.repository.namespaces)
        sparql += "\nINSERT DATA {\n"
        for predicate, object_ in self.graph.predicate_objects(subject=subject):
            if type(object_) == rdflib.BNode:
                for b_predicate, b_object in self.graph.predicate_objects(
                    subject=object_):
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
        sparql += "<> owl:sameAs <" + str(subject) + "> .\n"
        for predicate in [
            BF.authorizedAccessPoint,
            BF.label,
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
