FROM registry.access.redhat.com/ubi9/nginx-120 as serve

USER root

RUN dnf update -y && dnf install -y gettext && dnf clean all

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY nginx.conf.template /etc/nginx/nginx.conf.template

RUN mkdir -p /tmp/client_body_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp && \
    chmod -R 777 /tmp/client_body_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

RUN chmod -R 777 /entrypoint.sh && \
    chown -R default:root /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
