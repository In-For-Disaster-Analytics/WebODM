"""Database-free checks for the fork's release reconciliation boundaries."""
import ast
import mimetypes
import re
import tempfile
import unittest
from pathlib import Path
from wsgiref.util import FileWrapper

from django.http import FileResponse, HttpResponse, StreamingHttpResponse

ROOT = Path(__file__).resolve().parents[2]


class UpgradeCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load only the file-serving helper, without importing models or booting Django.
        tree = ast.parse((ROOT / 'app/api/tasks.py').read_text())
        nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                 and node.name in ('RangeFileWrapper', 'download_file_response')]
        namespace = dict(re=re, os=__import__('os'), mimetypes=mimetypes,
                         HttpResponse=HttpResponse, StreamingHttpResponse=StreamingHttpResponse,
                         FileResponse=FileResponse, FileWrapper=FileWrapper)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'download_helpers', 'exec'), namespace)
        cls.download = staticmethod(namespace['download_file_response'])

    def test_ranges_and_closeable_stream(self):
        from django.conf import settings
        if not settings.configured:
            settings.configure(DEFAULT_CHARSET='utf-8')
        for header, code, expected in [('bytes=2-4', 206, b'234'), ('bytes=-3', 206, b'789'),
                                       ('bytes=8-', 206, b'89'), ('bytes=10-', 416, b''),
                                       ('bytes=4-2', 416, b''), ('bytes=-0', 416, b'')]:
            with self.subTest(header=header), tempfile.NamedTemporaryFile() as file:
                file.write(b'0123456789')
                file.flush()
                request = type('Request', (), {'META': {'HTTP_RANGE': header}, 'GET': {}})()
                response = self.download(request, file.name, 'attachment')
                self.assertEqual(response.status_code, code)
                body = b''.join(response.streaming_content) if response.streaming else response.content
                self.assertEqual(body, expected)
                response.close()

    def test_new_upload_endpoints_keep_allocation_guard(self):
        for relative, names in [('app/api/media.py', ['TaskMediaUpload']),
                                ('app/api/splats.py', ['TaskSplatsUpload']),
                                ('app/api/tasks.py', ['TaskExternalImportInit', 'TaskExternalImportUpload', 'TaskExternalImportCommit'])]:
            tree = ast.parse((ROOT / relative).read_text())
            classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
            for name in names:
                with self.subTest(endpoint=name):
                    guards = [node for node in classes[name].body if isinstance(node, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == 'permission_classes' for t in node.targets)]
                    self.assertEqual(len(guards), 1, 'A later assignment would override the allocation guard')
                    self.assertIn('HasRequiredAllocation', ast.dump(guards[0]))

    def test_migration_graph_has_single_app_leaf(self):
        dependencies = {}
        for path in (ROOT / 'app/migrations').glob('*.py'):
            if path.stem == '__init__':
                continue
            tree = ast.parse(path.read_text())
            migration = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Migration')
            assignment = next(n for n in migration.body if isinstance(n, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == 'dependencies' for t in n.targets))
            dependencies[path.stem] = [ast.literal_eval(n) for n in assignment.value.elts if isinstance(n, ast.Tuple)]
        referenced = set()
        for name, deps in dependencies.items():
            for app, dependency in deps:
                if app == 'app':
                    self.assertIn(dependency, dependencies, (name, dependency))
                    referenced.add(dependency)
        self.assertEqual(set(dependencies) - referenced, {'0057_setting_organization_website'})


if __name__ == '__main__':
    unittest.main()
