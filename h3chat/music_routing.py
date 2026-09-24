"""Music is another destination in the same conversation, never another chat mode."""
import re
from .music_options import validate_fields

MUSIC_BRIEF = """You prepare a song for YuE2, the local music generation model.
Return JSON with exactly title, style, lyrics, abc, instrumental. title/style/lyrics/abc
are strings and instrumental is boolean. Style is an English musical direction:
genre, mood, tempo if requested, instruments, arrangement and vocal character.
Lyrics follow the user's language and use [Verse], [Chorus], [Bridge], [Outro] labels.
Use the supplied lyrics exactly unless the user asks to change them. Never sing the
user's generation instructions. Write original lyrics when lyrics were not provided.
For an instrumental request set instrumental=true and lyrics=[Instrumental], with
an explicitly instrumental style and no vocals. Otherwise instrumental=false.
Keep the song concise unless the user explicitly asks for a longer composition.
Preserve explicit title, style constraints and supplied ABC score. Do not invent ABC
unless the user specifically requests a score. You have not heard earlier generated
audio: use its saved composition details, not claims about what it sounds like.
Return the composition, never claim to have generated the audio. Follow the latest
request, using conversation context only to resolve references and revisions."""


def route(history,settings):
 text=history[-1]['content'].strip()
 if settings.get('_music'):return {'intent':'music','prompt':text,'selection':'explicit'}
 if settings.get('_image_model') or not settings.get('music_auto',True):return None
 opening=re.sub(r'^(?:(?:per favore[, ]*|puoi\s+|potresti\s+|vorrei\s+|mi piacerebbe\s+|please\s+|can you\s+))+','',text.casefold())
 if not re.match(r'^(?:crea(?:mi)?|creare|genera(?:mi)?|generare|componi(?:mi)?|comporre|produci|produrre|fammi|fai|suona|create|generate|compose|make)\b',opening):return None
 if re.search(r'\b(?:solo (?:il )?testo|testo (?:di|per)|lyrics only|senza audio|codice|immagine|copertina|spartito|diagramma|grafico)\b',opening[:250]):return None
 if re.search(r'\b(?:canzon[ei]|musica|brano|brani|traccia musicale|colonna sonora|base musicale|song|music|soundtrack|jingle|strumentale)\b',opening[:250]):
  return {'intent':'music','prompt':text,'selection':'auto'}
 return None


def direct_composition(prompt,fields):
 result=validate_fields(fields)
 # Explicitly labelled fields are also accepted in a normal chat prompt.
 chunks=re.split(r'(?im)^\s*(titolo|title|stile|style|testo|lyrics|abc)\s*:\s*',prompt)
 names={'titolo':'title','title':'title','stile':'style','style':'style','testo':'lyrics','lyrics':'lyrics','abc':'abc'}
 for i in range(1,len(chunks)-1,2):
  key=names[chunks[i].lower()]
  if not result[key]:result[key]=chunks[i+1].strip()
 result['instrumental']=result['instrumental'] or bool(re.search(r'\b(?:strumentale|instrumental|senza voce|senza voci|no vocals)\b',prompt,re.I))
 if result['instrumental']:
  result['lyrics']='[Instrumental]'
 elif not result['lyrics']:
  raise ValueError('Assistant Off: inserisci il testo in Music → Testo del brano, oppure nel messaggio dopo «Testo:». Per musica senza parole attiva Strumentale.')
 if not result['style']:result['style']=chunks[0].strip() or prompt
 if result['instrumental']:result['style']+='; instrumental music, no vocals'
 result['title']=result['title'] or 'Nuovo brano'
 return validate_fields(result)
