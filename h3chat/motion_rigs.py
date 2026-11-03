"""Data-only articulated paper characters, compiled to ordinary Motion v2 groups."""
import copy,hashlib,json,math,re
from uuid import uuid4
from .infographic_scene import validate as validate_scene

ACTIONS=('idle','wave','point')
PARTS=('head','torso','upper_arm','forearm_hand','thigh','shin_shoe')
JOINTS=('body','head','upper_l','lower_l','upper_r','lower_r','thigh_l','shin_l','thigh_r','shin_r')


def atlas_prompt(description,direction):
    # Scene direction also contains background, typography, framing and camera
    # instructions. Those conflict with the technical chroma sheet. Appearance
    # carries the character's own visual treatment, independently of the scene.
    return ('Technical sprite sheet of ONE coherent illustrated paper puppet. Character appearance and clothing: '+description+'. '
      'Premium softly shaded clean illustration, consistent materials and believable proportions. This is an asset sheet ONLY, not a scene, poster or infographic. '
      'EXACTLY TWO COLUMNS and THREE ROWS of equally sized square cells, six isolated parts total. Every item centered with wide margins inside its cell; no grid lines, labels, lettering, numbers or shadows on the background. Perfectly uniform pure magenta #FF00FF background; no magenta on the pieces. '
      'Top left: HEAD and short neck only, front view, no shoulders. Top right: TORSO from shoulders to hips, clothed, front view, no arms, hands, head or legs. '
      'Middle left: ONE UPPER ARM, straight vertical down from shoulder to elbow, rounded overlapping ends, matching long sleeve, no hand. '
      'Middle right: ONE FOREARM with its attached natural open HAND, vertical down, elbow at top, cuff and hand at bottom, matching sleeve, no upper arm or torso. '
      'Bottom left: ONE THIGH, vertical down, matching trousers, hip to knee only, no pelvis or torso. '
      'Bottom right: ONE SHIN with attached SHOE, vertical down, matching trousers, knee to ankle and shoe only. '
      'All parts belong to the SAME character with consistent color and materials. Paper-puppet pieces for animation, not anatomical or medical imagery. No whole figures, duplicate pieces, accessories, decorative objects or extra limbs. Every part fully visible, clean rounded joint ends.')


def validate_rig(scene,rig):
    if not isinstance(rig,dict) or set(rig)!={'version','joints','actions'} or rig.get('version')!=1:raise ValueError('Personaggio animabile: formato non valido.')
    joints=rig['joints'];objects={o['id']:o for o in scene['objects']}
    if not isinstance(joints,dict) or set(joints)!=set(JOINTS) or any(not isinstance(v,str) for v in joints.values()) or len(set(joints.values()))!=len(JOINTS):raise ValueError('Personaggio animabile: articolazioni incomplete.')
    if any(not isinstance(v,str) or v not in objects or objects[v]['type']!='group' for v in joints.values()):raise ValueError('Personaggio animabile: articolazione inesistente.')
    if rig['actions']!=list(ACTIONS):raise ValueError('Azioni personaggio non supportate.')
    expected={'head':'body','upper_l':'body','lower_l':'upper_l','upper_r':'body','lower_r':'upper_r','thigh_l':'body','shin_l':'thigh_l','thigh_r':'body','shin_r':'thigh_r'}
    for child,parent in expected.items():
        if objects[joints[child]].get('parentId')!=joints[parent]:raise ValueError('Personaggio animabile: collegamento delle articolazioni non valido.')
    return copy.deepcopy(rig)


