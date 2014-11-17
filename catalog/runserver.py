#!/home/jermnelson_gmail_com/bf-dev-env/bin/python
"""
Name:        runserver
Purpose:     Runs BIBFRAME Access and Discovery Catalog

Author:      Jeremy Nelson

Created:     2014/11/12
Copyright:   (c) Jeremy Nelson 2014
Licence:     GPLv3
"""
try:
    from bibframe_catalog import app
except ImportError:
    from __init__ import app

def main():
    app.run(host='0.0.0.0', port=80, debug=True)

if __name__ == '__main__':
    main()
