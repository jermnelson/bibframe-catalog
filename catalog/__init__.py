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
from flask.ext.elastic import Elastic
import sys
sys.path.append("C:\\Users\\jernelson\\Development\\flask-fedora")
from flask_fedora_commons import Repository

app = Flask(__name__)
repository = Repository(app)
es_search = Elastic(app)

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
    return jsonify(result)
    #return "{} phrase={}".format(search_type, phrase)


@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        repository=repository,
        search=es_search)
