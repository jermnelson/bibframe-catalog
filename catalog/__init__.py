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
from .forms import BasicSearch
import sys
#import flask_fedora_commons

app = Flask(__name__,  instance_relative_config=True)
app.config.from_pyfile('config.py')

#repository = flask_fedora_commons.Repository(app)

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

from .views import *
