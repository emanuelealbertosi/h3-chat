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
    'h3chat/study_library.py','ui/study-view.js','ui/study-style.js','ui/study-text.js','ui/study-export.js',
    'static/dialogs.css',
))
NEW_FEATURE_FILES=frozenset((
    'ui/image-viewer.js','ui/image-zoom.js',
    'ui/installations.js','ui/setup-guide.js','ui/settings-navigation.js','ui/settings-sections.js',
    'h3chat/ph3_image.py','native/ph3-worker.py','scripts/install-ph3.py','scripts/ph3-sources.json','docs/ph3-image.md',
    'h3chat/generation_presets.py','h3chat/slide_image_reuse.py','ui/generation-presets.js',
    'ui/work-center.js','ui/request-review.js','ui/slide-editor-actions.js','ui/editor-history-keys.js','static/workflows.css',
    'h3chat/poster_reference.py','h3chat/poster_reference_check.py','native/poster-reference-worker.py',
    'h3chat/video_sequence.py','ui/moss-layout-editor.js','h3chat/request_settings.py','ui/request-settings.js',
    'h3chat/infographic_voices.py','ui/voice-profiles.js',
    'static/voice-profiles/profiles.json','static/voice-profiles/limpida.wav','static/voice-profiles/aurora.wav',
    'static/vendor/moss-layout/le-editor.js','static/vendor/moss-layout/le-editor.css',
    'static/vendor/moss-layout/le-model.js','static/vendor/moss-layout/le-formats.js','static/vendor/moss-layout/le-validate.js',
    'static/vendor/moss-layout/LICENSE.txt','static/vendor/moss-layout/provenance.json',
    'static/infographic-cinema.js','h3chat/infographic_cinema.py',
    'h3chat/moss_tts.py','native/moss-voice-backend.py','native/h3_moss_audio.py',
))
FONT_FILES=frozenset('static/'+name+'.ttf' for name in ('Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers'))|frozenset((
    'licenses/Manrope-OFL.txt','licenses/Cormorant-OFL.txt',
    'static/font-licenses/bebasneue/OFL.txt','static/font-licenses/baloo2/OFL.txt',
    'static/font-licenses/caveat/OFL.txt','static/font-licenses/bangers/OFL.txt',
))
NVIDIA_INSTALLER_FILES=frozenset(('scripts/install-ph3.py','scripts/ph3-sources.json'))
REQUIRED=(POSTER_FILES|STUDIO_FILES|FONT_FILES|NEW_FEATURE_FILES)-NVIDIA_INSTALLER_FILES

def verify_members(names,platform=None):
    """Validate actual archive members, not merely files on the build host."""
    relative={str(name).removeprefix('H3-Chat/') for name in names}
    required=REQUIRED|(NVIDIA_INSTALLER_FILES if platform in ('windows','linux') else frozenset())
    missing=required-relative
    if missing:raise ValueError('Release incomplete: missing poster/Studio/font files: '+', '.join(sorted(missing)))
    return {'poster_files':len(POSTER_FILES),'studio_files':len(STUDIO_FILES),'font_and_license_files':len(FONT_FILES),'total_required_files':len(required)}
