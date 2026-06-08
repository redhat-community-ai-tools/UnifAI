FROM registry.access.redhat.com/ubi9/python-311

USER root
RUN dnf update -y && dnf install -y vim less iputils && dnf clean all

USER default

ADD  --chown=default:root --chmod=777 ./backend $HOME/backend
ADD  --chown=default:root --chmod=777 ./global_utils $HOME/global_utils

WORKDIR $HOME/backend

RUN chmod -R g+w .

RUN pip3 install --upgrade pip virtualenv
RUN python3 -m venv venv

RUN /bin/bash -c "source venv/bin/activate && \
    pip install -e . && \
    pip install -e '../global_utils/[backend]'"

ENV ROLE=flask \
    PORT=8005 \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=1 \
    GUNICORN_TIMEOUT=120

EXPOSE 8005

ENTRYPOINT ["./entrypoint.sh"]
