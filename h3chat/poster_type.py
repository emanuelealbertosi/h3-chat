"""Bounded professional lettering styles shared by planner, HTML and MOSS."""
import re
FONTS=('Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers')
STYLES=('auto','editorial','playful','cinematic','handwritten','comic','retro','neon','minimal')
EFFECTS=('auto','plain','shadow','outline','extruded','neon','metallic','letterpress')
PRESETS={'editorial':('Cormorant','Manrope','plain',.2),'playful':('Baloo2','Baloo2','extruded',.2),
 'cinematic':('BebasNeue','Manrope','metallic',2),'handwritten':('Caveat','Manrope','plain',.1),
 'comic':('Bangers','Manrope','outline',.8),'retro':('Cormorant','Manrope','letterpress',1),
 'neon':('BebasNeue','Manrope','neon',1.5),'minimal':('Manrope','Manrope','plain',.3)}
DEFAULTS={'lettering':'auto','text_effect':'auto','heading_font':'auto','body_font':'auto'}
APPEARANCE={'Manrope':'clean modern sans-serif','Cormorant':'elegant high-contrast serif','BebasNeue':'tall condensed display','Baloo2':'rounded playful display','Caveat':'handwritten script','Bangers':'bold comic brush'}

def options(prompt,value):
    out={k:value.get(k,v) for k,v in DEFAULTS.items()}
    aliases={'editorial':'editorial[ei]|elegant[ei]|seri[eo]|formale','playful':'giocos[oea]|playful|bambinesc[oa]',
      'cinematic':'cinematografic(?:[oa]|he|i)|cinematic|da film','handwritten':'manoscritt[oa]|calligrafic[oa]|handwritten',
      'comic':'fumett[oa]|comic','retro':'retr[oò]|vintage','neon':'neon','minimal':'minimal[ei]?'}
    for key,words in aliases.items():
        if re.search(r'\b(?:scritte|lettering|tipografia|caratteri|titoli|testi|stile delle scritte)\b.{0,35}\b(?:'+words+r')\b',prompt,re.I):out['lettering']=key;break
    for key,words in {'plain':'senza effetti|nessun effetto','shadow':'ombra morbida|soft shadow','outline':'contorn[oa]|outline','extruded':'estrus[oa]|tridimensional[ei]|3d','neon':'bagliore neon|glow','metallic':'metallizzat[oa]|metallic','letterpress':'letterpress|stampa a rilievo'}.items():
        if re.search(r'\b(?:'+words+r')\b',prompt,re.I):out['text_effect']=key;break
    if out['lettering'] not in STYLES or out['text_effect'] not in EFFECTS:raise ValueError('Stile delle scritte o effetto non valido.')
    for key,anchor in [('heading_font','titoli|titolo'),('body_font','testi|corpo|paragrafi')]:
        found=re.search(r'\b(?:'+anchor+r')\b.{0,15}\b(?:in|font|carattere)\s+(Manrope|Cormorant|Bebas\s*Neue|Baloo\s*2|Caveat|Bangers)\b',prompt,re.I)
        if found:out[key]=next(f for f in FONTS if re.sub(r'\s','',f).lower()==re.sub(r'\s','',found[1]).lower())
    for key in ('heading_font','body_font'):
        if out[key] not in ('auto',*FONTS):raise ValueError('Carattere locandine non disponibile.')
    return out

def brief(opts):
    return f'''LETTERING DIRECTION: {opts.get('lettering','auto')}; short-text effect: {opts.get('text_effect','auto')}.
Coordinate raster MOSS lettering and editable HTML type as one art direction.
Available locally embedded HTML families: {', '.join(FONTS)}. Heading font {opts.get('heading_font','auto')}, body font {opts.get('body_font','auto')}.
Choose character, tracking, italics and effects to match the illustration: serious editorial, playful, cinematic, handwritten, comic, retro or neon.
Keep long body copy clear and composed; strong outlines, glow and extrusion belong to headings and short labels.
In HTML use only these local families and static CSS effects (stroke, shadows, subtle relief or metallic gradient), never external font URLs.
User's explicit typography instructions override automatic matching. Do not print these instructions.'''

