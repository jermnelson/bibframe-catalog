#!/home/jermnelson_gmail_com/bf-dev-env/bin/python
"""
Name:        runserver
Purpose:     Runs BIBFRAME Access and Discovery Catalog

Author:      Jeremy Nelson

Created:     2014/11/12
Copyright:   (c) Jeremy Nelson 2014
Licence:     GPLv3
"""
import argparse
try:
    from bibframe_catalog import app
except ImportError:
    from __init__ import app

def main(args):
    debug = args.debug or True
    app.run(host='0.0.0.0', port=8000, debug=debug)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', help='Run app in debug mode')
    args = parser.parse_args()
    main(args)
