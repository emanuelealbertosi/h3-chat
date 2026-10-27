"""Host-declared capabilities: do not mistake a proposed tool for an installed one."""

def snapshot(config, settings):
    from .agent_tools import TOOLS,permission
    tools=[]
    for name in TOOLS:
        try:permission(config,name,{})
        except PermissionError:continue
        tools.append(name)
    computer=config.get('scope','h3') in ('sandbox','global')
    return {'scope':config.get('scope','h3'),'tools':sorted(tools),
        'computer_files':computer,'code_execution':computer,
        'administrator':config.get('scope')=='global','administrator_requires_human':True,
        'web_enabled':bool(settings.get('_web')),'human_clarification':True,'saved_step_retrieval':True,
        'planning_roles':{'count':config.get('planning_agents',1),'sequential':True,'independent_tool_execution':False},
        'interactive_browser':False,'desktop_mouse_keyboard':False,'persistent_terminal':False,
        'lsp':False,'mcp_plugins':False,'scheduled_agent_runs':False,
        'note':'File e comandi richiedono anche un grant locale valido. Le capacità false non vanno dichiarate disponibili. Preferisci sempre i tool H3 specifici.'}
