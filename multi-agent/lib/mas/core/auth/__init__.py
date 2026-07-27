"""
Auth layer — scheme-agnostic authentication infrastructure.

Subpackages:
  credentials/   — token storage, retrieval, presentation
  discovery/     — detect what auth a server requires
  strategies/    — concrete strategy implementations (oauth2, api_key, ...)

Consumers depend only on :class:`credentials.AuthCredential`.
"""
