"""Exercise the actual data-commit shell block against a concurrent local push."""
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

class WorkflowTests(unittest.TestCase):
    def test_data_commit_rebases_over_new_source_commit(self):
        def git(where,*args):
            return subprocess.run(['git', '-C', str(where), *args],check=True,text=True,capture_output=True).stdout
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/update.yml').read_text()
        script=textwrap.dedent(workflow.split('      - name: Record collected data\n        run: |\n',1)[1].split('\n      - uses:',1)[0])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            git(root,'init','--bare','--initial-branch=main','origin.git')
            git(root,'clone',str(root/'origin.git'),'collector')
            collector=root/'collector'
            git(collector,'config','user.name','Test')
            git(collector,'config','user.email','test@example.org')
            (collector/'README.md').write_text('initial source\n')
            git(collector,'add','.')
            git(collector,'commit','-m','initial')
            git(collector,'push','origin','main')
            git(root,'clone','--depth','1',(root/'origin.git').as_uri(),'shallow-collector')
            collector=root/'shallow-collector'
            self.assertEqual(git(collector,'rev-parse','--is-shallow-repository').strip(),'true')
            git(root,'clone',str(root/'origin.git'),'human')
            human=root/'human'
            git(human,'config','user.name','Test')
            git(human,'config','user.email','test@example.org')
            (human/'README.md').write_text('concurrent source update\n')
            git(human,'add','.')
            git(human,'commit','-m','source update during collection')
            git(human,'push','origin','main')
            (collector/'site/data').mkdir(parents=True)
            (collector/'site/data/latest.json').write_text('{"collection":"new"}\n')
            subprocess.run(['bash','-e','-c',script],cwd=collector,check=True,capture_output=True,text=True)
            self.assertEqual(git(root/'origin.git','show','main:README.md'),'concurrent source update\n')
            self.assertEqual(git(root/'origin.git','show','main:site/data/latest.json'),'{"collection":"new"}\n')
