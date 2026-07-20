# Use Red Hat Universal Base Image 10 Minimal (UBI10) — ships glibc ≥ 2.39 and Python 3.12
FROM registry.access.redhat.com/ubi10/python-312-minimal
#ARG comp="multi-agent"

USER root

# The minimal image lacks bash, curl, tar, and shadow-utils (useradd).
# Install these first since the rest of the Dockerfile depends on them.
RUN microdnf install -y bash curl tar gzip shadow-utils procps-ng && microdnf clean all

# Create the 'default' user (UID 1001, group 0) matching the full s2i image convention.
# The minimal image only sets USER 1001 without a named entry in /etc/passwd.
RUN useradd -u 1001 -r -g 0 -d ${HOME} -s /sbin/nologin -c "Default Application User" default || true

#the line below is meant to add mongosh to the image (not the server though), this is for debugging option
# NOTE: the version we use here is mongo 8 if building this part fails you might need to find the latest available mongo shell repo.
RUN echo -e "[mongodb-org-8.0]\nname=MongoDB Repository\nbaseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/8.0/\$basearch/\ngpgcheck=1\nenabled=1\ngpgkey=https://www.mongodb.org/static/pgp/server-8.0.asc" > /etc/yum.repos.d/mongodb-org-8.0.repo
RUN microdnf update -y && microdnf install -y vim less iputils mongodb-mongosh ca-certificates && microdnf clean all

# Install OpenShift CLI (oc) for oc_exec tool — pick the right binary for the build arch
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
      OC_URL="https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux-arm64.tar.gz"; \
    else \
      OC_URL="https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz"; \
    fi && \
    curl -fSL "$OC_URL" -o /tmp/openshift-client.tar.gz && \
    tar -xzf /tmp/openshift-client.tar.gz -C /tmp && \
    mv /tmp/oc /usr/local/bin/oc && \
    chmod +x /usr/local/bin/oc && \
    rm -f /tmp/openshift-client.tar.gz /tmp/kubectl /tmp/README.md && \
    oc version --client

# 'update-ca-trust enable' was removed in RHEL 10 — it is enabled by default

ARG CERT_URL="https://certs.corp.redhat.com/certs/Current-IT-Root-CAs.pem"
ARG CERT_NAME="Current-IT-Root-CAs.pem"

# Download and add the certificate to the system trust store
RUN curl -fSL "$CERT_URL" -o /etc/pki/ca-trust/source/anchors/$CERT_NAME && \
    update-ca-trust extract

# Ensure the CA bundle is readable by all users
RUN chmod 644 /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

# Set environment variables to use the system bundle (which now includes your company CA + public CAs)
ENV SSL_CERT_FILE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
ENV REQUESTS_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
ENV CURL_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

ADD  --chown=default:root --chmod=777 ./multi-agent $HOME/app
ADD  --chown=default:root --chmod=777 ./global_utils $HOME/global_utils
ADD  --chown=default:root --chmod=777 ./scripts $HOME/scripts

WORKDIR $HOME
COPY ./multi-agent/entrypoint.sh ./app/entrypoint.sh
RUN chmod +x ./app/entrypoint.sh
RUN pwd
RUN mkdir -p -m 777 $HOME/app/venv $HOME/app/logs $HOME/app/shared
RUN ls -lia
RUN chmod -R g+w .

USER default
RUN ls -lia

# The base image sets BASH_ENV / ENV / PROMPT_COMMAND to auto-activate its own
# venv at /opt/app-root. Unset these so bash subprocesses don't silently switch
# away from the app venv.
ENV BASH_ENV=""
ENV ENV=""
ENV PROMPT_COMMAND=""

# Create the app venv, activate it via PATH, then upgrade pip inside it.
RUN python3 -m venv --prompt "virtualenv" $HOME/app/venv
ENV VIRTUAL_ENV=$HOME/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --upgrade pip

RUN pip install -e "./app/[all]"
RUN pip install -e './global_utils/[multi-agent]'

# Workaround: openshell Linux wheels ship without generated protobuf stubs.
# Download .proto sources from the OpenShell repo and generate them into the
# installed package. This mirrors the upstream python:proto build task.
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
      "$PROTO_DIR"/inference.proto && \
    sed -i 's/^import datamodel_pb2/from . import datamodel_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import openshell_pb2/from . import openshell_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import sandbox_pb2/from . import sandbox_pb2/' "$SITE_PKG"/*.py && \
    sed -i 's/^import inference_pb2/from . import inference_pb2/' "$SITE_PKG"/*.py && \
    rm -rf "$PROTO_DIR" && \
    python3 -c "import openshell; print('openshell SDK OK')"

ENTRYPOINT ["./app/entrypoint.sh"]
