"""Avoid huge bounded repetitions in native GBNF; retain length checks in Python."""
import copy,json

def grammar_schema(schema):
    value=copy.deepcopy(schema)
    def visit(node):
        if isinstance(node,list):
            for child in node:visit(child)
        elif isinstance(node,dict):
            if node.get('type')=='string':
                for key in ('minLength','maxLength'):
                    if node.get(key,0)>128:node.pop(key)
            for child in node.values():visit(child)
    visit(value);return value

def check_lengths(value,schema,path='$'):
    if isinstance(value,str):
        if len(value)<schema.get('minLength',0) or len(value)>schema.get('maxLength',10**9):raise ValueError(f'Il campo JSON {path} non rispetta la lunghezza richiesta ({schema.get("minLength",0)}–{schema.get("maxLength","senza massimo")} caratteri).')
    elif isinstance(value,dict):
        for key,child in value.items():
            if key in schema.get('properties',{}):check_lengths(child,schema['properties'][key],path+'.'+key)
    elif isinstance(value,list):
        for index,child in enumerate(value):check_lengths(child,schema.get('items',{}),path+'['+str(index)+']')

def validate_response(content,schema):
    # The original schema is never modified. Other semantic checks stay with
    # each tool; a malformed/truncated response retains its normal error path.
    try:value=json.loads(content)
    except (TypeError,ValueError):return
    check_lengths(value,schema)
