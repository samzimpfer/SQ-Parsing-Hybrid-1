# Data Rules
- Raw drawings are external to the repo.
- The system never assumes their location.
- Access to raw drawings is only via explicit configuration.
- No module may hardcode paths or access environment variables directly.
- Normalization outputs:
    - MAY be written inside the project (e.g. artifacts/)
    - MUST NOT modify raw input PDFs
    - MUST be explicitly configured (no implicit paths)
- No new environment variables are needed.

---

# Data Access
- The environment variable `DATA_ROOT` is read once and only once during application startup.
- The resolved `DATA_ROOT` value (with any necessary expansion, e.g., ~) is passed explicitly as a parameter or config object to all components requiring filesystem access.
- No module should read environment variables directly or rely on global state.