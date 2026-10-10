"""Read reference geometry using the bundled video Pillow, without GPU libraries."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'runtime/vision/packages'))

def emit(event, **values):
    sys.stdout.write(json.dumps({'event':event, **values}, ensure_ascii=False)+'\n')
    sys.stdout.flush()

emit('hello', engine='image-size')
for line in sys.stdin:
    try:
        from PIL import Image
        request = json.loads(line)
        sizes = []
        for path in request['paths']:
            with Image.open(path) as image:
                width, height = image.size
                if image.getexif().get(274) in (5, 6, 7, 8):
                    width, height = height, width
                sizes.append([width, height])
        emit('result', result={'sizes':sizes})
    except ModuleNotFoundError as exc:
        emit('error', message='Motore video incompleto: reinstalla Video / Ming / Qwen dal Setup.' if exc.name == 'PIL' else str(exc))
    except Exception as exc:
        emit('error', message='Impossibile leggere il formato dell’immagine: '+str(exc))
