"""Per-response slide timeout, with zero inheriting the selected LLM preset."""


def value(options):
    seconds=options.get('llm_timeout',0)
    if type(seconds) is not int or (seconds!=0 and not 60<=seconds<=14400):
        raise ValueError('Tempo massimo per fase delle slide: 60–14400 secondi, oppure 0 per usare il timeout del modello.')
    return seconds


def apply(settings,options):
    seconds=value(options)
    return settings|{'llm_timeout':seconds or settings.get('llm_timeout',1800)}
