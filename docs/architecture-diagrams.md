# Legal Document Assistant - Architecture Diagrams

System Architecture Overview

```mermaid
graph TB
    subgraph WebUI["Web UI (React/Vite)"]
        FE_APP[App shell and panels]
        FE_API[API client<br/>error envelope parser]
        FE_APP --> FE_API
    end

    subgraph Backend["API (FastAPI)"]
        BE_ROUTES[Routes /api/v1]
        BE_PIPE[Pipeline service<br/>ingest, summarize, verify]
        BE_ROUTES --> BE_PIPE
    end

    subgraph Storage["Local storage (data/)"]
        ST_UP[(uploads/case_id/)]
        ST_IDX[(cases_index.json)]
        ST_CHROMA[(Chroma PersistentClient<br/>one collection per case)]
    end

    subgraph Runtime["Local LLM runtime (Ollama)"]
        OL_GEN[POST /api/generate]
        OL_TAGS[GET /api/tags]
        OL_MODEL[qwen2.5:7b default]
        OL_GEN --> OL_MODEL
    end

    FE_API -->|"HTTP JSON + multipart<br/>/api/v1 via Vite proxy :5173"| BE_ROUTES
    BE_PIPE -->|file I/O| ST_UP
    BE_PIPE -->|atomic JSON writes| ST_IDX
    BE_PIPE -->|"upsert / query (in-process)"| ST_CHROMA
    BE_PIPE -->|"HTTP :11434"| OL_GEN
    BE_ROUTES -->|health probe| OL_TAGS

    style FE_APP fill:#7b68ee
    style FE_API fill:#7b68ee
    style BE_ROUTES fill:#4a90e2
    style BE_PIPE fill:#4a90e2
    style ST_UP fill:#50c878
    style ST_IDX fill:#50c878
    style ST_CHROMA fill:#50c878
    style OL_GEN fill:#ffa500
    style OL_TAGS fill:#ffa500
    style OL_MODEL fill:#ffa500
```

## Component Interaction Diagram - Ingest

```mermaid
sequenceDiagram
    participant User
    participant UI as Web UI
    participant API as FastAPI
    participant Store as Storage service
    participant Pipe as Pipeline
    participant Emb as Embeddings
    participant VS as Chroma

    User->>UI: Create case
    UI->>API: POST /api/v1/cases
    API->>Store: Create case record
    Store-->>API: CaseResponse (status empty)
    API-->>UI: 201 CaseResponse

    User->>UI: Upload Bulgarian PDF or TXT
    UI->>API: POST /api/v1/cases/{case_id}/documents (multipart file)
    API->>API: Validate size, suffix .pdf or .txt, content type, non-empty, %PDF header
    API->>Store: Write file, record sha256
    Store-->>API: DocumentResponse
    API-->>UI: 201 DocumentResponse (case status uploaded)

    User->>UI: Click Ingest
    UI->>API: POST /api/v1/cases/{case_id}/ingest
    API->>Pipe: ingest_case(case_id)
    Pipe->>Store: Load documents
    alt No documents
        Pipe-->>API: no_documents
        API-->>UI: 409 error envelope
    else Documents present
        loop Each document
            Pipe->>Pipe: Extract text and split into chunks
        end
        alt Extraction error or no text in any document
            Pipe-->>API: ingest_failed (index left untouched)
            API-->>UI: 500 error envelope
        else Chunks available
            Pipe->>VS: Reset case collection
            Pipe->>Emb: Embed chunk texts
            Emb-->>Pipe: Vectors
            Pipe->>VS: Upsert chunks with metadata
            Pipe->>Store: Mark case ingested, set chunk_count and ingested_at
            Pipe-->>API: IngestResponse
            API-->>UI: 200 IngestResponse
        end
    end
```

## Component Interaction Diagram - Summarize

