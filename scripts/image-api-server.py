"""Start the optional, loopback-only image API adapter using protected config."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.image_api_server import serve
from h3chat.providers import protect

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,default=ROOT/'data/image-api-server.json')
    config=json.loads(parser.parse_args().config.read_text(encoding='utf-8'))
    serve(config,protect(config['credential'],decode=True))
