from pandas_plink import read_plink1_bin
import prov.model as pm
from .DerivativeObject import DerivativeObject
from ..core import Constants, getUUID


class PlinkGeneticsObject(DerivativeObject):
    """Class for NIDM-Experimenent GeneticsAcquisitionObject-Level Objects.

    Default constructor uses empty graph with namespaces added from NIDM/Scripts/Constants.py.
    Additional alternate constructors for user-supplied graphs and default namespaces (i.e. from Constants.py)
    and user-supplied graph and namespaces

    This class is to support the storage of metadata extracted from Plink .bim, .bed, .fam files in support of
    storing imaging-genetics related analysis metadata.

    @author: David Keator <dbkeator@uci.edu>
    @copyright: University of California, Irvine 2022

    """

    # constructor
    def __init__(self, derivative, attributes=None, uuid=None):
        """
        Default constructor, creates an derivative object and links to derivative activity object

        :param derivative: a Derivative activity object
        :param attributes: optional attributes to add to entity
        :param uuid: optional uuid...used mostly for reading in existing NIDM document
        :return: none

        """

        if uuid is None:
            # execute default parent class constructor
            super().__init__(
                derivative.graph,
                pm.QualifiedName(pm.Namespace("niiri", Constants.NIIRI), getUUID()),
                attributes,
            )
        else:
            super().__init__(derivative.graph, pm.Identifier(uuid), attributes)

        derivative.graph._add_record(self)

        # carry graph object around
        self.graph = derivative.graph

        # create link to acquisition activity
        derivative.add_derivative_object(self)

        # Plink Object from pandas_plink to store binary genetics data
        self.plink_bin_data

    def load_plink_files(self, bedfile, famfile, mapfile):
        """
        This function will load Plink-related files and instantiate additional derivative objects into the NIDM
        record, one for each of the bed, fam, and map files.  It will link those objects to the parent derivative
        activity

        :param bed: bed genotype results file
        :param fam: families file
        :param map: map file with info on genetics markers

        """

        self.plink_bin_data = read_plink1_bin(
            bedfile=bedfile, bimfile=mapfile, fam=famfile, verbose=False
        )

    def __str__(self):
        return "NIDM-Experiment Genetics Object Class"