```mermaid
sequenceDiagram
    participant User
    participant UI as Web UI
    participant API as FastAPI
    participant Pipe as Pipeline
    participant VS as Chroma
    participant LLM as LLM client
    participant OL as Ollama
    participant Cit as Citation checker

    User->>UI: Click Summarize
    UI->>API: POST /api/v1/cases/{case_id}/summarize (top_k optional, default 8)
    API->>Pipe: summarize_case(case_id, top_k)
    alt Case status empty or uploaded
        Pipe-->>API: case_not_ingested
        API-->>UI: 409 error envelope
    else Index available
        Pipe->>VS: Query top_k chunks for the case
        VS-->>Pipe: Chunks with metadata and distances
        Pipe->>LLM: Numbered excerpts + Bulgarian system prompt
        LLM->>OL: POST /api/generate (stream false)
        alt Ollama answers
            OL-->>LLM: JSON summary + citation_indices or citations as index and quote
            LLM-->>Pipe: text, stubbed false
        else Ollama unreachable and stub enabled
            LLM-->>Pipe: stub text, stubbed true
        end
        Pipe->>Cit: Map index and quote items to chunks, check quotes verbatim
        Cit-->>Pipe: Citation list
        Pipe-->>API: SummarizeResponse
        API-->>UI: 200 summary, citations, model, stubbed
    end
    User->>UI: Inspect citations, accept or reject
```

## Component Interaction Diagram - Verify

```mermaid
sequenceDiagram
    participant User
    participant UI as Web UI
    participant API as FastAPI
    participant Pipe as Pipeline
    participant VS as Chroma
    participant LLM as LLM client
    participant OL as Ollama
    participant Cit as Citation checker

    User->>UI: Enter claim in Bulgarian
    UI->>API: POST /api/v1/cases/{case_id}/verify (claim, top_k optional, default 5)
    API->>API: Validate claim length 3 to 1000
    API->>Pipe: verify_claim(case_id, claim, top_k)
    alt Case status empty or uploaded
        Pipe-->>API: case_not_ingested
        API-->>UI: 409 error envelope
    end
    Pipe->>VS: Query top_k chunks for claim text
    VS-->>Pipe: Retrieved chunks
    Pipe->>LLM: Claim + numbered quotes + JSON instructions
    LLM->>OL: POST /api/generate
    OL-->>LLM: JSON verdict, rationale, supporting_quotes and denying_quotes as index and quote pairs
    LLM-->>Pipe: raw text, stubbed flag
    Pipe->>Pipe: Parse JSON, normalise verdict (legacy index lists accepted)
    Pipe->>Cit: Resolve each index to a retrieved chunk, check quote against its text
    Note over Pipe,Cit: Invalid index, so attribute quote to the chunk that contains it, else drop
    Cit-->>Pipe: Citations with verbatim true or false
    Pipe-->>API: VerifyResponse
    API-->>UI: 200 verdict, rationale, quotes, model, stubbed
    User->>UI: Review quotes before using the result
```

## Data Model Diagram

```mermaid
erDiagram
    Case ||--o{ Document : "contains"
    Document ||--o{ Chunk : "split into"
    Case ||--o{ Chunk : "indexed in collection"
    Chunk ||--o{ Citation : "quoted by"
    SummaryResult ||--o{ Citation : "citations"
    VerifyResult ||--o{ Citation : "supporting, denying, retrieved"
    Case ||--o{ SummaryResult : "summarized as"
    Case ||--o{ VerifyResult : "claims checked"

    Case {
        uuid id PK
        string title "1 to 200 chars"
        string description "optional, up to 2000"
        enum status "empty, uploaded, ingested, stale"
        int document_count
        int chunk_count
        datetime created_at
        datetime updated_at
        datetime ingested_at "nullable"
    }

    Document {
        uuid id PK
        uuid case_id FK
        string filename
        string content_type "application/pdf or text/plain"
        int size_bytes
        string sha256
        datetime uploaded_at
    }

    Chunk {
        string chunk_id PK
        uuid document_id FK
        string document_filename
        int chunk_index
        string text
        vector embedding "MiniLM, nomic or hash_stub"
    }

    Citation {
        uuid document_id FK
        string document_filename
        string chunk_id FK
        int chunk_index "nullable"
        string quote
        float relevance "nullable"
        bool verbatim
    }

    SummaryResult {
        uuid case_id FK
        string summary
        string model
        bool stubbed
        int chunks_used
        float duration_ms
    }

    VerifyResult {
        uuid case_id FK
        string claim "3 to 1000 chars"
        enum verdict "supported, denied, inconclusive"
        string rationale
        string model
        bool stubbed
        float duration_ms
    }
```

