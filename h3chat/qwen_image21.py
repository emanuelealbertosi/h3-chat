"""Qwen's saved Turbo schedule, including the terminal denoising zero."""
TURBO_SCHEDULER = 'qwen21_turbo'
TURBO_SIGMAS = (1.0, .978453, .95418, .926626, .89508, .845148, .704534, .414568, 0.0)


def validate_schedule(architecture, options):
    if options.get('scheduler') != TURBO_SCHEDULER:
        return
    if architecture != 'qwen21':
        raise ValueError('Il preset Qwen 2.1 Turbo è disponibile solo per Qwen Image 2.1.')
    if options.get('steps') != 8 or options.get('sampler') != 'euler':
        raise ValueError('Il preset Qwen 2.1 Turbo richiede 8 passi e sampler Euler. Per sperimentare altri passi scegli uno scheduler diverso nelle impostazioni del modello.')
