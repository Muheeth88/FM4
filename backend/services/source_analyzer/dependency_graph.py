import networkx as nx
import os


class DependencyGraphBuilder:

    def build(self, files):

        graph = nx.DiGraph()

        path_map = {os.path.basename(f["path"]): f["path"] for f in files}

        for file in files:

            graph.add_node(file["path"])

            for imp in file.get("imports", []):

                imp = imp.replace("import", "").replace(";", "").strip()

                name = imp.split(".")[-1] + ".java"

                if name in path_map:

                    dep_path = path_map[name]

                    graph.add_edge(file["path"], dep_path)

        return graph

    def topological_sort(self, graph):

        try:
            return list(nx.topological_sort(graph))
        except:
            return []