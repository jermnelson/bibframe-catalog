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
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

with open(os.path.join(BASE_DIR, "VERSION")) as version:
    __version__ = version.read().strip()

import json
import rdflib
import urllib.request

from flask import abort, Flask, jsonify, render_template, redirect, request
from elasticsearch import Elasticsearch
import sys
import flask_fedora_commons

app = Flask(__name__,  instance_relative_config=True)
app.config.from_pyfile('config.py')

repository = flask_fedora_commons.Repository(app)

es_search = Elasticsearch([app.config.get("ELASTIC_SEARCH")])

@app.template_filter('bf_type')
def bibframe_type(entity):
    if 'type' in entity:
        entity_type = entity.get('type', [])
        if len(entity_type) > 0:
            return entity_type[0][3:]
    return "Unknown"

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

@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    if search_type.startswith("kw"):
        result = es_search.search(q=phrase, index='bibframe')
    else:
        result = es_search.search(
            q=phrase,
            index='bibframe',
            doc_type=search_type,
            size=50)
    for hit in result.get('hits').get('hits'):
        for key, value in hit['_source'].items():
            if key.startswith('fcrepo:uuid'):
                continue
            for i,row in enumerate(value):
                if es_search.exists(id=row, index='bibframe'):
                    hit['_source'][key][i] = es_search.get_source(id=row, index='bibframe')

    return render_template('results.html', search_type=search_type, result=result, phrase=phrase)
    #return jsonify(result)
    #return "{} phrase={}".format(search_type, phrase)

@app.route("/<uuid>.<ext>")
@app.route("/<uuid>")
def resource(uuid, ext='html'):
    """Detailed view for a single resource

    Args:
        uuid: Fedora UUID also used as ID in Elastic Search index
    """
    if es_search.exists(id=uuid, index='bibframe'):
        result = es_search.get_source(id=uuid, index='bibframe')
        for key, value in result.items():
            if key.startswith('fcrepo:uuid'):
                continue
            for i,row in enumerate(value):
                if es_search.exists(id=row, index='bibframe'):
                    result[key][i] = es_search.get_source(id=row, index='bibframe')
        #fedora_url = result.get('fcrepo:hasLocation')[0]
        #fedora_graph = rdflib.Graph().parse(fedora_url)
        related = es_search.search(q=uuid, index='bibframe')
        if ext.startswith('json'):
            #return fedora_graph.serialize(format='json-ld', indent=2).decode()
            return jsonify(result)
        return render_template(
            'detail.html',
            entity=result,
            #graph=fedora_graph,
            related=related,
            version=__version__
        )
    abort(404)


@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        repository=repository,
        search=es_search,
        version=__version__)
