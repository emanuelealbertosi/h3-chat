"""Human clarification pauses, distinct from permissions and credentials."""

class AwaitInput(Exception):
    pass


def prepare(ctx, args):
    ctx.action.update(status='awaiting_input', question={
        'text': args['question'], 'options': list(args.get('options', []))})
    ctx.state.update(status='awaiting_input', message='Agent attende una tua risposta per continuare questo lavoro.')
    raise AwaitInput()


def answer(state, action, body):
    if state['status'] != 'awaiting_input' or body.get('decision') != 'answer' or body.get('action_id') != action['id']:
        raise ValueError('Rispondi alla domanda in attesa oppure annulla il lavoro.')
    text = body.get('answer')
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('Scrivi una risposta da 1 a 4.000 caratteri.')
    action.update(status='done', result={'answer': text.strip(), 'source': 'human_clarification',
                  'note': 'Risposta al chiarimento; i permessi della sessione restano invariati.'})
