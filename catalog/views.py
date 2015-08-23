__author__ = "Original:Jeremy Nelson, Contributor:Mike Stabile"

import base64
import io
import json
import mimetypes
import requests
import logging
import re

from simplepam import authenticate

from elasticsearch.exceptions import NotFoundError
from flask import abort, jsonify, render_template, redirect
from flask import request, session, send_file, url_for
from flask import stream_with_context, Response

from .forms import BasicSearch
from . import app, datastore_url, es_search, __version__
from .filters import *
from .filters import __get_cover_art__, __get_held_items__

uuidPattern = re.compile('[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89aAbB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}')

def lookupRelatedDetails(v):
    #Test the value => v to see if it is a uuid
    returnList = []
    #print('Entered lookup: ', v)
    if isinstance(v, list):
        for pUuid in v:
            #print ("pUuid: ",pUuid)   
            mUuid = uuidPattern.match(pUuid)
            if mUuid:
                #if v matches a uuid pattern then search for the item in elasticsearch
                if es_search.exists(id=pUuid, index='bibframe'):
                    uuidResult = es_search.get_source(id=pUuid, index='bibframe')
                    returnList.append(uuidResult)
    if len(returnList) > 0:
        return returnList
    else:
        return 0
	
def findRelatedItems(filterFld,v):
    es_dsl = {'rel_instances':{}, 'rel_works':{}, 'rel_agents':{}, 'rel_topics':{}}
    #print(filterFld)
    if "instances" in filterFld:
        print("enter Instance DSL")
        es_dsl['rel_instances'] = {
                     "query" : {
                         "filtered" : {
                             "filter" : {
                                 "term" : {
                                    filterFld['instances'] : v
                                          }
                                        }
                                      }
                                }
                 }
    if "works" in filterFld:
        es_dsl['rel_works'] = {
                     "query" : {
                                 "term" : {
                                    filterFld['works'] : v
                                          }
                                }
                 }
    if "agents" in filterFld:
        es_dsl['rel_agents'] = {
                     "query" : {
                         "filtered" : {
                             "filter" : {
                                 "term" : {
                                    filterFld['agents'] : v
                                          }
                                        }
                                      }
                                }
                 }
    if "topics" in filterFld:
        es_dsl['rel_topics'] = {
                     "query" : {
                         "filtered" : {
                             "filter" : {
                                 "term" : {
                                    filterFld['topics'] : v
                                          }
                                        }
                                      }
                                }
                 }
    result = {}
    #print("es_dsl***",es_dsl)
    for k, dsl in es_dsl.items():
        #print ("k:",k," dsl:",dsl)
        if k.replace("rel_","") in filterFld:
            #print("*** Entered search ***")
            searchResult = es_search.search(
                body=dsl, 
                index='bibframe', 
                )
            #print("searchResult*** ", searchResult)
            result = {k:searchResult['hits']['hits']}
    #print("rel items *** ",result)
    return result
      
# Test comment
COVER_ART_SPARQL = """{}
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>
SELECT DISTINCT ?cover
WHERE {{{{
   ?cover fedora:uuid "{{}}"^^<http://www.w3.org/2001/XMLSchema#string>
}}}}""".format(PREFIX)

def __agent_search__(phrase):
    """Agent search for suggest completion 

    Args:
        phrase -- text phrase
    """
    output = []
    es_dsl = {
        "organization-suggest": {
            "text": phrase,
                "completion": {
                    "field": "organization_suggest"

               }
        },
       "person-suggest": {
           "text": phrase,
                "completion": {
                    "field": "person_suggest"
                }

            }
     }
    result = es_search.suggest(body=es_dsl, index='bibframe')
    for suggest_type in [ "person-suggest", 'organization-suggest']:
        for hit in result.get(suggest_type)[0]['options']:
            row = {'agent': hit['text'], 
                   'uuid':  hit['payload']['id']}
            output.append(row)
    return json.dumps(output)


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
    try:
        work = es_search.get(
            id=work_id[0],  
            index='bibframe', 
            fields=['bf:creator', 
                    'bf:subject'])
    except NotFoundError:
        #! Should preform secondary ES search on work_id
        return {}
    
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
    items = __get_held_items__(instance.get('fedora:uuid')[0])
    output['held_items'] = []
    if len(items) > 0:
        for row in items:
            item = dict()
            for field, value in row.items():
                item[field.split(":")[1]] = value
            if not 'circulationStatus' in item:
                item['circulationStatus'] = 'Available'
            for key in ['shelfMarkLcc', 'heldBy', 'subLocation']:
                if not key in item:
                    item[key] = None 
            output['held_items'].append(item)
    return output

def __generate_sort__(sort, doc_type):
    """Generates sort DSL based on type of sort and the doc_type"""
    output = {}
    if sort.startswith("a-z"):
        order = "asc"
    elif sort.startswith("z-a"):
        order = "desc"
    #! Need routing for Category?
    output["bf:label"] = {"order": order}
    return output
    
# Reporting Module Routes
@app.route("/kibana/<path:url>")
def kibana(url):
    if not 'username' in session:
        raise abort(403)
    kibana_url = config.get('KIBANA_URL') + url
    req = requests.get(kibana_url, stream=True)
    return Response(
        stream_with_context(
            req.iter_content()), content_type = req.headers['content-type'])

@app.route("/reports")
def reports():
    if not 'username' in session:
        raise abort(403)
    return "Reporting Module"

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
    size = int(request.form.get('size', 5))
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
        lookupFlds = {'works':'bf:creator'}
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
