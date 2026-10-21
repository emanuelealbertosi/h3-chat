"""Default Qwen illustrations for slides and infographics, with explicit overrides."""


def select(engine,settings,explicit=''):
    if explicit:return explicit
    catalog=getattr(engine,'catalog',{})
    models=list(catalog.values()) if isinstance(catalog,dict) else []
    candidates=[m for m in models if m.get('architecture')=='qwen21' and 'create' in m.get('capabilities',[])
                and m.get('external_config',{}).get('profile')!='qwen21-turbo']
    candidates.sort(key=lambda m:(m['id']!=settings.get('create_model'),m['id']))
    for model in candidates:
        try:engine.require_model(model['id'],'create')
        except ValueError:continue
        return model['id']
    return settings.get('create_model','')
