__author__ = "Jeremy Nelson"

import base64
import io
import json
import mimetypes
import requests
from flask import abort, jsonify, render_template, request
from flask import session, send_file
from .forms import BasicSearch
from . import app, datastore_url, es_search, __version__, datastore_url, PREFIX

COVER_ART_SPARQL = """{}
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>
SELECT DISTINCT ?cover
WHERE {{{{
   ?cover fedora:uuid "{{}}"^^<http://www.w3.org/2001/XMLSchema#string>
}}}}""".format(PREFIX)

@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    if search_type.startswith("kw"):
        result = es_search.search(q=phrase, index='bibframe', doc_type='Instance', size=5)
    else:
        result = es_search.search(
            q=phrase,
            index='bibframe',
            doc_type='Work',
            size=5)
    for hit in result.get('hits').get('hits'):
        for key, value in hit['_source'].items():
            if key.startswith('fcrepo:uuid'):
                continue
            for i,row in enumerate(value):
                if es_search.exists(id=row, index='bibframe'):
                    hit['_source'][key][i] = es_search.get_source(id=row, index='bibframe')

    return jsonify(result)

@app.route("/typeahead", methods=['GET', 'POST'])
def typeahead_search():
    """Search view for typeahead search"""
    output = []
    search_type = request.args.get('type')
    phrase = request.args.get('q')
    es_dsl = {
        "query": {
          "bool": {
            "should": [
              {"match": { "bf:authorizedAccessPoint": phrase }},
              {"match": { "bf:label": phrase }},
              {"match": { "bf:title": phrase }} 
            ]    
            }
        }
    #    "sort": { "bf:authorizedAccessPoint": "desc" }
    }
    result = es_search.search(
        body=es_dsl,
        index='bibframe',
        doc_type=search_type,
        size=5)
    key = search_type.lower()
    for hit in result.get('hits').get('hits'):
        row = {key: None}
        graph = hit['_source']
        if 'bf:label' in graph:
            row[key] = graph['bf:label'][0]
        if 'bf:title' in graph:
            row[key] = graph['bf:title'][0]
        if not row[key] is None:
            output.append(row)
    return json.dumps(output)

@app.route("/CoverArt/<uuid>.<ext>", defaults={"ext": "jpg"})
def cover(uuid, ext):
    if es_search.exists(id=uuid, index='bibframe'):
        cover = es_search.get_source(id=uuid, index='bibframe')
        raw_image = base64.decode(
            cover.get('hits').get('hits')[0]['bf:coverArt'][0])
        file_name = '{}.{}'.format(uuid, ext)
        return send_file(io.BytesIO(raw_image),
                         attachment_filename=file_name,
                         mimetype=mimetypes.guess_type(file_name)[0])
    abort(404)

@app.route("/<entity>/<uuid>", defaults={"ext": "html"})
@app.route("/<entity>/<uuid>.<ext>", 
           defaults={"entity": "Work", 
                     "ext": "html"})
def detail(entity, uuid, ext):
    if es_search.exists(id=uuid, index='bibframe', doc_type=entity):
        resource = dict()
        result = es_search.get_source(id=uuid, index='bibframe')
        resource.update(result)
        if entity.lower().startswith("work"):
            sparql = """SELECT DISTINCT ?instance
WHERE {{{{
  ?instance  bf:instanceOf <{}> . 
}}}}""".format(result['fcrepo:hasLocation'][0])
                    
        return render_template(
            'detail.html',
            entity=resource,
            version=__version__)
    abort(404)

##@app.route("/<entity>/<uuid>.<ext>")
##@app.route("/<uuid>.<ext>", defaults={"entity": "Work", "ext": "html"})
##@app.route("/<uuid>", defaults={"entity": None})
##def resource(uuid, entity, ext='html'):
##    """Detailed view for a single resource
##
##    Args:
##        uuid: Fedora UUID also used as ID in Elastic Search index
##    """
##    if es_search.exists(id=uuid, index='bibframe'):
##        result = es_search.get_source(id=uuid, index='bibframe')
##        for key, value in result.items():
##            if key.startswith('fcrepo:uuid'):
##                continue
##            for i,row in enumerate(value):
##                if es_search.exists(id=row, index='bibframe'):
##                    result[key][i] = es_search.get_source(id=row, index='bibframe')
##        #fedora_url = result.get('fcrepo:hasLocation')[0]
##        #fedora_graph = rdflib.Graph().parse(fedora_url)
##        related = es_search.search(q=uuid, index='bibframe')
##        if ext.startswith('json'):
##            #return fedora_graph.serialize(format='json-ld', indent=2).decode()
##            return jsonify(result)
##        return render_template(
##            'detail.html',
##            entity=result,
##            #graph=fedora_graph,
##            related=related,
##            version=__version__
##        )
##    abort(404)


@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        #repository=repository,
        search=es_search,
        basic_search=BasicSearch(),
        version=__version__)
