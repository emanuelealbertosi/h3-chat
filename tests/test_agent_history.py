import json
import unittest
from h3chat.agent_history import search,read
from h3chat.agent_tools import validate,writes


class RunHistory(unittest.TestCase):
    def setUp(self):
        self.state={'id':'a'*32,'actions':[{'id':f'{i:032x}','tool':'create_files','status':'done',
            'summary':f'Risultato {i}','arguments':{'name':str(i)},'result':{'code':'BORGO-918' if i==0 else 'test','body':'x'*20000}} for i in range(20)]}

    def test_old_result_is_retrievable_after_it_left_recent_context(self):
        result=search(self.state,'BORGO-918')
        self.assertEqual(result['matched'],1);self.assertEqual(result['matches'][0]['id'],'0'*32)
        ident=result['matches'][0]['id'];parts=[];offset=0
        while True:
            row=read(self.state,ident,offset,1000);parts.append(row['data'])
            if row['next_offset'] is None:break
            offset=row['next_offset']
        self.assertEqual(json.loads(''.join(parts))['result']['body'],'x'*20000)

    def test_other_run_ids_and_executing_actions_are_not_readable(self):
        with self.assertRaises(ValueError):read(self.state,'f'*32)
        self.state['actions'][0]['status']='executing'
        self.assertEqual(search(self.state,'BORGO-918')['matched'],0)
        with self.assertRaises(ValueError):read(self.state,'0'*32)

    def test_readonly_bounded_schema(self):
        self.assertFalse(writes('search_run_history',{}));self.assertFalse(writes('read_run_action',{}))
        with self.assertRaises(ValueError):validate('read_run_action',{'action_id':'a'*32,'limit':999999})
        self.assertEqual(len(search(self.state,limit=3)['matches']),3)
        with self.assertRaises(ValueError):read(self.state,'0'*32,offset=9999999)
