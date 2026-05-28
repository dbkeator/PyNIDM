"""
Auto-generated Pydantic classes for the NIDM-Experiment LinkML schema.

DO NOT EDIT BY HAND.  Regenerate with::

    python scripts/regen_schema.py

Source schema: src/nidm/experiment/schema/nidm_schema.yaml
"""
# ruff: noqa  -- generated file
# fmt: off
from __future__ import annotations
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
import re
import sys
from typing import Any, ClassVar, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

metamodel_version = "None"
version = "0.1.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )
    pass




class LinkMLMeta(RootModel):
    root: Dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'annotations': {'graph_hierarchy': {'tag': 'graph_hierarchy',
                                         'value': 'Project (nidm:Project, '
                                                  'prov:Activity)\n'
                                                  '  -> Session (nidm:Session, '
                                                  'prov:Activity)  [via '
                                                  'dct:isPartOf]\n'
                                                  '    -> Acquisition '
                                                  '(nidm:Acquisition, '
                                                  'prov:Activity)  [via '
                                                  'dct:isPartOf]\n'
                                                  '      -> AcquisitionObject '
                                                  '(nidm:AcquisitionObject, '
                                                  'prov:Entity)  [via '
                                                  'prov:wasGeneratedBy]\n'
                                                  '  -> DataElement '
                                                  '(nidm:DataElement, '
                                                  'prov:Entity)\n'
                                                  '  -> Derivative '
                                                  '(nidm:Derivative, '
                                                  'prov:Activity)  [via '
                                                  'dct:isPartOf]\n'
                                                  '    -> DerivativeObject '
                                                  '(prov:Entity)  [via '
                                                  'prov:wasGeneratedBy]'},
                     'important_notes': {'tag': 'important_notes',
                                         'value': '(1) All instance identifiers '
                                                  'typically use the niiri: '
                                                  'namespace with UUIDs (e.g. '
                                                  'niiri:abc123-def456). (2) '
                                                  'DataElement URIs serve a DUAL '
                                                  'PURPOSE: as RDF subjects '
                                                  'carrying metadata (label, '
                                                  'description, isAbout), AND as '
                                                  'RDF predicates on '
                                                  'AcquisitionObjects to store '
                                                  'actual measurement values. (3) '
                                                  'DataElements from processing '
                                                  'pipelines (FreeSurfer, FSL, '
                                                  'ANTs) may use pipeline-specific '
                                                  'namespaces (freesurfer:, fsl:, '
                                                  'ants:) instead of niiri:. (4) '
                                                  'Subject data is accessed '
                                                  'through the '
                                                  'prov:qualifiedAssociation '
                                                  'chain: Acquisition -> '
                                                  'prov:qualifiedAssociation -> '
                                                  'Association -> prov:agent -> '
                                                  'Person.  The Person carries '
                                                  'ndar:src_subject_id. (5) '
                                                  'Assessment/questionnaire and '
                                                  'demographic data are stored as '
                                                  'properties on '
                                                  'AcquisitionObjects, using '
                                                  'DataElement URIs as predicates '
                                                  'with literal values. (6) '
                                                  'Literal values are often typed '
                                                  'as xsd:string even for numeric '
                                                  "data. Check the DataElement's "
                                                  'nidm:valueType for the intended '
                                                  'type. (7) Multiple NIDM files '
                                                  'can describe data from '
                                                  'different sites or projects but '
                                                  'share the same schema '
                                                  'structure.'},
                     'sparql_get_all_projects': {'tag': 'sparql_get_all_projects',
                                                 'value': 'SELECT ?project ?title '
                                                          'WHERE {\n'
                                                          '  ?project rdf:type '
                                                          'nidm:Project .\n'
                                                          '  OPTIONAL { ?project '
                                                          'dctypes:title ?title }\n'
                                                          '}'},
                     'sparql_get_data_elements': {'tag': 'sparql_get_data_elements',
                                                  'value': 'SELECT ?de ?label '
                                                           '?description WHERE {\n'
                                                           '  { ?de rdf:type '
                                                           'nidm:DataElement }\n'
                                                           '  UNION\n'
                                                           '  { ?de rdf:type '
                                                           'nidm:PersonalDataElement '
                                                           '}\n'
                                                           '  OPTIONAL { ?de '
                                                           'rdfs:label ?label }\n'
                                                           '  OPTIONAL { ?de '
                                                           'dct:description '
                                                           '?description }\n'
                                                           '}'},
                     'sparql_get_export_provenance': {'tag': 'sparql_get_export_provenance',
                                                      'value': 'SELECT ?activity '
                                                               '?label ?software '
                                                               '?version ?time '
                                                               'WHERE {\n'
                                                               '  ?entity '
                                                               'prov:wasGeneratedBy '
                                                               '?activity .\n'
                                                               '  ?activity '
                                                               'prov:wasAssociatedWith '
                                                               '?agent ;\n'
                                                               '            '
                                                               'rdfs:label ?label '
                                                               ';\n'
                                                               '            '
                                                               'prov:startedAtTime '
                                                               '?time .\n'
                                                               '  ?agent rdf:type '
                                                               'prov:SoftwareAgent '
                                                               ';\n'
                                                               '         '
                                                               'rdfs:label '
                                                               '?software ;\n'
                                                               '         '
                                                               'schema:softwareVersion '
                                                               '?version .\n'
                                                               '}'},
                     'sparql_get_imaging_acquisitions': {'tag': 'sparql_get_imaging_acquisitions',
                                                         'value': 'SELECT ?acq_obj '
                                                                  '?modality '
                                                                  '?contrast '
                                                                  '?filename WHERE '
                                                                  '{\n'
                                                                  '  ?acq_obj '
                                                                  'rdf:type '
                                                                  'nidm:AcquisitionObject '
                                                                  ';\n'
                                                                  '           '
                                                                  'nidm:hadAcquisitionModality '
                                                                  '?modality ;\n'
                                                                  '           '
                                                                  'nidm:hadImageContrastType '
                                                                  '?contrast .\n'
                                                                  '  OPTIONAL { '
                                                                  '?acq_obj '
                                                                  'nfo:filename '
                                                                  '?filename }\n'
                                                                  '}'},
                     'sparql_get_sessions_for_project': {'tag': 'sparql_get_sessions_for_project',
                                                         'value': 'SELECT ?session '
                                                                  'WHERE {\n'
                                                                  '  ?session '
                                                                  'rdf:type '
                                                                  'nidm:Session ;\n'
                                                                  '           '
                                                                  'dct:isPartOf '
                                                                  '?project .\n'
                                                                  '  ?project '
                                                                  'rdf:type '
                                                                  'nidm:Project .\n'
                                                                  '}'},
                     'sparql_get_subject_data': {'tag': 'sparql_get_subject_data',
                                                 'value': 'SELECT ?acq_obj '
                                                          '?predicate ?value WHERE '
                                                          '{\n'
                                                          '  ?person '
                                                          'ndar:src_subject_id '
                                                          '"SUB_ID"^^xsd:string .\n'
                                                          '  ?assoc prov:agent '
                                                          '?person .\n'
                                                          '  ?acq '
                                                          'prov:qualifiedAssociation '
                                                          '?assoc .\n'
                                                          '  ?acq_obj '
                                                          'prov:wasGeneratedBy '
                                                          '?acq ;\n'
                                                          '           ?predicate '
                                                          '?value .\n'
                                                          '}'},
                     'sparql_get_subjects_and_ids': {'tag': 'sparql_get_subjects_and_ids',
                                                     'value': 'SELECT ?person '
                                                              '?subject_id WHERE '
                                                              '{\n'
                                                              '  ?person rdf:type '
                                                              'prov:Person ;\n'
                                                              '          '
                                                              'ndar:src_subject_id '
                                                              '?subject_id .\n'
                                                              '}'},
                     'sparql_get_values_for_variable': {'tag': 'sparql_get_values_for_variable',
                                                        'value': 'SELECT '
                                                                 '?subject_id '
                                                                 '?value WHERE {\n'
                                                                 '  ?de rdfs:label '
                                                                 '"VARIABLE_LABEL" '
                                                                 '.\n'
                                                                 '  ?acq_obj ?de '
                                                                 '?value ;\n'
                                                                 '           '
                                                                 'prov:wasGeneratedBy '
                                                                 '?acq .\n'
                                                                 '  ?acq '
                                                                 'prov:qualifiedAssociation '
                                                                 '?assoc .\n'
                                                                 '  ?assoc '
                                                                 'prov:agent '
                                                                 '?person .\n'
                                                                 '  ?person '
                                                                 'ndar:src_subject_id '
                                                                 '?subject_id .\n'
                                                                 '}'}},
     'default_prefix': 'https://purl.org/nidash/nidm/schema/',
     'default_range': 'string',
     'description': 'Schema describing the structure of NIDM (Neuroimaging Data '
                    'Model) RDF graphs. NIDM files use the W3C PROV data model to '
                    'represent neuroimaging study provenance, metadata, and '
                    'derived data.  This schema is used by AI-assisted SPARQL '
                    'query generation to understand the graph structure.',
     'id': 'https://purl.org/nidash/nidm/schema',
     'imports': ['linkml:types'],
     'license': 'Apache-2.0',
     'name': 'nidm-experiment',
     'prefixes': {'ants': {'prefix_prefix': 'ants',
                           'prefix_reference': 'http://stnava.github.io/ANTs/'},
                  'bids': {'prefix_prefix': 'bids',
                           'prefix_reference': 'http://bids.neuroimaging.io/'},
                  'crypto': {'prefix_prefix': 'crypto',
                             'prefix_reference': 'http://id.loc.gov/vocabulary/preservation/cryptographicHashFunctions#'},
                  'dcat': {'prefix_prefix': 'dcat',
                           'prefix_reference': 'http://www.w3.org/ns/dcat#'},
                  'dct': {'prefix_prefix': 'dct',
                          'prefix_reference': 'http://purl.org/dc/terms/'},
                  'dctypes': {'prefix_prefix': 'dctypes',
                              'prefix_reference': 'http://purl.org/dc/dcmitype/'},
                  'dicom': {'prefix_prefix': 'dicom',
                            'prefix_reference': 'http://uri.interlex.org/dicom/uris/terms/'},
                  'freesurfer': {'prefix_prefix': 'freesurfer',
                                 'prefix_reference': 'https://surfer.nmr.mgh.harvard.edu/'},
                  'fsl': {'prefix_prefix': 'fsl',
                          'prefix_reference': 'http://purl.org/nidash/fsl#'},
                  'ilx': {'prefix_prefix': 'ilx',
                          'prefix_reference': 'http://uri.interlex.org/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'ndar': {'prefix_prefix': 'ndar',
                           'prefix_reference': 'https://ndar.nih.gov/api/datadictionary/v2/dataelement/'},
                  'nfo': {'prefix_prefix': 'nfo',
                          'prefix_reference': 'http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#'},
                  'nidm': {'prefix_prefix': 'nidm',
                           'prefix_reference': 'http://purl.org/nidash/nidm#'},
                  'niiri': {'prefix_prefix': 'niiri',
                            'prefix_reference': 'http://iri.nidash.org/'},
                  'obo': {'prefix_prefix': 'obo',
                          'prefix_reference': 'http://purl.obolibrary.org/obo/'},
                  'onli': {'prefix_prefix': 'onli',
                           'prefix_reference': 'http://neurolog.unice.fr/ontoneurolog/v3.0/instrument.owl#'},
                  'prov': {'prefix_prefix': 'prov',
                           'prefix_reference': 'http://www.w3.org/ns/prov#'},
                  'rdf': {'prefix_prefix': 'rdf',
                          'prefix_reference': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'},
                  'rdfs': {'prefix_prefix': 'rdfs',
                           'prefix_reference': 'http://www.w3.org/2000/01/rdf-schema#'},
                  'reproschema': {'prefix_prefix': 'reproschema',
                                  'prefix_reference': 'http://schema.repronim.org/'},
                  'schema': {'prefix_prefix': 'schema',
                             'prefix_reference': 'http://schema.org/'},
                  'sio': {'prefix_prefix': 'sio',
                          'prefix_reference': 'http://semanticscience.org/ontology/sio.owl#'},
                  'xsd': {'prefix_prefix': 'xsd',
                          'prefix_reference': 'http://www.w3.org/2001/XMLSchema#'}},
     'source_file': '/Users/dbkeator/Documents/Coding/PyNIDM/src/nidm/experiment/schema/nidm_schema.yaml',
     'title': 'NIDM-Experiment Schema'} )

