"""Sample exact interval-local keyframes using the same floor timing as H3's source decoder."""


def sample_frames(decoded,*,start,count,positions,time_of):
    targets=sorted(positions.items(),key=lambda item:item[1]);cursor=0;previous=None;last_time=None
    for frame in decoded:
        when=time_of(frame)
        if when is None:continue
        if when<start:
            previous=frame;last_time=when;continue
        while cursor<len(targets) and start+targets[cursor][1]/24<=when+1e-6:
            name,index=targets[cursor]
            chosen=previous if previous is not None and when>start+index/24+1e-6 else frame
            yield name,index,chosen
            cursor+=1
        previous=frame;last_time=when
        if cursor==len(targets):return
    if previous is None or last_time is None or last_time+1/24<start+(count-1)/24-1e-6:
        raise ValueError('Fotogrammi del video sorgente mancanti.')
    for name,index in targets[cursor:]:yield name,index,previous


def extract(source,start,count,positions,folder,write):
    import av
    from uuid import uuid4
    if type(start) not in (int,float) or not 0<=start or type(count) is not int or not 24<=count<=360:
        raise ValueError('Intervallo delle guide non valido.')
    if not isinstance(positions,dict) or not positions or set(positions)-{'first','middle','last'} or any(type(n) is not int or not 0<=n<count for n in positions.values()):
        raise ValueError('Posizioni delle guide non valide.')
    folder.mkdir(parents=True,exist_ok=True);result={}
    with av.open(str(source),options={'protocol_whitelist':'file'}) as container:
        if not container.streams.video:raise ValueError('Sorgente senza video.')
        stream=container.streams.video[0];stream.codec_context.thread_count=2
        base=float((stream.start_time or 0)*stream.time_base)
        container.seek(max(0,int((base+start)/stream.time_base)),stream=stream,backward=True)
        time_of=lambda frame:float(frame.pts*stream.time_base)-base if frame.pts is not None else None
        for name,index,frame in sample_frames(container.decode(stream),start=start,count=count,positions=positions,time_of=time_of):
            ident=uuid4().hex;path=folder/(name+'.png');write(frame,path)
            result[name]={'id':ident,'path':str(path),'frame':index,'seconds':start+index/24,'width':frame.width,'height':frame.height}
    return result
