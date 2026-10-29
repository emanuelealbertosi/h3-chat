"""Host-declared capabilities: do not mistake a proposed tool for an installed one."""

def snapshot(config, settings,root=None):
    from .agent_tools import TOOLS,permission
    tools=[];disabled={}
    for name in TOOLS:
        try:permission(config,name,{})
        except PermissionError as exc:
            disabled[name]=str(exc)
            continue
        tools.append(name)
    computer=config.get('scope','h3') in ('sandbox','global')
    from pathlib import Path
    from .browser_runtime import executable
    browser=bool(config.get('allow_browser') and settings.get('_web') and executable(root or Path(__file__).resolve().parents[1]))
    from .web_media_runtime import status as online_video_status
    return {'scope':config.get('scope','h3'),'tools':sorted(tools),'disabled_tools':disabled,
        'computer_files':computer,'code_execution':computer,'install_dependencies_inside_granted_scope':computer,
        'online_video_download':{'tool':'download_online_video','sites':['YouTube'],'runtime':online_video_status(root or Path(__file__).resolve().parents[1]),'automatic_verified_component_install':True},
        'administrator':config.get('scope')=='global','administrator_requires_human':True,
        'web_enabled':bool(settings.get('_web')),'web_access_on_demand':config.get('web_on_demand',True),
        'web_consent':'ask' if config.get('confirm_writes',True) else 'autoapprove_for_this_run',
        'human_clarification':True,'saved_step_retrieval':True,
        'planning_roles':{'count':config.get('planning_agents',1),'sequential':True,'independent_tool_execution':False},
        'interactive_browser':browser,'browser_private_profile':True,'browser_public_internet_only':True,
        'browser_download_limit_megabytes':128,'desktop_mouse_keyboard':False,'persistent_terminal':False,
        'lsp':False,'mcp_plugins':False,'scheduled_agent_runs':False,
        'note':'File e comandi richiedono anche un grant locale valido. Le capacità false non vanno dichiarate disponibili. Preferisci sempre i tool H3 specifici.'}
