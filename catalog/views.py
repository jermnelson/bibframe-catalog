__author__ = "Jeremy Nelson"
from flask import abort, jsonify, render_template, request
from .forms import BasicSearch
from . import app, es_search, __version__

@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    print("IN search phrase={}".format(phrase))
    if search_type.startswith("kw"):
        result = es_search.search(q=phrase, index='bibframe', doc_type='Instance')
    else:
        result = es_search.search(
            q=phrase,
            index='bibframe',
            doc_type='Work',
            size=50)
    for hit in result.get('hits').get('hits'):
        for key, value in hit['_source'].items():
            if key.startswith('fcrepo:uuid'):
                continue
            for i,row in enumerate(value):
                if es_search.exists(id=row, index='bibframe'):
                    hit['_source'][key][i] = es_search.get_source(id=row, index='bibframe')

    #return render_template('results.html', search_type=search_type, result=result, phrase=phrase)
    return jsonify(result)
    #return "{} phrase={}".format(search_type, phrase)

@app.route("/<entity>/<uuid>.<ext>")
@app.route("/<uuid>.<ext>", defaults={"entity": "Work", "ext": "html"})
@app.route("/<uuid>")
def resource(uuid, entity, ext='html'):
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
        #repository=repository,
        search=es_search,
        basic_search=BasicSearch(),
        version=__version__)
