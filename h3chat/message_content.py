"""Append instructions without corrupting multimodal message parts."""
def append_text(message, text):
    content = message.get('content', '')
    if isinstance(content, str):
        message['content'] = content + text
    elif isinstance(content, list):
        message['content'] = [*content, {'type': 'text', 'text': text}]
    else:
        raise ValueError('Contenuto del messaggio non valido.')
