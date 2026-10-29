"""Shared release gate: new source/UI/font files must survive every packager."""

POSTER_FILES=frozenset((
    'h3chat/posters.py','h3chat/poster_visual.py','h3chat/poster_type.py',
    'h3chat/poster_overlay.py','h3chat/poster_plan_progress.py','h3chat/poster_typography.py','h3chat/infographic_document.py',
    'native/agent-layout-worker.py','ui/posters.js','ui/slide-pptx.js','docs/posters.md',
    'static/poster-fonts.css','static/typography-fonts.json',
))
STUDIO_FILES=frozenset((
    'h3chat/study.py','h3chat/study_import.py','h3chat/study_audio.py',
    'h3chat/web_media_runtime.py','native/study-captions-worker.py',
    'ui/study.js','ui/project-media-import.js','ui/source-origin.js','docs/studio.md',
))
FONT_FILES=frozenset('static/'+name+'.ttf' for name in ('Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers'))|frozenset((
    'licenses/Manrope-OFL.txt','licenses/Cormorant-OFL.txt',
    'static/font-licenses/bebasneue/OFL.txt','static/font-licenses/baloo2/OFL.txt',
    'static/font-licenses/caveat/OFL.txt','static/font-licenses/bangers/OFL.txt',
))
REQUIRED=POSTER_FILES|STUDIO_FILES|FONT_FILES

def verify_members(names):
    """Validate actual archive members, not merely files on the build host."""
    relative={str(name).removeprefix('H3-Chat/') for name in names}
    missing=REQUIRED-relative
    if missing:raise ValueError('Release incomplete: missing poster/Studio/font files: '+', '.join(sorted(missing)))
    return {'poster_files':len(POSTER_FILES),'studio_files':len(STUDIO_FILES),'font_and_license_files':len(FONT_FILES),'total_required_files':len(REQUIRED)}
