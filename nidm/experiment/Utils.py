import os,sys


from rdflib import Namespace, Literal,RDFS
from rdflib.namespace import XSD
from rdflib.resource import Resource
from urllib.parse import urlparse, urlsplit
from rdflib import Graph, RDF, URIRef, util
from rdflib.namespace import split_uri
import validators
import prov.model as pm
from prov.model import QualifiedName
from prov.model import Namespace as provNamespace
import requests
from fuzzywuzzy import fuzz
import json
from github import Github, GithubException
import getpass

#NIDM imports
from ..core import Constants
from ..core.Constants import DD

from .Project import Project
from .Session import Session
from .Acquisition import Acquisition
from .MRAcquisition import MRAcquisition
from .AcquisitionObject import AcquisitionObject
from .AssessmentAcquisition import AssessmentAcquisition
from .AssessmentObject import AssessmentObject
from .MRObject import MRObject
from .DataElement import DataElement
from .Derivative import Derivative
from .DerivativeObject import DerivativeObject
from .Core import getUUID
from .Core import Core
from prov.model import PROV
import logging

#Interlex stuff
import ontquery as oq



def read_nidm(nidmDoc):
    """
        Loads nidmDoc file into NIDM-Experiment structures and returns objects

        :nidmDoc: a valid RDF NIDM-experiment document (deserialization formats supported by RDFLib)

        :return: NIDM Project

    """

    from ..experiment.Project import Project
    from ..experiment.Session import Session


    # read RDF file into temporary graph
    rdf_graph = Graph()
    rdf_graph_parse = rdf_graph.parse(nidmDoc,format=util.guess_format(nidmDoc))


    # Query graph for project metadata and create project level objects
    # Get subject URI for project
    proj_id=None
    for s in rdf_graph_parse.subjects(predicate=RDF.type,object=URIRef(Constants.NIDM_PROJECT.uri)):
        #print(s)
        proj_id=s
        #Split subject URI into namespace, term
        nm,project_uuid = split_uri(proj_id)
        #Cycle through Project metadata adding to prov graph
        add_metadata_for_subject (rdf_graph_parse,proj_id,project.graph.namespaces,project)


    if proj_id is None:
        print("Warning!  NIDM document does not have a project object!  A new empty project object will be created")
        # print("Error reading NIDM-Exp Document %s, Must have Project Object" % nidmDoc)
        # exit(1)
        #create empty prov graph
        project_uuid = getUUID()


    #print("project uuid=%s" %project_uuid)

    #create empty prov graph
    project = Project(empty_graph=True,uuid=project_uuid)

    #add namespaces to prov graph
    for name, namespace in rdf_graph_parse.namespaces():
        #skip these default namespaces in prov Document
        if (name != 'prov') and (name != 'xsd') and (name != 'nidm'):
            project.graph.add_namespace(name, namespace)



    # The following loops are overlaying the tuples in the RDF file on top of the typical NIDM-experiment
    # hierarchy.
    #
    # In work with ReproNim it's possible that brain volume data are contained in the files and don't have
    # a typical NIDM-Experiment structure project->sessions->acquisition activities -> acquisition entities. In this
    # case an empty project will be created and data element and/or derived data (brain volume) elements will be
    # attached to the empty project.
    #



    #Query graph for sessions, instantiate session objects, and add to project._session list
    #Get subject URI for sessions
    for s in rdf_graph_parse.subjects(predicate=RDF.type,object=URIRef(Constants.NIDM_SESSION.uri)):
        #print("session: %s" % s)

        #Split subject URI for session into namespace, uuid
        nm,session_uuid = split_uri(s)

        #print("session uuid= %s" %session_uuid)

        #instantiate session with this uuid
        session = Session(project=project, uuid=session_uuid)

        #add session to project
        project.add_sessions(session)


        #now get remaining metadata in session object and add to session
        #Cycle through Session metadata adding to prov graph
        add_metadata_for_subject (rdf_graph_parse,s,project.graph.namespaces,session)

        #Query graph for acquistions dct:isPartOf the session
        for acq in rdf_graph_parse.subjects(predicate=Constants.DCT['isPartOf'],object=s):
            #Split subject URI for session into namespace, uuid
            nm,acq_uuid = split_uri(acq)
            #print("acquisition uuid: %s" %acq_uuid)

            #query for whether this is an AssessmentAcquisition of other Acquisition, etc.
            for rdf_type in  rdf_graph_parse.objects(subject=acq, predicate=RDF.type):
                #if this is an acquisition activity, which kind?
                if str(rdf_type) == Constants.NIDM_ACQUISITION_ACTIVITY.uri:
                    #if this is an MR acquisition then it's generated entity will have a predicate
                    # nidm:AcquisitionModality whose value is nidm:MagneticResonanceImaging
                    #first find the entity generated by this acquisition activity
                    for acq_obj in rdf_graph_parse.subjects(predicate=Constants.PROV["wasGeneratedBy"],object=acq):
                        #Split subject URI for session into namespace, uuid
                        nm,acq_obj_uuid = split_uri(acq_obj)
                        #print("acquisition object uuid: %s" %acq_obj_uuid)

                        #query for whether this is an MRI acquisition by way of looking at the generated entity and determining
                        #if it has the tuple [uuid Constants.NIDM_ACQUISITION_MODALITY Constants.NIDM_MRI]
                        if (acq_obj,URIRef(Constants.NIDM_ACQUISITION_MODALITY._uri),URIRef(Constants.NIDM_MRI._uri)) in rdf_graph:

                            #check whether this acquisition activity has already been instantiated (maybe if there are multiple acquisition
                            #entities prov:wasGeneratedBy the acquisition
                            if not session.acquisition_exist(acq_uuid):
                                acquisition=MRAcquisition(session=session,uuid=acq_uuid)
                                session.add_acquisition(acquisition)
                                #Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject (rdf_graph_parse,acq,project.graph.namespaces,acquisition)


                            #and add acquisition object
                            acquisition_obj=MRObject(acquisition=acquisition,uuid=acq_obj_uuid)
                            acquisition.add_acquisition_object(acquisition_obj)
                            #Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(rdf_graph_parse,acq_obj,project.graph.namespaces,acquisition_obj)

                            #MRI acquisitions may have an associated stimulus file so let's see if there is an entity
                            #prov:wasAttributedTo this acquisition_obj
                            for assoc_acq in rdf_graph_parse.subjects(predicate=Constants.PROV["wasAttributedTo"],object=acq_obj):
                                #get rdf:type of this entity and check if it's a nidm:StimulusResponseFile or not
                                #if rdf_graph_parse.triples((assoc_acq, RDF.type, URIRef("http://purl.org/nidash/nidm#StimulusResponseFile"))):
                                if (assoc_acq,RDF.type,URIRef(Constants.NIDM_MRI_BOLD_EVENTS._uri)) in rdf_graph:
                                    #Split subject URI for associated acquisition entity for nidm:StimulusResponseFile into namespace, uuid
                                    nm,assoc_acq_uuid = split_uri(assoc_acq)
                                    #print("associated acquisition object (stimulus file) uuid: %s" % assoc_acq_uuid)
                                    #if so then add this entity and associate it with acquisition activity and MRI entity
                                    events_obj = AcquisitionObject(acquisition=acquisition,uuid=assoc_acq_uuid)
                                    #link it to appropriate MR acquisition entity
                                    events_obj.wasAttributedTo(acquisition_obj)
                                    #cycle through rest of metadata
                                    add_metadata_for_subject(rdf_graph_parse,assoc_acq,project.graph.namespaces,events_obj)



                        #query whether this is an assessment acquisition by way of looking at the generated entity and determining
                        #if it has the rdf:type Constants.NIDM_ASSESSMENT_ENTITY
                        #for acq_modality in rdf_graph_parse.objects(subject=acq_obj,predicate=RDF.type):
                        if (acq_obj, RDF.type, URIRef(Constants.NIDM_ASSESSMENT_ENTITY._uri)) in rdf_graph:

                            #if str(acq_modality) == Constants.NIDM_ASSESSMENT_ENTITY._uri:
                            acquisition=AssessmentAcquisition(session=session,uuid=acq_uuid)
                            if not session.acquisition_exist(acq_uuid):
                                session.add_acquisition(acquisition)
                                 #Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject (rdf_graph_parse,acq,project.graph.namespaces,acquisition)

                            #and add acquisition object
                            acquisition_obj=AssessmentObject(acquisition=acquisition,uuid=acq_obj_uuid)
                            acquisition.add_acquisition_object(acquisition_obj)
                            #Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(rdf_graph_parse,acq_obj,project.graph.namespaces,acquisition_obj)
                        elif (acq_obj, RDF.type, URIRef(Constants.NIDM_MRI_BOLD_EVENTS._uri)) in rdf_graph:
                            #If this is a stimulus response file
                            #elif str(acq_modality) == Constants.NIDM_MRI_BOLD_EVENTS:
                            acquisition=Acquisition(session=session,uuid=acq_uuid)
                            if not session.acquisition_exist(acq_uuid):
                                session.add_acquisition(acquisition)
                                #Cycle through remaining metadata for acquisition activity and add attributes
                                add_metadata_for_subject (rdf_graph_parse,acq,project.graph.namespaces,acquisition)

                            #and add acquisition object
                            acquisition_obj=AcquisitionObject(acquisition=acquisition,uuid=acq_obj_uuid)
                            acquisition.add_acquisition_object(acquisition_obj)
                            #Cycle through remaining metadata for acquisition entity and add attributes
                            add_metadata_for_subject(rdf_graph_parse,acq_obj,project.graph.namespaces,acquisition_obj)



                #This skips rdf_type PROV['Activity']
                else:
                    continue

    #Query graph for DataElements and instantiate a DataElement class and add them to the project
    query='''
        select distinct ?uuid
            where {

                ?uuid a ?DataElements

                filter( regex(str(?DataElements), "DataElement" ))

            }'''

    qres = rdf_graph_parse.query(query)
    for row in qres:
        # instantiate a data element class assigning it the existing uuid
        de = DataElement(project=project,uuid=row['uuid'])
        # get the rest of the attributes for this data element and store
        add_metadata_for_subject(rdf_graph_parse,row['uuid'],project.graph.namespaces,de)

        # Query graph for prov:Entity that contains a reference to the data element UUID then get activity that generated
        # this entity and instantiate both Derivative and DerivativeObject classes and add in additional tuples
        for subj,obj in rdf_graph_parse.subject_objects(predicate=row['uuid']):
            # Query for prov:Activity that this subj was generated by
            for act in rdf_graph_parse.objects(predicate=PROV['wasGeneratedBy'], subject=subj):
                # check if derivative exists
                if not act in project.derivatives""
                    # instantiate a Derivative for this activity
                    der = Derivative(project=project,uuid=act)
                    # add additional tuples
                    add_metadata_for_subject(rdf_graph_parse,act,project.graph.namespaces,der)
            # check if derivative object exists
            if not subj in der.get_derivative_objects():
                #instantiate DerivativeObject for this entity
                der_obj = DerivativeObject(derivative=der,uuid=subj)
                # Now add additional tuples for subj
                add_metadata_for_subject(rdf_graph_parse,subj,project.graph.namespaces,der_obj)




    return(project)