## Evaluation Data Model Diagram

Evaluation artefacts are JSON and JSONL files under `eval/`, not database tables. Source licences are recorded per passage in the manifest `license` field and summarised in `LICENSE-NOTES.md`. Run logs are written to `eval/runs/` and are not versioned.

```mermaid
erDiagram
    Passage ||--o{ SeedClaim : "has"
    EvalRun ||--o{ EvalItem : "contains"
    Passage ||--o{ EvalItem : "evaluated in"
    SeedClaim ||--o{ EvalItem : "checked in"

    Passage {
        string id PK "P1 to P5"
        string language "bg"
        string source
        string celex_id "nullable, pending for P3"
        string license "e.g. CC-BY-SA 4.0"
        string split
        date retrieved_at
        string file_hash "SHA-256"
        int token_count_approx
        string tasks "summarize, verify"
        string notes
    }

    SeedClaim {
        string claim_id PK
        string passage_id FK
        string language "bg"
        string claim_text
        enum gold_label "SUPPORTED, REFUTED, NEI"
        string gold_evidence "chunk id or char span plus quote"
        string trap_type "optional"
        string annotator_notes
    }

    EvalRun {
        string run_id PK
        string package_version "eval-v0.1"
        string manifest_hash
        string model_tag "qwen2.5:7b, bggpt-7b, llama3.1:8b"
        string quantization
        int num_ctx
        float temperature
        int top_k
        int chunk_size
        int chunk_overlap
        string embedding_model
        string ollama_version
        string chat_template
        string git_commit
        datetime started_at
    }

    EvalItem {
        string run_id FK
        string scenario "S1 to S5"
        string passage_id FK
        string claim_id FK "null for summarize"
        string task "summarize or verify"
        string predicted_verdict "nullable"
        string gold_label "nullable"
        bool stubbed "excluded from scoring if true"
        int latency_ms
    }
```

## Data Flow Diagram - Document Upload Validation

```mermaid
flowchart TD
    Start([POST /api/v1/cases/case_id/documents]) --> FindCase{Case exists?}
    FindCase -->|No| E404[404 case_not_found]
    FindCase -->|Yes| Size{Size within<br/>MAX_UPLOAD_MB?}
    Size -->|No| E413[413 payload_too_large]
    Size -->|Yes| Suffix{Suffix .pdf or .txt?}
    Suffix -->|No| E415a[415 unsupported_media_type]
    Suffix -->|Yes| CType{Declared content type<br/>matches suffix?<br/>octet-stream or none accepted}
    CType -->|No| E415b[415 unsupported_media_type]
    CType -->|Yes| NonEmpty{File has bytes?}
    NonEmpty -->|No| E400[400 empty_file]
    NonEmpty -->|Yes| IsPdf{PDF?}
    IsPdf -->|Yes| Magic{"Content starts with %PDF?"}
    Magic -->|No| E415c[415 unsupported_media_type<br/>content is not a PDF]
    Magic -->|Yes| Store[Store file, sha256,<br/>canonical content type]
    IsPdf -->|No, TXT| Store
    Store --> Status[Case status: empty to uploaded,<br/>ingested or stale to stale]
    Status --> Done[201 DocumentResponse]

    style Start fill:#4a90e2
    style Done fill:#50c878
    style E404 fill:#ff6b6b
    style E413 fill:#ff6b6b
    style E415a fill:#ff6b6b
    style E415b fill:#ff6b6b
    style E415c fill:#ff6b6b
    style E400 fill:#ff6b6b
```

## Data Flow Diagram - Ingest

