"""Offline tests for generate.py: python3 -m unittest discover tests"""
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate  # noqa: E402

ADDON_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<addon id="plugin.test" version="1.0.0"/>\n'
FILES = {
    'addon.xml': ADDON_XML,
    'default.py': '',
    'resources/lib/main.py': '',
    'NOTES.md': '',
    'tools/build.sh': '',
    'README.md': '',
    '.gitattributes': 'NOTES.md export-ignore\ntools export-ignore\n.gitattributes export-ignore\n',
}


class SourceZipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, 'plugin.test')
        for rel, text in FILES.items():
            path = os.path.join(self.src, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(text)
        subprocess.check_call(['git', 'init', '-q', self.src])
        subprocess.check_call(['git', 'add', '-A'], cwd=self.src)
        self.out = generate.OUT
        generate.OUT = os.path.join(self.tmp.name, 'zips')

    def tearDown(self):
        generate.OUT = self.out
        self.tmp.cleanup()

    def test_export_ignore_left_out(self):
        with zipfile.ZipFile(generate.zip_source(self.src)) as z:
            names = sorted(z.namelist())
        self.assertEqual(names, ['plugin.test/addon.xml', 'plugin.test/default.py',
                                 'plugin.test/resources/lib/main.py'])


if __name__ == '__main__':
    unittest.main()
