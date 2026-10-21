# SPDX-License-Identifier: MIT
# Copyright (c) 2026 xyzDist
# Adapted from H3-LongTakeNoCuts/h3_blend_latents_by_frames.py at
# 0cad00ab92e4ad8de3d54ddd5254142bccb702d9. See LICENSE.

def factors(total,frames):
    """Upstream linear keyframes 0:0,22:0,44:1 on the native latent grid."""
    points={max(0,min(total-1,round(frame*total/max(1,frames)))):value
            for frame,value in ((0,0.),(22,0.),(44,1.))}
    pairs=sorted(points.items());result=[]
    for i in range(total):
        before=max((p for p in pairs if p[0]<=i),default=pairs[0])
        after=next((p for p in pairs if p[0]>=i),pairs[-1])
        t=0 if before[0]==after[0] else (i-before[0])/(after[0]-before[0])
        result.append(before[1]+(after[1]-before[1])*t)
    return result


def blend_video(base,refined,frames):
    if base.shape!=refined.shape or base.ndim!=5:raise ValueError('Latenti LongTake di dimensioni diverse.')
    result=base.clone()
    for i,weight in enumerate(factors(base.shape[2],frames)):
        result[:,:,i]=base[:,:,i]*(1-weight)+refined[:,:,i]*weight
    return result
