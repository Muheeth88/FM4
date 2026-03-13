import os
from .java_ast_parser import JavaASTParser


class ASTParser:

    def __init__(self):
        self.java_parser = JavaASTParser()

    def parse(self, file):
        ext = file["extension"]

        if ext == ".java":
            return self.java_parser.parse(file)

        return self._parse_generic(file)

    @staticmethod
    def _parse_generic(file):
        path = file["path"]
        relative_hint = path.replace("\\", "/").lower()
        is_binary = file["extension"] in {".xlsx"}

        ast = {
            "path": path,
            "name": file["name"],
            "extension": file["extension"],
            "imports": [],
            "parser": "generic",
            "is_binary": is_binary,
            "content_preview": "",
            "size": 0,
            "relative_hint": relative_hint,
        }

        try:
            ast["size"] = os.path.getsize(path)
            if not is_binary:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    ast["content_preview"] = handle.read(4000)
        except OSError:
            pass

        return ast
