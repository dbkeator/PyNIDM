import rdflib as rdf
import os, sys
from prov.model import *

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from nidm.core import Constants

#import NIDMExperimentCore
from nidm.experiment.Core import Core

class Project(Core, ProvActivity):
    """Class for NIDM-Experiment Project-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2017

    """
    #constructor, adds project
    def __init__(self,project_name, project_id, project_description):
        """
        Default contructor, creates document and adds Project activity to graph

        :param project_name: string, name of project
        :param project_id: string, identifier of project
        :param project_description: string, description of the project
        :return: nidm graph

        """
        #execute default parent class constructor
        Core.__init__(self)
        self.id = self.addProject(project_name,project_id,project_description)


    #constructor with user-supplied graph, namespaces come from base class import of Constants.py
    #note this sets the graph in the base class
    @classmethod
    def withGraph(self, graph):
        #execute default parent class constructor
        Core.withGraph(self, graph)

    #constructor with user-supplied graph and namespaces
    #note this sets the graph in the base class
    @classmethod
    def withGraphAndNamespaces(self, graph, namespaces):
        #sets up empty dictionary to map object URIs to experiment names
        self.inv_object_dict={}
        #execute default parent class constructor
        Core.withGraphAndNamespaces(self, graph, namespaces)


    def __str__(self):
        return "NIDM-Experiment Project Class"

    def getProject(self):
        """
        Returns project object in current graph
        :return: project object for use in adding attributes or associating agents with project for example
        """
        return self.id
    #adds and project entity to graph and stores URI
    def addProject(self, project_name, project_id, project_description):
        """
        Add investigation entity to graph

        :param project_name: string, name of project
        :param project_id: string, identifier of project
        :param project_description: string, description of the project
        :return: project object

        """
        #create unique ID
        self.uuid = self.getUUID()
        #get datatypes
        dt_name = self.getDataType(project_name)
        dt_id = self.getDataType(project_id)
        dt_desc = self.getDataType(project_description)


        #add to graph
        a1=self.graph.activity(self.namespaces["nidm"][self.uuid],None,None,{PROV_TYPE: Constants.NIDM_PROJECT_TYPE, \
                                                                          Constants.NIDM_PROJECT_NAME: Literal(project_id, datatype=dt_id), \
                                                                          Constants.NIDM_PROJECT_IDENTIFIER: Literal(project_name, datatype=dt_name), \
                                                                          Constants.NIDM_PROJECT_DESCRIPTION: Literal(project_description,datatype=dt_desc)})
        a1.add_attributes({PROV_TYPE: Constants.NIDM_PROJECT})
        return a1

    def addProjectPI(self,family_name=None, given_name=None,id=None):
        """
        Add prov:Person with role of PI using first/last name

        :param family_name: string, surname
        :param given_name: sting, first name or personal name
        :return: dictionary containing objects for agent, activity, and association between agent and role as PI
        """
        #Get unique ID for person
        person = self.addPerson()
        #create an activity for qualified association with person
        activity = self.graph.activity(self.namespaces["nidm"][self.getUUID()])

        #add minimal attributes to person
        person.add_attributes({PROV_TYPE: PROV['Person']})
        #check if famile_name is given
        if (family_name != None):
            person.add_attributes({Constants.NIDM_FAMILY_NAME:Literal(family_name, datatype=XSD_STRING)})
        if (given_name != None):
            person.add_attributes({Constants.NIDM_GIVEN_NAME:Literal(given_name, datatype=XSD_STRING)})
        if (id != None):
            person.add_attributes({Constants.NIDM_SUBJECTID:Literal(given_name, datatype=XSD_STRING)})

        #associate person with activity for qualified association
        assoc = self.graph.association(agent=person, activity=activity)
        #add role for qualified association
        assoc.add_attributes({PROV_ROLE:Constants.NIDM_PI})
        #connect project to person serving as PI
        self.graph.wasAssociatedWith(person,self.getProject())

        return {'agent':person, 'activity':activity, 'association':assoc}
