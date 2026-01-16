# DevOps Toolbox Docker Image

A comprehensive debugging and troubleshooting container for Docker/Kubernetes workloads. Built on [nicolaka/netshoot](https://github.com/nicolaka/netshoot) with additional database clients, cloud tools, and custom helpers.

## Quick Start

### Run Locally
```bash
docker run --rm -it demmonico/toolbox:latest bash
```

### Use as Kubernetes Ephemeral Container
```bash
kubectl debug -it <pod-name> \
  --target=<container-name> \
  --image=demmonico/toolbox:latest \
  --profile=sysadmin \
  --share-processes \
  -- zsh
```

Once inside the container, run `help` to see all available tools and usage examples.

## What's Included

### Base Image: nicolaka/netshoot
Comprehensive networking and debugging tools:
- **Network analysis**: tcpdump, wireshark, tshark
- **DNS tools**: dig, nslookup, host
- **HTTP clients**: curl, wget, httpie
- **Network utilities**: ping, traceroute, mtr, iperf3, netcat, socat
- **TLS/SSL**: openssl
- **Container tools**: ctop, docker, kubectl
- **Shells**: bash, zsh, fish

See [netshoot documentation](https://github.com/nicolaka/netshoot) for complete list.

### Database Clients

#### MySQL Client
```bash
mysql -h <host> -u <user> -p
```

#### Redis Client
```bash
redis-cli -h <host> -p <port>
redis -h <host> -p <port>         # Alias
```

#### MongoDB Shell (mongosh)
```bash
mongosh "mongodb://user:pass@host:27017/db"
mongo "mongodb://user:pass@host:27017/db"   # Alias with TLS: --tls --tlsAllowInvalidCertificates
```

**MongoDB Tools**: mongodump, mongorestore, mongoexport, mongoimport

### Cloud Tools

#### AWS CLI
```bash
aws <command>
aws help
```

## Custom Helper Scripts

### mysql-locks
Debug MySQL locks and blocking queries.

```bash
mysql-locks -h <host> -u <user> -p
```

### target-printenv
Show environment variables from target container (when running as ephemeral container).

```bash
target-printenv
```

### target-mount-fs
Mount target container's filesystem at `/target` (when running as ephemeral container with `--share-processes`).

```bash
target-mount-fs
cd /target
```

### help
Display comprehensive help with all tools and usage examples.

```bash
help
```

## Building

### Build Locally
```bash
make build
```

## MySQL Locks Helper

### Purpose
The script provides a brief description of transactions locking InnoDB tables.

Running with `--dump` option it will print content of the following tables:

- information_schema.processlist
- information_schema.innodb_trx
- information_schema.innodb_locks (MySQL 8.0: performance_schema.data_locks)
- information_schema.innodb_lock_waits (MySQL 8.0: performance_schema.data_lock_waits)
- performance_schema.threads

