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


from flask import abort, Flask, jsonify, render_template, redirect, request
#from flask.ext.elastic import Elastic
from elasticsearch import Elasticsearch
import sys
#sys.path.append("C:\\Users\\jernelson\\Development\\flask-fedora")
from flask_fedora_commons import Repository

app = Flask(__name__)
repository = Repository(app)
#es_search = Elastic(app)
es_search = Elasticsearch()

@app.template_filter('name')
def guess_name(entity):
    """Name filter attempts to serialize a BIBFRAME entity"""
    name = ''
    if 'bf:titleValue' in entity:
        name = ','.join(entity.get('bf:titleValue'))
    if 'bf:subtitle' in entity:
        name = ','.join(entity.get('bf:subtitle'))
    elif 'bf:titleStatement' in entity:
        name = ','.join(entity.get('bf:titleStatement'))
    elif 'bf:workTitle' in entity:
        name = ','.join([guess_name(title) for title in entity.get('bf:workTitle')])
    elif 'bf:label' in entity:
        name = ','.join(entity.get('bf:label'))
    return name

@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    if search_type.startswith("Keyw"):
        result = es_search.search(q=phrase)
    else:
        result = es_search.search(
            q=phrase,
            index='bibframe',
            doc_type=search_type)
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


@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        repository=repository,
        search=es_search)