```mermaid
flowchart TD
    Start([POST /api/v1/cases/case_id/ingest]) --> FindCase{Case exists?}
    FindCase -->|No| E404[404 case_not_found]
    FindCase -->|Yes| HasDocs{Any documents?}
    HasDocs -->|No| E409[409 no_documents]
    HasDocs -->|Yes| InitEmb{Configured embedding<br/>backend loads?}
    InitEmb -->|Yes| Loop[Next document]
    InitEmb -->|No| Fallback[Fall back to hash_stub<br/>report embedding_backend]
    Fallback --> Loop
    Loop --> Extract{Text extracted?<br/>pypdf or TXT read}
    Extract -->|Extraction error| E500[500 ingest_failed<br/>details name the document<br/>existing index untouched]
    Extract -->|File missing on disk| Skip[Skip document<br/>log warning]
    Skip --> More
    Extract -->|Yes| Chunk[Split into overlapping chunks<br/>CHUNK_SIZE / CHUNK_OVERLAP]
    Chunk --> More{More documents?}
    More -->|Yes| Loop
    More -->|No| AnyText{Any chunks<br/>at all?}
    AnyText -->|No| E500b[500 ingest_failed<br/>no extractable text<br/>existing index untouched]
    AnyText -->|Yes| Reset[Reset case collection<br/>re-ingest rebuilds it]
    Reset --> Embed[Embed chunks]
    Embed --> Upsert[Upsert into Chroma<br/>document_id, filename, chunk_index]
    Upsert --> Mark[Case status = ingested<br/>chunk_count, ingested_at,<br/>embedding backend and model]
    Mark --> Done[200 IngestResponse<br/>persisted, duration_ms]

    style Start fill:#4a90e2
    style Done fill:#50c878
    style Fallback fill:#ffa500
    style Skip fill:#ffa500
    style E404 fill:#ff6b6b
    style E409 fill:#ff6b6b
    style E500 fill:#ff6b6b
    style E500b fill:#ff6b6b
```

## Data Flow Diagram - Verify

```mermaid
flowchart TD
    Start([POST /api/v1/cases/case_id/verify]) --> Valid{Claim 3 to 1000 chars<br/>top_k 1 to 20?}
    Valid -->|No| E422[422 validation_error]
    Valid -->|Yes| Status{Case status<br/>ingested or stale?}
    Status -->|No| E409[409 case_not_ingested]
    Status -->|Yes| Retrieve[Retrieve top_k chunks for the claim<br/>top_k null uses VERIFY_TOP_K = 5]
    Retrieve --> Prompt[Prompt: claim + numbered quotes<br/>use only these quotes as evidence<br/>answer inconclusive when they give no support]
    Prompt --> Gen{Ollama generate ok?}
    Gen -->|No, stub enabled| Stub[Stub verdict inconclusive<br/>retrieved chunks as raw excerpts<br/>verbatim true, stubbed true]
    Gen -->|No, stub disabled| E503[503 llm_unavailable]
    Gen -->|Yes| Parse{Valid JSON with<br/>known verdict?}
    Parse -->|No| Inconc1[verdict = inconclusive<br/>rationale explains parse failure]
    Parse -->|Yes| Format{Evidence format}
    Format -->|"index + quote pairs"| Map[Resolve index to retrieved chunk<br/>invalid index: find chunk containing quote,<br/>else drop the quote]
    Format -->|"legacy index lists"| Legacy[Use chunk excerpt as quote]
    Map --> Verbatim[Verbatim check per quote<br/>NFC, whitespace collapsed]
    Legacy --> Verbatim
    Verbatim --> Flag[Keep non-verbatim quotes<br/>with verbatim false]
    Flag --> Empty{Any evidence<br/>returned?}
    Empty -->|No| Top[Attach top retrieved chunk<br/>so the closest excerpt is visible]
    Empty -->|Yes| Verdict{Model verdict}
    Top --> Verdict
    Verdict -->|supported / denied| Quotes[Supporting or denying quotes<br/>+ all retrieved quotes]
    Verdict -->|inconclusive| Inconc2[No support either way<br/>retrieved quotes still returned]
    Stub --> Resp[200 VerifyResponse]
    Inconc1 --> Resp
    Inconc2 --> Resp
    Quotes --> Resp

    style Start fill:#4a90e2
    style Resp fill:#50c878
    style Stub fill:#ffa500
    style Inconc1 fill:#ffa500
    style Inconc2 fill:#ffa500
    style Top fill:#ffa500
    style E422 fill:#ff6b6b
    style E409 fill:#ff6b6b
    style E503 fill:#ff6b6b
```

