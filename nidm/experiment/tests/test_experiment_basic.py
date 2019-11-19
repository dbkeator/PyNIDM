import os,sys
import pytest, pdb
from os import remove
import json
from nidm.experiment import Project, Session, Acquisition, AcquisitionObject, DataElement, Derivative, DerivativeObject
from nidm.core import Constants
from io import StringIO
from rdflib import Graph
from nidm.experiment.Utils import read_nidm
from nidm.experiment.Query import GetDataElements, GetTuplesForUUID
import tempfile

import prov, rdflib

def test_1(tmpdir):
    tmpdir.chdir()

    project = Project()

    #save a turtle file
    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())


def test_2(tmpdir):
    tmpdir.chdir()

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(attributes=kwargs)

    with open("test.ttl",'w') as f:
        f.write(project.serializeTurtle())


def test_sessions_1(tmpdir):
    tmpdir.chdir()

    project = Project()
    assert project.sessions == []

    session1 = Session(project)
    project.add_sessions(session1)
    assert session1.label == project.sessions[0].label

    session2 = Session(project)
    project.add_sessions(session2)
    assert len(project.sessions) == 2
    assert session2.label == project.sessions[1].label


def test_sessions_2(tmpdir):
    tmpdir.chdir()

    project = Project()
    assert project.sessions == []

    session1 = Session(project)
    assert project.sessions[0].label == session1.label


def test_sessions_3(tmpdir):
    tmpdir.chdir()

    project1 = Project()
    project2 = Project()

    session1 = Session(project1)
    session2 = Session(project2)

    project1.add_sessions(session1)
    project1.add_sessions(session2)

    assert len(project1.sessions) == 2
    assert session2.label == project1.sessions[1].label
    assert session1.label == project1.sessions[0].label


def test_project_noparameters():
    # creating project without parameters
    proj = Project()

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == 'prov:Activity'

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 1


def test_project_emptygraph():
    # creating project without parameters
    proj = Project(empty_graph=True)

    # checking if we created ProvDocument
    assert type(proj.bundle) is prov.model.ProvDocument

    # checking graph namespace
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert namesp == ["nidm"]

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == 'prov:Activity'

    assert len(proj.graph.get_records()) == 1


def test_project_uuid():
    # creating project without parameters
    proj = Project(uuid="my_uuid")

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == 'prov:Activity'

    # checking if uuid is correct
    assert proj.identifier.localpart == "my_uuid"

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 1


def test_project_att():
    # creating project without parameters
    proj = Project(attributes={prov.model.QualifiedName(Constants.NIDM, "title"): "MyPRoject"})

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l+[rdflib.term.URIRef('http://purl.org/nidash/nidm#prefix')]) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == 'prov:Activity'

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 1


def test_session_noparameters():
    # creating project without parameters and a session to the project
    proj = Project()
    sess = Session(proj)

    # checking if we created ProvDocument
    assert type(proj.bundle) is Constants.NIDMDocument
    assert issubclass(type(proj.bundle), prov.model.ProvDocument)

    # checking if one session is added
    assert len(proj.sessions)

    # checking graph namespace
    const_l = list(Constants.namespaces)
    namesp = [i.prefix for i in proj.graph.namespaces]
    assert sorted(const_l) == sorted(namesp)

    # checking type
    proj_type = proj.get_type()
    assert eval(proj_type.provn_representation()) == 'prov:Activity'

    # checking length of graph records; it doesn work if all tests are run
    assert len(proj.graph.get_records()) == 2


def test_jsonld_exports():

    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save a turtle file
    with open("test.json",'w') as f:
        f.write(project.serializeJSONLD())

    #load in JSON file
    with open("test.json") as json_file:
        data = json.load(json_file)


    assert(data["Identifier"]['@value'] == "9610")
    #WIP  Read back in json-ld file and check that we have the project info
    #remove("test.json")

def test_project_trig_serialization():

    outfile = StringIO()


    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)


    #save as trig file with graph identifier Constants.NIDM_Project
    test = project.serializeTrig(identifier=Constants.NIIRI["_996"])
    outfile.write(test)
    outfile.seek(0)

    # WIP: RDFLib doesn't seem to have a Trig parser?!?
    #load back into rdf graph and do assertions
    # project2 = Graph()
    # project2.parse(source=outfile)


    #test some assertion on read file
    # print(project2.serialize(format='turtle').decode('ASCII'))
    # print(project2.serialize(format='trig').decode('ASCII'))

