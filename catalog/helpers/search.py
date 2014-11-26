"""
Name:        search
Purpose:     This module provides search helper functions and classes for the
             BIBFRAME Search and Display Catalog

Author:      Jeremy Nelson

Created:     2014/11/21
Copyright:   (c) Jeremy Nelson 2014
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"
__license__ = "GPLv3"

def keyword_search(es, phrase, size=25):
    """Function takes an Elastic Search instance and a phrase, returns the
    expanded result.

    Args:
        es: Elastic Search instance
        phrase: Keyword phrase to search
        size: Result size, defaults to 25
    Returns:
        dict of expanded results
    """
    output = {}
    result = es.search(q=phrase, size=size)
    return output


def resource_search(es, phrase, _type='Resource', size=25):
    """Function takes an Elastic Search instance, a Resource Type and a phrase,
    returns the expanded result.

    Args:
        es: Elastic Search instance
        phrase: Keyword phrase to search
        _type: BIBFRAME type, defaults to Resource
        size: Result size, defaults to 25

    Returns:
        dict of expanded results
    """
    result = es.search(q=phrase, doc_type=_type, size=size)