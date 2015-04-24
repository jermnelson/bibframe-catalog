"""
Name:        catalog package
Purpose:     The catalog package is a Flask application for the BIBFRAME
             Access and Discovery Catalog.

Author:      Jeremy Nelson

Created:     2014/11/12
Copyright:   (c) Jeremy Nelson 2014
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

from flask import abort, Flask, jsonify, render_template, redirect, request
from flask import render_template, url_for
from elasticsearch import Elasticsearch
from .forms import BasicSearch
import sys

app = Flask(__name__,  instance_relative_config=True)
app.config.from_pyfile('config.py')

PREFIX = """PREFIX bf: <http://bibframe.org/vocab/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>"""

GET_CREATORS_INSTANCE_SPARQL = """{}
SELECT DISTINCT ?creator_name
WHERE {{{{
   <{{}}> bf:instanceOf ?work .
   ?work bf:creator ?creator .
   ?creator bf:label ?creator_name .
}}}}""".format(PREFIX)

GET_CREATORS_WORK_SPARQL = """{}
SELECT DISTINCT ?creator_name
WHERE {{{{
  <{{}}>  bf:creator ?creator .
   ?creator bf:label ?creator_name .
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

es_search = Elasticsearch([app.config.get("ELASTIC_SEARCH")])
if 'DATASTORE' in app.config:
    datastore_url = "http://"
    datastore_url += ":".join([app.config['DATASTORE']['host'], 
                               str(app.config['DATASTORE']['port'])])
else:
    # Default datastore url is http://localhost:18150
    datastore_url =  "http://localhost:18150"

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
    if 'bf:workTitle' in entity:
        sparql = GET_WORK_COVER_SPARQL.format(entity['fcrepo:hasLocation'][0])
    else:
        sparql = GET_INSTANCE_COVER_SPARQL.format(entity['fcrepo:hasLocation'][0])       
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
        name = ' '.join(
            [creator['bf:label'][0] for creator in entity['bf:creator']])
    return name

@app.template_filter('held_items')
def held_items(entity):
    output = str()
    fedora_url = entity['fcrepo:hasLocation'][0]
    if 'bf:workTitle' in entity:
        sparql = WORK_HELD_ITEMS_SPARQL.format(fedora_url)
    else:
        sparql = HELD_ITEMS_SPARQL.format(fedora_url)
    result = requests.post(
       "{}/triplestore".format(datastore_url), 
       data={"sparql": sparql})
    if result.status_code < 400:
        results = result.json()['results']
        for row in results['bindings']:
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
                    output += render_template(
                        'snippets/held-item.html', 
                        item=held_item_result.json()['results']['bindings'][0])
                else:
                    output = "Cannot find {} for {}".format(uuid, fedora_url)
    return output


        
        


@app.template_filter('name')
def guess_name(entity):
    """Name filter attempts to serialize a BIBFRAME entity"""
    name = ''
    if 'bf:titleValue' in entity:
        name = ','.join(entity.get('bf:titleValue'))
    if 'bf:subtitle' in entity:
        name = ','.join(entity.get('bf:subtitle'))
    elif 'bf:title' in entity:
        name = ','.join(entity.get('bf:title'))
    elif 'bf:titleStatement' in entity:
        name = ','.join(entity.get('bf:titleStatement'))
    elif 'bf:workTitle' in entity:
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
        if 'fcrepo:uuid' in entity:
            name = ','.join(entity.get('fcrepo:uuid'))
    return name

@app.template_filter('title_author')
def generate_title_author(entity):
    """Template filter takes either a bf:Work or bf:Instance and returns a 
    Item title/Author formated string

    Args:
        entity -- Dictionary of entity info
    """
    output = str()
    creators = []
    if type(entity['fcrepo:hasLocation'][0]) == str:
        entity_url = entity['fcrepo:hasLocation'][0]
    else:
        entity_url = entity['fcrepo:hasLocation'][0]['value']
    if 'bf:workTitle' in entity:
        sparql = GET_TITLEVALUE_SPARQL.format(entity['bf:workTitle'][0])
        result = requests.post(
           "{}/triplestore".format(datastore_url), 
           data={"sparql": sparql})
        output += result.json()['results']['bindings'][0]['titleValue']['value']
        creator_sparql = GET_CREATORS_WORK_SPARQL.format(entity_url)
    if 'bf:titleStatement' in entity:
        output += ",".join(entity['bf:titleStatement'])
        creator_sparql = GET_CREATORS_INSTANCE_SPARQL.format(entity_url)
    creator_result = requests.post(
        "{}/triplestore".format(datastore_url),
        data={"sparql": creator_sparql})
    if creator_result.status_code < 400:
        results = creator_result.json()['results']
        for row in results['bindings']:
            if 'value' in row:
                creators.append(row.get('value'))
            elif 'creator_name' in row:
                creators.append(row.get('creator_name')['value'])
    output += " / {}".format(' '.join(creators))
    return output

from .views import *
