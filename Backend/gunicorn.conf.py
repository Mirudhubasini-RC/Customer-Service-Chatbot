# Loaded automatically by gunicorn from the working directory (Render rootDir: Backend).
# The first SQL question loads the Schema RAG embedding model, which takes longer
# than gunicorn's 30s default on Render's small CPU; a killed worker returns a
# CORS-less 500 that the browser reports as "Failed to fetch".
timeout = 180