def get_RDFliteral_type(rdf_literal):
    if (rdf_literal.datatype == XSD["int"]):
        return (int(rdf_literal))
    elif ((rdf_literal.datatype == XSD["float"]) or (rdf_literal.datatype == XSD["double"])):
        return(float(rdf_literal))
    else:
        return (str(rdf_literal))

def add_metadata_for_subject (rdf_graph,subject_uri,namespaces,nidm_obj):
    """
    Cycles through triples for a particular subject and adds them to the nidm_obj

    :param rdf_graph: RDF graph object
    :param subject_uri: URI of subject to query for additional metadata
    :param namespaces: Namespaces in NIDM document
    :param nidm_obj: NIDM object to add metadata
    :return: None

    """
    #Cycle through remaining metadata and add attributes
    for predicate, objects in rdf_graph.predicate_objects(subject=subject_uri):
        #if find qualified association
        if predicate == URIRef(Constants.PROV['qualifiedAssociation']):
            #need to get associated prov:Agent uri, add person information to graph
            for agent in rdf_graph.objects(subject=subject_uri, predicate=Constants.PROV['wasAssociatedWith']):
                #add person to graph and also add all metadata
                person = nidm_obj.add_person(uuid=agent)
                #now add metadata for person
                add_metadata_for_subject(rdf_graph=rdf_graph,subject_uri=agent,namespaces=namespaces,nidm_obj=person)

            #get role information
            for bnode in rdf_graph.objects(subject=subject_uri,predicate=Constants.PROV['qualifiedAssociation']):
                #for bnode, query for object which is role?  How?
                #term.BNode.__dict__()

                #create temporary resource for this bnode
                r = Resource(rdf_graph,bnode)
                #get the object for this bnode with predicate Constants.PROV['hadRole']
                for r_obj in r.objects(predicate=Constants.PROV['hadRole']):
                    #create qualified names for objects
                    obj_nm,obj_term = split_uri(r_obj._identifier)
                    for uris in namespaces:
                        if uris.uri == URIRef(obj_nm):
                            #create qualified association in graph
                            nidm_obj.add_qualified_association(person=person,role=pm.QualifiedName(uris,obj_term))

        else:
            if validators.url(objects):
                #create qualified names for objects
                obj_nm,obj_term = split_uri(objects)
                for uris in namespaces:
                    if uris.uri == URIRef(obj_nm):
                        #prefix = uris.prefix
                        nidm_obj.add_attributes({predicate : pm.QualifiedName(uris,obj_term)})
            else:

                nidm_obj.add_attributes({predicate : get_RDFliteral_type(objects)})