class AcquisitionModalityEnum(str, Enum):
    """
    Imaging acquisition modality types
    """
    MagneticResonanceImaging = "MagneticResonanceImaging"
    PositronEmissionTomography = "PositronEmissionTomography"


class ImageContrastTypeEnum(str, Enum):
    """
    MRI image contrast types
    """
    T1Weighted = "T1Weighted"
    T2Weighted = "T2Weighted"
    T2StarWeighted = "T2StarWeighted"
    DiffusionWeighted = "DiffusionWeighted"
    DiffusionTensor = "DiffusionTensor"
    FlowWeighted = "FlowWeighted"
    ArterialSpinLabeling = "ArterialSpinLabeling"


class ImageUsageTypeEnum(str, Enum):
    """
    Intended usage of an acquired image
    """
    Anatomical = "Anatomical"
    Functional = "Functional"
    DiffusionWeighted = "DiffusionWeighted"



class Project(ConfiguredBaseModel):
    """
    Top-level container for a research project or study.  Every NIDM graph has at least one Project.  A Project is also a prov:Activity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Activity'}},
         'class_uri': 'nidm:Project',
         'comments': ['RDF types: nidm:Project, prov:Activity',
                      'Children are linked back to the Project via dct:isPartOf'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., description="""URI of this Project (typically niiri:<uuid>)""", json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    title: Optional[str] = Field(default=None, description="""Project or study name""", json_schema_extra = { "linkml_meta": {'alias': 'title', 'domain_of': ['Project'], 'slot_uri': 'dctypes:title'} })
    description: Optional[str] = Field(default=None, description="""Project description""", json_schema_extra = { "linkml_meta": {'alias': 'description',
         'domain_of': ['Project', 'DataElement'],
         'slot_uri': 'dct:description'} })
    license: Optional[str] = Field(default=None, description="""Data license""", json_schema_extra = { "linkml_meta": {'alias': 'license',
         'domain_of': ['Project', 'Collection'],
         'slot_uri': 'dct:license'} })
    funding: Optional[str] = Field(default=None, description="""Funding information""", json_schema_extra = { "linkml_meta": {'alias': 'funding', 'domain_of': ['Project'], 'slot_uri': 'obo:IAO_0000623'} })
    acknowledgments: Optional[str] = Field(default=None, description="""Acknowledgments""", json_schema_extra = { "linkml_meta": {'alias': 'acknowledgments',
         'domain_of': ['Project'],
         'slot_uri': 'obo:IAO_0000324'} })
    project_identifier: Optional[str] = Field(default=None, description="""Project version or identifier""", json_schema_extra = { "linkml_meta": {'alias': 'project_identifier',
         'domain_of': ['Project'],
         'slot_uri': 'sio:Identifier'} })
    author: Optional[str] = Field(default=None, description="""Dataset author(s)""", json_schema_extra = { "linkml_meta": {'alias': 'author', 'domain_of': ['Project'], 'slot_uri': 'dcat:author'} })
    version: Optional[str] = Field(default=None, description="""Dataset version""", json_schema_extra = { "linkml_meta": {'alias': 'version', 'domain_of': ['Project'], 'slot_uri': 'dct:hasVersion'} })
    sessions: Optional[List[Session]] = Field(default=None, description="""Sessions belonging to this project""", json_schema_extra = { "linkml_meta": {'alias': 'sessions', 'domain_of': ['Project']} })
    data_elements: Optional[List[DataElement]] = Field(default=None, description="""DataElement definitions for this project""", json_schema_extra = { "linkml_meta": {'alias': 'data_elements', 'domain_of': ['Project']} })
    derivatives: Optional[List[Derivative]] = Field(default=None, description="""Derivative processing activities""", json_schema_extra = { "linkml_meta": {'alias': 'derivatives', 'domain_of': ['Project']} })


class Session(ConfiguredBaseModel):
    """
    A study session, typically one per participant visit.  Contains acquisition activities.  A Session is also a prov:Activity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Activity'}},
         'class_uri': 'nidm:Session',
         'comments': ['RDF types: nidm:Session, prov:Activity',
                      'Linked to Project via dct:isPartOf'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    is_part_of: Optional[str] = Field(default=None, description="""The Project this Session belongs to""", json_schema_extra = { "linkml_meta": {'alias': 'is_part_of',
         'domain_of': ['Session', 'Acquisition', 'Derivative'],
         'slot_uri': 'dct:isPartOf'} })
    session_number: Optional[str] = Field(default=None, description="""Session number within the study""", json_schema_extra = { "linkml_meta": {'alias': 'session_number',
         'domain_of': ['Session'],
         'slot_uri': 'bids:session_number'} })
    acquisitions: Optional[List[Acquisition]] = Field(default=None, description="""Acquisition activities in this session""", json_schema_extra = { "linkml_meta": {'alias': 'acquisitions', 'domain_of': ['Session']} })


class Acquisition(ConfiguredBaseModel):
    """
    An acquisition activity such as an MRI scan or questionnaire administration.  Produces AcquisitionObjects.  Also a prov:Activity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Activity'}},
         'class_uri': 'nidm:Acquisition',
         'comments': ['RDF types: nidm:Acquisition, prov:Activity',
                      'Linked to Session via dct:isPartOf',
                      'May also carry onli:instrument-based-assessment type for '
                      'assessments',
                      'Participant linkage: Acquisition -> prov:qualifiedAssociation '
                      '-> prov:Association (with prov:agent -> Person, prov:hadRole -> '
                      'sio:Subject)'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    is_part_of: Optional[str] = Field(default=None, description="""The Session this Acquisition belongs to""", json_schema_extra = { "linkml_meta": {'alias': 'is_part_of',
         'domain_of': ['Session', 'Acquisition', 'Derivative'],
         'slot_uri': 'dct:isPartOf'} })
    qualified_association: Optional[List[Association]] = Field(default=None, description="""Association(s) linking this activity to agents (participants)""", json_schema_extra = { "linkml_meta": {'alias': 'qualified_association',
         'domain_of': ['Acquisition'],
         'slot_uri': 'prov:qualifiedAssociation'} })
    acquisition_objects: Optional[List[AcquisitionObject]] = Field(default=None, description="""Entities generated by this acquisition""", json_schema_extra = { "linkml_meta": {'alias': 'acquisition_objects', 'domain_of': ['Acquisition']} })


class AcquisitionObject(ConfiguredBaseModel):
    """
    A data entity produced by an Acquisition.  Can represent imaging data, assessment/questionnaire results, or demographic data.  Also a prov:Entity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Entity'}},
         'class_uri': 'nidm:AcquisitionObject',
         'comments': ['RDF types: nidm:AcquisitionObject, prov:Entity',
                      'May additionally have type onli:assessment-instrument for '
                      'assessments',
                      'Linked to its Acquisition via prov:wasGeneratedBy',
                      'Assessment and demographic values are stored as extra '
                      'properties on this object, using DataElement URIs as predicates '
                      'with literal values.'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    was_generated_by: Optional[str] = Field(default=None, description="""The Acquisition that produced this object""", json_schema_extra = { "linkml_meta": {'alias': 'was_generated_by',
         'domain_of': ['AcquisitionObject', 'DerivativeObject'],
         'slot_uri': 'prov:wasGeneratedBy'} })
    acquisition_modality: Optional[AcquisitionModalityEnum] = Field(default=None, description="""Imaging modality (MRI, PET)""", json_schema_extra = { "linkml_meta": {'alias': 'acquisition_modality',
         'domain_of': ['AcquisitionObject'],
         'slot_uri': 'nidm:hadAcquisitionModality'} })
    image_contrast_type: Optional[ImageContrastTypeEnum] = Field(default=None, description="""Image contrast type (T1, T2, DWI, etc.)""", json_schema_extra = { "linkml_meta": {'alias': 'image_contrast_type',
         'domain_of': ['AcquisitionObject'],
         'slot_uri': 'nidm:hadImageContrastType'} })
    image_usage_type: Optional[ImageUsageTypeEnum] = Field(default=None, description="""Intended image usage (Anatomical, Functional, DWI)""", json_schema_extra = { "linkml_meta": {'alias': 'image_usage_type',
         'domain_of': ['AcquisitionObject'],
         'slot_uri': 'nidm:hadImageUsageType'} })
    task: Optional[str] = Field(default=None, description="""Task name for functional MRI""", json_schema_extra = { "linkml_meta": {'alias': 'task', 'domain_of': ['AcquisitionObject'], 'slot_uri': 'nidm:Task'} })
    filename: Optional[str] = Field(default=None, description="""File path, often in BIDS format (e.g. bids::sub-XX/anat/sub-XX_T1w.nii.gz)""", json_schema_extra = { "linkml_meta": {'alias': 'filename',
         'domain_of': ['AcquisitionObject'],
         'slot_uri': 'nfo:filename'} })
    sha512: Optional[str] = Field(default=None, description="""SHA-512 hash of the file""", json_schema_extra = { "linkml_meta": {'alias': 'sha512',
         'domain_of': ['AcquisitionObject'],
         'slot_uri': 'crypto:sha512'} })
    location: Optional[str] = Field(default=None, description="""URL or file path location""", json_schema_extra = { "linkml_meta": {'alias': 'location',
         'domain_of': ['AcquisitionObject'],
         'slot_uri': 'prov:Location'} })


class DataElement(ConfiguredBaseModel):
    """
    Metadata describing a measured variable.  Defines the semantics, data type, units, and ontology mapping for a column/variable in the study data.  Also a prov:Entity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Entity'}},
         'class_uri': 'nidm:DataElement',
         'comments': ['RDF types: nidm:DataElement, prov:Entity',
                      'DataElement URIs serve a DUAL PURPOSE: (1) as subjects carrying '
                      'metadata (label, description, isAbout), and (2) as predicates '
                      'on AcquisitionObjects to store actual measurement values.',
                      'DataElements from processing pipelines (FreeSurfer, FSL, ANTs) '
                      'may use pipeline-specific namespaces (freesurfer:, fsl:, ants:) '
                      'instead of niiri: for their URIs.'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., description="""URI of this DataElement.  May use niiri:, freesurfer:, fsl:, or ants: namespace depending on origin.""", json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    label: Optional[str] = Field(default=None, description="""Human-readable variable label""", json_schema_extra = { "linkml_meta": {'alias': 'label',
         'domain_of': ['DataElement', 'SoftwareAgent', 'ExportActivity'],
         'slot_uri': 'rdfs:label'} })
    description: Optional[str] = Field(default=None, description="""Variable description""", json_schema_extra = { "linkml_meta": {'alias': 'description',
         'domain_of': ['Project', 'DataElement'],
         'slot_uri': 'dct:description'} })
    is_about: Optional[str] = Field(default=None, description="""Ontology concept this variable measures (typically ilx:, obo:, or dicom: URI)""", json_schema_extra = { "linkml_meta": {'alias': 'is_about', 'domain_of': ['DataElement'], 'slot_uri': 'nidm:isAbout'} })
    source_variable: Optional[str] = Field(default=None, description="""Original variable name in source data""", json_schema_extra = { "linkml_meta": {'alias': 'source_variable',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:sourceVariable'} })
    value_type: Optional[str] = Field(default=None, description="""XSD data type (xsd:string, xsd:float, xsd:integer)""", json_schema_extra = { "linkml_meta": {'alias': 'value_type',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:valueType'} })
    min_value: Optional[str] = Field(default=None, description="""Minimum allowed value""", json_schema_extra = { "linkml_meta": {'alias': 'min_value',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:minValue'} })
    max_value: Optional[str] = Field(default=None, description="""Maximum allowed value""", json_schema_extra = { "linkml_meta": {'alias': 'max_value',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:maxValue'} })
    measure_of: Optional[str] = Field(default=None, description="""Brain structure or region measured""", json_schema_extra = { "linkml_meta": {'alias': 'measure_of',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:measureOf'} })
    datum_type: Optional[str] = Field(default=None, description="""Type of measurement (e.g. anatomical volume)""", json_schema_extra = { "linkml_meta": {'alias': 'datum_type',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:datumType'} })
    has_unit: Optional[str] = Field(default=None, description="""Unit of measurement (e.g. mm^3)""", json_schema_extra = { "linkml_meta": {'alias': 'has_unit', 'domain_of': ['DataElement'], 'slot_uri': 'nidm:hasUnit'} })
    has_laterality: Optional[str] = Field(default=None, description="""Brain laterality (Left, Right, Bilateral)""", json_schema_extra = { "linkml_meta": {'alias': 'has_laterality',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:hasLaterality'} })
    choices: Optional[str] = Field(default=None, description="""Valid categorical choices for this variable""", json_schema_extra = { "linkml_meta": {'alias': 'choices',
         'domain_of': ['DataElement'],
         'slot_uri': 'reproschema:choices'} })


class PersonalDataElement(DataElement):
    """
    A DataElement for personal or demographic data (age, sex, handedness, diagnosis, etc.).  Subclass of nidm:DataElement.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Entity'}},
         'class_uri': 'nidm:PersonalDataElement',
         'comments': ['RDF types: nidm:PersonalDataElement, prov:Entity',
                      'nidm:PersonalDataElement rdfs:subClassOf nidm:DataElement'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., description="""URI of this DataElement.  May use niiri:, freesurfer:, fsl:, or ants: namespace depending on origin.""", json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    label: Optional[str] = Field(default=None, description="""Human-readable variable label""", json_schema_extra = { "linkml_meta": {'alias': 'label',
         'domain_of': ['DataElement', 'SoftwareAgent', 'ExportActivity'],
         'slot_uri': 'rdfs:label'} })
    description: Optional[str] = Field(default=None, description="""Variable description""", json_schema_extra = { "linkml_meta": {'alias': 'description',
         'domain_of': ['Project', 'DataElement'],
         'slot_uri': 'dct:description'} })
    is_about: Optional[str] = Field(default=None, description="""Ontology concept this variable measures (typically ilx:, obo:, or dicom: URI)""", json_schema_extra = { "linkml_meta": {'alias': 'is_about', 'domain_of': ['DataElement'], 'slot_uri': 'nidm:isAbout'} })
    source_variable: Optional[str] = Field(default=None, description="""Original variable name in source data""", json_schema_extra = { "linkml_meta": {'alias': 'source_variable',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:sourceVariable'} })
    value_type: Optional[str] = Field(default=None, description="""XSD data type (xsd:string, xsd:float, xsd:integer)""", json_schema_extra = { "linkml_meta": {'alias': 'value_type',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:valueType'} })
    min_value: Optional[str] = Field(default=None, description="""Minimum allowed value""", json_schema_extra = { "linkml_meta": {'alias': 'min_value',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:minValue'} })
    max_value: Optional[str] = Field(default=None, description="""Maximum allowed value""", json_schema_extra = { "linkml_meta": {'alias': 'max_value',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:maxValue'} })
    measure_of: Optional[str] = Field(default=None, description="""Brain structure or region measured""", json_schema_extra = { "linkml_meta": {'alias': 'measure_of',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:measureOf'} })
    datum_type: Optional[str] = Field(default=None, description="""Type of measurement (e.g. anatomical volume)""", json_schema_extra = { "linkml_meta": {'alias': 'datum_type',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:datumType'} })
    has_unit: Optional[str] = Field(default=None, description="""Unit of measurement (e.g. mm^3)""", json_schema_extra = { "linkml_meta": {'alias': 'has_unit', 'domain_of': ['DataElement'], 'slot_uri': 'nidm:hasUnit'} })
    has_laterality: Optional[str] = Field(default=None, description="""Brain laterality (Left, Right, Bilateral)""", json_schema_extra = { "linkml_meta": {'alias': 'has_laterality',
         'domain_of': ['DataElement'],
         'slot_uri': 'nidm:hasLaterality'} })
    choices: Optional[str] = Field(default=None, description="""Valid categorical choices for this variable""", json_schema_extra = { "linkml_meta": {'alias': 'choices',
         'domain_of': ['DataElement'],
         'slot_uri': 'reproschema:choices'} })


class Derivative(ConfiguredBaseModel):
    """
    A processing or analysis activity that produces derived data (e.g. brain volume measurements from FreeSurfer, FSL, ANTs).  Also a prov:Activity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Activity'}},
         'class_uri': 'nidm:Derivative',
         'comments': ['RDF types: nidm:Derivative, prov:Activity',
                      'Linked to Project via dct:isPartOf'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    is_part_of: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'alias': 'is_part_of',
         'domain_of': ['Session', 'Acquisition', 'Derivative'],
         'slot_uri': 'dct:isPartOf'} })
    used: Optional[str] = Field(default=None, description="""Source entity consumed by this derivative activity""", json_schema_extra = { "linkml_meta": {'alias': 'used',
         'domain_of': ['Derivative', 'ExportActivity'],
         'slot_uri': 'prov:used'} })


class DerivativeObject(ConfiguredBaseModel):
    """
    An entity produced by a Derivative processing activity.  Contains derived measurements.  Also a prov:Entity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Entity'}},
         'class_uri': 'nidm:DerivativeObject',
         'comments': ['RDF types: nidm:DerivativeObject, prov:Entity',
                      'Like AcquisitionObject, derived measurement values are stored '
                      'as properties using DataElement URIs as predicates.'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    was_generated_by: Optional[str] = Field(default=None, description="""The Derivative activity that produced this object""", json_schema_extra = { "linkml_meta": {'alias': 'was_generated_by',
         'domain_of': ['AcquisitionObject', 'DerivativeObject'],
         'slot_uri': 'prov:wasGeneratedBy'} })


class Person(ConfiguredBaseModel):
    """
    A research participant or subject.  Also a prov:Agent.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Agent'}},
         'class_uri': 'prov:Person',
         'comments': ['RDF types: prov:Person, prov:Agent',
                      'Linked to Acquisitions via prov:qualifiedAssociation -> '
                      'prov:Association (with prov:hadRole sio:Subject)'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    subject_id: Optional[str] = Field(default=None, description="""Subject ID in the study (e.g. 'sub-0050002').  This is the primary human-readable identifier for participants.""", json_schema_extra = { "linkml_meta": {'alias': 'subject_id',
         'domain_of': ['Person'],
         'slot_uri': 'ndar:src_subject_id'} })


class SoftwareAgent(ConfiguredBaseModel):
    """
    Software that produced or processed data (e.g. bidsmri2nidm.py, csv2nidm.py, FreeSurfer).  Also a prov:Agent.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Agent'}},
         'class_uri': 'prov:SoftwareAgent',
         'comments': ['RDF types: prov:SoftwareAgent, prov:Agent'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    label: Optional[str] = Field(default=None, description="""Display name (e.g. 'PyNIDM bidsmri2nidm.py')""", json_schema_extra = { "linkml_meta": {'alias': 'label',
         'domain_of': ['DataElement', 'SoftwareAgent', 'ExportActivity'],
         'slot_uri': 'rdfs:label'} })
    name: Optional[str] = Field(default=None, description="""Software name (e.g. 'PyNIDM')""", json_schema_extra = { "linkml_meta": {'alias': 'name', 'domain_of': ['SoftwareAgent'], 'slot_uri': 'schema:name'} })
    software_version: Optional[str] = Field(default=None, description="""Software version string""", json_schema_extra = { "linkml_meta": {'alias': 'software_version',
         'domain_of': ['SoftwareAgent'],
         'slot_uri': 'schema:softwareVersion'} })
    command: Optional[str] = Field(default=None, description="""Command or script name""", json_schema_extra = { "linkml_meta": {'alias': 'command', 'domain_of': ['SoftwareAgent'], 'slot_uri': 'nidm:command'} })
    runtime_platform: Optional[str] = Field(default=None, description="""Runtime environment (e.g. 'Python 3.9.23')""", json_schema_extra = { "linkml_meta": {'alias': 'runtime_platform',
         'domain_of': ['SoftwareAgent'],
         'slot_uri': 'schema:runtimePlatform'} })


class Association(ConfiguredBaseModel):
    """
    Links an Acquisition activity to an agent (participant) with a specific role.  Typically connects to a Person with role sio:Subject.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'prov:Association',
         'comments': ['RDF type: prov:Association',
                      'Created as a blank node in the graph'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    agent: Optional[str] = Field(default=None, description="""The agent (participant) involved""", json_schema_extra = { "linkml_meta": {'alias': 'agent', 'domain_of': ['Association'], 'slot_uri': 'prov:agent'} })
    had_role: Optional[str] = Field(default=None, description="""Role of the agent (typically sio:Subject)""", json_schema_extra = { "linkml_meta": {'alias': 'had_role', 'domain_of': ['Association'], 'slot_uri': 'prov:hadRole'} })


class Collection(ConfiguredBaseModel):
    """
    A collection of entities (e.g. a BIDS dataset, a FreeSurfer stats collection).  Also a prov:Entity.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'additional_rdf_types': {'tag': 'additional_rdf_types',
                                                  'value': 'prov:Entity'}},
         'class_uri': 'prov:Collection',
         'comments': ['RDF types: prov:Collection, prov:Entity',
                      'May additionally have type bids:Dataset, '
                      'nidm:FSStatsCollection, nidm:FSLStatsCollection, or '
                      'nidm:ANTSStatsCollection'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    bids_version: Optional[str] = Field(default=None, description="""BIDS standard version""", json_schema_extra = { "linkml_meta": {'alias': 'bids_version',
         'domain_of': ['Collection'],
         'slot_uri': 'bids:BIDSVersion'} })
    license: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'alias': 'license',
         'domain_of': ['Project', 'Collection'],
         'slot_uri': 'dct:license'} })
    members: Optional[List[str]] = Field(default=None, description="""Member entities of this collection""", json_schema_extra = { "linkml_meta": {'alias': 'members', 'domain_of': ['Collection'], 'slot_uri': 'prov:hadMember'} })


class ExportActivity(ConfiguredBaseModel):
    """
    An export activity recording which tool created or modified the NIDM file.  Part of the export provenance pattern.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'prov:Activity',
         'comments': ['RDF type: prov:Activity',
                      'Pattern: ExportActivity -> prov:wasAssociatedWith -> '
                      'SoftwareAgent; output Entity -> prov:wasGeneratedBy -> '
                      'ExportActivity; ExportActivity -> prov:used -> input Collection '
                      'or Project'],
         'from_schema': 'https://purl.org/nidash/nidm/schema'})

    identifier: str = Field(default=..., json_schema_extra = { "linkml_meta": {'alias': 'identifier',
         'domain_of': ['Project',
                       'Session',
                       'Acquisition',
                       'AcquisitionObject',
                       'DataElement',
                       'Derivative',
                       'DerivativeObject',
                       'Person',
                       'SoftwareAgent',
                       'Collection',
                       'ExportActivity']} })
    label: Optional[str] = Field(default=None, description="""Human-readable label (e.g. 'Create NIDM RDF from BIDS dataset', 'Add CSV data to NIDM file')""", json_schema_extra = { "linkml_meta": {'alias': 'label',
         'domain_of': ['DataElement', 'SoftwareAgent', 'ExportActivity'],
         'slot_uri': 'rdfs:label'} })
    output_format: Optional[str] = Field(default=None, description="""Output format (e.g. 'turtle')""", json_schema_extra = { "linkml_meta": {'alias': 'output_format',
         'domain_of': ['ExportActivity'],
         'slot_uri': 'nidm:outputFormat'} })
    started_at_time: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'alias': 'started_at_time',
         'domain_of': ['ExportActivity'],
         'slot_uri': 'prov:startedAtTime'} })
    ended_at_time: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'alias': 'ended_at_time',
         'domain_of': ['ExportActivity'],
         'slot_uri': 'prov:endedAtTime'} })
    was_associated_with: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'alias': 'was_associated_with',
         'domain_of': ['ExportActivity'],
         'slot_uri': 'prov:wasAssociatedWith'} })
    used: Optional[str] = Field(default=None, description="""Input entity (Collection or Project) that was used""", json_schema_extra = { "linkml_meta": {'alias': 'used',
         'domain_of': ['Derivative', 'ExportActivity'],
         'slot_uri': 'prov:used'} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Project.model_rebuild()
Session.model_rebuild()
Acquisition.model_rebuild()
AcquisitionObject.model_rebuild()
DataElement.model_rebuild()
PersonalDataElement.model_rebuild()
Derivative.model_rebuild()
DerivativeObject.model_rebuild()
Person.model_rebuild()
SoftwareAgent.model_rebuild()
Association.model_rebuild()
Collection.model_rebuild()
ExportActivity.model_rebuild()
