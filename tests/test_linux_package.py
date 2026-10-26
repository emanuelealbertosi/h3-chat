import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from scripts.verify_linux_package import verify


class LinuxPackageTests(unittest.TestCase):
    @unittest.skipIf(__import__('os').name=='nt','Linux packaging hardlinks')
    def test_only_identical_libraries_are_compacted_without_changing_paths(self):
        from scripts.compact_linux_runtime import compact
        import os
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'runtime'
            for name,data in (('a',b'a'),('b',b'a'),('c',b'b')):
                p=base/name/'libsample.so';p.parent.mkdir(parents=True);p.write_bytes(data*1024**2)
            result=compact(folder)
            self.assertEqual(result['hardlinks_created'],1)
            self.assertTrue(os.path.samefile(base/'a/libsample.so',base/'b/libsample.so'))
            self.assertFalse(os.path.samefile(base/'a/libsample.so',base/'c/libsample.so'))
            self.assertEqual((base/'c/libsample.so').read_bytes(),b'b'*1024**2)

    def archive(self,folder,extra=None):
        target=Path(folder)/'package.tar.gz'
        required=('Avvia-H3-Chat.sh','Ferma-H3-Chat.sh','Installa-dipendenze-Linux.sh','runtime/python/bin/python3','native/h3-sd-worker','runtime/cpu/llama/llama-server','skills/h3/SKILL.md')
        with tarfile.open(target,'w:gz') as package:
            for name in required:
                item=tarfile.TarInfo('H3-Chat/'+name);item.size=4;package.addfile(item,io.BytesIO(b'test'))
            if extra:package.addfile(extra)
        digest=hashlib.sha256(target.read_bytes()).hexdigest();target.with_name(target.name+'.sha256').write_text(digest+'  '+target.name)
        return target

    def test_complete_archive_is_read_and_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            report=verify(self.archive(folder));self.assertEqual(report['regular_files'],7);self.assertTrue(report['all_member_payloads_read'])

    def test_private_files_and_path_traversal_are_rejected(self):
        for name in ('H3-Chat/data/chat.sqlite','H3-Chat/docs/h3-session-state.json','H3-Chat/../../outside'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):verify(self.archive(folder,tarfile.TarInfo(name)))

    def test_external_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            item=tarfile.TarInfo('H3-Chat/runtime/link');item.type=tarfile.SYMTYPE;item.linkname='../../../outside'
            with self.assertRaisesRegex(ValueError,'External'):verify(self.archive(folder,item))

    def test_archive_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target=self.archive(folder);target.with_name(target.name+'.sha256').write_text('0'*64)
            with self.assertRaisesRegex(ValueError,'checksum'):verify(target)
