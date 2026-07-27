FROM registry.access.redhat.com/ubi9/python-311

USER root
RUN dnf update --nobest -y && dnf install -y vim less iputils mesa-libGL && dnf clean all


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
RUN pip3 install --upgrade pip virtualenv
RUN python3 -m venv --prompt "tests-venv" venv

ENV VIRTUAL_ENV=$HOME/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install shared package
RUN pip install -e ./global_utils/

# RAG application dependencies
RUN pip install -e ./rag/

# Multi-agent application dependencies
RUN pip install -e ./multi-agent/[all]

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
