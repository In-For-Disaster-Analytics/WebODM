# Local Checkpoint Dev Stack

This stack runs a local, connected WebODM -> ClusterODM -> NodeODM environment without using production Corral, Tapis, or TACC hostnames.

It is meant for control-plane and restart-flow testing. The LS6 checkpoint restore path still needs a connected Corral/Tapis deployment.

The startup script validates connectivity inside the Docker network:

- WebODM is serving its API
- WebODM can reach ClusterODM
- ClusterODM can reach NodeODM
- WebODM has a `clusterodm-local` processing node registered

The WebODM containers use the published WebODM image plus targeted source overlays from this branch for the restart/JWT path. Production `.env`, Tapis settings, Corral paths, and deployed images are not modified.

## Start

```bash
cd WebODM/local-dev
./up.sh
```

The stack uses local state under `WebODM/local-dev/.local-dev/`:

- `media/` for WebODM task media
- `db/` for Postgres
- `clusterodm-data/` for ClusterODM node and route data
- `nodeodm-data/` for local NodeODM task data

## URLs

- WebODM: http://localhost:8000
- ClusterODM: http://localhost:4000
- ClusterODM admin: http://localhost:10000
- NodeODM: http://localhost:3001

## Stop

```bash
./down.sh
```

Pass `-v` to also remove Docker-managed anonymous volumes. Local bind-mounted state under `.local-dev/` is left in place.

To fully reset local data, stop the stack and remove `WebODM/local-dev/.local-dev/`.
