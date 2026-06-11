#!/usr/bin/env python
"""
csv2nidm legacy-vs-new parity harness.

Runs BOTH csv2nidm implementations on the SAME CSV input and compares
their NIDM output for graph isomorphism.  Because each run mints fresh
random ``niiri:<uuid>`` instance URIs (which ``rdflib``'s
``to_isomorphic`` does NOT canonicalize -- it only canonicalizes blank
nodes), we first rewrite every instance URI to a blank node, then run
the standard isomorphism comparison.  This is the BNode-canonicalization
step noted as task 7 / Part B in TRANSFER.md.

Must run inside an env that has BOTH tools importable -- i.e. the
prov-toolbox-based legacy tool AND the new LinkML tool (``pynidm_v3`` or
``nidm_test_clean``).  It cannot run in the dev sandbox (no prov there).

    conda activate pynidm_v3
    python scripts/csv2nidm_parity.py
    python scripts/csv2nidm_parity.py --keep   # keep temp dir for inspection

Exit code 0 = every compared mode is isomorphic; 1 = at least one
divergence (or a tool failed / prompted).  When a mode diverges, the
in-legacy-only and in-new-only triples are printed, grouped by
predicate, so the output maps directly onto docs/csv2nidm_parity_audit.md.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD

LEGACY_MODULE = "nidm.experiment.tools.csv2nidm"
NEW_MODULE = "nidm.linkml.experiment.tools.csv2nidm"

# Instance namespace whose UUIDs differ run-to-run.
NIIRI = "http://iri.nidash.org/"

# Per-run timeout; a tool that drops into an interactive prompt will hit
# EOF (stdin is /dev/null) or hang until this fires.
TOOL_TIMEOUT_S = 180


def _subjectid_uri() -> str:
    """The src_subject_id concept URI, so detect_idfield finds the id
    column from the data dictionary's isAbout."""
    from nidm.linkml.core.constants import NIDM_SUBJECTID

    return str(NIDM_SUBJECTID)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_assessment_fixtures(workdir: Path) -> tuple[Path, Path]:
    """A plain assessment CSV + a CSV data dictionary covering every
    column (so neither tool drops into an interactive concept prompt)."""
    csv_path = workdir / "data.csv"
    csv_path.write_text(
        "participant_id,age,score\n"
        "0050001,25,88\n"
        "0050002,30,72\n"
    )

    dd_path = workdir / "dd.csv"
    dd_path.write_text(
        "source_variable,label,description,valueType,measureOf,isAbout,"
        "unitCode,minValue,maxValue\n"
        f"participant_id,Participant ID,Subject identifier,xsd:string,"
        f"subject,{_subjectid_uri()},,,\n"
        "age,Age,Age in years,xsd:integer,age,,,0,120\n"
        "score,Score,Test score,xsd:integer,score,,,0,100\n"
    )
    return csv_path, dd_path


# ---------------------------------------------------------------------------
# Running the tools
# ---------------------------------------------------------------------------


def _run_tool(module: str, args: list[str], workdir: Path) -> None:
    """Run ``python -m <module> <args>`` in *workdir*; raise on failure."""
    cmd = [sys.executable, "-m", module, *args]
    print(f"    $ {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(workdir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=TOOL_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{module} exited {proc.returncode}:\n"
            + "\n".join("      " + ln for ln in proc.stdout.splitlines()[-30:])
        )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


# Predicates whose OBJECT is legitimately run/tool-specific (export
# timestamps, the tool's own version + platform).  Their values are
# replaced with a constant so they don't desync bnode canonicalization.
_PROV = "http://www.w3.org/ns/prov#"
_SCHEMA = "https://schema.org/"
_VOLATILE_OBJECT_PREDICATES = {
    _PROV + "startedAtTime",
    _PROV + "endedAtTime",
    _SCHEMA + "softwareVersion",
    _SCHEMA + "runtimePlatform",
}


def _normalize_literals(g: Graph) -> Graph:
    """Copy *g*, neutralizing only the legitimately-different *values*:

      * ``xsd:string``-typed literals -> plain literals (RDF 1.1 equal,
        but rdflib hashes them differently);
      * objects of volatile predicates (export timestamps, tool version,
        runtime platform) -> a constant.

    Instance node identity (niiri URIs + blank nodes) is left intact here
    and canonicalized separately by :func:`_canonical` via color
    refinement -- rdflib's ``to_isomorphic`` mislabels these heavily-
    blank-node graphs and yields false-negative diffs.
    """
    out = Graph()
    for s, p, o in g:
        if str(p) in _VOLATILE_OBJECT_PREDICATES:
            o = Literal("NORMALIZED")
        elif isinstance(o, Literal) and o.datatype == XSD.string:
            o = Literal(str(o))
        out.add((s, p, o))
    return out


def _is_instance(term) -> bool:
    """A node whose identity is run-specific: a blank node, or a niiri
    instance URI (random per run)."""
    return isinstance(term, BNode) or (
        isinstance(term, URIRef) and str(term).startswith(NIIRI)
    )