def QuerySciCrunchElasticSearch(key,query_string,type='cde', anscestors=True):
    '''
    This function will perform an elastic search in SciCrunch on the [query_string] using API [key] and return the json package.
    :param key: API key from sci crunch
    :param query_string: arbitrary string to search for terms
    :param type: default is 'CDE'.  Acceptible values are 'cde' or 'pde'.
    :return: json document of results form elastic search
    '''

    #Note, once Jeff Grethe, et al. give us the query to get the ReproNim "tagged" ancestors query we'd do that query first and replace
    #the "ancestors.ilx" parameter in the query data package below with new interlex IDs...
    #this allows interlex developers to dynamicall change the ancestor terms that are part of the ReproNim term trove and have this
    #query use that new information....


    #Add check for internet connnection, if not then skip this query...return empty dictionary


    headers = {
        'Content-Type': 'application/json',
    }

    params = (
        ('key', key),
    )
    if type is 'cde':
        if anscestors:
            data = '\n{\n  "query": {\n    "bool": {\n       "must" : [\n       {  "term" : { "type" : "cde" } },\n       { "terms" : { "ancestors.ilx" : ["ilx_0115066" , "ilx_0103210", "ilx_0115072", "ilx_0115070"] } },\n       { "multi_match" : {\n         "query":    "%s", \n         "fields": [ "label", "definition" ] \n       } }\n]\n    }\n  }\n}\n' %query_string
        else:
            data = '\n{\n  "query": {\n    "bool": {\n       "must" : [\n       {  "term" : { "type" : "cde" } },\n             { "multi_match" : {\n         "query":    "%s", \n         "fields": [ "label", "definition" ] \n       } }\n]\n    }\n  }\n}\n' %query_string
    elif type is 'pde':
        if anscestors:
            data = '\n{\n  "query": {\n    "bool": {\n       "must" : [\n       {  "term" : { "type" : "pde" } },\n       { "terms" : { "ancestors.ilx" : ["ilx_0115066" , "ilx_0103210", "ilx_0115072", "ilx_0115070"] } },\n       { "multi_match" : {\n         "query":    "%s", \n         "fields": [ "label", "definition" ] \n       } }\n]\n    }\n  }\n}\n' %query_string
        else:
            data = '\n{\n  "query": {\n    "bool": {\n       "must" : [\n       {  "term" : { "type" : "pde" } },\n              { "multi_match" : {\n         "query":    "%s", \n         "fields": [ "label", "definition" ] \n       } }\n]\n    }\n  }\n}\n' %query_string
    elif type is 'fde':
        if anscestors:
            data = '\n{\n  "query": {\n    "bool": {\n       "must" : [\n       {  "term" : { "type" : "fde" } },\n       { "terms" : { "ancestors.ilx" : ["ilx_0115066" , "ilx_0103210", "ilx_0115072", "ilx_0115070"] } },\n       { "multi_match" : {\n         "query":    "%s", \n         "fields": [ "label", "definition" ] \n       } }\n]\n    }\n  }\n}\n' %query_string
        else:
            data = '\n{\n  "query": {\n    "bool": {\n       "must" : [\n       {  "term" : { "type" : "fde" } },\n              { "multi_match" : {\n         "query":    "%s", \n         "fields": [ "label", "definition" ] \n       } }\n]\n    }\n  }\n}\n' %query_string

    else:
        print("ERROR: Valid types for SciCrunch query are 'cde','pde', or 'fde'.  You set type: %s " %type)
        print("ERROR: in function Utils.py/QuerySciCrunchElasticSearch")
        exit(1)

    response = requests.post('https://scicrunch.org/api/1/elastic-ilx/interlex/term/_search#', headers=headers, params=params, data=data)

    return json.loads(response.text)

def GetNIDMTermsFromSciCrunch(key,query_string,type='cde', ancestor=True):
    '''
    Helper function which issues elastic search query of SciCrunch using QuerySciCrunchElasticSearch function and returns terms list
    with label, definition, and preferred URLs in dictionary
    :param key: API key from sci crunch
    :param query_string: arbitrary string to search for terms
    :param type: should be 'cde' or 'pde' for the moment
    :param ancestor: Boolean flag to tell Interlex elastic search to use ancestors (i.e. tagged terms) or not
    :return: dictionary with keys 'ilx','label','definition','preferred_url'
    '''

    json_data = QuerySciCrunchElasticSearch(key, query_string,type,ancestor)
    results={}
    #check if query was successful
    if json_data['timed_out'] != True:
        #example printing term label, definition, and preferred URL
        for term in json_data['hits']['hits']:
            #find preferred URL
            results[term['_source']['ilx']] = {}
            for items in term['_source']['existing_ids']:
                if items['preferred']=='1':
                    results[term['_source']['ilx']]['preferred_url']=items['iri']
                results[term['_source']['ilx']]['label'] = term['_source']['label']
                results[term['_source']['ilx']]['definition'] = term['_source']['definition']

    return results

