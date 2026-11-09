# Build a given version of Xapian (core + Python bindings) from the official
# sources, then run test.py (test_xapian.py and test_xapian.cc).
#
#     docker build -f docker/Dockerfile --build-arg XAPIAN_VERSION=2.1.0 -t xapian_test_notquery:2.1.0 .
#     docker run --rm xapian_test_notquery:2.1.0
FROM debian:trixie

ARG XAPIAN_VERSION=2.1.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils \
        build-essential zlib1g-dev uuid-dev \
        python3 python3-dev python3-sphinx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN curl -fsSLO https://oligarchy.co.uk/xapian/${XAPIAN_VERSION}/xapian-core-${XAPIAN_VERSION}.tar.xz \
    && curl -fsSLO https://oligarchy.co.uk/xapian/${XAPIAN_VERSION}/xapian-bindings-${XAPIAN_VERSION}.tar.xz \
    && tar xJf xapian-core-${XAPIAN_VERSION}.tar.xz \
    && tar xJf xapian-bindings-${XAPIAN_VERSION}.tar.xz \
    && cd xapian-core-${XAPIAN_VERSION} \
    && ./configure --prefix=/usr/local && make -j"$(nproc)" && make install && ldconfig \
    && cd ../xapian-bindings-${XAPIAN_VERSION} \
    && ./configure --prefix=/usr/local --with-python3 && make -j"$(nproc)" && make install \
    && cd / && rm -rf /build

WORKDIR /xapian_test
COPY test.py test_xapian.py test_xapian.cc ./

CMD ["python3", "test.py"]
