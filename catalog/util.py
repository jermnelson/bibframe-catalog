__author__ = "Jeremy Nelson, Mike Stabilea"

import re
from werkzeug.routing import BaseConverter
from . import es_search

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]



uuidPattern = re.compile('[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89aAbB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}')

def lookupRelatedDetails(v):
    #Test the value => v to see if it is a uuid
    returnList = []
    #print('Entered lookup: ', v)
    if isinstance(v, list):
        for pUuid in v:
            #print ("pUuid: ",pUuid)   
            mUuid = uuidPattern.match(pUuid)
            if mUuid:
                #if v matches a uuid pattern then search for the item in elasticsearch
                if es_search.exists(id=pUuid, index='bibframe'):
                    uuidResult = es_search.get_source(id=pUuid, index='bibframe')
                    returnList.append(uuidResult)
    if len(returnList) > 0:
        return returnList
    else:
        return 0

def findRelatedItems(filterFld,v):
    es_dsl = {'rel_instances':{}, 'rel_works':{}, 'rel_agents':{}, 'rel_topics':{}}
    #print(filterFld)
    if "instances" in filterFld:
        print("enter Instance DSL")
        es_dsl['rel_instances'] = {
                     "query" : {
                         "filtered" : {
                             "filter" : {
                                 "term" : {
                                    filterFld['instances'] : v
                                          }
                                        }
                                      }
                                }
                 }
    if "works" in filterFld:
        es_dsl['rel_works'] = {
                     "query" : {
                                 "term" : {
                                    filterFld['works'] : v
                                          }
                                }
                 }
    if "agents" in filterFld:
        es_dsl['rel_agents'] = {
                     "query" : {
                         "filtered" : {
                             "filter" : {
                                 "term" : {
                                    filterFld['agents'] : v
                                          }
                                        }
                                      }
                                }
                 }
    if "topics" in filterFld:
        es_dsl['rel_topics'] = {
                     "query" : {
                         "filtered" : {
                             "filter" : {
                                 "term" : {
                                    filterFld['topics'] : v
                                          }
                                        }
                                      }
                                }
                 }
    result = {}
    #print("es_dsl***",es_dsl)
    for k, dsl in es_dsl.items():
        #print ("k:",k," dsl:",dsl)
        if k.replace("rel_","") in filterFld:
            #print("*** Entered search ***")
            searchResult = es_search.search(
                body=dsl, 
                index='bibframe', 
                )
            #print("searchResult*** ", searchResult)
            result = {k:searchResult['hits']['hits']}
    #print("rel items *** ",result)
    return result

def __agent_search__(phrase):
    """Agent search for suggest completion 

    Args:
        phrase -- text phrase
    """
    output = []
    es_dsl = {
        "organization-suggest": {
            "text": phrase,
                "completion": {
                    "field": "organization_suggest"

               }
        },
       "person-suggest": {
           "text": phrase,
                "completion": {
                    "field": "person_suggest"
                }

            }
     }
    result = es_search.suggest(body=es_dsl, index='bibframe')
    for suggest_type in [ "person-suggest", 'organization-suggest']:
        for hit in result.get(suggest_type)[0]['options']:
            row = {'agent': hit['text'], 
                   'uuid':  hit['payload']['id']}
            output.append(row)
    return json.dumps(output)


def __expand_instance__(instance):
    """Helper function takes a search result Instance, queries index for 
    creator and holdings information 

    Args:
        instance -- Elastic search hit result
    """
    output = dict()
    work_id = instance.get('bf:instanceOf')
    if not work_id:
        return {}
    try:
        work = es_search.get(
            id=work_id[0],  
            index='bibframe', 
            fields=['bf:creator', 
                    'bf:subject'])
    except NotFoundError:
        #! Should preform secondary ES search on work_id
        return {}
    
    if not work.get('found'):
        return {}
    creators = str()
    for creator_id in work.get('fields', {}).get('bf:creator', []):
        creator = es_search.get(
            id=creator_id, 
            index='bibframe', 
            fields=['bf:label'])
        if creator.get('found'):
            creators += ' '.join(creator.get('fields', 
                                 {}).get('bf:label'))
    if len(creators) > 0:
        output['creators'] = creators
    cover_art = __get_cover_art__(instance.get('fedora:uuid')[0])
    if cover_art:
        output['cover'] = cover_art
    items = __get_held_items__(instance.get('fedora:uuid')[0])
    output['held_items'] = []
    if len(items) > 0:
        for row in items:
            item = dict()
            for field, value in row.items():
                item[field.split(":")[1]] = value
            if not 'circulationStatus' in item:
                item['circulationStatus'] = 'Available'
            for key in ['shelfMarkLcc', 'heldBy', 'subLocation']:
                if not key in item:
                    item[key] = None 
            output['held_items'].append(item)
    return output

def __generate_sort__(sort, doc_type):
    """Generates sort DSL based on type of sort and the doc_type"""
    output = {}
    if sort.startswith("a-z"):
        order = "asc"
    elif sort.startswith("z-a"):
        order = "desc"
    #! Need routing for Category?
    output["bf:label"] = {"order": order}
    return output
