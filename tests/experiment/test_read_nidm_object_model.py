from pathlib import Path
from rdflib import RDF, RDFS, Graph, Literal, URIRef
from nidm.core import Constants
from nidm.experiment.Utils import _rdflib_graph_from_prov_graph, read_nidm

DATA_DIR = Path(__file__).resolve().parent / "data" / "read_nidm"


def _fixture_path(*names: str) -> Path:
    for name in names:
        path = DATA_DIR / name
        if path.exists():
            return path
    raise FileNotFoundError(f"None of these fixtures exist under {DATA_DIR}: {names}")


def _load_graph(path: Path) -> Graph:
    g = Graph()
    g.parse(str(path))
    return g


def _association_signatures(graph: Graph):
    """
    Compare qualifiedAssociation structures by owner/agent/role, ignoring blank-node IDs.
    """
    sigs = set()
    for owner, assoc in graph.subject_objects(
        URIRef(Constants.PROV["qualifiedAssociation"])
    ):
        agents = list(graph.objects(assoc, URIRef(Constants.PROV["agent"])))
        roles = list(graph.objects(assoc, URIRef(Constants.PROV["hadRole"])))
        if not agents:
            continue
        if not roles:
            sigs.add((str(owner), str(agents[0]), None))
        else:
            for role in roles:
                sigs.add((str(owner), str(agents[0]), str(role)))
    return sigs


def test_read_nidm_loads_export_provenance_into_model():
    """
    Prove read_nidm() loads the bidsmri2nidm export provenance into the in-memory model,
    rather than only preserving it via lossless writeback.
    """
    nidm_ttl = _fixture_path("derivatives_nidm.ttl", "fmriprep_nidm_trimmed.ttl")
    project = read_nidm(str(nidm_ttl))

    # IMPORTANT: inspect the object-generated graph, not the lossless merged serializer output.
    g_model = _rdflib_graph_from_prov_graph(project.graph)

    activity = None
    for subj in g_model.subjects(
        RDFS.label, Literal("Create NIDM RDF from BIDS dataset")
    ):
        activity = subj
        break
    assert (
        activity is not None
    ), "Export prov:Activity missing from loaded in-memory model"

    software = None
    for subj in g_model.subjects(RDFS.label, Literal("PyNIDM bidsmri2nidm.py")):
        software = subj
        break
    assert (
        software is not None
    ), "Export prov:SoftwareAgent missing from loaded in-memory model"

    assert (
        activity,
        URIRef(Constants.PROV["wasAssociatedWith"]),
        software,
    ) in g_model, "Export activity is not associated with the PyNIDM software agent in the loaded model"

    datasets_used = list(g_model.objects(activity, URIRef(Constants.PROV["used"])))
    assert datasets_used, "Export activity does not use any dataset in the loaded model"

    dataset = datasets_used[0]
    assert (
        dataset,
        RDF.type,
        URIRef(str(Constants.BIDS["Dataset"])),
    ) in g_model, "Used dataset is missing bids:Dataset typing in the loaded model"
    assert (
        dataset,
        RDF.type,
        URIRef(Constants.PROV["Collection"]),
    ) in g_model, "Used dataset is missing prov:Collection typing in the loaded model"


def test_read_nidm_loads_qualified_associations_into_model():
    """
    Prove read_nidm() reconstructs qualifiedAssociation structures into the in-memory model.
    Compare semantic owner/agent/role signatures, not raw blank-node IDs.
    """
    nidm_ttl = _fixture_path("brainvol_nidm.ttl", "brainvol_nidm_trimmed.ttl")
    g_in = _load_graph(nidm_ttl)

    project = read_nidm(str(nidm_ttl))
    g_model = _rdflib_graph_from_prov_graph(project.graph)

    in_sigs = _association_signatures(g_in)
    model_sigs = _association_signatures(g_model)

    assert in_sigs, "Input fixture has no qualifiedAssociation signatures to test"
    assert model_sigs, "Loaded in-memory model has no qualifiedAssociation signatures"

    missing = sorted(in_sigs - model_sigs)
    assert not missing, (
        "Qualified associations missing from loaded in-memory model. "
        f"Examples: {missing[:10]}"
    )
