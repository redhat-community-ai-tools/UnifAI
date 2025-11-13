FROM registry.access.redhat.com/ubi9/python-311

USER root
RUN dnf update -y && dnf install -y vim less iputils && dnf clean all

USER default

# Copy all backend files (including entrypoint.sh) and global_utils
ADD --chown=default:root --chmod=777 ./shared-resources/sso-backend $HOME/app
ADD --chown=default:root --chmod=777 ./global_utils $HOME/global_utils

WORKDIR $HOME/app

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh && chmod -R g+w .

RUN pip3 install --upgrade pip virtualenv
RUN python3 -m venv venv

# Activate venv and install requirements
RUN /bin/bash -c "source venv/bin/activate && \
    pip install -r requirements.txt && \
    pip install -e ../global_utils/"

ENTRYPOINT ["./entrypoint.sh"]
