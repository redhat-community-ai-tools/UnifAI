Stage 1 — Domain & Pipeline Context (foundation)

Add owner_id: str field to PipelineContext dataclass in rag/core/pipeline/domain/port.py
Update build_context() in rag/infrastructure/celery/workers/pipeline_tasks.py to extract owner_id from source_data["upload_by"] (with validation)
Update test fixtures that construct PipelineContext

Stage 2 — Ingestion: stamp chunks with owner_id

Add "owner_id": context.owner_id to chunk metadata in DocumentPipelineHandler.chunk_and_embed()
Same for SlackPipelineHandler.chunk_and_embed()
Update related tests
Stage 3 — Qdrant index

Add metadata.owner_id keyword index in QdrantVectorRepository.initialize()
Stage 4 — Retrieval: enforce mandatory owner_id filtering

Modify RetrievalService.search() — replace scope/user with mandatory owner_id, always apply filter
Update SearchQuery dataclass accordingly
Update SourceFilterResolver if needed (add upload_by filter to MongoDB tag/doc resolution too)
Stage 5 — HTTP endpoints: wire owner_id from session

Update docs.py /query.match — remove scope param, pass owner_id=g.user_id
Update slack.py /query.match — same
Add @rag_require_session to /available.docs.get and /available.tags.get
Scope DocumentService.get_available_tags() and list_available_docs() by upload_by
Stage 6 — Migration CLI

New rag/infrastructure/cli/migrate_owner_id.py — batched set_payload backfill from MongoDB
Create the metadata.owner_id index on existing collections
Stage 7 — MAS coordination (separate PR likely)

Address the MAS loggedInUser query param mismatch
Fix Slack retriever using raw requests.get without session cookie
Stages 1-3 are the write-path foundation. Stage 4-5 are the read-path enforcement + your points about tags/docs listing. Stage 6 is the migration. Stage 7 is a follow-up concern.