def InitializeInterlexRemote(key):
    '''
    This function initializes a connection to Interlex for use in adding personal data elements
    :param key: Interlex API key
    :return: interlex object
    '''
    endpoint = "https://scicrunch.org/api/1/"
    # beta endpoint for testing
    # endpoint = "https://beta.scicrunch.org/api/1/"

    InterLexRemote = oq.plugin.get('InterLex')
    ilx_cli = InterLexRemote(api_key=key, apiEndpoint=endpoint)
    try:
        ilx_cli.setup()
    except Exception as e:
        print("error initializing InterLex connection...")
        print("you will not be able to add new personal data elements.")

    return ilx_cli

def AddPDEToInterlex(ilx_obj,label,definition,units, min, max, datatype, categorymappings=None):
    '''
    This function will add the PDE (personal data elements) to Interlex using the Interlex ontquery API.  
    
    :param interlex_obj: Object created using ontquery.plugin.get() function (see: https://github.com/tgbugs/ontquery) 
    :param label: Label for term entity being created
    :param definition: Definition for term entity being created
    :param comment: Comments to help understand the object
    :return: response from Interlex 
    '''

    # Interlex uris for predicates, tmp_ prefix dor beta endpoing, ilx_ for production
    prefix='ilx'
    # for beta testing
    # prefix = 'tmp'
    uri_datatype = 'http://uri.interlex.org/base/' + prefix + '_0382131'
    uri_units = 'http://uri.interlex.org/base/' + prefix + '_0382130'
    uri_min = 'http://uri.interlex.org/base/' + prefix + '_0382133'
    uri_max = 'http://uri.interlex.org/base/' + prefix + '_0382132'
    uri_category = 'http://uri.interlex.org/base/' + prefix + '_0382129'


    # return ilx_obj.add_pde(label=label, definition=definition, comment=comment, type='pde')
    if categorymappings is not None:
        tmp = ilx_obj.add_pde(label=label, definition=definition, predicates = {
            uri_datatype : datatype,
            uri_units : units,
            uri_min : min,
            uri_max : max,
            uri_category : categorymappings
        })
    else:
        tmp = ilx_obj.add_pde(label=label, definition=definition, predicates = {

            uri_datatype : datatype,
            uri_units : units,
            uri_min : min,
            uri_max : max
        })
    return tmp


def load_nidm_owl_files():
    '''
    This function loads the NIDM-experiment related OWL files and imports, creates a union graph and returns it.
    :return: graph of all OWL files and imports from PyNIDM experiment
    '''
    #load nidm-experiment.owl file and all imports directly
    #create empty graph
    union_graph = Graph()
    #check if there is an internet connection, if so load directly from https://github.com/incf-nidash/nidm-specs/tree/master/nidm/nidm-experiment/terms and
    # https://github.com/incf-nidash/nidm-specs/tree/master/nidm/nidm-experiment/imports
    basepath=os.path.dirname(os.path.dirname(__file__))
    terms_path = os.path.join(basepath,"terms")
    imports_path=os.path.join(basepath,"terms","imports")

    imports=[
            "crypto_import.ttl",
            "dc_import.ttl",
            "iao_import.ttl",
            "nfo_import.ttl",
            "nlx_import.ttl",
            "obi_import.ttl",
            "ontoneurolog_instruments_import.ttl",
            "pato_import.ttl",
            "prv_import.ttl",
            "qibo_import.ttl",
            "sio_import.ttl",
            "stato_import.ttl"
    ]

    #load each import
    for resource in imports:
        temp_graph = Graph()
        try:

            temp_graph.parse(os.path.join(imports_path,resource),format="turtle")
            union_graph=union_graph+temp_graph

        except Exception:
            logging.info("Error opening %s import file..continuing" %os.path.join(imports_path,resource))
            continue

    owls=[
            "https://raw.githubusercontent.com/incf-nidash/nidm-specs/master/nidm/nidm-experiment/terms/nidm-experiment.owl"
    ]

    #load each owl file
    for resource in owls:
        temp_graph = Graph()
        try:
            temp_graph.parse(location=resource, format="turtle")
            union_graph=union_graph+temp_graph
        except Exception:
            logging.info("Error opening %s owl file..continuing" %os.path.join(terms_path,resource))
            continue


    return union_graph



def fuzzy_match_terms_from_graph(graph,query_string):
    '''
    This function performs a fuzzy match of the constants in Constants.py list nidm_experiment_terms for term constants matching the query....i
    ideally this should really be searching the OWL file when it's ready
    :param query_string: string to query
    :return: dictionary whose key is the NIDM constant and value is the match score to the query
    '''


    match_scores={}

    #search for labels rdfs:label and obo:IAO_0000115 (description) for each rdf:type owl:Class
    for term in graph.subjects(predicate=RDF.type, object=Constants.OWL["Class"]):
        for label in graph.objects(subject=term, predicate=Constants.RDFS['label']):
            match_scores[term] = {}
            match_scores[term]['score'] = fuzz.token_sort_ratio(query_string,label)
            match_scores[term]['label'] = label
            match_scores[term]['url'] = term
            match_scores[term]['definition']=None
            for description in graph.objects(subject=term,predicate=Constants.OBO["IAO_0000115"]):
                match_scores[term]['definition'] =description

    #for term in owl_graph.classes():
    #    print(term.get_properties())
    return match_scores


