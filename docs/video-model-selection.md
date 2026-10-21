# Video: model selection and experimental resolution

The Video settings page lists linked MiniMax H3 models and stores a separate
preset for each model. `Ricrea video` and `Modifica clip` can select a different
installed standalone H3 model for a single request. Changing model loads its
saved preset into the modal; submitting the modal does not save preferences.
The attention selector is available in both modals. When changing model,
recreation also uses the selected model's attention chunking and VEDA predictor
configuration. Newly linked H3 models inherit attention settings from the default
video model; explicitly saved per-model choices remain unchanged.

`Risoluzione sperimentale` explicitly permits 0.2–2 MP. With this switch off,
the native 0.98 MP canvas limit remains in place, including legacy 1 MP presets.
With it on, both output size and padded inference canvas actually grow. The
model's native training canvas is unchanged, and higher resolution can require
substantially more memory and time. Duration, saved aspect ratio, scene timing,
references and audio are preserved during recreation.

PDD is optional. The matching FL2VA/Ref2VA adapter must be selected explicitly;
it uses 8 steps, Euler, CFG 1 and shifts 12/3. Changing steps to 12/16/20 turns
PDD off in the modal. Choosing PDD does not alter saved model presets.

Clip edits default to reassembly of the full source video. Disable `Rimonta
nel video` to receive each generated interval as a separate MP4 with the
corresponding original audio. Partial edits then return only the selected
interval, without restoring surrounding frames. When reassembly is enabled,
replacement footage is fitted to the original video dimensions so the other
clips and their timing remain compatible. When disabled, the generated size
is retained.

Generated intervals are checkpointed before audio/montage work. Retrying a
failed assembly reuses saved generation; it does not load MiniMax again.
