"""
Name:        filters
Purpose:     jinja2 filters for bibcat.org.

Author:      Jeremy Nelson

Created:     2015/06/03
Copyright:   (c) Jeremy Nelson 2015
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"
__license__ = "GPLv3"
import os
import requests

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

with open(os.path.join(BASE_DIR, "VERSION")) as version:
    __version__ = version.read().strip()

import json
import rdflib
import urllib.request
import re
from flask import render_template, url_for
from .forms import BasicSearch
import sys
from . import app, datastore_url, es_search
from .util import *
from .util import __get_cover_art__, __get_held_items__

PREFIX = """PREFIX bf: <http://bibframe.org/vocab/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>"""

GET_CREATORS_INSTANCE_SPARQL = """{}
SELECT DISTINCT ?name
WHERE {{{{
   <{{}}> bf:instanceOf ?work .
   {{{{ ?work bf:creator ?agent }}}} UNION {{{{ ?work bf:contributor ?agent }}}} .
   ?agent bf:label ?name .
}}}}""".format(PREFIX)

GET_CREATORS_WORK_SPARQL = """{}
SELECT DISTINCT ?name
WHERE {{{{
   {{{{ <{{}}>  bf:creator ?agent . }}}} UNION {{{{ <{{}}> bf:contributor ?agent }}}} .
   ?agent bf:label ?name .
}}}}""".format(PREFIX)


#! Both cover sparql should be combined into a single 
#! SPARQL statement.
GET_INSTANCE_COVER_SPARQL = """{}
SELECT DISTINCT ?cover_metadata ?uuid
WHERE {{{{
    ?cover_metadata bf:coverArtFor <{{}}> .
    ?cover_metadata fedora:uuid ?uuid . 
}}}}""".format(PREFIX)

GET_WORK_COVER_SPARQL = """{}

SELECT DISTINCT ?cover_metadata ?uuid
WHERE {{{{
    ?instance bf:instanceOf <{{}}> .
    ?cover_metadata bf:coverArtFor ?instance .
    ?cover_metadata fedora:uuid ?uuid .
}}}}""".format(PREFIX)



GET_INSTANCE_SPARQL = """{}
SELECT DISTINCT ?instance
WHERE {{{{
    ?instance bf:instanceOf <{{}}> 

}}}}""".format(PREFIX)

GET_LABEL_SPARQL = """{}
SELECT DISTINCT ?label
WHERE {{{{
   <{{}}> bf:label ?label .
}}}}""".format(PREFIX)

GET_TITLEVALUE_SPARQL = """{}
SELECT DISTINCT ?titleValue
WHERE {{{{
 <{{}}> bf:titleValue ?titleValue .
}}}}""".format(PREFIX)

HELD_ITEM_SPARQL = """{}
SELECT DISTINCT ?org_label ?circ_status ?item_id
WHERE {{{{
   ?held_item fedora:uuid "{{}}"^^<http://www.w3.org/2001/XMLSchema#string> .
   ?held_item bf:circulationStatus ?circ_status .
   ?held_item bf:itemId ?item_id .
   ?held_item bf:heldBy ?org .
   ?org bf:label ?org_label .
}}}}""".format(PREFIX)

HELD_ITEMS_SPARQL = """{}
SELECT DISTINCT ?uuid
WHERE {{{{
  ?held_item bf:holdingFor <{{}}> .
  ?held_item fedora:uuid ?uuid .
}}}}""".format(PREFIX)

WORK_HELD_ITEMS_SPARQL = """{}
SELECT DISTINCT ?uuid
WHERE {{{{
 ?instance bf:instanceOf <{{}}> .
 ?held_item bf:holdingFor ?instance .
 ?held_item fedora:uuid ?uuid .
}}}}""".format(PREFIX)




@app.template_filter('bf_type')
def bibframe_type(entity):
    if 'type' in entity:
        entity_type = entity.get('type', [])
        if len(entity_type) > 0:
            return entity_type[0][3:]
    return "Unknown"

@app.template_filter('cover_art')
def get_cover(entity):
    cover_url = url_for('static', filename='images/cover-placeholder.png')
    entity_id = entity.get('fedora:uuid')
    cover_art = __get_cover_art__(entity_id)
    if cover_art is not None:
        cover_url = cover_art.get('src')
    return cover_url       

def get_cover_sparql(entity):
    cover_url = url_for('static', filename='images/cover-placeholder.png')
    if 'bf:workTitle' in entity:
        sparql = GET_WORK_COVER_SPARQL.format(entity['fedora:hasLocation'][0])
    else:
        sparql = GET_INSTANCE_COVER_SPARQL.format(entity['fedora:hasLocation'][0])       
    result = requests.post(
       "{}/triplestore".format(datastore_url), 
       data={"sparql": sparql})
    
    if result.status_code < 400:
        results = result.json()['results']
        if len(results['bindings']) > 0: 
            cover_url = url_for('cover', 
                uuid=results['bindings'][0]['uuid']['value'], ext='jpg')
    return cover_url

@app.template_filter('creator')
def creator(entity):
    name = ''
    if 'bf:creator' in entity:
        for creator in entity['bf:creator']:
            if 'bf:label' in creator:
                name += " {}".format(creator['bf:label'][0])
            elif 'mads:authoritativeLabel' in creator:
                name += "  {}".format(
                    creator['mads:authoritativeLabel'][0])
    return name

