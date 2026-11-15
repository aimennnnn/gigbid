# GigBid in ONE container, for a free host that gives you one port (Render free web service: it sets $PORT).
# It builds from the public GitHub repo: the clone below, not the build context, is what runs.
FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
USER node
ENV HOME=/home/node UV_LINK_MODE=copy NEXT_TELEMETRY_DISABLED=1
WORKDIR /home/node
# change this value to make the host fetch the newest commit instead of reusing its cached copy
ARG CODE_VERSION=1
RUN git clone --depth 1 https://github.com/aimennnnn/gigbid.git app
WORKDIR /home/node/app
RUN uv sync --frozen --no-dev
RUN cd apps/web && npm ci && NEXT_PUBLIC_API_URL=same-origin GIGBID_API_PROXY=http://127.0.0.1:8000 npm run build
# Stand-in models by default: it starts with no key. For the real open model set GROQ_API_KEY as a secret and
# GIGBID_LLM=real (and GIGBID_RAG_MODELS=real) as variables in the host's settings.
ENV GIGBID_LLM=fake GIGBID_RAG_MODELS=fake GIGBID_STATE_DIR=/home/node/state PORT=7860
EXPOSE 7860
CMD ["bash", "infra/space/start.sh"]
