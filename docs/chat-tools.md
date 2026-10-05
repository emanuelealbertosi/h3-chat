# Documents, web and speech in H3-Chat 0.11

These tools feed the existing chat LLM. They do not require a second chat model,
external inference server, system Python, compiler or cloud model account.

## Documents

Attach up to three PDF / Word `.docx` files, 25 MB each. PDF text is extracted
locally with pypdf and retains page references. Word paragraphs and tables are
read with python-docx in document order and retain block references; Word does
not provide stable page numbers. Macro documents, legacy `.doc`, password PDFs,
archives exceeding 100 MB decompressed and PDFs exceeding 300 pages are rejected.
Extracted text is limited to two million characters per file.

The parser runs in a private subprocess with a 90-second deadline and can be
cancelled with the chat job. Extraction results are cached locally, atomically,
under `data/document-cache/`; filenames and contents are not sent to search.
Original documents remain attachable and downloadable. Later questions retrieve
the most recent document attachments again without reparsing unchanged files.

The app selects passages within a conservative context budget, using requested
pages and matching terms. General summaries use passages spread across the file
when there are no matching terms. It states when only excerpts were supplied;
it does not claim the LLM saw the complete file. Excerpts preserve locations and
avoid splitting numbers or words at truncation boundaries. Reading a requested
page is marked as a selection when other pages were omitted.

For PDFs without extractable text, Vision can receive rasterized page images.
Explicit requests such as “analizza il grafico a pagina 3” can also render pages
with selectable text and embedded figures. PDFium renders locally at a maximum
1600-pixel edge; the chat model's image limit is respected, with at most four
pages per document. Each image is labelled with filename and original page.
Other pages are explicitly described as unread. Vision must be enabled and have
a compatible mmproj on the chat-selected CPU/GPU device. Word images, headers, footers, comments, tracked changes
and original layout are not interpreted by the Word text importer. Vision/OCR
accuracy and tables' reading order depend on the document and chosen model.

## Web

The **Web** button applies to each queued message and is remembered per chat.
Explicit requests such as “cerca sul web…” also trigger search when `web_auto`
is enabled. Ordinary chat does not search. DuckDuckGo Lite is the default with
Bing RSS fallback; administrators can select Bing directly or configure their
own SearXNG endpoint. No API key is required. The search query is derived from
the user's message only; attachments, transcripts and conversation history are
not automatically sent to the search provider.

The app retrieves at most five public pages, with bounded responses and timeouts.
It rejects non-public source addresses, unsupported URL schemes, credentials and
redirects to private addresses. An explicitly configured local SearXNG instance
is permitted as a search provider; its result pages must still be public.
URLs are real provider results, filtered for site constraints and basic relevance.
HTML scripts and styles are removed; document/page commands are treated as data,
not instructions for the LLM.

Pages requiring JavaScript, access challenges or unsupported content may only
contribute the search snippet. Those sources are labelled **solo estratto**. If
no usable, relevant sources are obtained, the job reports an error instead of
claiming to have searched. The app appends clickable source links to the final
answer, or inside the canvas when selected. Search providers may rate-limit or
change their interfaces; retrieval does not bypass paywalls or login pages.
The app cannot guarantee that a small LLM interprets the sources correctly.

## Speech transcription

**Setup → Documenti, ricerca e trascrizione** installs the optional Faster Whisper
runtime from pinned Windows wheels with SHA-256 checks. Choose **Whisper Small**
(multilingual default) or **Tiny**, download their complete pinned CTranslate2
model files, or browse an existing model directory containing `model.bin`,
`config.json` and `tokenizer.json`. Local models remain in their original folder.
GGUF / whisper.cpp `.bin` files and arbitrary Transformers model directories
cannot be used directly by this runtime. There is no model conversion or remote
model-code execution.

Whisper runs on **CPU INT8**, with configurable language, CPU threads and beam
size. Audio decoding and VAD are bundled; no system FFmpeg is required. Models
and the private worker are released after extraction. Under **A richiesta**,
previous inference processes are released before transcribing; resident chat
processes may remain when **Residenti** is selected. The speech model itself is
always transient and consumes RAM, not VRAM. Decoder limits are 64 MB and 30
minutes per audio, with at most three audio attachments per message.

**Trascrivi**, or an unambiguous transcription-only request, returns the full
recognized text without loading a chat LLM. TXT and timed SRT files are generated
under the job output folder. Canvas mode puts transcript and downloads in the
side panel. Other audio chat requests transcribe first and feed selected text to
the existing LLM for summaries or questions; complete TXT/SRT remain downloadable.
The explicit transcription button overrides automatic media routing.

Audio references destined for Video retain their original role and are not
automatically transcribed. Whisper recognizes speech; it does not analyse musical
instruments, background sounds, emotions or speaker identity, and it does not
perform speaker diarization. Silent/non-speech results are identified as such.
Transcription, translation and LLM summaries may contain mistakes.

## Standalone distribution and provenance

The Windows application ZIP includes document wheels and Microsoft runtime
libraries beside the private packages. Clone installation prepares those same
components. Speech wheels are installed from the admin; model weights are never
bundled. `runtimes.json`, `tools-models.json` and `scripts/tools-sources.json`
record pinned URLs, revisions, SHA-256 and upstream provenance. Distribution
licenses remain inside each wheel's `.dist-info` / package folders and the native
runtime notice. Readiness is published only after completed installation and is
invalidated when the pinned manifest changes. After downloading the optional
components and weights, document reading and transcription operate offline;
web search requires Internet.

Primary sources: [Faster Whisper](https://github.com/SYSTRAN/faster-whisper),
[pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[python-docx](https://python-docx.readthedocs.io/en/latest/),
[pypdfium2](https://github.com/pypdfium2-team/pypdfium2),
[SearXNG search API](https://docs.searxng.org/dev/search_api.html).
