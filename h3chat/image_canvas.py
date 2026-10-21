"""Pixel-preserving output crop for a padded model canvas."""
def crop_canvas(array,width,height):
    top,left=(array.shape[0]-height)//2,(array.shape[1]-width)//2
    if min(top,left)<0:raise ValueError('Il motore ha prodotto una tela più piccola della richiesta.')
    return array[top:top+height,left:left+width]
