"""
Name:        catalog package
Purpose:     The catalog package is a Flask application for the BIBFRAME
             Access and Discovery Catalog.

Author:      Jeremy Nelson

Created:     2014/11/12
Copyright:   (c) Jeremy Nelson 2014, 2015
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

es_search = Elasticsearch([app.config.get("ELASTIC_SEARCH")])
if 'DATASTORE' in app.config:
    datastore_url = "http://"
    datastore_url += ":".join([app.config['DATASTORE']['host'], 
                               str(app.config['DATASTORE']['port'])])
else:
    # Default datastore url is http://localhost:18150
    datastore_url =  "http://localhost:18150"


from .views import *