def authenticate_github(authed=None,credentials=None):
    '''
    This function will hangle GitHub authentication with or without a token.  If the parameter authed is defined the
    function will check whether it's an active/valide authentication object.  If not, and username/token is supplied then
    an authentication object will be created.  If username + token is not supplied then the user will be prompted to input
    the information.
    :param authed: Optional authenticaion object from PyGithub
    :param credentials: Optional GitHub credential list username,password or username,token
    :return: GitHub authentication object or None if unsuccessful

    '''

    print("GitHub authentication...")
    indx=1
    maxtry=5
    while indx < maxtry:
        if (len(credentials)>= 2):
            #authenticate with token
            g=Github(credentials[0],credentials[1])
        elif (len(credentials)==1):
            pw = getpass.getpass("Please enter your GitHub password: ")
            g=Github(credentials[0],pw)
        else:
            username = input("Please enter your GitHub user name: ")
            pw = getpass.getpass("Please enter your GitHub password: ")
            #try to logging into GitHub
            g=Github(username,pw)

        authed=g.get_user()
        try:
            #check we're logged in by checking that we can access the public repos list
            repo=authed.public_repos
            logging.info("Github authentication successful")
            new_term=False
            break
        except GithubException as e:
            logging.info("error logging into your github account, please try again...")
            indx=indx+1

    if (indx == maxtry):
        logging.critical("GitHub authentication failed.  Check your username / password / token and try again")
        return None
    else:
        return authed

def getSubjIDColumn(column_to_terms,df):
    '''
    This function returns column number from CSV file that matches subjid.  If it can't automatically
    detect it based on the Constants.NIDM_SUBJECTID term (i.e. if the user selected a different term
    to annotate subject ID then it asks the user.
    :param column_to_terms: json variable->term mapping dictionary made by nidm.experiment.Utils.map_variables_to_terms
    :param df: dataframe of CSV file with tabular data to convert to RDF.
    :return: subject ID column number in CSV dataframe
    '''

    #look at column_to_terms dictionary for NIDM URL for subject id  (Constants.NIDM_SUBJECTID)
    id_field=None
    for key, value in column_to_terms.items():
        if Constants.NIDM_SUBJECTID._str == column_to_terms[key]['label']:
            id_field=key

    #if we couldn't find a subject ID field in column_to_terms, ask user
    if id_field is None:
        option=1
        for column in df.columns:
            print("%d: %s" %(option,column))
            option=option+1
        selection=input("Please select the subject ID field from the list above: ")
        id_field=df.columns[int(selection)-1]
    return id_field

