# UBI10 Minimal + Python 3.12 — glibc ≥ 2.39 required for openshell manylinux_2_39 wheels
FROM registry.access.redhat.com/ubi10/python-312-minimal

USER root

# Minimal image lacks common tools used below.
RUN microdnf install -y bash curl tar gzip shadow-utils procps-ng \
        vim less iputils mesa-libGL ca-certificates \
    && microdnf clean all

# Create the 'default' user (UID 1001, group 0) matching the full s2i convention.
# The minimal image only sets USER 1001 without a named entry in /etc/passwd.
RUN useradd -u 1001 -r -g 0 -d ${HOME} -s /sbin/nologin -c "Default Application User" default || true

USER default
RUN pwd
WORKDIR $HOME
# --------------------------------------------------------------------------
# Copy source trees
# --------------------------------------------------------------------------
ADD --chown=default:root --chmod=777 ./rag           $HOME/rag
ADD --chown=default:root --chmod=777 ./multi-agent   $HOME/multi-agent
ADD --chown=default:root --chmod=777 ./shared-resources/identity $HOME/shared-resources/identity
ADD --chown=default:root --chmod=777 ./global_utils  $HOME/global_utils

RUN chmod -R g+w rag multi-agent global_utils

# --------------------------------------------------------------------------
# Virtual environment + dependencies
# --------------------------------------------------------------------------
# Unset s2i auto-activate so subprocesses stay on our venv
ENV BASH_ENV=""
ENV ENV=""
ENV PROMPT_COMMAND=""

RUN python3 -m venv --prompt "tests-venv" venv

ENV VIRTUAL_ENV=$HOME/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Upgrade pip inside the venv (base ensurepip is too old for modern wheels)
RUN pip install --upgrade pip

# Install shared package
RUN pip install -e ./global_utils/

# RAG application dependencies
RUN pip install -e ./rag/

# Multi-agent application dependencies (includes openshell via [all])
RUN pip install -e "./multi-agent/[all]"

# Workaround: openshell Linux wheels ship without generated protobuf stubs.
# Mirrors multi-agent/Dockerfile — generate stubs from NVIDIA/OpenShell protos.
ARG OPENSHELL_PROTO_REF="main"
RUN pip install 'grpcio-tools>=1.68.0' && \
    PROTO_DIR=$(mktemp -d) && \
    SITE_PKG=$(python3 -c "import pathlib,site; p=next(pathlib.Path(site.getsitepackages()[0]).rglob('openshell/_proto')); print(p)") && \
    for f in datamodel.proto openshell.proto sandbox.proto inference.proto options.proto; do \
      curl -fsSL "https://raw.githubusercontent.com/NVIDIA/OpenShell/${OPENSHELL_PROTO_REF}/proto/$f" \
        -o "$PROTO_DIR/$f"; \
    done && \
    python3 -m grpc_tools.protoc \
      -I"$PROTO_DIR" \
      --python_out="$SITE_PKG" \
      --pyi_out="$SITE_PKG" \
      --grpc_python_out="$SITE_PKG" \
      "$PROTO_DIR"/datamodel.proto \
      "$PROTO_DIR"/openshell.proto \
      "$PROTO_DIR"/sandbox.proto \
      "$PROTO_DIR"/inference.proto \
      "$PROTO_DIR"/options.proto && \
    sed -i 's/^import datamodel_pb2/from . import datamodel_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import openshell_pb2/from . import openshell_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import sandbox_pb2/from . import sandbox_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import inference_pb2/from . import inference_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import options_pb2/from . import options_pb2/' "$SITE_PKG"/*.py && \
    rm -rf "$PROTO_DIR" && \
    python3 -c "import openshell; print('openshell SDK OK')"

# Shared resources dependencies
RUN pip install -e ./shared-resources/identity/

# Stress test dependencies
RUN pip install -r ./rag/tests/docs/requirements_stress_test.txt


# Test framework and utilities
RUN pip install \
    pytest \
    pytest-asyncio \
    pytest-mock \
    pytest-html \
    pytest-cov \
    pytest-xdist \
    pytest-timeout \
    pytest-benchmark \
    pytest-clarity \
    pytest-sugar \
    aiohttp \
    reportlab \
    requests \
    pyyaml

# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------
COPY --chown=default:root --chmod=755 ./tests/run_tests.sh $HOME/run_tests.sh

ENTRYPOINT ["./run_tests.sh"]
CMD ["all"]
