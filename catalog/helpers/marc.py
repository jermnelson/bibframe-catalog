#-------------------------------------------------------------------------------
# Name:        marc
# Purpose:     MARC21 module includes helper classes and functions for using
#              MARC 21 with Fedora 4 and Elasticsearch
#
# Author:      Jeremy Nelson
#
# Created:     2014/11/07
# Copyright:   (c) Jeremy Nelson 2014
# Licence:     GPLv3
#-------------------------------------------------------------------------------
__author__ = "Jeremy Nelson"

import pymarc


class MARCIngester(object):
    """Class takes a MARC21 or MARC XML file, ingests into Fedora 4 repository
    and into Elastic search"""

    def __init__(self, **kwargs):
        self.elastic_search = kwargs.get('elastic_search')
        self.record = kwargs.get('record')
        self.repository = kwargs.get('repository')


    def dedup(self, ils='III'):
        if ils.startswith('III'):
            # III MARC specific sys number
            bib_number = self.record['907']['a'][1:-1]
        else:
            return
        if self.elastic_search is not None:
            existing_result = self.elastic_search.search(
                index='marc',
                body={
                    "query": { "match": { "rdfs:label": bib_number}},
                    "_source": ["rdfs:label", "owl:sameAs"]})
            if existing_result.get('hits').get('total') > 0:
                # Returns first id
                first_hit = existing_result['hits']['hits'][0]
                return first_hit['_source']['owl:sameAs']

    def ingest(self, ils):
        existing_marc = self.dedup(record, ils)
        if existing_marc is not None:
            return existing_marc
        try:
            marc21 = record.as_marc()
        except UnicodeEncodeError:
            record.force_utf8 = True
            marc21 = record.as_marc()
        marc_content_uri = self.repository.create(data=marc21)
        marc_uri = marc_content_uri.replace('/fcr:content', '')
        # III specific BIB Number
        if ils.startswith("III"):
            bib_number = record['907']['a'][1:-1]

        else:
            # Use 001 as rdfs:label for MARC record
            bib_number = record['001'].data
        self.fedora.insert(marc_uri, 'rdfs:label', bib_number)
        if self.elastic_search is not None:
            marc_graph = rdflib.Graph().parse(marc_uri)
            marc_body = {
                "owl:sameAs": marc_uri,
                "rdfs:label": bib_number,
                "fcrepo:created": marc_graph.value(
                                    subject=rdflib.URIRef(marc_uri),
                                    predicate=FCREPO.created)}
            self.elastic_search.index(
                index='marc',
                doc_type='marc21',
                id=str(marc_graph.value(
                    subject=rdflib.URIRef(marc_uri),
                    predicate=FCREPO.uuid)),
                body=marc_body)
        return marc_uri

def main():
    pass

if __name__ == '__main__':
    main()
