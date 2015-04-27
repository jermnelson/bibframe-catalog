__author__ = "Jeremy Nelson"

import base64
import io
import json
import mimetypes
import requests
from flask import abort, jsonify, render_template, request
from flask import session, send_file, url_for
from .forms import BasicSearch
from . import app, datastore_url, es_search, __version__, datastore_url, PREFIX
from . import get_label, guess_name

COVER_ART_SPARQL = """{}
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>
SELECT DISTINCT ?cover
WHERE {{{{
   ?cover fedora:uuid "{{}}"^^<http://www.w3.org/2001/XMLSchema#string>
}}}}""".format(PREFIX)


def __get_cover_art__(instance_uuid):
    """Helper function takes an instance_uuid and searches for 
    any cover art, returning the CoverArt ID and schema:isBasedOnUrl.
    This may change in the future versions.

    Args:
        instance_uuid -- RDF fedora:uuid 
    """
    es_dsl = {
      "fields": ['schema:isBasedOnUrl'],
      "query": {
        "bool": {
          "must": [
            {"match": { 
              "bf:coverArtFor": instance_uuid}
            }
          ]
        }
      }
     }
    result = es_search.search(
        body=es_dsl,
        index='bibframe')
    if result.get('hits').get('total') > 0:
        top_hit = result['hits']['hits'][0]
        return {"src": url_for('cover', uuid=top_hit['_id'], ext='jpg'),
                "url": top_hit['fields']['schema:isBasedOnUrl']}

def __get_held_items__(instance_uuid):
    """Helper function takes an instance uuid and search for any heldItems
    that match the instance, returning the circulation status and 
    name of the organization that holds the item

    Args:
      instance_uuid -- RDF fedora:uuid
    """
    items = list()
    es_dsl = {
      "fields": ['bf:circulationStatus', 'bf:heldBy'],
      "query": {
        "bool": {
          "must": [
            {"match": {
              "bf:holdingFor": instance_uuid}
            }
          ]
        }
      }
    }
    result = es_search.search(
        body=es_dsl,
        index='bibframe',
        doc_type='HeldItem')
    for hit in result.get('hits', []).get('hits', []):
        if not 'fields' in hit:
            continue
        items.append({"location": get_label(hit['fields']['bf:heldBy'][0]),
                      "circulationStatus": hit['fields'].get('bf:circulationStatus')})    
    return items 


def __expand_instance__(instance):
    """Helper function takes a search result Instance, queries index for 
    creator and holdings information 

    Args:
        instance -- Elastic search hit result
    """
    output = dict()
    work_id = instance.get('bf:instanceOf')
    if not work_id:
        return {}
    work = es_search.get(
        id=work_id[0],  
        index='bibframe', 
        fields=['bf:creator', 
                'bf:subject'])
    
    if not work.get('found'):
        return {}
    creators = str()
    for creator_id in work.get('fields').get('bf:creator', []):
        creator = es_search.get(
            id=creator_id, 
            index='bibframe', 
            fields=['bf:label'])
        if creator.get('found'):
            creators += ' '.join(creator.get('fields', 
                                 {}).get('bf:label'))
    if len(creators) > 0:
        output['creators'] = creators
    cover_art = __get_cover_art__(instance.get('fedora:uuid')[0])
    if cover_art:
        output['cover'] = cover_art
    locations = __get_held_items__(instance.get('fedora:uuid')[0])
    if locations:
        output['locations'] = locations
    return output


@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    results = []
    if search_type.startswith("kw"):
        result = es_search.search(q=phrase, index='bibframe', doc_type='Instance', size=5)
    else:
        result = es_search.search(
            q=phrase,
            index='bibframe',
            doc_type='Work',
            size=5)
    for hit in result.get('hits').get('hits'):
        item = {
            "title": guess_name(hit['_source']),
            "uuid": hit['_id'], 
            "url": "{}/{}".format(hit['_type'], hit['_id'])}
        item.update(__expand_instance__(hit['_source']))
##        for key, value in hit['_source'].items():
##            if key.startswith('fcrepo:uuid'):
##                continue
##            for i,row in enumerate(value):
##                # quick hack to check if value is uuid
##                if row.count('-') == 4 and es_search.exists(id=row, index='bibframe'):
##                    item[key] = es_search.get_source(id=row, index='bibframe')
##                    #hit['_source'][key][i] = es_search.get_source(id=row, index='bibframe')
##                else:
##                    item[key] = row
        results.append(item)
    return jsonify({"hits": results})

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
        raw_image = base64.b64decode(
            cover.get('bf:coverArt')[0])
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