def prepare(zone,opts):
    if not isinstance(zone.get('text'),str) or not isinstance(zone.get('role'),str):raise ValueError('Testo o ruolo tipografico non valido.')
    zone=dict(zone);style=opts.get('lettering','auto')
    short=zone['role'] in ('title','subtitle','facts') and len(zone['text'])<=140
    preset=PRESETS.get(style)
    # Auto still needs a coherent display family when the user selects an
    # effect without selecting a separate lettering profile.
    inferred={'neon':'neon','extruded':'playful','outline':'comic','metallic':'cinematic','letterpress':'retro'}.get(opts.get('text_effect'))
    display_preset=preset or PRESETS.get(inferred)
    font=zone.get('font_family','Manrope');effect=zone.get('effect','plain');tracking=zone.get('tracking',0);italic=zone.get('italic',False)
    if preset:font=preset[0 if short else 1];effect=preset[2] if short else 'plain';tracking=preset[3] if short else 0
    forced=opts.get('heading_font' if short else 'body_font','auto')
    if forced!='auto':font=forced
    if short and opts.get('text_effect','auto')!='auto':effect=opts['text_effect']
    if not short and effect not in ('plain','shadow'):effect='plain'
    if font not in FONTS or effect not in EFFECTS[1:] or type(tracking) not in (int,float) or not -1<=tracking<=6 or type(italic) is not bool:raise ValueError('Tipografia del piano non valida.')
    pad={'plain':0,'shadow':4,'outline':3,'extruded':7,'neon':9,'metallic':2,'letterpress':3}[effect]
    heading=opts.get('heading_font','auto');heading=(display_preset[0] if display_preset else zone.get('heading_family',font)) if heading=='auto' else heading
    heading_effect=opts.get('text_effect','auto')
    if heading_effect=='auto':heading_effect=display_preset[2] if display_preset else zone.get('heading_effect','plain')
    if heading not in FONTS or heading_effect not in EFFECTS[1:]:raise ValueError('Tipografia dei titoletti non valida.')
    heading_pad={'plain':0,'shadow':4,'outline':3,'extruded':7,'neon':9,'metallic':2,'letterpress':3}[heading_effect]
    return zone|{'font_family':font,'effect':effect,'tracking':tracking,'italic':italic,'effect_padding':max(pad,heading_pad if not short else 0),'heading_family':heading,'heading_effect':heading_effect}

def css(zone):
    effect=zone.get('effect','plain');color=zone['color'];surface=zone['surface']
    dark='#17212c' if surface=='light' else '#050b18';light='#fff9e8'
    effects={'plain':'text-shadow:none', 'shadow':f'text-shadow:0 2px 4px {dark}88',
      'outline':f'-webkit-text-stroke:1.4px {dark};paint-order:stroke fill;text-shadow:0 2px 0 {dark}88',
      'extruded':f'text-shadow:1px 1px 0 {dark},2px 2px 0 {dark},3px 3px 0 {dark},4px 4px 0 {dark},5px 5px 4px {dark}55',
      'neon':f'text-shadow:0 0 2px {light},0 0 5px {color},0 0 9px {color}99',
      'metallic':f'background:linear-gradient(180deg,{light} 0%,{color} 28%,#8b9bab 48%,{light} 51%,{color} 100%);background-clip:text;-webkit-background-clip:text;color:transparent;-webkit-text-stroke:.4px {color}',
      'letterpress':f'text-shadow:0 1px 0 {light}88,0 -1px 1px {dark}99'}
    return f"font-family:{zone.get('font_family','Manrope')},sans-serif;font-style:{'italic' if zone.get('italic') else 'normal'};letter-spacing:{zone.get('tracking',0)}px;{effects.get(effect,effects['plain'])}"