def template(asset,parts,name,description,direction):
    """Use a single transparent atlas for all parts, including mirrored limbs."""
    if set(parts)!=set(PARTS):raise ValueError('Il foglio deve contenere tutte le sei parti del personaggio.')
    objects=[]
    def group(id,parent,x,y,w=1,h=1,layer=0):
        objects.append({'id':id,'type':'group','parentId':parent,'width':w,'height':h,'layer':layer,'transform':{'x':x,'y':y}})
    def picture(id,key,parent,h,anchor=(.5,.07),flip=False,layer=0):
        crop=parts[key];w=h*crop['width']/crop['height']
        objects.append({'id':id,'type':'image','parentId':parent,'width':w,'height':h,'layer':layer,'assetId':asset['id'],'imageFit':'contain','crop':crop,'flipX':flip,'anchor':{'x':anchor[0],'y':anchor[1]},'transform':{'x':0,'y':0}})
        return w
    group('body',None,250,0,600,800)
    torso_width=235*parts['torso']['width']/parts['torso']['height'];shoulder=min(98,max(65,torso_width*.43));hip=min(49,max(32,torso_width*.23))
    for side,sign in [('l',-1),('r',1)]:
        group('thigh_'+side,'body',sign*hip,440,90,155,0);picture('thighImage_'+side,'thigh','thigh_'+side,155,flip=side=='l')
        group('shin_'+side,'thigh_'+side,0,140,90,170,0);picture('shinImage_'+side,'shin_shoe','shin_'+side,170,flip=side=='l')
        group('upper_'+side,'body',sign*shoulder,240,70,130,1);picture('upperImage_'+side,'upper_arm','upper_'+side,130,flip=side=='l')
        group('lower_'+side,'upper_'+side,0,117,70,150,0);picture('lowerImage_'+side,'forearm_hand','lower_'+side,150,flip=side=='l')
    # Torso paints over shoulder and hip seams; overlapping ends remain hidden.
    group('torsoHolder','body',0,210,torso_width,235,2);picture('torsoImage','torso','torsoHolder',235,(.5,0))
    group('head','body',0,213,180,180,3);picture('headImage','head','head',180,(.5,.97))
    scene=validate_scene({'version':2,'id':'character','width':600,'height':800,'duration':1,'background':'none','objects':objects,'camera':{'keyframes':[]}})
    rig={'version':1,'joints':{k:k for k in JOINTS},'actions':list(ACTIONS)};validate_rig(scene,rig)
    digest=hashlib.sha256(json.dumps(scene,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'version':1,'id':uuid4().hex,'name':name,'description':description,'style':direction[:160],
        'tags':['personaggio','articolato','saluto','indica'],'palette':[],'sha256':digest,'scene':scene,'rig':rig,'media':[asset]}


def animate(sprite,gesture,start,end,duration):
    scene=copy.deepcopy(sprite['scene']);rig=validate_rig(scene,sprite['rig'])
    if gesture not in ACTIONS or type(start) not in (int,float) or type(end) not in (int,float) or not math.isfinite(start+end) or not 0<=start<end<=duration:raise ValueError('Azione personaggio: scegli posa, saluto o indicazione entro la durata della scena.')
    by_id={o['id']:o for o in scene['objects']};span=end-start
    def track(joint,prop,keys):
        by_id[rig['joints'][joint]].setdefault('tracks',[]).append({'property':prop,'keyframes':[{'t':round(start+t*span,8),'value':value,'ease':'easeInOut'} for t,value in keys]})
    track('head','rotation',[(0,0),(.35,-1.8),(.7,1.2),(1,0)])
    # Breathing pivots near the shoulders; the feet remain fixed on the floor.
    holder=by_id.get('torsoHolder')
    if holder:holder['tracks']=[{'property':'scaleY','keyframes':[{'t':round(i*duration/4,8),'value':1+(.004 if i%2 else 0),'ease':'easeInOut'} for i in range(5)]}]
    if gesture=='wave':
        track('upper_r','rotation',[(0,-3),(.18,-135),(.84,-135),(1,-3)])
        track('lower_r','rotation',[(0,0),(.18,-35),(.3,-57),(.42,-15),(.54,-57),(.66,-15),(.78,-42),(.86,-35),(1,0)])
    elif gesture=='point':
        track('upper_r','rotation',[(0,-3),(.22,-82),(.82,-82),(1,-3)])
        track('lower_r','rotation',[(0,0),(.24,-8),(.82,-8),(1,0)])
    else:
        track('upper_r','rotation',[(0,-3),(.5,-1),(1,-3)]);track('upper_l','rotation',[(0,3),(.5,1),(1,3)])
    scene['duration']=duration;return validate_scene(scene)


def instantiate(sprite,instance,duration):
    """Expand an action once; export and editor keep ordinary editable keyframes."""
    obj=copy.deepcopy(instance);gesture=obj.pop('gesture',None);start=obj.pop('actionStart',None);end=obj.pop('actionEnd',None)
    graph=animate(sprite,gesture,start,end,duration);prefix=obj['id'][:45]+'_rig';mapping={o['id']:prefix+'_'+str(i) for i,o in enumerate(graph['objects'])}
    scale=min(obj['width']/graph['width'],obj['height']/graph['height']);wrapper={'id':prefix,'type':'group','parentId':obj['id'],'width':graph['width'],'height':graph['height'],'transform':{'x':(obj['width']-graph['width']*scale)/2,'y':obj['height']-graph['height']*scale,'scaleX':scale,'scaleY':scale}}
    objects=[obj,wrapper]
    for child in graph['objects']:
        child['parentId']=mapping[child['parentId']] if child.get('parentId') else prefix;child['id']=mapping[child['id']];child['parallax']=1;objects.append(child)
    return objects
