"""Private progress and decoded JSON-string bounds for poster planning streams."""
import json,time

class FieldLimit(ValueError):
    def __init__(self,path,limit,count):
        self.path=path;self.limit=limit;self.count=count
        super().__init__(f'Il campo JSON {path} supera il limite di {limit} caratteri ({count} già prodotti). Conserva i testi obbligatori e correggi soltanto il campo troppo lungo; non aggiungere ripetizioni o nuove informazioni.')

class Progress:
    """Observe a cumulative stream once; never truncate or publish the copy.

    Native GBNF omits large string bounds to avoid parser recursion overflow.
    This observer enforces those *original* bounds as soon as they are really
    exceeded. Escapes and surrogate pairs count as decoded characters, not
    serialized bytes. Malformed JSON prefixes remain the final parser's job.
    """
    def __init__(self,schema,folder,attempt,stage,clock=time.monotonic):
        self.schema=schema;self.folder=folder;self.attempt=attempt;self.stage=stage;self.clock=clock
        self.stack=[];self.string=False;self.key_string=False;self.key_parts=[];self.escape=False;self.hex=None;self.high=None;self.count=0;self.limit=None;self.path='$'
        self.cursor=0;self.raw='';self.valid=True;self.primitive=False;self.root_started=False;self.last=-1e9;self.reasoning_events=0
    def expected(self):
        if not self.stack:return self.schema,'$'
        frame=self.stack[-1]
        if frame['kind']=='object':return frame['schema'].get('properties',{}).get(frame.get('key'),{}),frame['path']+'.'+str(frame.get('key','?'))
        return frame['schema'].get('items',{}),frame['path']+'['+str(frame['index'])+']'
    def consumed(self):
        if not self.stack:self.root_started=True;return
        frame=self.stack[-1];frame['expect']='comma'
        if frame['kind']=='array':frame['index']+=1
    def decoded(self,point):
        if self.high is not None:
            high=self.high;self.high=None
            if 0xDC00<=point<=0xDFFF:self.character(chr(0x10000+((high-0xD800)<<10)+point-0xDC00));return
            self.character(chr(high))
        if 0xD800<=point<=0xDBFF:self.high=point
        else:self.character(chr(point))
    def character(self,value):
        if self.key_string:self.key_parts.append(value);return
        self.count+=1
        if self.valid and self.limit is not None and self.count>self.limit:raise FieldLimit(self.path,self.limit,self.count)
    def scan(self,char):
        if self.string:
            if self.hex is not None:
                self.hex+=char
                if len(self.hex)==4:
                    digits=self.hex;self.hex=None
                    try:self.decoded(int(digits,16))
                    except ValueError as error:
                        if isinstance(error,FieldLimit):raise
                        self.valid=False
                return
            if self.escape:
                self.escape=False
                if char=='u':self.hex='';return
                values={'"':'"','\\':'\\','/':'/','b':'\b','f':'\f','n':'\n','r':'\r','t':'\t'}
                if char not in values:self.valid=False
                else:self.decoded(ord(values[char]))
                return
            if char=='\\':self.escape=True;return
            if char=='"':
                if self.high is not None:self.character(chr(self.high));self.high=None
                self.string=False
                if self.key_string:
                    self.stack[-1].update(key=''.join(self.key_parts),expect='colon')
                else:self.consumed()
                return
            if ord(char)<32:self.valid=False
            self.decoded(ord(char));return
        if self.primitive:
            if char not in ',}] \r\n\t':return
            self.primitive=False;self.consumed()
        if char.isspace():return
        if char=='"':
            self.string=True;self.escape=False;self.hex=None;self.high=None;self.count=0;self.key_parts=[]
            self.key_string=bool(self.stack and self.stack[-1]['kind']=='object' and self.stack[-1]['expect']=='key')
            node,self.path=self.expected();self.limit=node.get('maxLength') if not self.key_string else None
            return
        if char in '{[':
            node,path=self.expected();self.consumed();kind='object' if char=='{' else 'array'
            self.stack.append({'schema':node,'path':path,'kind':kind,'expect':'key' if kind=='object' else 'value','index':0});return
        if char in '}]':
            if not self.stack or self.stack[-1]['kind']!=('object' if char=='}' else 'array'):self.valid=False
            elif self.stack:self.stack.pop()
            return
        if char==':' and self.stack and self.stack[-1]['kind']=='object':self.stack[-1]['expect']='value';return
        if char==',' and self.stack:self.stack[-1]['expect']='key' if self.stack[-1]['kind']=='object' else 'value';return
        if char in '-0123456789tfn':self.primitive=True;return
        self.valid=False
    def persist(self,status='streaming',force=False,error=None):
        now=self.clock()
        if not force and now-self.last<1:return
        self.last=now;self.folder.mkdir(parents=True,exist_ok=True)
        # Diagnostic only, never a ready plan. Bound disk usage independently
        # of the caller's generation/token budget; retain metadata if truncated.
        cap=2_000_000
        (self.folder/f'poster-plan-{self.attempt}.partial.json').write_text(self.raw[:cap],encoding='utf8',errors='replace')
        info={'status':status,'json_characters':len(self.raw),'current_field':self.path if self.string and not self.key_string else None,'field_decoded_characters':self.count if self.string and not self.key_string else None,'reasoning_events':self.reasoning_events,'diagnostic_truncated':len(self.raw)>cap}
        if error:info.update(limit_exceeded={'path':error.path,'limit':error.limit,'decoded_characters':error.count})
        (self.folder/f'poster-plan-{self.attempt}.partial-state.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
        self.stage('Locandine · contenuti e direzione artistica · '+str(len(self.raw))+' caratteri JSON'+(' · ragionamento del modello' if self.reasoning_events and not self.raw else ''))
    def __call__(self,text):
        self.raw=text
        if len(text)<self.cursor:self.valid=False;self.cursor=len(text)
        try:
            for char in text[self.cursor:]:self.scan(char)
            self.cursor=len(text)
        except FieldLimit as error:
            self.persist('field_limit',True,error);raise
        self.persist()
    def reasoning(self):self.reasoning_events+=1;self.persist()
    def finish(self):self.persist('completed',True)
