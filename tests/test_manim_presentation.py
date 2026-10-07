import base64,io,json,subprocess,tempfile,threading,unittest,zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.manim_presentation import options,build,PPTX,aligned_source
from h3chat.store import DEFAULTS

ROOT=Path(__file__).resolve().parents[1]
def pptx_bytes(image=None):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('ppt/presentation.xml','<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="second"/><p:sldId r:id="first"/></p:sldIdLst><p:sldSz cx="9144000" cy="6858000"/></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="first" Target="slides/slide1.xml"/><Relationship Id="second" Target="slides/slide2.xml"/></Relationships>')
        for i,text in ((1,'SECONDA'),(2,'PRIMA')):
            z.writestr(f'ppt/slides/slide{i}.xml','<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:spPr><a:xfrm><a:off x="914400" y="914400"/><a:ext cx="6000000" cy="2000000"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:p><a:r><a:rPr sz="3000"><a:solidFill><a:srgbClr val="112233"/></a:solidFill></a:rPr><a:t>'+text+'</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
        if image:
            name='ppt/slides/slide2.xml'
            # Rebuild this member below to avoid duplicate ZIP entries.
            picture='<p:pic><p:blipFill><a:blip r:embed="picture"/></p:blipFill><p:spPr><a:xfrm><a:off x="5000000" y="4000000"/><a:ext cx="2000000" cy="1500000"/></a:xfrm></p:spPr></p:pic>'
            original=z.read(name).decode().replace('<p:sld ', '<p:sld xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ').replace('</p:spTree>',picture+'</p:spTree>')
            z.writestr('ppt/slides/_rels/slide2.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="picture" Target="../media/picture.png"/></Relationships>')
            z.writestr('ppt/media/picture.png',image)
    if image:
        rebuilt=io.BytesIO()
        with zipfile.ZipFile(stream) as source,zipfile.ZipFile(rebuilt,'w') as dest:
            for name in source.namelist():dest.writestr(name,original if name=='ppt/slides/slide2.xml' else source.read(name))
        return rebuilt.getvalue()
    return stream.getvalue()

class PresentationTests(unittest.TestCase):
    def test_controls_require_real_supported_source(self):
        self.assertIsNone(options(None,[]))
        for media in ([],[{'mime':'audio/wav'}],[{'mime':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}]):
            with self.assertRaises(ValueError):options({},media)
        self.assertEqual(options({},[{'mime':PPTX}])['mode'],'preserve')
        with self.assertRaises(ValueError):options({'mode':'bogus'},[{'mime':'image/png'}])

    def test_pptx_upload_and_request_validation(self):
        from h3chat.service import Service
        with tempfile.TemporaryDirectory() as tmp:
            app=Service(ROOT,tmp,start_worker=False)
            try:
                item=app.upload({'name':'deck.pptx','data':base64.b64encode(pptx_bytes()).decode()})
                self.assertEqual(item['mime'],PPTX)
                chat=app.store.create_chat()
                with patch.object(app.engine,'require_model',return_value={'id':'fixture'}):
                    with self.assertRaises(ValueError):app.send(chat['id'],{'prompt':'Anima','lab':'manim','manim_presentation':{},'media':[]})
                    sent=app.send(chat['id'],{'prompt':'Anima','lab':'manim','manim_presentation':{},'media':[item]})
                payload=json.loads(app.store.one('select payload from jobs where id=?',(sent['job_id'],))['payload'])
                self.assertEqual(payload['settings']['_manim_presentation']['mode'],'preserve')
                self.assertEqual(app.store.messages(chat['id'])[0]['meta']['manim_presentation']['mode'],'preserve')
            finally:app.close()

    def flow(self,mode,narrated=False):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);app=Mock(root=ROOT,data=data);app.store.messages.return_value=[]
            app.engine.chat_messages.side_effect=lambda h,m,s,format_instructions=None:[{'role':'system','content':format_instructions},*h]
            pages=[];requests=[];prompts=[]
            def worker(name,request,*args,**kw):
                requests.append((name,request))
                if name=='presentation-worker.py':
                    folder=Path(request['output']);folder.mkdir(parents=True)
                    for i in (1,2):
                        path=folder/f'slide-{i:03}.png';path.write_bytes(b'fixture')
                        pages.append({'number':i,'original':'slide '+str(i),'text':'Argomento '+str(i),'aspect':4/3,'regions':[],
                            'assets':[{'name':path.name,'path':str(path),'original':'slide '+str(i)}]})
                    return {'pages':pages,'warnings':[]}
                if name=='manim-worker.py':
                    folder=Path(request['output']);p=folder/'animation.mp4';p.write_bytes(b'fixture');return {'path':str(p),'duration':1}
                if name=='media-compose-worker.py':
                    p=Path(request['output']);p.write_bytes(b'fixture');return {'path':str(p),'duration':sum(request['durations'])}
                raise AssertionError(name)
            def complete(messages,*args,**kw):
                prompts.append(messages)
                if 'narration' in kw['schema']['properties']:return json.dumps({'narration':'Spiegazione.','visual':'Evidenzia il concetto.'}),'stop'
                return json.dumps({'title':'Pagina','scene_name':'Demo','code':'from manim import *\nclass Demo(Scene):\n def construct(self): self.wait(1)'}),'stop'
            app.engine.tool_call.side_effect=worker;app.engine.completion.side_effect=complete
            settings=DEFAULTS|{'_manim_presentation':{'mode':mode,'source':'attachments'},'_manim_voice':narrated,'vision_enabled':False}
            payload={'prompt':'Anima in 10 secondi','media':[{'name':'Source.pdf','mime':'application/pdf','path':'uploads/source.pdf'}],'canvas':True}
            (data/'uploads').mkdir();(data/'uploads/source.pdf').write_bytes(b'%PDF-fixture')
            history=[{'role':'user','content':payload['prompt'],'media':payload['media'],'status':'done','seq':1}]
            def speech(app,folder,parts,*args):
                folder.mkdir(parents=True);p=folder/'voice.wav';p.write_bytes(b'fixture')
                return {'duration':6,'timeline':[{'scene_id':0,'text':'Uno.','start':0,'end':2},{'scene_id':1,'text':'Due.','start':2,'end':6}]},[{'id':'voice','name':'voice.wav','mime':'audio/wav','path':p.relative_to(data).as_posix()}]
            with patch('h3chat.tools_runtime.status',return_value={'lab':{'ready':True},'documents':{'ready':True},'latex':{'ready':True}}),patch('h3chat.voice.configuration'),patch('h3chat.voice.synthesize',side_effect=speech):
                meta={};_,_,media=build(app,{'id':'job','chat_id':'chat'},payload,history,settings,{'id':'fixture','vision':{'enabled':False}},threading.Event(),lambda _:None,data/'log',meta)
            renders=[r for n,r in requests if n=='manim-worker.py'];self.assertEqual(len(renders),2)
            self.assertEqual([r['assets'][0]['name'] for r in renders],['slide-001.png','slide-002.png'])
            self.assertEqual(renders[0]['options']['width']/renders[0]['options']['height'],4/3)
            self.assertEqual(renders[0]['presentation']['show_background'],mode=='preserve')
            self.assertEqual(renders[0]['presentation']['geometry'],1 if mode=='preserve' else 2)
            if mode=='reconstruct':self.assertTrue(any('slide.place' in str(p) for p in prompts))
            mux=next(r for n,r in requests if n=='media-compose-worker.py')
            self.assertEqual(mux['durations'],[2,4] if narrated else [5,5]);self.assertEqual(bool(mux['audio']),narrated)
            self.assertEqual(media[0]['mime'],'video/mp4');self.assertEqual(meta['manim_slide_count'],2)
            self.assertTrue(all(not m.get('media') for p in prompts for m in p))
    def test_preserve_render_order_aspect_and_silent_mux(self):self.flow('preserve')
    def test_reconstruct_and_voice_timing(self):self.flow('reconstruct',True)

    def test_pixel_geometry_is_repaired_before_render_but_free_reconstruction_is_allowed(self):
        from h3chat.manim_code import SCHEMA
        bad={'title':'Pixel','scene_name':'Demo','code':'from manim import *\nclass Demo(Scene):\n def construct(self): self.add(Rectangle(width=864,height=486))'}
        good=bad|{'code':'from manim import *\nclass Demo(Scene):\n def construct(self): self.add(slide.box("text-001"))'}
        engine=Mock();engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(good),'stop')]
        self.assertEqual(aligned_source(engine,[],DEFAULTS,threading.Event(),lambda _:None,'Codice',True),good)
        self.assertEqual(engine.completion.call_count,2)
        engine.completion.side_effect=[(json.dumps(bad),'stop')]
        self.assertEqual(aligned_source(engine,[],DEFAULTS,threading.Event(),lambda _:None,'Codice',False),bad)

    @unittest.skipUnless((ROOT/'runtime/tools/documents/pypdfium2/__init__.py').exists(),'Document runtime not installed')
    def test_real_pptx_import_keeps_relationship_order_and_aspect(self):
        import sys
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from PIL import Image
        picture=io.BytesIO();Image.new('RGB',(80,60),'#e02020').save(picture,format='PNG')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'deck.pptx';source.write_bytes(pptx_bytes(picture.getvalue()))
            result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/presentation-worker.py')],
                input=json.dumps({'inputs':[{'path':str(source),'name':'Deck.pptx'}],'output':str(folder/'output')})+'\n',capture_output=True,text=True,encoding='utf-8',timeout=150)
            events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            errors=[e for e in events if e['event']=='error'];self.assertFalse(errors,(errors,result.stderr))
            manifest=next(e['result'] for e in events if e['event']=='result');pages=manifest['pages']
            self.assertEqual(len(pages),2);self.assertIn('PRIMA',pages[0]['text']);self.assertIn('SECONDA',pages[1]['text'])
            self.assertAlmostEqual(pages[0]['aspect'],4/3,places=2)
            self.assertTrue(pages[0]['regions']);self.assertTrue(Path(pages[0]['assets'][0]['path']).is_file())
            self.assertTrue(any(a['kind']=='text' and 'PRIMA' in a['text'] for a in pages[0]['anchors']))
            region=next(r for r in pages[0]['regions'] if r['kind']=='image')
            self.assertAlmostEqual(region['left'],5000000/9144000,places=2)
            asset=next(a for a in pages[0]['assets'] if 'assets/'+a['name']==region['asset'])
            with Image.open(asset['path']) as cropped:
                pixel=cropped.getpixel((cropped.width//2,cropped.height//2))
                self.assertGreater(pixel[0],180);self.assertLess(pixel[2],80)

    @unittest.skipUnless((ROOT/'runtime/tools/lab/manim/__init__.py').exists(),'Manim runtime not installed')
    def test_actual_reconstruction_has_measured_helper_and_rejects_overflow(self):
        import sys
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);picture=folder/'slide.png';Image.new('RGB',(160,120),'#ffffff').save(picture)
            good='from manim import *\nclass Demo(Scene):\n def construct(self):\n  label=slide.place(Text("Titolo"),"title")\n  self.add(label)\n  self.wait(.2)'
            bad='from manim import *\nclass Demo(Scene):\n def construct(self):\n  self.add(Text("Fuori").move_to([10,0,0]))\n  self.wait(.2)'
            base={'assets':[{'name':'slide.png','path':str(picture),'original':'Synthetic slide'}],
                'presentation':{'background':'slide.png','geometry':2,'show_background':False,'anchors':[{'id':'title','left':.1,'top':.1,'width':.8,'height':.2}]},
                'options':{'width':320,'height':180,'fps':10,'device':'cpu','timeout':90,'memory_gb':4,'frame_width':128/9,'frame_height':8}}
            requests=[base|{'source':{'title':'Layout','scene_name':'Demo','code':code},'output':str(folder/str(i))} for i,code in enumerate((good,bad))]
            result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/manim-worker.py')],
                input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,encoding='utf-8',timeout=240)
            events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            self.assertEqual(len([e for e in events if e['event']=='result']),1,result.stdout+result.stderr)
            errors=[e for e in events if e['event']=='error'];self.assertEqual(len(errors),1,result.stdout)
            self.assertIn('fuori inquadratura',errors[0]['message'])

    @unittest.skipUnless((ROOT/'runtime/tools/lab/manim/__init__.py').exists(),'Manim runtime not installed')
    def test_actual_isolated_render_keeps_original_pixels_after_scene_clear(self):
        import sys
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from PIL import Image,ImageDraw
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);picture=folder/'slide.png';image=Image.new('RGB',(160,120),'#e02020')
            ImageDraw.Draw(image).rectangle((80,0,159,119),fill='#2020e0');image.save(picture)
            request={'source':{'title':'Pixel fidelity','scene_name':'Demo','code':'from manim import *\nclass Demo(Scene):\n def construct(self):\n  self.clear()\n  self.add(slide.box("right",padding=0,color="#00ff00",stroke_width=12))\n  self.wait(.4)'},
                'assets':[{'name':'slide.png','path':str(picture),'original':'Synthetic slide'}],
                'presentation':{'background':'slide.png','geometry':1,'anchors':[{'id':'right','left':.5,'top':0,'width':.5,'height':1}]},
                'output':str(folder/'render'),'options':{'width':320,'height':180,'fps':10,'device':'cpu','timeout':90,'memory_gb':4,'frame_width':128/9,'frame_height':8}}
            result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/manim-worker.py')],input=json.dumps(request)+'\n',capture_output=True,text=True,encoding='utf-8',timeout=150)
            events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            self.assertFalse([e for e in events if e['event']=='error'],result.stdout+result.stderr)
            rendered=next(e['result'] for e in events if e['event']=='result')
            check=r'''
import os,sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path[:0]=[str(root/'runtime/tools/documents'),str(root/'runtime/tools/lab')]
dll=os.add_dll_directory(str(root/'runtime/tools/documents')) if os.name=='nt' else None
import av
with av.open(sys.argv[2]) as video:
 frames=list(video.decode(video=0));assert frames
 for frame in frames:
  pixels=frame.to_ndarray(format='rgb24')
  left=pixels[90,100];right=pixels[90,220];border=pixels[90,158:163];peak=border[border[:,1].argmax()]
  assert left[0]>180 and left[2]<80,(left,right)
  assert right[2]>180 and right[0]<80,(left,right)
  assert int(peak[1])>180 and int(peak[1])-int(peak[0])>90 and int(peak[1])-int(peak[2])>90,border
  assert pixels[90,150,1]<100 and pixels[90,170,1]<100
print('Original pixels and measured annotation aligned with letterboxing in all frames')
'''
            verified=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8','-c',check,str(ROOT),rendered['path']],capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(verified.returncode,0,verified.stderr)

if __name__=='__main__':unittest.main()
