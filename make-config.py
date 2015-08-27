__author__ = "Jeremy Nelson"

import argparse
import hashlib
import os
import uuid 

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "instance", "config.py")

def create_config(args):
    if os.path.exists(CONFIG_PATH):
        print("Configuration already exists")
        return
    os.mkdir(os.path.join(PROJECT_ROOT, "instance"))
    with open(CONFIG_PATH, "w+") as config:
        config.write("""SECRET_KEY="{}"\n""".format(args.secret_key))
        config.write("""ELASTIC_SEARCH="{}"\n""".format(args.es_url))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'action',
        choices=['create'],
        help='Creates Bibcat Instance Configuration')
    parser.add_argument(
        '--es_url',
        default='bf_search:9200',
        help='Elasticsearch URL, defaults to localhost:9200')
    parser.add_argument(
        '--secret_key',
        default = hashlib.sha1(os.urandom(30)).hexdigest(),
        help='Secret key, defaults to os.urandom()')
    args = parser.parse_args()
    create_config(args)
