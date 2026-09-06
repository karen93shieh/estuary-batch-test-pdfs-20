# estuary-batch-test-pdfs-20

Twenty synthetic character-dossier PDFs for testing Estuary's batch character
creation endpoint (`POST /api/v1/characters/batch`, SCRUM-245) and the
per-character knowledge document endpoints. Every fact in every PDF is made up
and deterministic (seed 20260906), and `manifest.json` carries the answer key.

| | |
|---|---|
| Characters | 16 |
| PDFs | 20 (13 characters own 1, two own 2, one owns 3) |
| Pages | 237 total, 1 to 73 per file |
| Size | 0.5 MB total |
| Bilingual | `007-halcyon-hartwell.pdf` has a Chinese and Japanese section |
| URL pattern | `https://raw.githubusercontent.com/karen93shieh/estuary-batch-test-pdfs-20/main/pdfs/<file>` |

Files:

- `batch_request.json`: 16 items, 20 documents, ready to POST.
- `batch_request_10.json`: the first 10 items (document counts 1, 2, 3, 1, 1, 1, 1, 1, 2, 1).
- `batch_request_multi.json`: only the three multi-PDF characters.
- `manifest.json`: per character, the facts, which file holds each one, and `retrieval_checks` (question, expected answer, source file).
- `urls.txt`: all 20 URLs.
- `probe.py`: asks each created character its answer-key questions over the `/sdk` chat socket.
- `generate_pdfs.py` + `generate_pdfs_20.py`: regenerate the set.

## Model used by the items

Every item sets `"llm_provider": "openai", "llm_model": "gpt-5-nano"`. Without
those fields a character inherits the platform default, `gpt-5-mini`, which
OpenAI only serves to verified organizations; an unverified key fails every
turn with a 404 and the dashboard shows nothing. Change or delete the two
fields to test another model (for example `"llm_provider": "google"` and
`"llm_model": "gemini-2.5-flash"`). If you regenerate the set, re-add them; the
generator does not write them.

## Reproduce with curl

Bash (Git Bash on Windows works). `jq` is optional but the examples use it.

```bash
export BASE=http://localhost:4001          # production: https://api.estuary-ai.com
export API_KEY=est_...                     # an Estuary API key (dashboard -> API Keys)
git clone https://github.com/karen93shieh/estuary-batch-test-pdfs-20.git
cd estuary-batch-test-pdfs-20
```

### 1. Submit the batch

Characters are created before the response returns. Documents are fetched and
ingested afterwards by the worker. Expect `202`, a `Location` header, and
`Retry-After: 5`.

```bash
curl -i -X POST "$BASE/api/v1/characters/batch" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: pdf20-$(date +%s)" \
  --data-binary @batch_request.json
```

Copy the `id` from the body:

```bash
export BATCH_ID=cb_...
```

Optional headers: `X-Org-Id` makes the batch, its characters and documents
org-owned; `X-Player-Id` is stamped on every character.

### 2. Poll until it completes

```bash
curl -s "$BASE/api/v1/characters/batch/$BATCH_ID" -H "X-API-Key: $API_KEY" \
  | jq '{status, counts, documentCounts}'
```

Or loop:

```bash
until [ "$(curl -s "$BASE/api/v1/characters/batch/$BATCH_ID" -H "X-API-Key: $API_KEY" | jq -r .status)" != "processing" ]; do
  sleep 5; echo -n .
done; echo
```

Per-item detail, including each document's status and error:

```bash
curl -s "$BASE/api/v1/characters/batch/$BATCH_ID" -H "X-API-Key: $API_KEY" \
  | jq '.items[] | {customId, status, characterId, warnings: [.warnings[].code], documents: [.documents[] | {name, status, error}]}'
```

What a healthy run looks like on a local stack: `202` in about two seconds, all
20 documents `ready` in roughly a minute, every item `succeeded`, and one
warning per item, `text_only_inferred`, because the items configure no voice.

### 3. Inspect a character's documents

```bash
export CHAR_ID=$(curl -s "$BASE/api/v1/characters/batch/$BATCH_ID" -H "X-API-Key: $API_KEY" | jq -r '.items[2].characterId')   # Delphine, 3 PDFs

curl -s "$BASE/api/v1/characters/$CHAR_ID/documents" -H "X-API-Key: $API_KEY" \
  | jq '.documents[] | {id, filename, status, pageCount, chunkCount, sourceUrl}'
```

