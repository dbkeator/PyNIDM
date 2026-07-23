""" Tools for working with NIDM-Experiment files (LinkML native) """

from argparse import ArgumentParser
import os.path
from rdflib import Graph, util
from nidm.linkml.experiment.utils import read_nidm


def main():
    """argparse entry point for the standalone NIDM-Experiment utilities.

    Exposes three subcommands: ``concat`` (merge NIDM files into one turtle
    output), ``visualize`` (render each file to a PDF DotGraph), and
    ``jsonld`` (re-serialize each file as JSON-LD next to the original).
    """
    parser = ArgumentParser(
        description="This program contains various NIDM-Experiment utilities"
    )
    sub = parser.add_subparsers(dest="command")
    concat = sub.add_parser(
        "concat",
        description="This command will simply concatenate the supplied NIDM files into a single output",
    )
    visualize = sub.add_parser(
        "visualize",
        description="This command will produce a visualization(pdf) of the supplied NIDM files",
    )
    jsonld = sub.add_parser(
        "jsonld", description="This command will save NIDM files as jsonld"
    )

    for arg in [concat, visualize, jsonld]:
        arg.add_argument(
            "-nl",
            "--nl",
            dest="nidm_files",
            nargs="+",
            required=True,
            help="A comma separated list of NIDM files with full path",
        )

    concat.add_argument(
        "-o",
        "--o",
        dest="output_file",
        required=True,
        help="Merged NIDM output file name + path",
    )

    args = parser.parse_args()

    # concatenate nidm files
    if args.command == "concat":
        # create empty graph
        graph = Graph()
        for nidm_file in args.nidm_files:
            tmp = Graph()
            graph = graph + tmp.parse(nidm_file, format=util.guess_format(nidm_file))

        graph.serialize(args.output_file, format="turtle")

    elif args.command == "visualize":
        for nidm_file in args.nidm_files:
            # read in nidm file
            project = read_nidm(nidm_file)

            # split path and filename for output file writing; the prov-free
            # renderer (Core.save_DotGraph) writes <basename>.pdf next to it
            file_parts = os.path.split(nidm_file)
            base_path = os.path.join(file_parts[0], os.path.splitext(file_parts[1])[0])
            project.save_DotGraph(filename=base_path, format="pdf")

    elif args.command == "jsonld":
        for nidm_file in args.nidm_files:
            project = read_nidm(nidm_file)
            # serialize to jsonld
            with open(
                os.path.splitext(nidm_file)[0] + ".json", "w", encoding="utf-8"
            ) as f:
                f.write(project.serializeJSONLD())


if __name__ == "__main__":
    main()