#TODO: checking
#attributes{pm.QualifiedName(Namespace("uci", "https.../"), "mascot"): "bleble", ...}
# (has to be "/" at the end (or #)

def test_dataelements():
    '''
    Tests that data elements get connected to Project object via DCT:isPartOf relationship and checks attributes get
    set during instantiation.
    :return:
    '''


    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)

    kwargs={Constants.NIDM["datumType"]:"http://uri.interlex.org/base/ilx_0102597",Constants.NIDM["hasLaterality"]:"Right"}
    datael1 = DataElement(project=project,uuid="_99999",attributes=kwargs)

    # write temporary file to disk and use for stats
    temp = tempfile.NamedTemporaryFile(delete=False,suffix=".ttl")
    temp.write(project.serializeTurtle().encode())
    temp.close()
    df = GetTuplesForUUID(uuid=Constants.NIIRI["_99999"],nidm_file_list=temp.name)

    #check df for datumType
    # df[df["pred"]==Constants.NIDM["datumType"]].index.tolist()
    assert(str(df.loc[df['pred'] == Constants.NIDM["datumType"],'obj'].values[0]) == "http://uri.interlex.org/base/ilx_0102597")
    assert(str(df.loc[df['pred'] == Constants.NIDM["hasLaterality"],'obj'].values[0]) == "Right")
    assert(str(df.loc[df['pred'] == Constants.DCT["isPartOf"],'obj'].values[0]) == str(Constants.NIIRI["_123456"]))

def test_derivative():
    '''
    Tests derivative activity and derivative object entity classes
    :return:
    '''
    kwargs={Constants.NIDM_PROJECT_NAME:"FBIRN_PhaseII",Constants.NIDM_PROJECT_IDENTIFIER:9610,Constants.NIDM_PROJECT_DESCRIPTION:"Test investigation"}
    project = Project(uuid="_123456",attributes=kwargs)

    # add derivative activity
    kwargs={Constants.NIDM_PROJECT_DESCRIPTION:"Freesurfer Segmentation Statistics"}
    derivative = Derivative(project=project,uuid='_99999',attributes=kwargs)

    # add derivative entity
    kwargs={Constants.PROV["type"]:Constants.NIDM["FSStatsCollection"]}
    derivative_entity = DerivativeObject(derivative=derivative,uuid='_99998')
    derivative_entity.add_attributes({Constants.freesurfer["fs_00000"]:12345})

    # create qualified association with activity
    derivative.add_qualified_association(person= derivative.add_person(attributes=({Constants.NIDM_SUBJECTID:"996"})),role=Constants.NIDM_PARTICIPANT)


    # check assertions that derivative activity is part of the project and the derivative entity is generated by
    # the derivative
    # write temporary file to disk and use for stats
    temp = tempfile.NamedTemporaryFile(delete=False,suffix=".ttl")
    temp.write(project.serializeTurtle().encode())
    temp.close()
    derivative_df = GetTuplesForUUID(uuid=Constants.NIIRI["_99999"],nidm_file_list=temp.name)
    derivative_entity_df = GetTuplesForUUID(uuid=Constants.NIIRI["_99998"],nidm_file_list=temp.name)

    # derivative activity is part of the project
    assert(str(derivative_df.loc[derivative_df['pred'] == Constants.DCT["isPartOf"],'obj'].values[0]) == str(Constants.NIIRI["_123456"]))
    # derivative activity has a description
    assert(str(derivative_df.loc[derivative_df['pred'] == Constants.NIDM_PROJECT_DESCTIOION,'obj'].values[0]) == "Freesurfer Segmentation Statistics")
    # derivative entity is connected to derivative activity
    assert(str(derivative_entity_df.loc[derivative_entity_df['pred'] == Constants.PROV["wasGeneratedBy"],'obj'].values[0]) == str(Constants.NIIRI["_99998"]))
    # derivative entity attributes
    assert(str(derivative_entity_df.loc[derivative_entity_df['pred'] == Constants.freesurfer["fs_00000"],'obj'].values[0]) == 12345)
    # check derivative object counter
    assert(str(Constants.NIIRI["_99998"]) in derivative.get_derivative_objects())

