FROM nicolaka/netshoot

# Working directory
ENV APP_HOME=/toolbox

# Install runtime clients
RUN apk add --no-cache \
        python3 \
        py3-pip \
        aws-cli \
        groff \
        less \
        mysql-client \
        redis \
        mongodb-tools \
        nodejs \
        npm

# Install build deps, build packages, then remove build deps (single layer to save space)
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        g++ \
        make \
        musl-dev \
    && npm install -g mongosh \
    && npm cache clean --force \
    && apk del .build-deps \
    && rm -rf /root/.cache /root/.npm /tmp/* /var/cache/apk/*

# Create command symlinks (mongosh is installed to /usr/bin via npm)
RUN ln -s $(which redis-cli) /usr/local/bin/redis

# Copy helper scripts
COPY src/bin/* /usr/local/bin/
RUN chmod +x /usr/local/bin/mongo /usr/local/bin/toolbox-mysql-locks /usr/local/bin/toolbox-printenv /usr/local/bin/toolbox-mount-fs /usr/local/bin/toolbox-help

WORKDIR $APP_HOME

# Copy and install Python dependencies
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        g++ \
        make \
        musl-dev \
    && pip install --no-cache-dir --break-system-packages -r requirements.txt \
    && apk del .build-deps \
    && rm -rf /root/.cache /tmp/* /var/cache/apk/* requirements.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# copy scripts
COPY src/scripts/mysql-locks-helper.py .