## Case Lifecycle State Diagram

```mermaid
stateDiagram-v2
    [*] --> empty: Case created
    empty --> uploaded: Upload document
    uploaded --> uploaded: Upload another document
    uploaded --> ingested: Ingest
    ingested --> stale: Upload or delete a document
    stale --> stale: Further uploads or deletions
    uploaded --> uploaded: Delete a document, others remain
    stale --> ingested: Re-ingest rebuilds collection
    uploaded --> empty: Delete last document
    ingested --> empty: Delete last document
    stale --> empty: Delete last document
    empty --> [*]: Delete case
    uploaded --> [*]: Delete case
    ingested --> [*]: Delete case
    stale --> [*]: Delete case

    note right of empty
        document_count = 0
        collection cleared when last document deleted
        ingest returns 409 no_documents
        summarize and verify return 409 case_not_ingested
    end note

    note right of uploaded
        Files on disk, no index yet
        summarize and verify return 409 case_not_ingested
    end note

    note right of ingested
        Chroma collection matches documents
        chunk_count and ingested_at set
    end note

    note right of stale
        Index exists but documents changed
        deleted documents already removed from Chroma
        new uploads not indexed until re-ingest
        summarize and verify still allowed
        UI suggests re-ingest
    end note
```

## Service and Deployment Architecture

```mermaid
graph LR
    subgraph Local["Local machine (no cloud)"]
        subgraph Client["Client"]
            Browser[Web browser<br/>127.0.0.1:5173]
        end

        subgraph Dev["Vite dev server :5173"]
            Vite[Static assets<br/>proxy /api to :8000]
        end

        subgraph ApiProc["FastAPI process (uvicorn :8000)"]
            App[FastAPI app<br/>create_app]
            Emb[MiniLM embedder<br/>CPU, in-process]
            ChromaClient[Chroma PersistentClient<br/>in-process]
        end

        subgraph Disk["Disk ./data"]
            Uploads[(uploads/)]
            Index[(cases_index.json)]
            ChromaDir[(chroma/)]
        end

        subgraph OllamaProc["Ollama daemon :11434"]
            Ollama[Ollama HTTP API]
            Models[(Model files<br/>one 7B to 8B Q4 loaded)]
        end
    end

    Browser -->|HTTP| Vite
    Vite -->|"proxy /api (HTTP JSON)"| App
    App --> Emb
    App --> ChromaClient
    ChromaClient -->|files| ChromaDir
    App -->|files| Uploads
    App -->|atomic writes| Index
    App -->|"HTTP /api/generate, /api/tags"| Ollama
    Ollama --> Models

    style Browser fill:#7b68ee
    style Vite fill:#7b68ee
    style App fill:#4a90e2
    style Emb fill:#4a90e2
    style ChromaClient fill:#4a90e2
    style Uploads fill:#50c878
    style Index fill:#50c878
    style ChromaDir fill:#50c878
    style Ollama fill:#ffa500
    style Models fill:#ffa500
```

## Docker Compose Deployment (optional)

```mermaid
graph LR
    subgraph Local["Local machine (no cloud)"]
        Browser[Web browser<br/>localhost:8080]

        subgraph ComposeNet["docker compose network"]
            subgraph FrontendSvc["frontend service (nginx) :8080 to :80"]
                Nginx[nginx<br/>static build + SPA fallback<br/>client_max_body_size 25m]
            end

            subgraph BackendSvc["backend service :8000"]
                Api[FastAPI 0.2.0<br/>LOG_FORMAT json]
            end

            subgraph OllamaSvc["ollama service :11434"]
                OllamaC[Ollama HTTP API]
            end

            DataVol[(backend-data volume<br/>/data: uploads, index, chroma)]
            ModelVol[(ollama volume<br/>model files)]
        end
    end

    Browser -->|HTTP| Nginx
    Nginx -->|"proxy /api/ to backend:8000"| Api
    Api -->|"OLLAMA_BASE_URL http://ollama:11434"| OllamaC
    Api --> DataVol
    OllamaC --> ModelVol

    style Browser fill:#7b68ee
    style Nginx fill:#7b68ee
    style Api fill:#4a90e2
    style OllamaC fill:#ffa500
    style DataVol fill:#50c878
    style ModelVol fill:#50c878
```

