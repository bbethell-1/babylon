FROM quay.io/redhat-cop/python-kopf-s2i:v1.36

USER root

COPY . /tmp/src

RUN dnf install -y @ruby && \
    rm -rf /tmp/src/.git* && \
    chown -R 1001 /tmp/src && \
    chgrp -R 0 /tmp/src && \
    chmod -R g+w /tmp/src

USER 1001

RUN /usr/libexec/s2i/assemble

CMD ["/usr/libexec/s2i/run"]
