# Local Checkpoint Dev Stack

This stack runs a local, connected WebODM -> ClusterODM -> NodeODM environment without using production Corral, Tapis, or TACC hostnames.

It is meant for control-plane and restart-flow testing. The LS6 checkpoint restore path still needs a connected Corral/Tapis deployment.

The startup script validates connectivity inside the Docker network:

- WebODM is serving its API
- WebODM can reach ClusterODM
- ClusterODM can reach NodeODM
- WebODM has a `clusterodm-local` processing node registered

The WebODM containers build a local `webodm:ls6-checkpoint-local` image from this branch so the app code and database migrations stay in sync. Production `.env`, Tapis settings, Corral paths, and deployed images are not modified.

For local API smoke tests, this stack sets `WO_LOCAL_DEV_SKIP_AUTH=YES`. WebODM API requests are authenticated as a disposable `localdev` superuser only when `WO_DEBUG=YES` is also set. The published ports bind to `127.0.0.1` on offset host ports by default, and production configs should not set this flag.

Local smoke tests upload image files through WebODM/ClusterODM. `WO_SHARED_VOLUME_ROOT` is intentionally empty here because the local NodeODM image does not consume the LS6/Corral shared-directory submission path.

The offset ports avoid conflicts with another WebODM already using `127.0.0.1:8000`.

## Start

```bash
cd WebODM/local-dev
./install-hosts.sh
./up.sh
```

The stack uses local state under `WebODM/local-dev/.local-dev/`:

- `media/` for WebODM task media
- `db/` for Postgres
- `clusterodm-data/` for ClusterODM node and route data
- `nodeodm-data/` for local NodeODM task data

`install-hosts.sh` adds these local aliases to `/etc/hosts`:

```text
127.0.0.1 webodm.local.test clusterodm.local.test nodeodm.local.test webodm.local clusterodm.local nodeodm.local
```

Use `.env.local` to override ports without committing machine-specific values:

```bash
LOCAL_DEV_WEBODM_PORT=18001
LOCAL_DEV_CLUSTERODM_PORT=14001
LOCAL_DEV_CLUSTERODM_ADMIN_PORT=11001
LOCAL_DEV_NODEODM_PORT=13002
WEBODM_LOCAL_DEV_URL=http://webodm.local.test:18001
```

## URLs

- WebODM: http://webodm.local.test:18000
- ClusterODM: http://clusterodm.local.test:14000
- ClusterODM admin: http://clusterodm.local.test:11000
- NodeODM: http://nodeodm.local.test:13001

The script also adds `webodm.local`, `clusterodm.local`, and `nodeodm.local` aliases. Prefer `.local.test` on macOS if `.local` resolution is slow or inconsistent.

## Stop

```bash
./down.sh
```

Pass `-v` to also remove Docker-managed anonymous volumes. Local bind-mounted state under `.local-dev/` is left in place.

To fully reset local data, stop the stack and remove `WebODM/local-dev/.local-dev/`.

## NodeODM Restart Smoke Test

After the stack is up, run:

```bash
python3 restart-nodeodm-smoke.py --iterations 2
```

The script submits the 20-image dataset from `ClusterODM/testData/images/` through the WebODM HTTP API without credentials. By default it uses the `low-memory` profile, which resizes uploads to 2048px and lowers ODM concurrency/features so the run can fit inside a laptop Docker environment. It watches task output for completed ODM stage markers, then stops and starts the local NodeODM container and requests a WebODM task restart after each marker.

If a task never receives a NodeODM UUID, the script exits after `--routing-timeout` seconds instead of polling for the full processing timeout.

Use `--profile full` to submit the 20-image set with normal ODM defaults on a machine with enough memory.

Default restart markers:

```text
opensfm, openmvs, odm_meshing, mvs_texturing, odm_georeferencing, odm_dem, odm_orthophoto
```

Use `--restart-mode between-tasks` to use the older lightweight behavior that restarts NodeODM only after each task is routed.
