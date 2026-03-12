import networkx as nx
import os


class DependencyGraphBuilder:

    def build(self, files):
        graph = nx.DiGraph()
        path_map = {os.path.basename(f["path"]): f["path"] for f in files}
        file_map = {f["path"]: f for f in files}

        for file in files:
            graph.add_node(file["path"])

            for imp in file.get("imports", []):
                imp = imp.replace("import", "").replace(";", "").strip()
                name = imp.split(".")[-1] + ".java"
                if name in path_map:
                    dep_path = path_map[name]
                    if not self._should_include_dependency(file, file_map[dep_path]):
                        continue
                    graph.add_edge(file["path"], dep_path)

        return graph

    def topological_sort(self, graph):
        return self._safe_topological_sort(graph)

    def topological_sort_for_role(self, graph, files, role):
        role_paths = [file["path"] for file in files if file["file_type"] == role]
        role_graph = graph.subgraph(role_paths).copy()
        ordered = self._safe_topological_sort(role_graph)
        if ordered:
            return ordered
        return role_paths

    @staticmethod
    def _should_include_dependency(source_file, target_file):
        if source_file["file_type"] == "infra_file" and target_file["file_type"] == "test_file":
            return False
        return True

    @staticmethod
    def _safe_topological_sort(graph):
        try:
            return list(nx.topological_sort(graph))
        except:
            return []
