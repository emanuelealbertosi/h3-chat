"""CPU chroma extraction and bounded six-cell character-part registration."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'runtime/tools/documents')]


def prepare(source,target):
    import numpy as np
    from PIL import Image,ImageFilter
    image=Image.open(source).convert('RGB')
    if image.width*image.height>16_000_000:raise ValueError('Foglio parti oltre16MP.')
    rgb=np.array(image).astype('float32');key=np.minimum(rgb[:,:,0],rgb[:,:,2])-rgb[:,:,1]
    border=np.concatenate((key[0],key[-1],key[:,0],key[:,-1]))
    # A thin magenta frame around a pale opaque sheet is not chroma backing.
    if float((border>80).mean())<.65 or float((key>80).mean())<.30:raise ValueError('Il foglio parti non ha il fondale magenta uniforme richiesto. Le parti restano disponibili per verifica; nessun ritaglio inventato.')
    alpha=np.clip((68-key)/42,0,1);mask=Image.fromarray(np.uint8(alpha*255)).filter(ImageFilter.GaussianBlur(.22));alpha=np.array(mask).astype('float32')/255
    edge=(alpha>0)&(alpha<.98);ceiling=rgb[:,:,1]+30
    rgb[:,:,0][edge]=np.minimum(rgb[:,:,0][edge],ceiling[edge]);rgb[:,:,2][edge]=np.minimum(rgb[:,:,2][edge],ceiling[edge])
    output=Image.fromarray(np.dstack((np.uint8(rgb),np.uint8(alpha*255))),'RGBA')
    parts={};adjustments=[]
    def component(mask,cx,cy):
        from collections import deque
        ys,xs=np.where(mask)
        if not len(xs):return None
        index=int(np.argmin((xs-cx)**2+(ys-cy)**2));sx=int(xs[index]);sy=int(ys[index]);queue=deque([(sx,sy)]);mask=mask.copy();mask[sy,sx]=False;left=right=sx;top=bottom=sy;area=0
        while queue:
            x,y=queue.popleft();area+=1;left=min(left,x);right=max(right,x);top=min(top,y);bottom=max(bottom,y)
            for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx]:mask[ny,nx]=False;queue.append((nx,ny))
        return (left,top,right+1,bottom+1),area
    for i,name in enumerate(('head','torso','upper_arm','forearm_hand','thigh','shin_shoe')):
        col=i%2;row=i//2
        # Registration tolerates small deviations from the requested cell grid.
        # Follow the central connected part, excluding neighboring cuffs/shoes.
        x0=max(0,round((col-.06)*image.width/2));x1=min(image.width,round((col+1.06)*image.width/2));y0=max(0,round((row-.08)*image.height/3));y1=min(image.height,round((row+1.08)*image.height/3))
        cell=np.array(output.getchannel('A').crop((x0,y0,x1,y1)))
        found=component(cell>180,(col+.5)*image.width/2-x0,(row+.5)*image.height/3-y0)
        if not found:raise ValueError('Parte mancante nel foglio: '+name)
        box,area=found
        left,top,right,bottom=box;w=right-left;h=bottom-top
        if area<(x1-x0)*(y1-y0)*.02:raise ValueError('Parte troppo piccola o incompleta: '+name)
        if name=='torso' and w/h>.95:
            # Some image models draw sleeves on the torso. Keep the central
            # garment component instead of duplicating those arms in the rig.
            widths=[];center=(left+right)//2
            for y in range(top+round(h*.35),top+round(h*.85)):
                line=cell[y]>180
                if not line[center]:continue
                l=center;r=center
                while l>left and line[l-1]:l-=1
                while r<right-1 and line[r+1]:r+=1
                widths.append(r-l+1)
            core=int(np.median(widths)) if widths else round(h*.7);core=min(w,max(round(h*.52),core))
            if core<w*.9:left=center-core//2;right=left+core;adjustments.append(name+': maniche laterali escluse dal busto')
        if name in ('upper_arm','thigh') and h/w>(2.5 if name=='upper_arm' else 3.5):
            bottom=top+round(h*(.54 if name=='upper_arm' else .53));adjustments.append(name+': tratto superiore isolato da un segmento troppo lungo')
        parts[name]={'x':x0+left,'y':y0+top,'width':right-left,'height':bottom-top,'sourceWidth':image.width,'sourceHeight':image.height}
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);output.save(target)
    return {'parts':parts,'width':image.width,'height':image.height,'adjustments':adjustments,'semantic_review':'Verificare visivamente parti e giunture prima di salvare nella raccolta.'}


if __name__=='__main__':
    wire=sys.stdout;sys.stdout=sys.stderr
    def emit(event,**value):
        wire.write(json.dumps({'event':event,**value},ensure_ascii=False)+'\n');wire.flush()
    emit('hello',engine='motion-atlas-cpu')
    try:
        request=json.loads(sys.stdin.readline());result=prepare(request['input'],request['output']);emit('result',result=result)
    except Exception as exc:emit('error',message=str(exc))
