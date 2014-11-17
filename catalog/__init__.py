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


from flask import abort, Flask, jsonify, render_template
from flask.ext.elastic import Elastic
import sys
from flask_fedora_commons import Repository

app = Flask(__name__)
repository = Repository(app)
search = Elastic(app)

@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        repository=repository,
        search=search)