Models are pulled once inside the Ollama container (`docker compose exec ollama ollama pull qwen2.5:7b`). Ports 8000 and 11434 are also published on the host for the OpenAPI docs and diagnostics.

## Error Handling and Stub Fallback Flow

```mermaid
flowchart TD
    Req[Incoming request] --> RID{X-Request-ID<br/>header present?}
    RID -->|Yes| Echo[Reuse client request id]
    RID -->|No| Gen[Generate UUID]
    Echo --> Route[Route handler]
    Gen --> Route
    Route --> Valid{Request valid?}
    Valid -->|No| E422[422 validation_error]
    Valid -->|Yes| Svc[Service call]
    Svc -->|AppError raised| Map[Map to code and status<br/>case_not_found, no_documents,<br/>case_not_ingested, payload_too_large, ...]
    Svc -->|Unexpected exception| E500[500 internal_error<br/>stack trace logged, not returned]
    Svc -->|Needs generation| LLM{Ollama generate ok?<br/>connect, timeout, HTTP, empty}
    LLM -->|Yes| Ok[2xx response<br/>stubbed = false]
    LLM -->|No| StubCfg{OLLAMA_STUB_ON_UNAVAILABLE?}
    StubCfg -->|true| Stub[2xx response<br/>stubbed = true<br/>citations from retrieved chunks]
    StubCfg -->|false| E503[503 llm_unavailable]
    Svc -->|No generation needed| Ok
    E422 --> Env[Error envelope<br/>error.code, error.message,<br/>error.details, request_id]
    Map --> Env
    E500 --> Env
    E503 --> Env
    Env --> Out[Response + X-Request-ID header<br/>access log line with request id]
    Ok --> Out
    Stub --> Out

    style Req fill:#4a90e2
    style Ok fill:#50c878
    style Stub fill:#ffa500
    style E422 fill:#ff6b6b
    style E500 fill:#ff6b6b
    style E503 fill:#ff6b6b
    style Map fill:#ff6b6b
```

## Model Switching and A/B Evaluation Flow

```mermaid
flowchart TD
    Start([Select generator]) --> Which{Generator role}
    Which -->|Baseline| Qwen[ollama pull qwen2.5:7b]
    Which -->|Control| Llama[ollama pull llama3.1:8b]
    Which -->|A/B| GGUF[Download BgGPT-7B-Instruct-v0.2<br/>Q4_K_M GGUF]
    GGUF --> Modelfile[Modelfile: FROM path to GGUF<br/>Mistral INST template]
    Modelfile --> Create[ollama create bggpt-7b -f Modelfile]
    Qwen --> SetEnv[Set OLLAMA_MODEL to the tag<br/>restart API]
    Llama --> SetEnv
    Create --> SetEnv
    SetEnv --> Check[GET /api/v1/models<br/>active tag installed?]
    Check --> Frozen{eval-v0.1 frozen?}
    Frozen -->|No| Stop[Do not run comparison<br/>freeze package first]
    Frozen -->|Yes| Const[Constant parameters:<br/>embedding model, chunk size and overlap,<br/>top_k, temperature 0.0, num_ctx 4096,<br/>system prompt]
    Const --> Run[python -m app.eval.run<br/>S1 to S5 in fixed order]
    Run --> Log[Run log: model tag, quantization,<br/>num_ctx, temperature, top_k, chunking,<br/>embedding model, Ollama version,<br/>chat template, manifest hash, git commit, date]
    Log --> StubCheck{Any stubbed items?}
    StubCheck -->|Yes| Rerun[Exclude and re-run<br/>with Ollama reachable]
    Rerun --> Run
    StubCheck -->|No| Score[python -m app.eval.score<br/>+ blinded human annotation]
    Score --> AllDone{All three generators done?}
    AllDone -->|No| Start
    AllDone -->|Yes| Rule{"BgGPT better than or equal to Qwen<br/>on faithfulness and citation support<br/>(Bulgarian S1 to S5)?"}
    Rule -->|Yes| BgDefault[BgGPT becomes default generator]
    Rule -->|No| QwenDefault[Qwen stays default<br/>BgGPT reported as alternative<br/>Llama read as control only]

    style Start fill:#4a90e2
    style BgDefault fill:#50c878
    style QwenDefault fill:#50c878
    style Stop fill:#ff6b6b
    style Rerun fill:#ffa500
```

