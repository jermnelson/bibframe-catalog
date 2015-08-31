__author__ = "Original:Jeremy Nelson, Contributor:Mike Stabile"

import base64
import io
import json
import mimetypes
import requests
import logging
import re


from elasticsearch.exceptions import NotFoundError
from flask import abort, jsonify, render_template, redirect
from flask import request, session, send_file, url_for
from flask import stream_with_context, Response


from .forms import BasicSearch
from . import app, datastore_url, es_search, __version__
from .filters import *
from .filters import __get_cover_art__, __get_held_items__
from .util import *

try:
    from simplepam import authenticate
except ImportError:
    def authenticate(user, pwd):
        return True

app.url_map.converters['regex'] = RegexConverter

# Test comment
COVER_ART_SPARQL = """{}
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>
SELECT DISTINCT ?cover
WHERE {{{{
   ?cover fedora:uuid "{{}}"^^<http://www.w3.org/2001/XMLSchema#string>
}}}}""".format(PREFIX)


# Reporting Module Routes

@app.route('/reports/<regex("(.*)"):url>')
def kibana(url=None):
    if not 'username' in session:
        raise abort(403)
    kibana_url = app.config.get('KIBANA_URL')
    if not kibana_url.startswith("http"):
        kibana_url = 'http://' + kibana_url
    url = "{}/{}".format(kibana_url, url)
    req = requests.get(url, stream=True)
    return Response(
        stream_with_context(
            req.iter_content()), content_type = req.headers['content-type'])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if authenticate(str(username), str(password)):
            session['username'] = request.form['username']
            return redirect(url_for('index'))
        else:
            return 'Invalid username/password'
    else:
         return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('username')
    return redirect(url_for('index'))

@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    size = int(request.form.get('size', 20))
    from_ = int(request.form.get('from'))
    filter_ = request.form.get('filter', 'All').lower()
    sort = request.form.get('sort', 'Relevance').lower()
    doc_type, results = None, []
    es_dsl = {
        "query": {},
        "sort": {}
    }
    if filter_.startswith("all"):
        es_dsl['query']['match'] =  {"_all": phrase}
    else:
        if filter_.endswith("s"):
            filter_ = filter_[:-1]
        doc_type = filter_
        es_dsl["query"]["filtered"] =  {
            "query": {
                "match": {"_all": phrase}
            }
        }
        if doc_type.startswith("agent"):
            es_dsl["query"]["filtered"]["filter"] = {
                "or": [
                    {
                        "type": {
                            "value": "Person"
                        }
                     },
                     {
                         "type": {
                             "value": "Organization"
                         }
                     }
                ]
            }
        else:
            es_dsl["query"]["filtered"]["filter"] = {
                "type": {
                    "value": doc_type.title()
                }
           }
    if not sort.startswith("relevance"):
      es_dsl['sort'] = __generate_sort__(sort, doc_type)
    #print(es_dsl)
    result = es_search.search(
        body=es_dsl, 
        index='bibframe', 
        size=size,
        from_=from_)
    for hit in result.get('hits').get('hits'):
        typeDisplay = ""
        #if filter_.startswith("all"):
        typeDisplay =  hit['_type']
        item = {
            "title": guess_name(hit['_source']),
            "uuid": hit['_id'],
            "creators": find_creators(['_source']),
            "iType": typeDisplay,
            "url": "{}/{}".format(hit['_type'], hit['_id'])}
        item.update(__expand_instance__(hit['_source']))
        results.append(item)
    #print(results)
    return jsonify(
        {"hits": results, 
         "from": from_ + size,
         "total": result['hits']['total']})

@app.route("/typeahead", methods=['GET', 'POST'])
def typeahead_search():
    """Search view for typeahead search"""
    output = []
    search_type = request.args.get('type')
    key = search_type.lower()
    phrase = request.args.get('q')
   ##if key.startswith('alltypes'):
		
    if key.startswith('agent'):
        return __agent_search__(phrase)
    else: 
        es_dsl = {
            "{}-suggest".format(key): {
                "text": phrase,
                "completion": {
                    "field": "{}_suggest".format(key)
                }
            }
        }
    result = es_search.suggest(
        body=es_dsl,
        index='bibframe')
    
    for hit in result.get('{}-suggest'.format(key))[0]['options']:
        row = {key: hit['text'], 
               'uuid': hit['payload']['id']}
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

#@app.route("/<entity>/<uuid>.<ext>")
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

@app.route("/itemDetails")
def itemDetails():
    uuid = request.args.get('uuid')
    doc_type = request.args.get('type')
    relItems = {}
    if es_search.exists(id=uuid, index='bibframe'):
        resource = dict()
    result = es_search.get(id=uuid, index='bibframe')
    for k, v in result['_source'].items():
        #print(k," : ",v," --> ",type(v))
        itemLookup = lookupRelatedDetails(v)
        if itemLookup:
            result['_source'][k] = {'uuid':result['_source'][k],'lookup':itemLookup}
    if doc_type == 'Work':
        #print("*** work Type")
        lookupFlds = {'instances':'bf:instanceOf'}
        relItems = findRelatedItems(lookupFlds, uuid)
    if doc_type == 'Person':
        #print("*** Person Type")
        lookupFlds = {'works':'bf:contributor'}
        relItems = findRelatedItems(lookupFlds, uuid)
    if doc_type == 'Topic':
        lookupFlds = {'works':'bf:subject'}
        relItems = findRelatedItems(lookupFlds, uuid)
        		
    result['_z_relatedItems'] = relItems    
    resource.update(result)
    return jsonify(resource)

@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        #repository=repository,
        search=es_search,
        basic_search=BasicSearch(),
        version=__version__)
