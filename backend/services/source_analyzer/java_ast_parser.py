from tree_sitter import Parser
import tree_sitter_languages

JAVA_LANGUAGE = tree_sitter_languages.get_language("java")


class JavaASTParser:

    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(JAVA_LANGUAGE)

    def parse(self, file):
        path = file["path"]

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        tree = self.parser.parse(bytes(source, "utf8"))

        root = tree.root_node

        classes = []
        imports = []
        annotations = []
        package_name = ""

        for node in root.children:
            if node.type == "import_declaration":
                imports.append(source[node.start_byte:node.end_byte])

            if node.type == "package_declaration":
                package_name = self._normalize_package(source[node.start_byte:node.end_byte])

            if node.type in {"class_declaration", "interface_declaration", "enum_declaration"}:
                declaration = self._parse_declaration(node, source)
                classes.append(declaration)
                annotations.extend(declaration.get("annotations", []))

        return {
            "path": path,
            "parser": "java",
            "source": source,
            "imports": imports,
            "package": package_name,
            "classes": classes,
            "annotations": annotations
        }

    def _parse_declaration(self, node, source):
        name = None
        methods = []
        fields = []
        annotations = []
        modifiers = []
        extends = None
        implements = []
        kind = node.type.replace("_declaration", "")

        for child in node.children:
            if child.type == "identifier":
                name = source[child.start_byte:child.end_byte]

            if child.type == "modifiers":
                modifiers = self._extract_modifiers(child, source)
                annotations = self._extract_annotations(child, source)

            if child.type == "superclass":
                extends = self._clean_clause(source[child.start_byte:child.end_byte], "extends")

            if child.type == "super_interfaces":
                implements = self._split_interfaces(
                    self._clean_clause(source[child.start_byte:child.end_byte], "implements")
                )

            if child.type == "class_body":
                for member in child.named_children:
                    if member.type == "field_declaration":
                        fields.extend(self._parse_fields(member, source))
                    elif member.type in {"method_declaration", "constructor_declaration"}:
                        methods.append(self._parse_method(member, source))

        return {
            "kind": kind,
            "name": name,
            "annotations": annotations,
            "modifiers": modifiers,
            "extends": extends,
            "implements": implements,
            "fields": fields,
            "methods": methods,
        }

    def _parse_fields(self, node, source):
        field_type = None
        modifiers = []
        annotations = []
        names = []

        for child in node.children:
            if child.type == "modifiers":
                modifiers = self._extract_modifiers(child, source)
                annotations = self._extract_annotations(child, source)
                continue

            if child.type == "variable_declarator":
                declarator_name = self._find_identifier_text(child, source)
                if declarator_name:
                    names.append(declarator_name)
                continue

            if field_type is None and child.type not in {";", ","}:
                field_type = self._slice(child, source)

        fields = []
        for name in names:
            fields.append(
                {
                    "name": name,
                    "type": field_type or "",
                    "annotations": annotations,
                    "modifiers": modifiers,
                }
            )
        return fields

    def _parse_method(self, node, source):
        method_name = self._find_identifier_text(node, source)
        method_signature = source[node.start_byte:node.end_byte].strip().split("{", 1)[0].strip()
        parameters = []
        modifiers = []
        annotations = []
        return_type = ""

        for child in node.children:
            if child.type == "modifiers":
                modifiers = self._extract_modifiers(child, source)
                annotations = self._extract_annotations(child, source)
                continue

            if child.type == "formal_parameters":
                parameters = self._parse_parameters(child, source)
                continue

            if node.type == "method_declaration" and not return_type and child.type not in {
                "modifiers",
                "type_parameters",
                "identifier",
                "formal_parameters",
                "dimensions",
                "throws",
                "block",
            }:
                return_type = self._slice(child, source)

        return {
            "name": method_name,
            "signature": method_signature,
            "return_type": return_type if node.type == "method_declaration" else "",
            "parameters": parameters,
            "annotations": annotations,
            "modifiers": modifiers,
        }

    def _parse_parameters(self, node, source):
        parameters = []
        for child in node.named_children:
            parameter_name = self._find_identifier_text(child, source)
            parameter_type = ""

            for grandchild in child.children:
                if grandchild.type == "identifier":
                    continue
                if grandchild.type in {"modifiers", ","}:
                    continue
                if not parameter_type:
                    parameter_type = self._slice(grandchild, source)

            if parameter_name:
                parameters.append(
                    {
                        "name": parameter_name,
                        "type": parameter_type,
                    }
                )
        return parameters

    def _extract_annotations(self, node, source):
        annotations = []
        for child in node.children:
            if "annotation" in child.type:
                annotations.append(self._slice(child, source))
        return annotations

    def _extract_modifiers(self, node, source):
        modifiers = []
        for child in node.children:
            if "annotation" in child.type:
                continue
            text = self._slice(child, source)
            if text:
                modifiers.append(text)
        return modifiers

    def _find_identifier_text(self, node, source):
        if node.type == "identifier":
            return self._slice(node, source)

        for child in node.children:
            identifier = self._find_identifier_text(child, source)
            if identifier:
                return identifier

        return None

    @staticmethod
    def _clean_clause(text, keyword):
        value = text.strip()
        if value.startswith(keyword):
            value = value[len(keyword):].strip()
        return value or None

    @staticmethod
    def _split_interfaces(value):
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _normalize_package(package_stmt):
        return (
            package_stmt.replace("package", "")
            .replace(";", "")
            .strip()
        )

    @staticmethod
    def _slice(node, source):
        return source[node.start_byte:node.end_byte].strip()