@app.template_filter('held_items')
def held_items(entity):
    output = str()
    entity_uuid = entity.get('fedora:uuid')
    items = __get_held_items__(entity_uuid)
    if len(items) > 0:
        for item in items:
            output += render_template('snippets/held-item.html',
                                       item=item)
    return output

def held_items_sparql(entity):
    output = str()
    fedora_url = entity['fedora:hasLocation'][0]
    # Ugly hack to determine if the entity is a Work
    if 'bf:workTitle' in entity:
        sparql = WORK_HELD_ITEMS_SPARQL.format(fedora_url)
    else:
        sparql = HELD_ITEMS_SPARQL.format(fedora_url)
    result = requests.post(
       "{}/triplestore".format(datastore_url), 
       data={"sparql": sparql})
    if result.status_code < 400:
        results = result.json()['results']
        for row in results.get('bindings', []):
            uuid = row['uuid']['value']
            if es_search.exists(id=uuid, index='bibframe'):
                held_item = es_search.get_source(id=uuid, index='bibframe')
                output += render_template('snippets/held-item.html',
                                          item=held_item)
            else:
                sparql= HELD_ITEM_SPARQL.format(uuid)
                held_item_result = requests.post(
                    "{}/triplestore".format(datastore_url), 
                    data={"sparql": sparql})
                if held_item_result.status_code < 400:
                    bindings = held_item_result.json().get('results').get('bindings')
                    if len(bindings) > 0:
                        output += render_template(
                            'snippets/held-item.html', 
                            item=[0])
                else:
                    output = "Cannot find {} for {}".format(uuid, fedora_url)
    return output

@app.template_filter('get_label')
def get_label(uuid):
    """get_label filter takes a uuid and attempt to retrieve the label

    Args:
        uuid -- Unique id used as key in Elastic Search
    """
    if es_search.exists(id=uuid, index='bibframe'):
        result = es_search.get(id=uuid, index='bibframe', fields=['bf:label'])
        if 'fields' in result:
            return ' '.join(result['fields']['bf:label'])
    return uuid
    

@app.template_filter('name')
def guess_name(entity):
    """Name filter attempts to serialize a BIBFRAME entity"""
    name = ''
    if 'bf:titleValue' in entity:
        #print('guess->bf:titleValue--> ', entity['bf:titleValue'],' --> ', entity['bf:titleValue'][0])
        name = entity['bf:titleValue'][0]
        if 'bf:subtitle' in entity:
            name += ','.join(entity.get('bf:subtitle'))
    elif 'bf:title' in entity:
        name = ','.join(entity.get('bf:title'))
    elif 'bf:titleStatement' in entity:
        name = ','.join(entity.get('bf:titleStatement'))
    elif 'bf:workTitle' in entity:
        #print(entity.get('bf:workTitle'))
        name = ','.join([guess_name(title) for title in entity.get('bf:workTitle')])
    elif 'bf:label' in entity:
        name = ','.join(entity.get('bf:label'))
    elif 'bf:authorizedAccessPoint' in entity:
        for row in entity.get('bf:authorizedAccessPoint'):
            if row.find(" ") < 0:
                continue
            name += "{},".format(row)
        if name.endswith(","):
            name = name[:-1]
    elif len(name) < 1:
        if 'fedora:uuid' in entity:
            name = ','.join(entity['fedora:uuid'][0])
        else:
            lookupObj = lookupRelatedDetails([entity])
            try:
                name = lookupObj[0]['bf:titleValue'][0]
            except:
                pass
            if len(name) < 1:
                name = entity[0]
    return name

def find_creators(entity):
    """Name filter attempts to serialize a BIBFRAME entity"""
    name = ''
    if 'bf:contributor' in entity:
        lookupObj = lookupRelatedDetails(entity[bf:contributor])
        try:
            name = lookupObj[0]['bf:authorizedAccessPoint'][0]
        except:
            pass
    if 'bf:creator' in entity:
        lookupObj = lookupRelatedDetails(entity[bf:creator])
        try:
            name = lookupObj[0]['bf:authorizedAccessPoint'][0]
        except:
            pass
    return name
    
@app.template_filter('title_author')
def generate_detail_title(entity):
    output = str()
    work = None
    entity_classes = entity.get('type', [])
    if 'bf:Work' in entity_classes:
        if 'bf:workTitle' in entity:
            for key in entity.get('bf:workTitle'):
                if not es_search.exists(id=title_key, index='bibframe'):
                    continue 
                title = es_search.get_source(id=entity.get('bf:workTitle')[0], 
                    index='bibframe')
            output += title 
        work = entity
    if 'bf:Instance' in entity_classes:
        if 'bf:titleStatement' in entity:
            output += ",".join(entity.get('bf:titleStatement'))
        elif 'bf:title' in entity:
            output += ",".join(entity.get('bf:title'))
        for work_key in entity.get('bf:instanceOf'):
            if not es_search.exists(id=work_key, index='bibframe'):
                continue
            work = es_search.get_source(id=work_key, index='bibframe')
            break
    if output.count("/") < 1:
        output += " / "
    for agent in ['bf:creator', 'bf:contributor']:
        if work is not None and agent in work:
            for i, key in enumerate(work[agent]):
                if not es_search.exists(id=key, index='bibframe'):
                    continue
                contributor = es_search.get_source(id=key, index='bibframe')
                output += " ".join(contributor.get('bf:label'))
                if i < len(work[agent])-1:
                    output += ","
    return output