def _wl_labels(g: Graph) -> dict:
    """Assign each instance node a stable label via 1-WL color refinement.

    Seeded from each node's non-instance context (rdf:type values,
    literals, fixed-vocabulary URIs), then iteratively folded with
    neighbor labels.  Two isomorphic graphs produce matching labels for
    corresponding nodes; the per-subject literals (subject_id, age,
    score) break the two-subject symmetry that defeats rdflib.
    """
    nodes = {t for tr in g for t in (tr[0], tr[2]) if _is_instance(t)}

    def seed(n):
        sig = []
        for p, o in g.predicate_objects(n):
            if not _is_instance(o):
                sig.append(("o", str(p), str(o)))
        for s, p in g.subject_predicates(n):
            if not _is_instance(s):
                sig.append(("i", str(p), str(s)))
        return hashlib.sha1(repr(sorted(sig)).encode()).hexdigest()

    labels = {n: seed(n) for n in nodes}
    for _ in range(len(nodes) + 5):
        nxt = {}
        for n in nodes:
            sig = [("self", labels[n])]
            for p, o in g.predicate_objects(n):
                if _is_instance(o):
                    sig.append(("o", str(p), labels[o]))
            for s, p in g.subject_predicates(n):
                if _is_instance(s):
                    sig.append(("i", str(p), labels[s]))
            nxt[n] = hashlib.sha1(repr(sorted(sig)).encode()).hexdigest()
        if nxt == labels:
            break
        labels = nxt
    return labels


def _canonical(path: Path) -> set:
    """Parse *path*, normalize volatile values, and relabel every instance
    node to a content-derived canonical URI.  Returns a set of triples
    that is equal across isomorphic graphs."""
    g = _normalize_literals(_parse(path))
    labels = _wl_labels(g)

    def relabel(t):
        return URIRef("urn:canon:" + labels[t]) if _is_instance(t) else t

    return {(relabel(s), p, relabel(o)) for s, p, o in g}


def _parse(path: Path) -> Graph:
    g = Graph()
    g.parse(source=str(path), format="turtle")
    return g


def _short(term) -> str:
    """Compact display: localname for URIs, repr for literals, tag for bnodes."""
    if isinstance(term, BNode):
        return "[bnode]"
    if isinstance(term, Literal):
        dt = f"^^{term.datatype.split('#')[-1].split('/')[-1]}" if term.datatype else ""
        return f'"{term}"{dt}'
    s = str(term)
    for sep in ("#", "/"):
        if sep in s:
            return s.rsplit(sep, 1)[-1] or s
    return s


def _summarize_triples(triples, label: str) -> None:
    print(f"      {label}: {len(triples)} triple(s)")
    rows = sorted(f"        {_short(p):<22} -> {_short(o)}" for _, p, o in triples)
    for row in rows:
        print(row)


def compare(legacy_ttl: Path, new_ttl: Path) -> bool:
    """Return True when the two NIDM files are isomorphic (after instance
    -node canonicalization); otherwise print the divergence and return
    False."""
    gl = _canonical(legacy_ttl)
    gn = _canonical(new_ttl)

    if gl == gn:
        print("    ISOMORPHIC ✓")
        return True

    in_legacy_only = gl - gn
    in_new_only = gn - gl
    print("    DIVERGENT ✗")
    print(f"      legacy={len(gl)} triples  new={len(gn)} triples")
    if in_legacy_only:
        print("    --- in LEGACY only (new is missing these) ---")
        _summarize_triples(in_legacy_only, "legacy-only")
    if in_new_only:
        print("    --- in NEW only (new emits these extra) ---")
        _summarize_triples(in_new_only, "new-only")
    return False


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def mode_assessment(workdir: Path) -> bool:
    """New-file assessment mode: CSV -> fresh NIDM, both tools."""
    print("[mode: assessment / new file]")
    csv_path, dd_path = _write_assessment_fixtures(workdir)

    # Write each tool's output to the SAME basename (out.ttl) in its own
    # subdir, so the export entity's nfo:filename isn't a false diff.
    legacy_dir = workdir / "legacy"
    new_dir = workdir / "new"
    legacy_dir.mkdir(exist_ok=True)
    new_dir.mkdir(exist_ok=True)
    legacy_ttl = legacy_dir / "out.ttl"
    new_ttl = new_dir / "out.ttl"

    common = ["-csv", str(csv_path), "-csv_map", str(dd_path), "-no_concepts"]
    print("  legacy:")
    _run_tool(LEGACY_MODULE, [*common, "-out", str(legacy_ttl)], workdir)
    print("  new:")
    _run_tool(NEW_MODULE, [*common, "-out", str(new_ttl)], workdir)

    if not legacy_ttl.exists():
        raise RuntimeError(f"legacy produced no output at {legacy_ttl}")
    if not new_ttl.exists():
        raise RuntimeError(f"new produced no output at {new_ttl}")
    return compare(legacy_ttl, new_ttl)


# Additional modes (-nidm add-to-existing, -derivative) build on a shared
# base NIDM file + software-metadata fixture; they land in the next
# iteration once the assessment mode runs clean end to end.
MODES = {
    "assessment": mode_assessment,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=[*MODES, "all"],
        default="all",
        help="Which parity mode(s) to run (default: all implemented).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temp working directory for manual inspection.",
    )
    args = parser.parse_args(argv)

    selected = list(MODES) if args.mode == "all" else [args.mode]
    workdir = Path(tempfile.mkdtemp(prefix="csv2nidm_parity_"))
    print(f"workdir: {workdir}\n")

    results: dict[str, bool] = {}
    try:
        for name in selected:
            try:
                results[name] = MODES[name](workdir)
            except Exception as exc:  # noqa: BLE001 -- report, don't crash the sweep
                print(f"    ERROR running mode {name!r}: {exc}")
                results[name] = False
            print()
    finally:
        if args.keep:
            print(f"(kept workdir: {workdir})")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    print("=" * 60)
    print("parity summary")
    for name, ok in results.items():
        print(f"  {name:<14} {'ISOMORPHIC' if ok else 'DIVERGENT/ERROR'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