def map_variables_to_terms(df,apikey,directory, assessment_name, output_file=None,json_file=None,owl_file='nidm'):
    '''

    :param df: data frame with first row containing variable names
    :param assessment_name: Name for the assessment to use in storing JSON mapping dictionary keys
    :param json_file: optional json document with variable names as keys and minimal fields "definition","label","url"
    :param apikey: scicrunch key for rest API queries
    :param output_file: output filename to save variable-> term mappings
    :param directory: if output_file parameter is set to None then use this directory to store default JSON mapping file
    if doing variable->term mappings
    :return:return dictionary mapping variable names (i.e. columns) to terms
    '''
    # minimum match score for fuzzy matching NIDM terms
    min_match_score = 50

    # dictionary mapping column name to preferred term
    column_to_terms = {}

    # flag for whether a new term has been defined, on first occurance ask for namespace URL
    new_term = True

    # check if user supplied a JSON file and we already know a mapping for this column
    if json_file is not None:
        # load file and

        with open(json_file,'r+') as f:
            json_map = json.load(f)

    # if no JSON mapping file was specified then create a default one for variable-term mappings

    # create a json_file filename from the output file filename
    if output_file is None:
        output_file = os.path.join(directory, "nidm_pde_terms.json")
    # remove ".ttl" extension
    # else:
    #    output_file = os.path.join(os.path.dirname(output_file), os.path.splitext(os.path.basename(output_file))[0]
    #                               + ".json")

    # initialize InterLex connection
    try:
        ilx_obj = InitializeInterlexRemote(key=apikey)
    except Exception as e:
        print("ERROR: initializing InterLex connection...")
        print("You will not be able to add new personal data elements.")
        ilx_obj=None
    # load NIDM OWL files if user requested it
    if owl_file=='nidm':
        try:
            nidm_owl_graph = load_nidm_owl_files()
        except Exception as e:
            print()
            print("ERROR: initializing internet connection to NIDM OWL files...")
            print("You will not be able to select terms from NIDM OWL files.")
            nidm_owl_graph = None

    # else load user-supplied owl file
    elif owl_file is not None:
        nidm_owl_graph = Graph()
        nidm_owl_graph.parse(location=owl_file)

    # iterate over columns
    for column in df.columns:

        # search term for elastic search
        search_term=str(column)
        # loop variable for terms markup
        go_loop=True
        # set up a dictionary entry for this column
        current_tuple = str(DD(source=assessment_name, variable=column))
        column_to_terms[current_tuple] = {}

        # if we loaded a json file with existing mappings
        try:
            json_map

            # check for column in json file
            json_key = [key for key in json_map if column in key]
            if (json_map is not None) and (len(json_key)>0):

                column_to_terms[current_tuple]['label'] = json_map[json_key[0]]['label']
                column_to_terms[current_tuple]['definition'] = json_map[json_key[0]]['definition']
                column_to_terms[current_tuple]['url'] = json_map[json_key[0]]['url']
                # column_to_terms[current_tuple]['variable'] = json_map[json_key[0]]['variable']

                print("Column %s already mapped to terms in user supplied JSON mapping file" %column)
                print("Label: %s" %column_to_terms[current_tuple]['label'])
                print("Definition: %s" %column_to_terms[current_tuple]['definition'])
                print("Url: %s" %column_to_terms[current_tuple]['url'])
                # print("Variable: %s" %column_to_terms[current_tuple]['variable'])

                if 'description' in json_map[json_key[0]]:
                    column_to_terms[current_tuple]['description'] = json_map[json_key[0]]['description']
                    print("Description: %s" %column_to_terms[current_tuple]['description'])

                if 'levels' in json_map[json_key[0]]:
                    column_to_terms[current_tuple]['levels'] = json_map[json_key[0]]['levels']
                    print("Levels: %s" %column_to_terms[current_tuple]['levels'])

                print("---------------------------------------------------------------------------------------")
                continue
        except NameError:
            print("json mapping file not supplied")
        # flag for whether to use ancestors in Interlex query or not
        ancestor = True



        #Before we run anything here if both InterLex and NIDM OWL file access is down we should just alert
        #the user and return cause we're not going to be able to do really anything
        if (nidm_owl_graph is None) and (ilx_obj is None):
            print("Both InterLex and NIDM OWL file access is not possible")
            print("Check your internet connection and try again or supply a JSON mapping file with all the variables "
                  "mapped to terms")
            return column_to_terms


        #added for an automatic mapping of participant_id, subject_id, and variants
        if ( ("participant_id" in search_term.lower()) or ("subject_id" in search_term.lower()) or
            (("participant" in search_term.lower()) and ("id" in search_term.lower())) or
            (("subject" in search_term.lower()) and ("id" in search_term.lower())) ):

            # map this term to Constants.NIDM_SUBJECTID
            # since our subject ids are statically mapped to the Constants.NIDM_SUBJECTID we're creating a new
            # named tuple for this json map entry as it's not the same source as the rest of the data frame which
            # comes from the 'assessment_name' function parameter.
            subjid_tuple = str(DD(source='ndar', variable=search_term))
            column_to_terms[subjid_tuple] = {}
            column_to_terms[subjid_tuple]['label'] = search_term
            column_to_terms[subjid_tuple]['definition'] = "subject/participant identifier"
            column_to_terms[subjid_tuple]['url'] = Constants.NIDM_SUBJECTID.uri
            # column_to_terms[subjid_tuple]['variable'] = str(column)

            # delete temporary current_tuple key for this variable as it has been statically mapped to NIDM_SUBJECT
            del column_to_terms[current_tuple]

            print("Variable %s automatically mapped to participant/subject idenfier" %search_term)
            print("Label: %s" %column_to_terms[subjid_tuple]['label'])
            print("Definition: %s" %column_to_terms[subjid_tuple]['definition'])
            print("Url: %s" %column_to_terms[subjid_tuple]['url'])
            print("---------------------------------------------------------------------------------------")
            # don't need to continue while loop because we've defined a term for this CSV column
            go_loop=False
            continue

        # loop to find a term definition by iteratively searching InterLex...or defining your own
        while go_loop:
            # variable for numbering options returned from elastic search
            option = 1

            print()
            print("Query String: %s " %search_term)


            if ilx_obj is not None:
                # for each column name, query Interlex for possible matches
                search_result = GetNIDMTermsFromSciCrunch(apikey, search_term, type='fde', ancestor=ancestor)

                temp = search_result.copy()
                #print("Search Term: %s" %search_term)
                if len(temp)!=0:

                    print("InterLex Terms (FDEs):")
                    #print("Search Results: ")
                    for key, value in temp.items():

                        print("%d: Label: %s \t Definition: %s \t Preferred URL: %s " %(option,search_result[key]['label'],search_result[key]['definition'],search_result[key]['preferred_url']  ))

                        search_result[str(option)] = key
                        option = option+1

                # for each column name, query Interlex for possible matches
                cde_result = GetNIDMTermsFromSciCrunch(apikey, search_term, type='cde', ancestor=ancestor)
                if len(cde_result) != 0:
                    #only update search_result with new terms.  This handles what I consider a bug in InterLex queries
                    #where FDE and CDE queries return the same terms.
                    search_result.update(cde_result)
                    #temp = search_result.copy()
                    temp = cde_result.copy()

                    if len(temp)!=0:
                        print()
                        print("InterLex Terms (CDEs):")
                        #print("Search Results: ")
                        for key, value in temp.items():

                            print("%d: Label: %s \t Definition: %s \t Preferred URL: %s " %(option,search_result[key]['label'],search_result[key]['definition'],search_result[key]['preferred_url']  ))

                            search_result[str(option)] = key
                            option = option+1


                # for each column name, query Interlex for possible matches
                pde_result = GetNIDMTermsFromSciCrunch(apikey, search_term, type='pde', ancestor=ancestor)
                if len(pde_result) != 0:
                    search_result.update(pde_result)
                    #temp = search_result.copy()
                    temp = pde_result.copy()

                    if len(temp)!=0:
                        print()
                        print("InterLex Terms (PDEs):")
                        #print("Search Results: ")
                        for key, value in temp.items():

                            print("%d: Label: %s \t Definition: %s \t Preferred URL: %s " %(option,search_result[key]['label'],search_result[key]['definition'],search_result[key]['preferred_url']  ))

                            search_result[str(option)] = key
                            option = option+1


            # if user supplied an OWL file to search in for terms
            #if owl_file:

            if nidm_owl_graph is not None:
                # Add existing NIDM Terms as possible selections which fuzzy match the search_term
                nidm_constants_query = fuzzy_match_terms_from_graph(nidm_owl_graph, search_term)



                first_nidm_term=True
                for key, subdict in nidm_constants_query.items():
                    if nidm_constants_query[key]['score'] > min_match_score:
                        if first_nidm_term:
                            print()
                            print("NIDM Terms:")
                            first_nidm_term=False


                        print("%d: Label(NIDM Term): %s \t Definition: %s \t URL: %s" %(option, nidm_constants_query[key]['label'], nidm_constants_query[key]['definition'], nidm_constants_query[key]['url']))
                        search_result[key] = {}
                        search_result[key]['label']=nidm_constants_query[key]['label']
                        search_result[key]['definition']=nidm_constants_query[key]['definition']
                        search_result[key]['preferred_url']=nidm_constants_query[key]['url']
                        search_result[str(option)] = key
                        option=option+1
            # else just give a list of the NIDM constants for user to choose
            #else:
            #    match_scores={}
            #    for index, item in enumerate(Constants.nidm_experiment_terms):
            #        match_scores[item._str] = fuzz.ratio(search_term, item._str)
            #    match_scores_sorted=sorted(match_scores.items(), key=lambda x: x[1])
            #    for score in match_scores_sorted:
            #        if score[1] > min_match_score:
            #            for term in Constants.nidm_experiment_terms:
            #                if term._str == score[0]:
            #                    search_result[term._str] = {}
            #                    search_result[term._str]['label']=score[0]
            #                    search_result[term._str]['definition']=score[0]
            #                    search_result[term._str]['preferred_url']=term._uri
            #                    search_result[str(option)] = term._str
            #                    print("%d: NIDM Constant: %s \t URI: %s" %(option,score[0],term._uri))
            #                    option=option+1

            if ancestor:
                # Broaden Interlex search
                print("%d: Broaden Interlex query " %option)
            else:
                # Narrow Interlex search
                print("%d: Narrow Interlex query " %option)
            option = option+1

            # Add option to change query string
            print("%d: Change Interlex query string from: \"%s\"" % (option, search_term))

            # Add option to define your own term
            option = option + 1
            print("%d: Define my own term for this variable" % option)

            print("---------------------------------------------------------------------------------------")
            # Wait for user input
            selection=input("Please select an option (1:%d) from above: \t" % option)

            # Make sure user selected one of the options.  If not present user with selection input again
            while not selection.isdigit():
                # Wait for user input
                selection = input("Please select an option (1:%d) from above: \t" % option)

            # toggle use of ancestors in interlex query or not
            if int(selection) == (option-2):
                ancestor=not ancestor
            # check if selection is to re-run query with new search term
            elif int(selection) == (option-1):
                # ask user for new search string
                search_term = input("Please input new search term for CSV column: %s \t:" % column)
                print("---------------------------------------------------------------------------------------")

            elif int(selection) == option:
                # user wants to define their own term.  Ask for term label and definition
                print("\nYou selected to enter a new term for CSV column: %s" % column)

                # collect term information from user
                term_label = input("Please enter a term label for this column [%s]:\t" % column)
                if term_label == '':
                    term_label = column

                # WIP do a quick query of Interlex to see if term already exists with that label. If so show user
                # If user says it's the correct term then use it and stop dialog with user about new term


                term_definition = input("Please enter a definition:\t")


                #get datatype
                while True:
                    term_datatype = input("Please enter the datatype (string,integer,real,categorical):\t")
                    # check datatypes if not in [integer,real,categorical] repeat until it is
                    if (term_datatype == "string") or (term_datatype == "integer") or (term_datatype == "real") or (term_datatype == "categorical"):
                        break

                # now check if term_datatype is categorical and if so let's get the label <-> value mappings
                if term_datatype == "categorical":
                    term_category = {}
                    # ask user for the number of categories
                    while True:
                        num_categories = input("Please enter the number of categories/labels for this term:\t")
                        #check if user supplied a number else repeat question
                        try:
                            val = int(num_categories)
                            break
                        except ValueError:
                            print("That's not a number, please try again!")

                    # loop over number of categories and collect information
                    for category in range(1, int(num_categories)+1):
                        # term category dictionary has labels as keys and value associated with label as value
                        cat_label = input("Please enter the text string label for the category %d:\t" % category)
                        cat_value = input("Please enter the value associated with label \"%s\":\t" % cat_label)
                        term_category[cat_label] = cat_value

                # if term is not categorical then ask for min/max values.  If it is categorical then simply extract
                # it from the term_category dictionary
                if term_datatype != "categorical":
                    term_min = input("Please enter the minimum value:\t")
                    term_max = input("Please enter the maximum value:\t")
                    term_units = input("Please enter the units:\t")
                else:
                    term_min = min(term_category.values())
                    term_max = max(term_category.values())
                    term_units = "categorical"

                # set term variable name as column from CSV file we're currently interrogating
                term_variable_name = column

                # don't need to continue while loop because we've defined a term for this CSV column
                go_loop = False

                # Add personal data element to InterLex
                if term_datatype != 'categorical':
                    ilx_output = AddPDEToInterlex(ilx_obj=ilx_obj, label=term_label, definition=term_definition, min=term_min,
                                max=term_max, units=term_units, datatype=term_datatype)
                else:
                    ilx_output = AddPDEToInterlex(ilx_obj=ilx_obj, label=term_label, definition=term_definition, min=term_min,
                                max=term_max, units=term_units, datatype=term_datatype,categorymappings=json.dumps(term_category))

                # store term info in dictionary
                column_to_terms[current_tuple]['label'] = term_label
                column_to_terms[current_tuple]['definition'] = term_definition
                # column_to_terms[current_tuple]['variable'] = str(column)
                column_to_terms[current_tuple]['url'] = ilx_output.iri + "#"
                column_to_terms[current_tuple]['datatype'] = term_datatype
                column_to_terms[current_tuple]['units'] = term_units
                column_to_terms[current_tuple]['min'] = term_min
                column_to_terms[current_tuple]['max'] = term_max
                if term_datatype == 'categorical':
                    column_to_terms[current_tuple]['levels'] = json.dumps(term_category)


                # print mappings
                print()
                print("Stored mapping Column: %s ->  " % column)
                print("Label: %s" % column_to_terms[current_tuple]['label'])
                # print("Variable: %s" % column_to_terms[current_tuple]['variable'])
                print("Definition: %s" % column_to_terms[current_tuple]['definition'])
                print("Url: %s" % column_to_terms[current_tuple]['url'])
                print("Datatype: %s" % column_to_terms[current_tuple]['datatype'])
                print("Units: %s" % column_to_terms[current_tuple]['units'])
                print("Min: %s" % column_to_terms[current_tuple]['min'])
                print("Max: %s" % column_to_terms[current_tuple]['max'])
                if term_datatype == 'categorical':
                    print("Levels: %s" % column_to_terms[current_tuple]['levels'])
                print("---------------------------------------------------------------------------------------")\

                # don't need to continue while loop because we've defined a term for this CSV column
                go_loop=False


            else:
                # add selected term to map
                column_to_terms[current_tuple]['label'] = search_result[search_result[selection]]['label']
                column_to_terms[current_tuple]['definition'] = search_result[search_result[selection]]['definition']
                column_to_terms[current_tuple]['url'] = search_result[search_result[selection]]['preferred_url']
                # column_to_terms[current_tuple]['variable'] = str(column)

                # print mappings
                print("Stored mapping Column: %s ->  " % current_tuple)
                print("Label: %s" % column_to_terms[current_tuple]['label'])
                print("Definition: %s" % column_to_terms[current_tuple]['definition'])
                print("Url: %s" % column_to_terms[current_tuple]['url'])
                # print("Variable: %s" % column_to_terms[current_tuple]['variable'])
                print("---------------------------------------------------------------------------------------")

                # don't need to continue while loop because we've selected a term for this CSV column
                go_loop=False

        # write variable-> terms map as JSON file to disk
        # get -out directory from command line parameter
        # this is to be sure we've written out our work so far in case user ctrl-c exists program or it crashes
        # will have saved the output
        if output_file is not None:
            # dir = os.path.dirname(output_file)
            # file_path=os.path.relpath(output_file)
            # print("writing %s " %output_file)
            logging.info("saving json mapping file: %s" %os.path.join(os.path.basename(output_file), \
                                        os.path.splitext(output_file)[0]+".json"))
            with open(os.path.join(os.path.basename(output_file),os.path.splitext(output_file)[0]+".json"),'w+') \
                    as fp:
                json.dump(column_to_terms,fp)


    # write variable-> terms map as JSON file to disk
    # get -out directory from command line parameter
    if output_file is not None:
        # dir = os.path.dirname(output_file)
        # file_path=os.path.relpath(output_file)
        # print("writing %s " %output_file)
        logging.info("saving json mapping file: %s" %os.path.join(os.path.basename(output_file), \
                                        os.path.splitext(output_file)[0]+".json"))
        with open(os.path.join(os.path.dirname(output_file),os.path.splitext(output_file)[0]+".json"),'w+') \
                    as fp:
            json.dump(column_to_terms,fp)
        #listb.pack()
        #listb.autowidth()
        #root.mainloop()
        #input("Press Enter to continue...")

    # get CDEs for data dictonary and NIDM graph entity of data
    cde = DD_to_nidm(column_to_terms)


    return [column_to_terms, cde]

