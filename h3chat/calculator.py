"""A bounded Python syntax interpreter for numbers and data, without eval/exec or I/O."""
import ast
import json
import math
import operator

MATH={name:getattr(math,name) for name in ('sin','cos','tan','asin','acos','atan','atan2','sqrt','exp','log','log10','floor','ceil','fabs','hypot','degrees','radians')}
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
COMPARE={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge}

class Calculator:
    def __init__(self):self.values={'pi':math.pi,'e':math.e};self.output=[];self.steps=0
    def tick(self):
        self.steps+=1
        if self.steps>50000:raise ValueError('Calcolo troppo complesso: massimo 50.000 operazioni.')
    def bounded(self,value):
        if isinstance(value,(list,tuple,dict,str)) and len(value)>10000:raise ValueError('Valore troppo grande.')
        if isinstance(value,(list,tuple,dict)):
            pending=[(value,0)];count=0
            while pending:
                item,depth=pending.pop();count+=1
                if count>10000 or depth>64:raise ValueError('Struttura dati troppo grande o profonda.')
                if isinstance(item,(list,tuple)):pending.extend((x,depth+1) for x in item)
                elif isinstance(item,dict):pending.extend((x,depth+1) for pair in item.items() for x in pair)
                elif isinstance(item,str):count+=len(item)
        if type(value) is int and value.bit_length()>4096:raise ValueError('Intero troppo grande.')
        if type(value) is float and not math.isfinite(value):raise ValueError('Risultato numerico non finito.')
        return value
    def name(self,node):
        if not isinstance(node,ast.Name) or node.id.startswith('_') or node.id in ('math','print','range','sum','min','max','abs','round','len'):raise ValueError('Nome variabile non consentito.')
        return node.id
    def expr(self,node):
        self.tick()
        if isinstance(node,ast.Constant) and type(node.value) in (int,float,str,bool,type(None)):return self.bounded(node.value)
        if isinstance(node,ast.Name):
            if node.id not in self.values:raise ValueError('Variabile sconosciuta: '+node.id)
            return self.values[node.id]
        if isinstance(node,(ast.List,ast.Tuple)):return self.bounded([self.expr(x) for x in node.elts])
        if isinstance(node,ast.Dict):return self.bounded({self.expr(k):self.expr(v) for k,v in zip(node.keys,node.values)})
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub,ast.Not)):
            v=self.expr(node.operand);return self.bounded(not v if isinstance(node.op,ast.Not) else v if isinstance(node.op,ast.UAdd) else -v)
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:
            left,right=self.expr(node.left),self.expr(node.right)
            if not all(type(v) in (int,float,bool) for v in (left,right)) and not isinstance(node.op,(ast.Add,ast.Mult)):raise ValueError('Questa operazione richiede valori numerici.')
            if isinstance(node.op,ast.Pow) and abs(right)>1000:raise ValueError('Esponente troppo grande.')
            if isinstance(node.op,ast.Mult) and isinstance(left,(list,str)) and isinstance(right,int) and len(left)*right>10000:raise ValueError('Ripetizione troppo grande.')
            if isinstance(node.op,ast.Mult) and isinstance(right,(list,str)) and isinstance(left,int) and len(right)*left>10000:raise ValueError('Ripetizione troppo grande.')
            return self.bounded(OPS[type(node.op)](left,right))
        if isinstance(node,ast.Compare):
            left=self.expr(node.left)
            for op,rightnode in zip(node.ops,node.comparators):
                right=self.expr(rightnode)
                if type(op) not in COMPARE:raise ValueError('Confronto non supportato.')
                if not COMPARE[type(op)](left,right):return False
                left=right
            return True
        if isinstance(node,ast.IfExp):return self.expr(node.body if self.expr(node.test) else node.orelse)
        if isinstance(node,ast.Subscript):
            value=self.expr(node.value)
            if isinstance(node.slice,ast.Slice):index=slice(*(self.expr(x) if x else None for x in (node.slice.lower,node.slice.upper,node.slice.step)))
            else:index=self.expr(node.slice)
            return self.bounded(value[index])
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='math' and node.attr in ('pi','e'):return getattr(math,node.attr)
        if isinstance(node,ast.Call):
            if node.keywords:raise ValueError('Usa argomenti posizionali per i calcoli.')
            args=[self.expr(a) for a in node.args]
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='math' and node.func.attr in MATH:return self.bounded(MATH[node.func.attr](*args))
            if isinstance(node.func,ast.Name):
                name=node.func.id
                if name=='range':
                    value=range(*args)
                    if len(value)>10000:raise ValueError('Intervallo troppo grande.')
                    return list(value)
                if name=='print':
                    self.output.append(' '.join(str(a) for a in args))
                    if sum(map(len,self.output))>100000:raise ValueError('Output troppo lungo.')
                    return None
                functions={'sum':sum,'min':min,'max':max,'abs':abs,'round':round,'len':len}
                if name in functions:return self.bounded(functions[name](*args))
            raise ValueError('Funzione non consentita. Sono disponibili math, range, sum, min, max, abs, round, len e print.')
        if isinstance(node,ast.ListComp) and len(node.generators)==1 and not node.generators[0].is_async:
            gen=node.generators[0];name=self.name(gen.target);result=[];old=self.values.get(name);exists=name in self.values
            for item in self.expr(gen.iter):
                self.tick();self.values[name]=item
                if all(self.expr(test) for test in gen.ifs):result.append(self.expr(node.elt))
            if exists:self.values[name]=old
            else:self.values.pop(name,None)
            return self.bounded(result)
        raise ValueError('Sintassi non supportata nell’interprete numerico: '+type(node).__name__)
    def statement(self,node):
        self.tick()
        if isinstance(node,ast.Assign) and len(node.targets)==1:self.values[self.name(node.targets[0])]=self.expr(node.value)
        elif isinstance(node,ast.AugAssign) and type(node.op) in OPS:
            name=self.name(node.target);self.values[name]=self.expr(ast.BinOp(left=node.target,op=node.op,right=node.value))
        elif isinstance(node,ast.Expr):self.expr(node.value)
        elif isinstance(node,ast.Import) and all(n.name=='math' and n.asname in (None,'math') for n in node.names):pass
        elif isinstance(node,ast.For) and not node.orelse:
            name=self.name(node.target)
            for item in self.expr(node.iter):
                self.tick();self.values[name]=item
                for stmt in node.body:self.statement(stmt)
        elif isinstance(node,ast.If):
            for stmt in node.body if self.expr(node.test) else node.orelse:self.statement(stmt)
        else:raise ValueError('Istruzione non supportata nell’interprete numerico: '+type(node).__name__)
    def run(self,source):
        if not isinstance(source,str) or len(source)>20000:raise ValueError('Codice troppo lungo.')
        tree=ast.parse(source)
        if sum(1 for _ in ast.walk(tree))>4000:raise ValueError('Codice troppo complesso.')
        for node in tree.body:self.statement(node)
        result={'output':'\n'.join(self.output),'values':{k:v for k,v in self.values.items() if k not in ('pi','e')}}
        raw=json.dumps(result,allow_nan=False)
        if len(raw)>200000:raise ValueError('Risultato troppo grande.')
        return result
