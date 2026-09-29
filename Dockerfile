# OpenSandbox server, Docker runtime.
#
# Based on the official release image rather than the PyPI package: the
# opensandbox-server 1.1.0 wheel on PyPI is missing its generated gRPC stubs
# and crashes on import (fixed upstream after the release).
#
# The server does not run sandboxes itself: it asks the Docker daemon to, so
# mount the host's Docker socket.
#
#   docker build -t opensandbox-server .
#   docker run --rm -p 8080:8080 \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -e OPENSANDBOX_INSECURE_SERVER=YES \
#     opensandbox-server
#
# To require an API key instead of OPENSANDBOX_INSECURE_SERVER, mount your own
# config over /etc/opensandbox/config.toml with server.api_key set.
#
# Clients must route sandbox traffic through the server (SDK:
# ConnectionConfigSync(..., use_server_proxy=True)). The server reports sandbox
# endpoints on Docker's bridge network, which the host cannot reach directly,
# and the server can only reach them from inside that network.
ARG OPENSANDBOX_VERSION=1.1.0
FROM opensandbox/server:release-${OPENSANDBOX_VERSION}

# The base image ships a Kubernetes config. Replace it with the packaged Docker
# example, listening on all interfaces so the port can be published.
RUN opensandbox-server init-config /etc/opensandbox/config.toml --example docker --force \
    && sed -i 's/^host = "127.0.0.1"/host = "0.0.0.0"/' /etc/opensandbox/config.toml

# SQLite store (sandbox and snapshot records).
VOLUME ["/root/.opensandbox"]

EXPOSE 8080