## Backend Module Dependency Graph

```mermaid
graph TD
    subgraph Entry["Entry"]
        Main[main.py<br/>create_app]
    end

    subgraph Routes["routes/ (HTTP, /api/v1)"]
        RInit[routes/__init__.py<br/>api_router]
        RSys[system.py]
        RCases[cases.py]
        RDocs[documents.py]
        RRag[rag.py]
    end

    subgraph Schemas["schemas/ (pydantic)"]
        SCommon[common.py<br/>ErrorBody, ErrorResponse]
        SOther[system, cases,<br/>documents, rag]
    end

    subgraph Services["services/"]
        Pipe[pipeline.py]
        Storage[storage.py]
        Extract[extraction.py]
        Chunk[chunking.py]
        Embed[embeddings.py]
        VStore[vector_store.py]
        LLM[llm.py]
        Prompts[prompts.py]
        Cit[citations.py]
    end

    subgraph Core["core/"]
        Config[config.py]
        Logging[logging.py]
        Errors[errors.py]
        MW[middleware.py]
    end

    subgraph Eval["eval/ (CLI)"]
        ERun[run.py]
        EScore[score.py]
        EManifest[manifest loader]
    end

    Main --> RInit
    Main --> MW
    Main --> Errors
    Main --> Logging
    Main --> Config
    RInit --> RSys
    RInit --> RCases
    RInit --> RDocs
    RInit --> RRag
    RSys --> LLM
    RSys --> Embed
    RCases --> Storage
    RCases --> VStore
    RDocs --> Storage
    RRag --> Pipe
    Routes --> Schemas
    SOther --> SCommon
    Pipe --> Storage
    Pipe --> Extract
    Pipe --> Chunk
    Pipe --> VStore
    Pipe --> LLM
    Pipe --> Prompts
    Pipe --> Cit
    VStore --> Embed
    Services --> Config
    Services --> Errors
    ERun --> EManifest
    ERun --> Pipe
    EScore --> EManifest

    style Main fill:#4a90e2
    style Pipe fill:#7b68ee
    style LLM fill:#ffa500
    style VStore fill:#50c878
    style Storage fill:#50c878
    style Errors fill:#ff6b6b
```

## Memory Budget Note (about 16 GB RAM)

Qualitative view; measured peak RAM belongs to the evaluation protocol and is not stated here.

```mermaid
graph TB
    subgraph Budget["About 16 GB system RAM"]
        Reserve[Reserve about 4 to 6 GB<br/>OS, FastAPI, MiniLM on CPU, Chroma]
        Weights[One generator loaded<br/>Q4 model file about 4.4 to 4.9 GB]
        KV[KV cache grows with num_ctx<br/>moderate num_ctx 4096 by default]
    end

    subgraph Rules["Design rules"]
        R1[One Ollama model at a time]
        R2[Embeddings on CPU, no second large model]
        R3[Retrieve top-k chunks<br/>never the whole case in one prompt]
    end

    subgraph Excluded["Excluded by the hardware filter"]
        X1[70B class]
        X2[Mixtral 8x7B, about 26 GB at Q4]
        X3[BgGPT 27B]
        X4[Qwen2.5-14B, about 9 GB at Q4<br/>borderline with the RAG stack]
    end

    Weights --- KV
    R1 --> Weights
    R2 --> Reserve
    R3 --> KV
    Excluded -.->|does not fit| Budget

    style Reserve fill:#50c878
    style Weights fill:#4a90e2
    style KV fill:#ffa500
    style X1 fill:#ff6b6b
    style X2 fill:#ff6b6b
    style X3 fill:#ff6b6b
    style X4 fill:#ffa500
```
