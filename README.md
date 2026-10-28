<img alt="WebODM" src="https://user-images.githubusercontent.com/1951843/34074943-8f057c3c-e287-11e7-924d-3ccafa60c43a.png" width="180">

![Build Status](https://img.shields.io/github/actions/workflow/status/WebODM/WebODM/build-and-publish.yml?branch=master) ![Version](https://img.shields.io/github/v/release/WebODM/WebODM) [![Translated](https://hosted.weblate.org/widgets/webodm/-/svg-badge.svg)](https://hosted.weblate.org/engage/webodm/) [![Documentation](https://img.shields.io/badge/Documentation-%F0%9F%93%96-pink)](https://docs.webodm.org) [![Download](https://img.shields.io/badge/Download-%F0%9F%93%A5-white)](https://webodm.org/download) [![Lightning](https://img.shields.io/badge/Lightning-%E2%98%81-white)](https://webodm.net/)

> **📢 WebODM has officially decoupled from OpenDroneMap!** [Read the announcement](https://webodm.org/blog/announcement/)

# WebODM CLI (webodm.sh)

Manage the WebODM Docker stack with `WebODM/webodm.sh`.

```bash
./webodm.sh <command> [options]

Commands:
  start [options]                         Start WebODM containers
  stop                                   Stop WebODM containers
  down                                   Stop and remove WebODM containers
  update                                 Update WebODM to the latest release
  liveupdate                             Update WebODM without stopping it
  rebuild                                Rebuild all docker containers and perform cleanups
  checkenv                               Environment check and install missing components
  test [frontend|backend] [args]         Run tests
  resetadminpassword "<new password>"    Reset the administrator password

Options:
  --port <port>                           Bind port (default: 8000)
  --hostname <hostname>                   Public hostname (default: localhost)
  --media-dir <path>                      Processing results storage path
  --db-dir <path>                         Postgres data path
  --default-nodes                         Number of default NodeODM nodes
  --with-micmac                           Start a NodeMICMAC node
  --ssl                                  Enable SSL with LetsEncrypt
  --ssl-key <path>                        Path to SSL private key (.pem)
  --ssl-cert <path>                       Path to SSL certificate (.pem)
  --ssl-insecure-port-redirect <port>     Redirect HTTP port when SSL enabled
  --debug                                Enable debug mode
  --dev                                  Development mode with live source edits
  --dev-watch-plugins                     Auto-build plugins in dev mode
  --broker                                Celery broker URL
  --detached                             Run in background (headless)
  --gpu                                  Use GPU NodeODM nodes (Linux only)
  --settings <path>                       Custom settings.py path
  --worker-memory                         Worker memory limit
  --worker-cpus                           Worker CPU limit
  --ipv6                                 Enable IPv6
```

A user-friendly, commercial grade software for drone image processing. Generate georeferenced maps, point clouds, elevation models and textured 3D models from aerial images. It supports multiple engines for processing, currently [ODM](https://github.com/OpenDroneMap/ODM) and [MicMac](https://github.com/OpenDroneMap/NodeMICMAC/).

![image](https://user-images.githubusercontent.com/1951843/174504753-6869e56e-7b65-4775-bb23-6c1dc256575c.png)


- [WebODM CLI (webodm.sh)](#webodm-cli-webodmsh)
- [Getting Started](#getting-started)
   * [Recommended Machine Specs](#recommended-machine-specs)
   * [Manual installation (Docker)](#manual-installation-docker)
      + [Requirements](#requirements)
      + [Installation with Docker](#installation-with-docker)
      + [Manage Processing Nodes](#manage-processing-nodes)
      + [Enable MicMac](#enable-micmac)
      + [Enable SSL](#enable-ssl)
      + [Enable IPv6](#enable-ipv6)
      + [Where Are My Files Stored?](#where-are-my-files-stored)
      + [Common Troubleshooting](#common-troubleshooting)
      + [Backup and Restore](#backup-and-restore)
      + [Reset Password](#reset-password)
      + [Manage Plugins](#manage-plugins)
      + [Update](#update)
   * [Run the docker version as a Linux Service](#run-the-docker-version-as-a-linux-service)
   * [Run it natively](#run-it-natively)
   * [Run it on the cloud (Google Compute, Amazon AWS)](#run-it-on-the-cloud-google-compute-amazon-aws)
- [Customizing and Extending](#customizing-and-extending)
- [API Docs](#api-docs)
- [Roadmap](#roadmap)
- [Getting Help](#getting-help)
- [Support the Project](#support-the-project)
- [Translations](#translations)
- [Become a Contributor](#become-a-contributor)
- [Architecture Overview](#architecture-overview)
- [License](#license)
- [Trademark](#trademark)


![image](https://user-images.githubusercontent.com/1951843/174504771-b0bcfd29-3960-41f7-8d44-103b63050bd5.png)

> **If you like WebODM, take a second and ⭐ the project 🙏**

A user-friendly, commercial grade software for drone image processing. Generate georeferenced maps, point clouds, elevation models, textured 3D models and gaussian splats from aerial images. It supports multiple engines for processing, currently [ODX](https://github.com/WebODM/ODX), [MicMac](https://github.com/OpenDroneMap/NodeMICMAC/) and [LGT](https://webodm.net/lgt).

![image](https://github.com/user-attachments/assets/aa1c4340-728d-46c3-a8e1-53bcb4851adc)

# Getting Started

 * [Download](https://webodm.org/download)
 * [Documentation](https://docs.webodm.org/)
 * [Hardware Requirements](https://docs.webodm.org/installation/#hardware-requirements)
 * [Support the Project](https://docs.webodm.org/support-the-project/)


This fork preserves the custom Tapis, LS6, Corral and plugin integrations described in [the customization inventory](docs/upgrade/2026-10-27-webodm-customization-inventory.md).

# License

WebODM is licensed under the terms of the [GNU Affero General Public License v3.0](https://github.com/WebODM/WebODM/blob/master/LICENSE.md).

# Trademark

See [Trademark Guidelines](https://github.com/WebODM/WebODM/blob/master/TRADEMARK.md)

# Notes

 * WebODM is [not affiliated with OpenDroneMap](https://webodm.org/blog/announcement/) and is not a user interface to OpenDroneMap
 * For processing, WebODM uses [ODX](https://github.com/WebODM/ODX), not ODM
 * Official, up-to-date WebODM installers [are free](https://webodm.org/download) to download and make installation a breeze. If you paid for an installer after April 2026, you bought a different software. See how to [migrate from a purchased installer](https://docs.webodm.org/tutorials/opendronemap-migration-guide/#webodm).

# Fork integration reference

The sections below preserve the fork’s existing integration descriptions. Deployment addresses and operational commands require environment-specific verification before use; this source upgrade does not deploy them.

#### High-Performance Computing Integration (TACC)

This WebODM instance is configured for distributed processing using TACC's Lonestar6 supercomputer via ClusterODM-Tapis:

- **Automatic Scaling**: Datasets of 50+ images automatically trigger distributed processing
- **Split-Merge Processing**: Large datasets are intelligently split across multiple 16-core VMs
- **Resource Optimization**: Tapis automatically selects appropriate compute resources based on dataset size:
  - ≤50 images: 1×16-core VM, 30GB RAM
  - ≤150 images: 1×16-core VM, 30GB RAM
  - ≤300 images: 2×16-core VMs, 30GB RAM each
  - ≤600 images: 3×16-core VMs, 30GB RAM each
  - ≤1000 images: 4×16-core VMs, 30GB RAM each
  - ≤1500 images: 6×16-core VMs, 30GB RAM each

**Split-Merge Options**: Advanced users can control distributed processing via task options:
- `split`: Number of images per submodel (auto-determined by default)
- `split-overlap`: Overlap between submodels in meters (default: 150m)
- `sm-cluster`: Cluster coordinator URL (automatically set)

**Tapis Options**: ClusterODM-Tapis exposes queue, allocation, and max run time task options. Allocation choices are loaded from TAS with service credentials:
- `WO_TAS_URL` or `TAS_URL`
- `WO_TAS_SERVICE_USERNAME` or `TAS_SERVICE_USERNAME`
- `WO_TAS_SERVICE_PASSWORD` or `TAS_SERVICE_PASSWORD`
- `WO_TAS_RESOURCE_FILTER` or `TAS_RESOURCE_FILTER` (comma-separated, defaults to LS6/Lonestar6 names)
- `WO_TAS_DEFAULT_ALLOCATION` or `TAS_DEFAULT_ALLOCATION` (defaults to `PT2050-DataX`)

If you don't need the default "node-odm-1" node, simply pass `--default-nodes 0` flag when starting WebODM:

`./webodm.sh restart --default-nodes 0`.

Then from the web interface simply manually remove the "node-odm-1" node.

# Architecture Overview

The [OpenDroneMap project](https://github.com/OpenDroneMap/) is composed of several components.

- [ODM](https://github.com/OpenDroneMap/ODM) is a command line toolkit that processes aerial images. Users comfortable with the command line are probably OK using this component alone.
- [NodeODM](https://github.com/OpenDroneMap/NodeODM) is a lightweight interface and API (Application Program Interface) built directly on top of [ODM](https://github.com/OpenDroneMap/ODM). Users not comfortable with the command line can use this interface to process aerial images and developers can use the API to build applications. Features such as user authentication, map displays, etc. are not provided.
- [WebODM](https://github.com/OpenDroneMap/WebODM) adds more features such as user authentication, map displays, 3D displays, a higher level API and the ability to orchestrate multiple processing nodes (run jobs in parallel). Processing nodes are simply servers running [NodeODM](https://github.com/OpenDroneMap/NodeODM).

![webodm](https://cloud.githubusercontent.com/assets/1951843/25567386/5aeec7aa-2dba-11e7-9169-aca97b70db79.png)

WebODM is built with scalability and performance in mind. While the default setup places all databases and applications on the same machine, users can separate its components for increased performance (ex. place a Celery worker on a separate machine for running background tasks).

![Architecture](https://user-images.githubusercontent.com/1951843/36916884-3a269a7a-1e23-11e8-997a-a57cd6ca7950.png)

A few things to note:
 * We use Celery workers to do background tasks such as resizing images and processing task results, but we use an ad-hoc scheduling mechanism to communicate with NodeODM (which processes the orthophotos, 3D models, etc.). The choice to use two separate systems for task scheduling is due to the flexibility that an ad-hoc mechanism gives us for certain operations (capture task output, persistent data and ability to restart tasks mid-way, communication via REST calls, etc.).
 * If loaded on multiple machines, Celery workers should all share their `app/media` directory with the Django application (via network shares). You can manage workers via `./worker.sh`
