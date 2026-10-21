"""Experimental latent img2img; no claim of trained semantic reference editing."""
import math


def canvas(width,height,image_width,image_height,preserve=True):
    if preserve:
        area=width*height;ratio=image_width/image_height
        width=math.ceil(math.sqrt(area*ratio));height=math.ceil(area/width)
    if min(width,height)<256 or max(width,height)>4096 or width*height>4_194_304:
        raise ValueError('Formato del riferimento troppo estremo per questa tela MOSS. Scegli un formato esplicito o meno megapixel.')
    return width,height


def encode(vae,image,width,height,*,upscale,torch):
    rgb=image[:,:,:,:3]
    if image.shape[-1]>3:rgb=rgb*image[:,:,:,3:]+1-image[:,:,:,3:]
    rgb=upscale(rgb.movedim(-1,1),width,height,'lanczos','center')
    w,h=math.ceil(width/16)*16,math.ceil(height/16)*16
    if w!=width or h!=height:
        rgb=torch.nn.functional.pad(rgb,((w-width)//2,w-width-(w-width)//2,(h-height)//2,h-height-(h-height)//2),mode='replicate')
    return vae.encode(rgb.movedim(1,-1))