### 4. Add one more PDF to that character by URL

Runs as a one-document batch under the hood, so the response carries a
`batchId` you can retry or cancel.

```bash
curl -s -X POST "$BASE/api/v1/characters/$CHAR_ID/documents" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"url":"https://raw.githubusercontent.com/karen93shieh/estuary-batch-test-pdfs-20/main/pdfs/016-qadira-jessop.pdf","name":"Extra volume (test)","type":"pdf"}' \
  | tee /tmp/add.json | jq .

export DOC_ID=$(jq -r .documentId /tmp/add.json)
curl -s "$BASE/api/v1/characters/documents/$DOC_ID" -H "X-API-Key: $API_KEY" | jq '{status, pageCount, chunkCount, error}'
```

Private URLs can carry request headers: add `"headers": {"Authorization": "Bearer ..."}`
to the document object. They are encrypted at rest, dropped on cross-origin
redirects, wiped when the document finishes, and never echoed back.

### 5. Remove it

```bash
curl -i -X DELETE "$BASE/api/v1/characters/$CHAR_ID/documents/$DOC_ID" -H "X-API-Key: $API_KEY"   # 204
curl -i "$BASE/api/v1/characters/documents/$DOC_ID" -H "X-API-Key: $API_KEY"                      # 404
```

### 6. Retry and cancel

Retry creates a new batch containing every failed item plus, for succeeded
items with failed or cancelled documents, a document-only item that re-fetches
just those documents onto the existing character. `400` when nothing is
retryable, `409` while the original is still running.

```bash
curl -i -X POST "$BASE/api/v1/characters/batch/$BATCH_ID/retry" -H "X-API-Key: $API_KEY"
```

Cancel marks queued documents `cancelled`, lets in-flight fetches finish, and
keeps the characters. `409` once the batch is terminal.

```bash
curl -i -X POST "$BASE/api/v1/characters/batch/$BATCH_ID/cancel" -H "X-API-Key: $API_KEY"
```

### 7. List batches

```bash
curl -s "$BASE/api/v1/characters/batch?limit=10" -H "X-API-Key: $API_KEY" \
  | jq '.batches[] | {id, status, counts, retryOf}'
```

### 8. Rejections you can provoke

All return `422` and write nothing:

```bash
# duplicate customId
curl -s -X POST "$BASE/api/v1/characters/batch" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"requests":[{"customId":"dup","persona":{"name":"A"}},{"customId":"dup","persona":{"name":"B"}}]}' | jq .

# blocked host (cloud metadata address)
curl -s -X POST "$BASE/api/v1/characters/batch" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"requests":[{"customId":"x","persona":{"name":"A"},"documents":[{"url":"http://169.254.169.254/x.pdf"}]}]}' | jq .

# unsupported scheme and type
curl -s -X POST "$BASE/api/v1/characters/batch" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"requests":[{"customId":"x","persona":{"name":"A"},"documents":[{"url":"ftp://example.com/a.pdf","type":"docx"}]}]}' | jq .
```

A second submit while a batch is still running returns `429` with
`runningBatchId`. Re-sending the same body with the same `Idempotency-Key`
within 24 hours returns the original batch instead of creating another.

## Verify retrieval

`manifest.json` lists, for every character, the questions to ask and the file
that holds each answer. Facts are split per volume so a missing document is
detectable: the dossier holds the favourite dish, lucky number and pet name;
the relationships volume holds the workshop password, rival and mentor; each
chronicle volume holds one "what does X call the <thing>" nickname.

Ask through the dashboard, or run the probe against the batch you just created:

```bash
pip install "python-socketio[asyncio_client]"
python probe.py "$BASE" "$API_KEY" "$BATCH_ID"
```

Two things to know when scoring by hand. The characters have no voice
configured, so they are text-only. And the relationships text says the
character tells strangers the workshop password "is written on the wall", so
most characters repeat that line instead of the password; it is a role-play
choice, not a retrieval miss.

## Regenerate

```bash
pip install reportlab pymupdf
python generate_pdfs_20.py . https://raw.githubusercontent.com/<you>/<repo>/main/pdfs
```

Keep `.gitattributes` (`*.pdf binary`): reportlab writes uncompressed PDFs that
git's text heuristic would otherwise CRLF-convert on Windows and corrupt.
