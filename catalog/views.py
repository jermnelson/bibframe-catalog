__author__ = "Jeremy Nelson"

import base64
import io
import json
import mimetypes
import requests
from flask import abort, jsonify, render_template, redirect
from flask import request, session, send_file, url_for
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
    for creator_id in work.get('fields', {}).get('bf:creator', []):
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
    size = int(request.form.get('size', 5))
    from_ = int(request.form.get('from'))
    results = []
    if search_type.startswith("kw"):
        result = es_search.search(
            q=phrase, 
            index='bibframe', 
            doc_type='Instance', 
            size=size,
            from_=from_)
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
        results.append(item)
    return jsonify(
        {"hits": results, 
         "from": from_ + size,
         "total": result['hits']['total']})

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
        row = {key: None, 'uuid': hit['_id']}
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
        cover = es_search.get(
            id=uuid, 
            index='bibframe', 
            fields=['bf:coverArt'])
        raw_image = base64.b64decode(
            cover.get('fields').get('bf:coverArt')[0])
        file_name = '{}.{}'.format(uuid, ext)
        return send_file(io.BytesIO(raw_image),
                         attachment_filename=file_name,
                         mimetype=mimetypes.guess_type(file_name)[0])
    abort(404)

@app.route("/<uuid>", defaults={"ext": "html"})
@app.route("/<uuid>.<ext>")
def detail_redirect(uuid, ext):
    """View resolves an uuid to more specific entity in the catalog.

    Args:
        uuid -- UUID of Bibframe Resource
        ext -- extension of the view, defaults to html
    """
    if es_search.exists(id=uuid, index='bibframe'):
        result = es_search.get(id=uuid, index='bibframe', fields=['_type'])
        entity = result.get('_type')   
        return redirect(url_for('detail', 
                        entity=entity, 
                        uuid=uuid, 
                        ext=ext))
    abort(404)

@app.route("/<entity>/<uuid>.<ext>")
@app.route("/<entity>/<uuid>")
@app.route("/<entity>/<uuid>.json")
def detail(uuid, entity="Work", ext="html"):
    if es_search.exists(id=uuid, index='bibframe', doc_type=entity):
        resource = dict()
        result = es_search.get_source(id=uuid, index='bibframe')
        resource.update(result)
        if ext.startswith('json'):
            return jsonify(resource)
        template = "detail.html"
        if entity.lower().startswith("instance"):
            template = "{}-detail.html".format(entity.lower())
        return render_template(
            template,
            entity=resource,
            version=__version__)
    abort(404)


@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        #repository=repository,
        search=es_search,
        basic_search=BasicSearch(),
        version=__version__)
