from .java_ast_parser import JavaASTParser


class ASTParser:

    def __init__(self):
        self.java_parser = JavaASTParser()

    def parse(self, file):

        ext = file["extension"]

        if ext == ".java":
            return self.java_parser.parse(file)

        raise Exception(f"Unsupported language: {ext}")