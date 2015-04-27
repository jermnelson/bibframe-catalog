from flask_wtf import Form
from wtforms import StringField

class BasicSearch(Form):
    query = StringField('queryString')
