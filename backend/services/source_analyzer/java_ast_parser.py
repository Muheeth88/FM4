from tree_sitter import Parser
import tree_sitter_languages
import os

JAVA_LANGUAGE = tree_sitter_languages.get_language("java")


class JavaASTParser:

    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(JAVA_LANGUAGE)

    def parse(self, file):

        path = file["path"]

        with open(path, "r") as f:
            source = f.read()

        tree = self.parser.parse(bytes(source, "utf8"))

        root = tree.root_node

        classes = []
        methods = []
        imports = []
        annotations = []

        for node in root.children:

            if node.type == "import_declaration":
                imports.append(source[node.start_byte:node.end_byte])

            if node.type == "class_declaration":
                classes.append(self._parse_class(node, source))

        return {
            "path": path,
            "source": source,
            "imports": imports,
            "classes": classes,
            "methods": methods,
            "annotations": annotations
        }

    def _parse_class(self, node, source):

        name = None
        methods = []

        for child in node.children:

            if child.type == "identifier":
                name = source[child.start_byte:child.end_byte]

            if child.type == "method_declaration":
                methods.append(
                    source[child.start_byte:child.end_byte]
                )

        return {
            "name": name,
            "methods": methods
        }