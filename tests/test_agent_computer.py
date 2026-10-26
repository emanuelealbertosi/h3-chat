"""Capability boundaries and actual CPU programs; no elevation or real inference."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from h3chat import agent_computer as pc,agent_state
import test_agent_runtime as fixture
from test_agent_runtime import decision

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location('test_'+name,ROOT/'native'/name);value=importlib.util.module_from_spec(spec);old=sys.stdout
    try:spec.loader.exec_module(value)
    finally:sys.stdout=old
    return value

class ComputerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.app=SimpleNamespace(root=self.base/'app',data=self.base/'app/data')
        self.app.data.mkdir(parents=True);self.workspace=self.base/'workspace';self.workspace.mkdir();self.runner=module('agent-computer-runner.py')
    def tearDown(self):self.temp.cleanup()
    def request(self,op,args):return {'scope':'sandbox','root':str(self.workspace),'op':op,'args':args}
    def test_trusted_confirmation_role_and_nonforgeable_scope(self):
        with self.assertRaises(ValueError):pc.create(self.app,{'scope':'global'})
        grant=pc.create(self.app,{'scope':'global','confirmed':True});self.assertEqual(pc.grant(self.app,grant)['scope'],'global')
        with self.assertRaises(PermissionError):pc.grant(self.app,{'scope':'sandbox','grant_id':grant['grant_id']})
        pc.revoke(self.app,grant['grant_id'])
        with self.assertRaises(PermissionError):pc.grant(self.app,grant)
        self.app.execution_owner=object()
        with self.assertRaises(PermissionError):pc.create(self.app,{'scope':'global','confirmed':True})
    def test_sandbox_cannot_be_disk_app_data_or_linked_tree(self):
        for path in [self.app.root,self.app.data,self.base,Path(self.base.anchor)]:
            with self.subTest(path=path),self.assertRaises(ValueError):pc.create(self.app,{'scope':'sandbox','root':str(path),'confirmed':True})
        a=self.workspace/'link.txt';a.write_text('file');os.link(a,self.workspace/'alias.txt')
        with self.assertRaisesRegex(ValueError,'collegamenti'):pc.check_root(self.app,str(self.workspace))
    def test_sandbox_path_guards_hash_replace_backup_and_nonrecursive_delete(self):
        run=self.runner.run
        for path in ['../outside.txt','C:/outside.txt','private.txt:ads','/outside.txt']:
            with self.subTest(path=path),self.assertRaises((PermissionError,ValueError)):run(self.request('computer_files',{'operation':'write','path':path,'text':'bad'}))
        run(self.request('computer_files',{'operation':'write','path':'src/a.txt','text':'first line'}))
        old=run(self.request('computer_files',{'operation':'read','path':'src/a.txt'}))
        with self.assertRaises(ValueError):run(self.request('computer_files',{'operation':'write','path':'src/a.txt','text':'lost'}))
        run(self.request('computer_files',{'operation':'replace','path':'src/a.txt','find':'first','text':'next','expected_sha256':old['sha256']}))
        self.assertEqual((self.workspace/'src/a.txt').read_text(),'next line');self.assertTrue(list((self.workspace/'src').glob('*.h3-backup-*')))
        with self.assertRaises((PermissionError,OSError)):run(self.request('computer_files',{'operation':'remove','path':'.'}))
    @unittest.skipUnless(os.name=='nt','Windows CPU broker test')
    def test_global_real_program_exit_and_output_without_admin(self):
        worker=module('agent-computer-worker.py')
        request={'scope':'global','root':'','app_root':str(ROOT),'folder':str(self.base/'broker'),'op':'computer_run','args':{'engine':'python','workdir':str(self.workspace),'code':"from pathlib import Path\nPath('result.txt').write_text('created')\nprint('verified CPU')\nraise SystemExit(7)",'timeout':10}}
        result=worker.run(request);self.assertEqual(result['exit_code'],7);self.assertIn('verified CPU',result['output']);self.assertEqual((self.workspace/'result.txt').read_text(),'created')
    def test_admin_is_human_pause_and_rejected_outside_global(self):
        config=pc.create(self.app,{'scope':'global','confirmed':True});action={};state={'config':config}
        ctx=SimpleNamespace(app=self.app,state=state,action=action,persist=lambda:None)
        with self.assertRaises(pc.AwaitAdmin):pc.execute(ctx,'request_admin',{'command':'Get-Date','reason':'Test'})
        self.assertEqual(state['status'],'awaiting_admin');self.assertNotIn('admin_approved',action)
        state['config']=pc.create(self.app,{'scope':'sandbox','root':str(self.workspace),'confirmed':True})
        with self.assertRaises(PermissionError):pc.execute(ctx,'request_admin',{'command':'Get-Date','reason':'Test'})

class AdminFlowTests(fixture.AgentTests):
    # Inherit fixture helpers, not all AgentTests a second time.
    @unittest.skipUnless(os.name=='nt','Windows CPU integration')
    def test_file_repair_invalidates_command_cache_and_files_round_trip_h3(self):
        workspace=self.base/'workspace';workspace.mkdir();target=workspace/'input.txt';target.write_text('first')
        grant=pc.create(self.app,{'scope':'global','confirmed':True});chat,job=self.ticket('agent: Modifica il file e verifica il programma',confirm_writes=False,scope='global',grant_id=grant['grant_id'])
        n=[0];command={'engine':'python','code':"from pathlib import Path;print(Path('input.txt').read_text())",'workdir':str(workspace),'timeout':10};first=[None];second=[None]
        def choose(messages,*a,**kwargs):
            n[0]+=1;data=json.loads(messages[-1]['content']);last=json.loads(data['observations'][-1]['data']) if data['observations'] else {}
            if n[0]==1:return decision('computer_files',{'operation':'read','path':str(target)})
            if n[0]==2:first[0]=last['sha256'];return decision('computer_run',command)
            if n[0]==3:return decision('computer_run',command)
            if n[0]==4:return decision('computer_files',{'operation':'write','path':str(target),'text':'second','expected_sha256':first[0]})
            if n[0]==5:return decision('computer_files',{'operation':'read','path':str(target)})
            if n[0]==6:second[0]=last['sha256'];return decision('computer_run',command)
            if n[0]==7:return decision('import_computer_file',{'path':str(target)})
            if n[0]==8:return decision('export_computer_file',{'artifact_id':data['artifacts'][-1]['id'],'number':1,'path':str(workspace/'roundtrip.txt')})
            return decision('finish')
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=choose):self.app.execute_job(job,threading.Event())
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertTrue(all(a['status'] in ('done','reused') for a in state['actions']),state['actions'])
        commands=[a for a in state['actions'] if a['tool']=='computer_run'];self.assertEqual([a['status'] for a in commands],['done','reused','done']);self.assertIn('first',commands[0]['result']['output']);self.assertIn('second',commands[-1]['result']['output']);self.assertNotEqual(first[0],second[0]);self.assertEqual((workspace/'roundtrip.txt').read_text(),'second')
        self.assertNotIn('data',state['actions'][-2]['result'])
    def test_uac_request_releases_queue_and_cannot_resume_without_human_api(self):
        from h3chat.agent_admin import approve
        grant=pc.create(self.app,{'scope':'global','confirmed':True})
        chat,job=self.ticket('agent: Prepara operazione amministratore',confirm_writes=False,scope=grant['scope'],grant_id=grant['grant_id'])
        # UI root is display-only, not a model-settable option.
        n=[0]
        def choose(*a,**kw):
            n[0]+=1
            return decision('request_admin',{'command':'Write-Output test','reason':'Prova conferma'}) if n[0]==1 else decision('finish')
        self.run_job(job,choose)
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'awaiting_admin');ident=state['actions'][0]['id']
        with self.assertRaises(ValueError):agent_state.resume(self.app,chat,job['id'],{})
        with self.assertRaises(ValueError):approve(self.app,chat,job['id'],{'action_id':ident})
        result=approve(self.app,chat,job['id'],{'action_id':ident,'confirmed':True});self.assertNotEqual(result['job_id'],job['id'])
        self.assertEqual(approve(self.app,chat,job['id'],{'action_id':ident,'confirmed':True})['job_id'],result['job_id'])
        child=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],))
        answer,worker,_=self.run_job(child,lambda *a,**kw:decision('finish'),layout={'denied':True,'executed':False})
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'rejected');self.assertEqual(worker.call_count,1)
    @unittest.skipUnless(os.name=='nt' and os.environ.get('H3_COMPUTER_OS_TEST')=='1','Real Windows isolation opt-in')
    def test_real_sandbox_io_child_boundaries_and_stop_kills_descendants(self):
        import time
        from h3chat.downloads import Cancelled
        workspace=self.base/'workspace';workspace.mkdir();outside=self.base/'private.txt';outside.write_text('private')
        grant=pc.create(self.app,{'scope':'sandbox','root':str(workspace),'confirmed':True})
        worker=module('agent-computer-worker.py')
        request={'op':'computer_run','scope':'sandbox','root':str(workspace),'app_root':str(ROOT),'folder':str(self.base/'broker'),'args':{'engine':'python','code':"from pathlib import Path\nPath('created.txt').write_text('created')\ntry:Path("+repr(str(outside))+").read_text()\nexcept PermissionError:print('DENIED')",'timeout':10}}
        result=worker.run(request);self.assertEqual(result['exit_code'],0);self.assertIn('DENIED',result['output']);self.assertEqual(outside.read_text(),'private')
        request['folder']=str(self.base/'broker-stop');request['args']['code']="import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-I','-c',\"import time;from pathlib import Path;time.sleep(3);Path('leak.txt').write_text('leaked')\"])\nprint('CHILD_STARTED',flush=True)\ntime.sleep(30)";request['args']['timeout']=40
        cancel=threading.Event()
        def stop_after_spawn():
            until=time.monotonic()+20
            while time.monotonic()<until:
                logs=list((workspace/'.h3-tmp').glob('command-*.log'))
                if any(b'CHILD_STARTED' in p.read_bytes() for p in logs):cancel.set();return
                time.sleep(.1)
        threading.Thread(target=stop_after_spawn,daemon=True).start()
        with self.assertRaises(Cancelled):self.app.engine.tool_call('agent-computer-worker.py',request,cancel,lambda stage:None,self.base/'stop.log',timeout=30)
        time.sleep(3.5);self.assertFalse((workspace/'leak.txt').exists())

# unittest should not rerun the inherited baseline test methods.
for name in list(vars(fixture.AgentTests)):
    if name.startswith('test_'):setattr(AdminFlowTests,name,None)

if __name__=='__main__':unittest.main()
