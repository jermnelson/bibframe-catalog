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
from flask import url_for
from elasticsearch import Elasticsearch
from .forms import BasicSearch
import sys

app = Flask(__name__,  instance_relative_config=True)
app.config.from_pyfile('config.py')

PREFIX = """PREFIX bf: <http://bibframe.org/vocab/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>"""

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
    return cover_url

@app.template_filter('creator')
def creator(entity):
    name = ''
    if 'bf:creator' in entity:
        name = ' '.join(
            [creator['bf:label'][0] for creator in entity['bf:creator']])
    return name

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
    if 'bf:workTitle' in entity:
        sparql = GET_TITLEVALUE_SPARQL.format(entity['bf:workTitle'][0])
        result = requests.post(
           "{}/triplestore".format(datastore_url), 
           data={"sparql": sparql})
        output += result.json()['results']['bindings'][0]['titleValue']['value']
    output += " / "
    for creator_url in entity.get('bf:creator', []):
        sparql = GET_LABEL_SPARQL.format(creator_url)
        result = requests.post(
           "{}/triplestore".format(datastore_url), 
           data={"sparql": sparql})
        for row in result.json()['results']['bindings']:
            output += row['label']['value']    
    return output

from .views import *
