import base64,json,struct,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
from h3chat.service import Service
from h3chat.slide_images import request,download
ROOT=Path(__file__).resolve().parents[1]

def png():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([30,90,140])*2)*2))+chunk(b'IEND',b'')

class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.app=Service(ROOT,self.tmp.name,start_worker=False);self.addCleanup(self.app.close)
        self.project=self.app.knowledge.save({'name':'Libro'});self.chat=self.app.store.create_chat(project_id=self.project['id'])
        self.media=self.app.upload({'name':'Figura.png','data':base64.b64encode(png()).decode()})
        self.app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('source',self.project['id'],str(self.app.data/self.media['path']),'Libro.pdf'))
        self.app.store.execute('INSERT INTO rag_chunks(source_id,location,page,text,image_path,modality) VALUES (?,?,?,?,?,?)',('source','pagina 20',20,'Diagramma batteria',self.media['path'],'image'))

    def test_rag_gallery_search_import_and_normalized_upload(self):
        value=request(self.app,'rag',{'chat_id':self.chat['id'],'query':'batteria'})
        self.assertEqual(len(value['items']),1);self.assertTrue(value['items'][0]['thumbnail'].startswith('data:image/jpeg'))
        self.assertEqual(request(self.app,'rag',{'chat_id':self.chat['id'],'query':'inesistente'})['items'],[])
        media=request(self.app,'import',{'chat_id':self.chat['id'],'source':'rag','id':value['items'][0]['id']})
        self.assertEqual(media['mime'],'image/jpeg');self.assertEqual(media['provenance']['kind'],'rag')
        self.assertEqual(self.app.validate_media([media],canvas=True)[0]['provenance'],media['provenance'])
        other=self.app.store.create_chat()
        self.assertEqual(request(self.app,'rag',{'chat_id':other['id']})['items'],[])
        with self.assertRaisesRegex(ValueError,'progetto'):request(self.app,'import',{'chat_id':other['id'],'source':'rag','id':value['items'][0]['id']})

    def test_web_results_and_attribution_use_bounded_commons_downloads(self):
        info={'query':{'pages':{'1':{'title':'File:Batteria.png','imageinfo':[{'thumburl':'https://upload.wikimedia.org/example.png','descriptionurl':'https://commons.wikimedia.org/wiki/File:Batteria.png','extmetadata':{'Artist':{'value':'<b>Autore</b>'},'LicenseShortName':{'value':'CC BY 4.0'}}}]}}}}
        with patch('h3chat.slide_images.download',side_effect=[json.dumps(info).encode(),png()]):
            results=request(self.app,'search',{'chat_id':self.chat['id'],'query':'batteria'})
        self.assertEqual(results['items'][0]['credit'],'Autore');self.assertEqual(results['items'][0]['license'],'CC BY 4.0')
        with patch('h3chat.slide_images.download',return_value=png()):
            media=request(self.app,'import',{'chat_id':self.chat['id'],'source':'web',**results['items'][0]})
        self.assertEqual(media['provenance']['license'],'CC BY 4.0')
        for url in ('http://127.0.0.1/private','https://evil.example/x','file:///C:/private','https://upload.wikimedia.org.evil.example/x'):
            with self.assertRaises(ValueError):download(url)

if __name__=='__main__':unittest.main()