def DD_to_nidm(dd_struct):
    '''

    Takes a DD json structure and returns nidm CDE-style graph to be added to NIDM documents
    :param DD:
    :return: NIDM graph
    '''

    # create empty graph for CDEs
    g=Graph()
    g.bind(prefix='prov',namespace=Constants.PROV)
    g.bind(prefix='dct',namespace=Constants.DCT)

    # key_num = 0
    # for each named tuple key in data dictionary
    for key in dd_struct:
        # bind a namespace for the the data dictionary source field of the key tuple
        # for each source variable create entity where the namespace is the source and ID is the variable
        # e.g. calgary:FISCAL_4, aims:FIAIM_9
        #
        # Then when we're storing acquired data in entity we'll use the entity IDs above to reference a particular
        # CDE.  The CDE definitions will have metadata about the various aspects of the data dictionary CDE.

        # add the DataElement RDF type in the source namespace
        key_tuple = eval(key)
        for subkey, item in key_tuple._asdict().items():
            # if subkey == 'source':
                # check if namespace exists else bind it...
                # namespace_found = False
                #for prefix,namespace in g.namespaces():
                #    if namespace == URIRef(dd_struct[str(key_tuple)]["url"].rsplit('/', 1)[0] +"/"):
                #        namespace_found = True
                #        break

                #if namespace_found == False:
                #    item_ns = Namespace(dd_struct[str(key_tuple)]["url"].rsplit('/', 1)[0] +"/")
                #    g.bind(prefix=os.path.splitext(item)[0], namespace=item_ns)
            # if subkey == 'source':
            #    source = item

            if subkey == 'variable':

            # else:
                # cde_id = item_ns[dd_struct[str(key_tuple)]['label']]
                # item_ns = Namespace(dd_struct[str(key_tuple)]["url"].rsplit('/', 1)[0] +"/")
                item_ns = Namespace(dd_struct[str(key_tuple)]["url"]+"/")
                g.bind(prefix=item, namespace=item_ns)
                nidm_ns = Namespace(Constants.NIDM)
                g.bind(prefix='nidm', namespace=nidm_ns)
                # cde_id = item_ns[str(key_num).zfill(4)]
                import hashlib
                # hash the key_tuple and use for local part of ID

                cde_id = item_ns[hashlib.md5(str(key).encode()).hexdigest()]
                g.add((cde_id,RDF.type, Constants.NIDM['DataElement']))


                g.add((cde_id,nidm_ns['variable'],Literal(item)))
                # key_num = key_num + 1
                # source_ns = Namespace("http://uri.interlex.org/base/")
                # g.bind(prefix ='source',namespace=source_ns)
                # g.add((cde_id,source_ns["ilx_0115023"],Literal(source)))



        # this code adds the properties about the particular CDE into NIDM document
        for key, value in dd_struct[str(key_tuple)].items():
            if key == 'definition':
                g.add((cde_id,RDFS['comment'],Literal(value)))
            elif key == 'description':
                g.add((cde_id,Constants.DCT['description'],Literal(value)))
            elif key == 'url':
                g.add((cde_id,Constants.PROV['Location'],Literal(value)))
            elif key == 'label':
                g.add((cde_id,Constants.RDFS['label'],Literal(value)))
            elif key == 'levels':
                g.add((cde_id,Constants.NIDM['levels'],Literal(value)))




            # testing
            # g.serialize(destination="/Users/dbkeator/Downloads/csv2nidm_cde.ttl", format='turtle')



    return g

def add_attributes_with_cde(prov_object, cde, row_variable, value):

    # find the ID in cdes where nidm:variable matches the row_variable
    # qres = cde.subjects(predicate=Constants.RDFS['label'],object=Literal(row_variable))
    qres = cde.subjects(predicate=Constants.NIDM['variable'],object=Literal(row_variable))
    for s in qres:
        entity_id = s
        # provNamespace(entity_id.rsplit('/', 1)[0] +"/")
        # find prefix matching our url in rdflib graph...this is because we're bouncing between
        # prov and rdflib objects
        for prefix,namespace in cde.namespaces():
            if namespace == URIRef(entity_id.rsplit('/',1)[0]+"/"):
                cde_prefix = prefix
                # this basically stores the row_data with the predicate being the cde id from above.
                prov_object.add_attributes({QualifiedName(provNamespace(prefix=cde_prefix, \
                       uri=entity_id.rsplit('/',1)[0]+"/"),entity_id.rsplit('/', 1)[-1]):value})
                break



