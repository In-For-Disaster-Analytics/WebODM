# WebODM customization commit ledger

Prepared: 2026-10-27. [Read the catalog and scope first](2026-10-27-webodm-customization-inventory.md).

Range: local `upstream/master..8fe74e8b5bd7353982c3b142d5f208ef424a1501`; cached upstream `a4501835a0544c1bcb3acca61e376e9e3a6a4b0b`. 225 commits in reverse topological order (parents before descendants; author dates can be non-monotonic). No remote fetch.

**Mapping caveat:** “Explicit evidence reference” means the catalog cites that commit for a specific entry. Other mappings are broad, path-based navigation suggestions, not proof that every change in the commit implements the suggested feature. Shared files and merge commits can touch several domains. The full paths remain the audit trail even where no precise mapping is available. Merge path lists are relative to the first parent and can include ordinary upstream changes; they are not all custom features.

## 7ae29a4a — Add Tapis OAuth2 authentication integration

- Date: 2025-09-10; type: non-merge.
- Evidence: [7ae29a4ad0a6b8285a90f1655ac74051040f8d44](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ae29a4ad0a6b8285a90f1655ac74051040f8d44).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01), [DATA-01](2026-10-27-webodm-customization-inventory.md#data-01), [DATA-02](2026-10-27-webodm-customization-inventory.md#data-02), [DATA-06](2026-10-27-webodm-customization-inventory.md#data-06), [BUILD-02](2026-10-27-webodm-customization-inventory.md#build-02). Basis: explicit evidence reference.
- Changed paths: `.env`, `CLAUDE.md`, `DEPLOYMENT_INSTRUCTIONS.md`, `DOCKER_DEPLOYMENT.md`, `Dockerfile`, `TAPIS_OAUTH2_INTEGRATION.md`, `TAPIS_STORAGE_INTEGRATION.md`, `app/admin.py`, `app/api/tapis_oauth2.py`, `app/api/tapis_preferences.py`, `app/api/tapis_storage.py`, `app/api/urls.py`, `app/auth/tapis_oauth2.py`, `app/contexts/tapis.py`, `app/management/__init__.py`, `app/management/commands/__init__.py`, `app/management/commands/discover_tapis_flights.py`, `app/management/commands/wait_for_db.py`, `app/migrations/0002_tapis_oauth2_models.py`, `app/models/__init__.py`, `app/models/oauth2.py`, `app/models/tapis_preferences.py`, `app/services/tapis_storage.py`, `app/tasks/tapis_storage.py`, `app/templates/app/registration/login.html`, `app/templates/app/registration/tapis_login.html`, `app/urls.py`, `app/views/tapis_auth.py`, `docker-compose.yml`, `requirements.txt`, `scripts/entrypoint-tapis.sh`, `scripts/setup_tapis_oauth2.py`, `setup_tapis_oauth2.py`, `ssl/cert.pem`, `ssl/key.pem`, `webodm/settings.py`, `webodm/urls.py`.

## 3da2d9cc — Add JWT token support for ClusterODM integration

- Date: 2025-09-10; type: non-merge.
- Evidence: [3da2d9ccdf9a343afef3a574528c15508e1c3fee](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3da2d9ccdf9a343afef3a574528c15508e1c3fee).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `app/migrations/0002_tapis_oauth2_models.py`, `app/migrations/0045_merge_20250910_1747.py`, `app/migrations/0046_auto_20250910_1902.py`, `app/models/task.py`, `cookies.txt`, `nodeodm/jwt_node_wrapper.py`, `nodeodm/models.py`, `webodm/settings.py`.

## 9beeb545 — Update .env

- Date: 2025-09-11; type: non-merge.
- Evidence: [9beeb545572df624d055ac31d84b4834e4ea5098](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9beeb545572df624d055ac31d84b4834e4ea5098).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`.

## ecd7c007 — Create setup.sh

- Date: 2025-09-11; type: non-merge.
- Evidence: [ecd7c007d28f367c2ca2a3005aeda15d927501b8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ecd7c007d28f367c2ca2a3005aeda15d927501b8).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: explicit evidence reference.
- Changed paths: `setup.sh`.

## beb86fe6 — Update setup.sh

- Date: 2025-09-11; type: non-merge.
- Evidence: [beb86fe6bb88a28415d6fd6e9a5327c1e11ac124](https://github.com/In-For-Disaster-Analytics/WebODM/commit/beb86fe6bb88a28415d6fd6e9a5327c1e11ac124).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## fe0b40c3 — Update setup.sh

- Date: 2025-09-11; type: non-merge.
- Evidence: [fe0b40c37bfd2d32740c0a4ad3f2d190ed0eedd9](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fe0b40c37bfd2d32740c0a4ad3f2d190ed0eedd9).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 54df4275 — Update setup.sh

- Date: 2025-09-11; type: non-merge.
- Evidence: [54df42754a4c92ab4cb381a91b6d19c299bb3fa6](https://github.com/In-For-Disaster-Analytics/WebODM/commit/54df42754a4c92ab4cb381a91b6d19c299bb3fa6).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 6bd3a045 — Update setup.sh

- Date: 2025-09-11; type: non-merge.
- Evidence: [6bd3a04536d34c9f803e31778643313b6e86228a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6bd3a04536d34c9f803e31778643313b6e86228a).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 6b5da3b1 — Update setup.sh and symlinks

- Date: 2025-09-12; type: non-merge.
- Evidence: [6b5da3b1e6b2114a7bdcfe689d7983192b8dbd53](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6b5da3b1e6b2114a7bdcfe689d7983192b8dbd53).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: explicit evidence reference.
- Changed paths: `.env`, `setup.sh`, `setup_corral_symlinks.sh`.

## 7d9fb7c0 — update tapis oauth

- Date: 2025-09-12; type: non-merge.
- Evidence: [7d9fb7c0d0ddf914d9d3e4d1e4f3389372534112](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7d9fb7c0d0ddf914d9d3e4d1e4f3389372534112).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01). Basis: explicit evidence reference.
- Changed paths: `.gitignore`, `scripts/setup_tapis_oauth2.py`.

## 4b07104a — update docker compose

- Date: 2025-09-12; type: non-merge.
- Evidence: [4b07104adbbc7a294a0e4e56699586aae393eb02](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4b07104adbbc7a294a0e4e56699586aae393eb02).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01), [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `docker-compose.yml`, `scripts/setup_tapis_oauth2.py`.

## edf0acc8 — Update setup_tapis_oauth2.py

- Date: 2025-09-12; type: non-merge.
- Evidence: [edf0acc8d5a2b21b95153462bcb116889415e679](https://github.com/In-For-Disaster-Analytics/WebODM/commit/edf0acc8d5a2b21b95153462bcb116889415e679).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/setup_tapis_oauth2.py`.

## 61908fec — Update setup_tapis_oauth2.py

- Date: 2025-09-12; type: non-merge.
- Evidence: [61908fec2cf097b73c3ce70a7f64fd1a3d694875](https://github.com/In-For-Disaster-Analytics/WebODM/commit/61908fec2cf097b73c3ce70a7f64fd1a3d694875).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/setup_tapis_oauth2.py`.

## aa54bceb — Update setup_tapis_oauth2.py

- Date: 2025-09-12; type: non-merge.
- Evidence: [aa54bcebf1ec448f06a686e8c38bf640d8a00a39](https://github.com/In-For-Disaster-Analytics/WebODM/commit/aa54bcebf1ec448f06a686e8c38bf640d8a00a39).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/setup_tapis_oauth2.py`.

## 52e53e6a — Update setup_tapis_oauth2.py

- Date: 2025-09-12; type: non-merge.
- Evidence: [52e53e6a35309ba80899e438dbe63c77ac9b91d6](https://github.com/In-For-Disaster-Analytics/WebODM/commit/52e53e6a35309ba80899e438dbe63c77ac9b91d6).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01). Basis: explicit evidence reference.
- Changed paths: `scripts/setup_tapis_oauth2.py`.

## 78c46c0c — Update docker-compose.yml

- Date: 2025-09-12; type: non-merge.
- Evidence: [78c46c0c8da5f53293f84a14e4abc2df94d86764](https://github.com/In-For-Disaster-Analytics/WebODM/commit/78c46c0c8da5f53293f84a14e4abc2df94d86764).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `docker-compose.yml`.

## 7e655e28 — Revert "Update setup.sh and symlinks"

- Date: 2025-09-12; type: non-merge.
- Evidence: [7e655e280df8a6b9ad97ac6bfc7a3a450f2d523d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7e655e280df8a6b9ad97ac6bfc7a3a450f2d523d).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: explicit evidence reference.
- Changed paths: `.env`, `setup.sh`, `setup_corral_symlinks.sh`.

## 528bd322 — Update setup.sh

- Date: 2025-09-12; type: non-merge.
- Evidence: [528bd3227e44d095ebc2575c57dc92762fca3079](https://github.com/In-For-Disaster-Analytics/WebODM/commit/528bd3227e44d095ebc2575c57dc92762fca3079).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 073037da — Update NGINX and tapis auth

- Date: 2025-09-12; type: non-merge.
- Evidence: [073037da48f11d3f7ffe26d1cd891e47a716cb14](https://github.com/In-For-Disaster-Analytics/WebODM/commit/073037da48f11d3f7ffe26d1cd891e47a716cb14).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01), [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: explicit evidence reference.
- Changed paths: `setup.sh`.

## f8ddaa29 — Merge pull request #1 from OpenDroneMap/master

- Date: 2025-09-12; type: merge.
- Evidence: [f8ddaa29eb2895502c8d1eb8b860313f02f37a50](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f8ddaa29eb2895502c8d1eb8b860313f02f37a50).
- Catalog: [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03), [MAP-01](2026-10-27-webodm-customization-inventory.md#map-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/api/tasks.py`, `app/management/commands/translate.py`, `app/models/task.py`, `app/raster_utils.py`, `app/static/app/js/components/CropButton.jsx`, `app/static/app/js/components/ImportTaskPanel.jsx`, `app/static/app/js/components/Map.jsx`, `app/static/app/js/components/ProjectListItem.jsx`, `app/static/app/js/translations/odm_autogenerated.js`, `app/tests/test_api_task.py`, `coreplugins/contours/api.py`, `coreplugins/dronedb/api_views.py`, `coreplugins/objdetect/api.py`, `locale`, `package.json`.

## 18b601be — Merge branch 'master' of https://github.com/In-For-Disaster-Analytics/WebODM

- Date: 2025-09-12; type: merge.
- Evidence: [18b601becfabeb9692ab4355dbb11b7a244a5ee8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/18b601becfabeb9692ab4355dbb11b7a244a5ee8).
- Catalog: [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03), [MAP-01](2026-10-27-webodm-customization-inventory.md#map-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/api/tasks.py`, `app/management/commands/translate.py`, `app/models/task.py`, `app/raster_utils.py`, `app/static/app/js/components/CropButton.jsx`, `app/static/app/js/components/ImportTaskPanel.jsx`, `app/static/app/js/components/Map.jsx`, `app/static/app/js/components/ProjectListItem.jsx`, `app/static/app/js/translations/odm_autogenerated.js`, `app/tests/test_api_task.py`, `coreplugins/contours/api.py`, `coreplugins/dronedb/api_views.py`, `coreplugins/objdetect/api.py`, `locale`, `package.json`.

## efc59e6a — Update setup.sh

- Date: 2025-09-12; type: non-merge.
- Evidence: [efc59e6a24fd188054f1a4f2ff749d46c4588b2c](https://github.com/In-For-Disaster-Analytics/WebODM/commit/efc59e6a24fd188054f1a4f2ff749d46c4588b2c).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## e1dc3da6 — Update urls.py

- Date: 2025-09-12; type: non-merge.
- Evidence: [e1dc3da682cda864a3cbbe868129ec24d417d7dd](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e1dc3da682cda864a3cbbe868129ec24d417d7dd).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/api/urls.py`.

## 6aef77e9 — Update setup.sh

- Date: 2025-09-12; type: non-merge.
- Evidence: [6aef77e9127c8fe9e30360180b5cfa6e50ebdcb0](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6aef77e9127c8fe9e30360180b5cfa6e50ebdcb0).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## a24ecf0f — connect cluster odm

- Date: 2025-09-12; type: non-merge.
- Evidence: [a24ecf0fe336a9b669a5383143cefc796227ead5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a24ecf0fe336a9b669a5383143cefc796227ead5).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `setup.sh`, `setup_tapis_oauth2.py`.

## 6180aefb — Update setup.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [6180aefbafc69a7368a71797d6e887a2f953bb42](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6180aefbafc69a7368a71797d6e887a2f953bb42).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 1ab34c2f — Create separate connect clusterodm script.

- Date: 2025-09-13; type: non-merge.
- Evidence: [1ab34c2fd7b4d6bb98d1f37612560925048e1582](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1ab34c2fd7b4d6bb98d1f37612560925048e1582).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `connect_clusterodm.sh`, `setup.sh`.

## 54e4a687 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [54e4a6879d9465c6f5360b0d7cc59790ce5e8bcb](https://github.com/In-For-Disaster-Analytics/WebODM/commit/54e4a6879d9465c6f5360b0d7cc59790ce5e8bcb).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## 523c8b33 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [523c8b33e852655379a6a8221d832833cf86dad7](https://github.com/In-For-Disaster-Analytics/WebODM/commit/523c8b33e852655379a6a8221d832833cf86dad7).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## 0f898468 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [0f898468156655f477089c15813d3cbead547e48](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0f898468156655f477089c15813d3cbead547e48).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## bb5e3ea0 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [bb5e3ea000d25cd10e048b95e657e9f15e60ca53](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bb5e3ea000d25cd10e048b95e657e9f15e60ca53).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## 76738e27 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [76738e27e2421a088a0faafe4357ed67d91e5e18](https://github.com/In-For-Disaster-Analytics/WebODM/commit/76738e27e2421a088a0faafe4357ed67d91e5e18).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## aff1ab0c — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [aff1ab0c4db1673adb6f21ae303670f94f14fef2](https://github.com/In-For-Disaster-Analytics/WebODM/commit/aff1ab0c4db1673adb6f21ae303670f94f14fef2).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## 4f0d122b — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [4f0d122b1e95360548a9e2358f7788400b279443](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4f0d122b1e95360548a9e2358f7788400b279443).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## d5c6c181 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [d5c6c181e71dab71eb4a3ba93e00f24dd508212a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d5c6c181e71dab71eb4a3ba93e00f24dd508212a).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## 562ce399 — Update connect_clusterodm.sh

- Date: 2025-09-13; type: non-merge.
- Evidence: [562ce399f459fb2ccdead350bae63848a8551452](https://github.com/In-For-Disaster-Analytics/WebODM/commit/562ce399f459fb2ccdead350bae63848a8551452).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `connect_clusterodm.sh`.

## 91a7037b — Updated to fix clusterodm

- Date: 2025-09-13; type: non-merge.
- Evidence: [91a7037ba46b4152c370fab55f9037817894c68a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/91a7037ba46b4152c370fab55f9037817894c68a).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `debug_clusterodm.py`, `fix_clusterodm.py`.

## dc486272 — Update models.py

- Date: 2025-09-14; type: non-merge.
- Evidence: [dc486272510f33962d125ebd91b09f1c2ce9bfa7](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dc486272510f33962d125ebd91b09f1c2ce9bfa7).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `nodeodm/models.py`.

## f8360c26 — Fix number of images

- Date: 2025-09-14; type: non-merge.
- Evidence: [f8360c26314e891995d68390f5acfcee7a65ed30](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f8360c26314e891995d68390f5acfcee7a65ed30).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `fix_clusterodm.py`, `nodeodm/models.py`.

## 07320a10 — update node issues for https

- Date: 2025-09-14; type: non-merge.
- Evidence: [07320a105c9651d87fb7699f1856b72cf2556fc4](https://github.com/In-For-Disaster-Analytics/WebODM/commit/07320a105c9651d87fb7699f1856b72cf2556fc4).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `nodeodm/jwt_node_wrapper.py`, `nodeodm/models.py`.

## b1d58092 — Update setup.sh

- Date: 2025-09-14; type: non-merge.
- Evidence: [b1d580923daa7e3f2ce726659de6e79489810dad](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b1d580923daa7e3f2ce726659de6e79489810dad).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 307a415a — Update setup.sh

- Date: 2025-09-14; type: non-merge.
- Evidence: [307a415ab2510e1c479b6095aa64790afaa8e8f3](https://github.com/In-For-Disaster-Analytics/WebODM/commit/307a415ab2510e1c479b6095aa64790afaa8e8f3).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 6a819dcd — Update setup.sh

- Date: 2025-09-14; type: non-merge.
- Evidence: [6a819dcd6e8a0d1d22e57af0d958aa924538309f](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6a819dcd6e8a0d1d22e57af0d958aa924538309f).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## d6b566a8 — Update setup.sh

- Date: 2025-09-14; type: non-merge.
- Evidence: [d6b566a846685091684e833ae35df8ae96804a59](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d6b566a846685091684e833ae35df8ae96804a59).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 95cb7148 — Add autologout

- Date: 2025-09-14; type: non-merge.
- Evidence: [95cb714899d2f2ee4f94fa36e665819b24875e23](https://github.com/In-For-Disaster-Analytics/WebODM/commit/95cb714899d2f2ee4f94fa36e665819b24875e23).
- Catalog: [AUTH-02](2026-10-27-webodm-customization-inventory.md#auth-02). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/classes/TapisTokenManager.js`, `app/static/app/js/main.jsx`, `app/templates/app/base.html`, `app/templatetags/tapis_tags.py`.

## bd7bcd35 — Update setup.sh

- Date: 2025-09-15; type: non-merge.
- Evidence: [bd7bcd358b6da8e5e64e96b35158f8db72d4ad82](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd7bcd358b6da8e5e64e96b35158f8db72d4ad82).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## da0fbc42 — Update setup.sh

- Date: 2025-09-15; type: non-merge.
- Evidence: [da0fbc4211258027d7f5231c5cf1d891bac43e02](https://github.com/In-For-Disaster-Analytics/WebODM/commit/da0fbc4211258027d7f5231c5cf1d891bac43e02).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 932d8390 — Update jwt_node_wrapper.py

- Date: 2025-09-15; type: non-merge.
- Evidence: [932d83908d7623e5e6b55ad52902b0a481995f97](https://github.com/In-For-Disaster-Analytics/WebODM/commit/932d83908d7623e5e6b55ad52902b0a481995f97).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## 21b8acff — Update jwt wrapper and setup.sh

- Date: 2025-09-16; type: non-merge.
- Evidence: [21b8acff0783e1ac5ce421417b4ab37ed4ca17b2](https://github.com/In-For-Disaster-Analytics/WebODM/commit/21b8acff0783e1ac5ce421417b4ab37ed4ca17b2).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `nodeodm/jwt_node_wrapper.py`, `setup.sh`.

## cd87a317 — Update jwt_node_wrapper.py

- Date: 2025-09-16; type: non-merge.
- Evidence: [cd87a317cc559b053134a0808338965457c64f04](https://github.com/In-For-Disaster-Analytics/WebODM/commit/cd87a317cc559b053134a0808338965457c64f04).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## 1854c8be — Update jwt_node_wrapper.py

- Date: 2025-09-16; type: non-merge.
- Evidence: [1854c8bea8eead5a611ecf821006a46bd77560fa](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1854c8bea8eead5a611ecf821006a46bd77560fa).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## 4dbc16cc — Update Authentication Issues

- Date: 2025-09-18; type: non-merge.
- Evidence: [4dbc16cc095aafb612822f69a8ad2f250ba9b248](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4dbc16cc095aafb612822f69a8ad2f250ba9b248).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01). Basis: explicit evidence reference.
- Changed paths: `app/models/task.py`, `nodeodm/jwt_node_wrapper.py`.

## 90a77ed4 — Update README.md

- Date: 2025-09-19; type: non-merge.
- Evidence: [90a77ed4b5e7b05193b2c0c719f628325d885e50](https://github.com/In-For-Disaster-Analytics/WebODM/commit/90a77ed4b5e7b05193b2c0c719f628325d885e50).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `README.md`.

## aceb725a — update logs

- Date: 2025-10-29; type: non-merge.
- Evidence: [aceb725acc1521f8de442e22caba8f673db083b8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/aceb725acc1521f8de442e22caba8f673db083b8).
- Catalog: [UI-02](2026-10-27-webodm-customization-inventory.md#ui-02). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/static/app/js/components/TaskListItem.jsx`.

## 9f85ddcb — Update TaskListItem.jsx

- Date: 2025-10-29; type: non-merge.
- Evidence: [9f85ddcb4deb957eaf40d5172c6ae58432caa012](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9f85ddcb4deb957eaf40d5172c6ae58432caa012).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/static/app/js/components/TaskListItem.jsx`.

## 22f7cdce — Update jwt_node_wrapper.py

- Date: 2025-10-29; type: non-merge.
- Evidence: [22f7cdce5c3fad64a0ae8f0d1cd17c627e711e35](https://github.com/In-For-Disaster-Analytics/WebODM/commit/22f7cdce5c3fad64a0ae8f0d1cd17c627e711e35).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## 2805c9cd — Update TaskListItem.jsx

- Date: 2025-10-29; type: non-merge.
- Evidence: [2805c9cda52fc288dd0241f825fed4af5ae63e5e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2805c9cda52fc288dd0241f825fed4af5ae63e5e).
- Catalog: [TASK-01](2026-10-27-webodm-customization-inventory.md#task-01). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/TaskListItem.jsx`.

## f433f8fa — Update jwt token

- Date: 2025-10-29; type: non-merge.
- Evidence: [f433f8fa040b0b4ba41ce58ccf44621cf2348cca](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f433f8fa040b0b4ba41ce58ccf44621cf2348cca).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03), [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01), [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/models/task.py`, `nodeodm/jwt_node_wrapper.py`, `nodeodm/models.py`, `setup.sh`.

## c3574267 — Update JWT cancel funciton

- Date: 2025-10-29; type: non-merge.
- Evidence: [c3574267b0ffb64361bb272ed3d482acbe83fbdf](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c3574267b0ffb64361bb272ed3d482acbe83fbdf).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `nodeodm/jwt_node_wrapper.py`, `nodeodm/models.py`.

## bd7ade13 — Add Cluster UUID and fix jwt wrapper

- Date: 2025-10-30; type: non-merge.
- Evidence: [bd7ade13e5df90b131159f82994d9e3f118a703f](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd7ade13e5df90b131159f82994d9e3f118a703f).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03), [UI-02](2026-10-27-webodm-customization-inventory.md#ui-02). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/TaskListItem.jsx`, `app/static/app/js/css/TaskListItem.scss`, `connect_clusterodm.sh`, `nodeodm/jwt_node_wrapper.py`, `setup.sh`.

## 7d72b43c — Update setup.sh

- Date: 2025-10-30; type: non-merge.
- Evidence: [7d72b43c0b54070f0b7ec83521197aa2b1afdb14](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7d72b43c0b54070f0b7ec83521197aa2b1afdb14).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 671c0d9b — Update setup.sh

- Date: 2025-10-30; type: non-merge.
- Evidence: [671c0d9b7a3097be67c5920548a095e93dc2b5fc](https://github.com/In-For-Disaster-Analytics/WebODM/commit/671c0d9b7a3097be67c5920548a095e93dc2b5fc).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 699ae5f1 — Update jwt_node_wrapper.py

- Date: 2025-10-30; type: non-merge.
- Evidence: [699ae5f1c192c0aac88561195161ad93112e346b](https://github.com/In-For-Disaster-Analytics/WebODM/commit/699ae5f1c192c0aac88561195161ad93112e346b).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## bb8ec216 — Update JWT wrapper to accept outputs

- Date: 2025-10-30; type: non-merge.
- Evidence: [bb8ec216c11451a434963d10f7b4431f56c1bd5b](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bb8ec216c11451a434963d10f7b4431f56c1bd5b).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `DEPLOYMENT_INSTRUCTIONS.md`, `nodeodm/jwt_node_wrapper.py`.

## 25023d84 — Update jwt_node_wrapper.py

- Date: 2025-10-30; type: non-merge.
- Evidence: [25023d842796fd5fcb86578be07268a4ee497e21](https://github.com/In-For-Disaster-Analytics/WebODM/commit/25023d842796fd5fcb86578be07268a4ee497e21).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## 632166a0 — Update jwt_node_wrapper.py

- Date: 2025-10-30; type: non-merge.
- Evidence: [632166a0c14d8b0401c509dad9f8db2db400a3d7](https://github.com/In-For-Disaster-Analytics/WebODM/commit/632166a0c14d8b0401c509dad9f8db2db400a3d7).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## 60bec30e — Update Oauth for Downlaod Zip

- Date: 2025-10-30; type: non-merge.
- Evidence: [60bec30e10f964f32d577e97497dd190a7758725](https://github.com/In-For-Disaster-Analytics/WebODM/commit/60bec30e10f964f32d577e97497dd190a7758725).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tapis_oauth2.py`, `app/models/oauth2.py`, `app/models/task.py`, `app/services/tapis_storage.py`.

## 87b88ff2 — Update jwt_node_wrapper.py

- Date: 2025-10-30; type: non-merge.
- Evidence: [87b88ff21b93a69ad9cb7625d2e3a1ea41b8400e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/87b88ff21b93a69ad9cb7625d2e3a1ea41b8400e).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## a452fe1b — update oauth to handle jwt for downloads

- Date: 2025-10-30; type: non-merge.
- Evidence: [a452fe1b8c46f59dd67af15a73492ca0c8c1595c](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a452fe1b8c46f59dd67af15a73492ca0c8c1595c).
- Catalog: [AUTH-03](2026-10-27-webodm-customization-inventory.md#auth-03). Basis: explicit evidence reference.
- Changed paths: `app/models/oauth2.py`.

## b1422944 — Update Dockerfile

- Date: 2025-10-30; type: non-merge.
- Evidence: [b14229445c7f457d2f6c1b91b05b30507c0e4824](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b14229445c7f457d2f6c1b91b05b30507c0e4824).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `Dockerfile`.

## e2f92f3c — Update Dockerfile

- Date: 2025-10-30; type: non-merge.
- Evidence: [e2f92f3c4f03f6e579d165dc6f38ba9b9e87cf1d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e2f92f3c4f03f6e579d165dc6f38ba9b9e87cf1d).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `db/Dockerfile`.

## a4552cf9 — Update Dockerfile

- Date: 2025-10-30; type: non-merge.
- Evidence: [a4552cf98e25b5fcf3949d9bcdbd7c8ac62e3222](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a4552cf98e25b5fcf3949d9bcdbd7c8ac62e3222).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `db/Dockerfile`.

## da1707d8 — Update setup.sh

- Date: 2025-10-31; type: non-merge.
- Evidence: [da1707d838f7e85482d36b779f174eaa6c964eda](https://github.com/In-For-Disaster-Analytics/WebODM/commit/da1707d838f7e85482d36b779f174eaa6c964eda).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 0c7c1145 — Update setup.sh

- Date: 2025-10-31; type: non-merge.
- Evidence: [0c7c1145cbe1ed83f188a64403d2d8b260faa9b8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0c7c1145cbe1ed83f188a64403d2d8b260faa9b8).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## e730bc23 — Update setup.sh

- Date: 2025-10-31; type: non-merge.
- Evidence: [e730bc234e233216941a38b72857f0220962dd2e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e730bc234e233216941a38b72857f0220962dd2e).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 4374b9ba — Update setup.sh

- Date: 2025-10-31; type: non-merge.
- Evidence: [4374b9ba24e281f9dbe6570dbcfda247cad55e3a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4374b9ba24e281f9dbe6570dbcfda247cad55e3a).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## e36b7ad6 — Update setup.sh

- Date: 2025-10-31; type: non-merge.
- Evidence: [e36b7ad6264f3c950f54a6451e53d569904e08b5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e36b7ad6264f3c950f54a6451e53d569904e08b5).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 7b21b65f — Update Dockerfile

- Date: 2025-10-31; type: non-merge.
- Evidence: [7b21b65fe369d58aafedc2ad94e52173512a06ad](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7b21b65fe369d58aafedc2ad94e52173512a06ad).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `Dockerfile`.

## d552f93d — Update Dockerfile

- Date: 2025-10-31; type: non-merge.
- Evidence: [d552f93d8bea613cc0656a9ebb3676123e59a77d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d552f93d8bea613cc0656a9ebb3676123e59a77d).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `Dockerfile`.

## 9d1f4577 — Update Dockerfile

- Date: 2025-10-31; type: non-merge.
- Evidence: [9d1f45776a884c7b064018be3d69263df4abe28f](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9d1f45776a884c7b064018be3d69263df4abe28f).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `Dockerfile`.

## 0e9b4c9a — Update Dockerfile

- Date: 2025-10-31; type: non-merge.
- Evidence: [0e9b4c9abe9144c022c765ef8660bcb0e826d1b2](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0e9b4c9abe9144c022c765ef8660bcb0e826d1b2).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `Dockerfile`.

## 93bc30b2 — Update Dockerfile

- Date: 2025-10-31; type: non-merge.
- Evidence: [93bc30b2f2e701b438f142a320286c65b038b93a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/93bc30b2f2e701b438f142a320286c65b038b93a).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `Dockerfile`.

## 4d35e435 — Update webodm.sh

- Date: 2025-10-31; type: non-merge.
- Evidence: [4d35e4351686bfbfe9e382754a168bee58f8accf](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4d35e4351686bfbfe9e382754a168bee58f8accf).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `webodm.sh`.

## 163b0148 — Update settings.py

- Date: 2025-10-31; type: non-merge.
- Evidence: [163b0148a06392ac8a36fc7f08e3975fcd3062a3](https://github.com/In-For-Disaster-Analytics/WebODM/commit/163b0148a06392ac8a36fc7f08e3975fcd3062a3).
- Catalog: [UI-01](2026-10-27-webodm-customization-inventory.md#ui-01). Basis: explicit evidence reference.
- Changed paths: `app/templatetags/settings.py`.

## e4624e69 — Update settings.py

- Date: 2025-10-31; type: non-merge.
- Evidence: [e4624e69c05c8548ce0251c33841029e452e6c1d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e4624e69c05c8548ce0251c33841029e452e6c1d).
- Catalog: [UI-01](2026-10-27-webodm-customization-inventory.md#ui-01). Basis: explicit evidence reference.
- Changed paths: `app/templatetags/settings.py`.

## 5056f7ad — Update .env

- Date: 2025-10-31; type: non-merge.
- Evidence: [5056f7ade9ece14cd2db2221434784dca058d091](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5056f7ade9ece14cd2db2221434784dca058d091).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`.

## 8e19e0ab — Update .env

- Date: 2025-10-31; type: non-merge.
- Evidence: [8e19e0abdbee10057644a51ea856abd998b5cd07](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8e19e0abdbee10057644a51ea856abd998b5cd07).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`.

## d279324f — Update .env

- Date: 2025-10-31; type: non-merge.
- Evidence: [d279324f5c7b46333e236d1d07fa0a25ca44bce7](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d279324f5c7b46333e236d1d07fa0a25ca44bce7).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`.

## 9980a8e3 — Update .env

- Date: 2025-10-31; type: non-merge.
- Evidence: [9980a8e372c410bb7cb15285fa69af8161621fe1](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9980a8e372c410bb7cb15285fa69af8161621fe1).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`.

## 4fe0d77c — Add import from server functionality

- Date: 2025-11-01; type: non-merge.
- Evidence: [4fe0d77c7084c98c642823d9e707ee5e3958632d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4fe0d77c7084c98c642823d9e707ee5e3958632d).
- Catalog: [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/models/task.py`, `app/static/app/js/components/ImportTaskPanel.jsx`, `app/tests/test_api_task_import.py`.

## 3d94165d — Update .env

- Date: 2025-11-01; type: non-merge.
- Evidence: [3d94165dc70ae77f1cca70bd7c65a3295054d13c](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3d94165dc70ae77f1cca70bd7c65a3295054d13c).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`.

## 28a44929 — Update start to do corral

- Date: 2025-11-01; type: non-merge.
- Evidence: [28a44929138715e0a6783dd2ac8a2a8b74f10966](https://github.com/In-For-Disaster-Analytics/WebODM/commit/28a44929138715e0a6783dd2ac8a2a8b74f10966).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: explicit evidence reference.
- Changed paths: `.env`, `DEPLOYMENT_INSTRUCTIONS.md`, `docker-compose.yml`, `setup.sh`.

## f3c9033e — Update webodm.sh

- Date: 2025-11-01; type: non-merge.
- Evidence: [f3c9033e5fec8018a2677de4a6b6a48fe3d069b0](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f3c9033e5fec8018a2677de4a6b6a48fe3d069b0).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `webodm.sh`.

## 3a52b694 — Update webodm.sh

- Date: 2025-11-01; type: non-merge.
- Evidence: [3a52b6949a1f1a25950f92027a86659d8c15b583](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3a52b6949a1f1a25950f92027a86659d8c15b583).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `webodm.sh`.

## c3d0ba83 — Update import to allow user to create tasks after

- Date: 2025-11-01; type: non-merge.
- Evidence: [c3d0ba833d8febda00c024eafe5be70a706d9c30](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c3d0ba833d8febda00c024eafe5be70a706d9c30).
- Catalog: [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/static/app/js/components/ImportTaskPanel.jsx`, `app/tests/test_api_task_import.py`.

## 44e74602 — More import functionality

- Date: 2025-11-01; type: non-merge.
- Evidence: [44e74602a2aea267e6b1d711c54a87b9f818927e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/44e74602a2aea267e6b1d711c54a87b9f818927e).
- Catalog: [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/static/app/js/components/ImportTaskPanel.jsx`, `app/tests/test_api_task_import.py`.

## dd8921f6 — Update ImportTaskPanel.jsx

- Date: 2025-11-03; type: non-merge.
- Evidence: [dd8921f69b9a25a62b1b043bd9744b8327aac4f9](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dd8921f69b9a25a62b1b043bd9744b8327aac4f9).
- Catalog: [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/static/app/js/components/ImportTaskPanel.jsx`.

## 0bec2a11 — Update celery.py

- Date: 2025-11-03; type: non-merge.
- Evidence: [0bec2a111cf18d7745dee5c59b86a0e91a99d0de](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0bec2a111cf18d7745dee5c59b86a0e91a99d0de).
- Catalog: [TASK-03](2026-10-27-webodm-customization-inventory.md#task-03). Basis: explicit evidence reference.
- Changed paths: `worker/celery.py`.

## 2c6a09d1 — Update celery.py

- Date: 2025-11-03; type: non-merge.
- Evidence: [2c6a09d11515307dc20308bf122beac43c21fdbc](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2c6a09d11515307dc20308bf122beac43c21fdbc).
- Catalog: [TASK-03](2026-10-27-webodm-customization-inventory.md#task-03). Basis: explicit evidence reference.
- Changed paths: `worker/celery.py`.

## 3ba7261b — Update celery to fix issue.

- Date: 2025-11-03; type: non-merge.
- Evidence: [3ba7261b835be4a3b30d4e2afeef739c2516fa7a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3ba7261b835be4a3b30d4e2afeef739c2516fa7a).
- Catalog: [TASK-03](2026-10-27-webodm-customization-inventory.md#task-03). Basis: explicit evidence reference.
- Changed paths: `DEPLOYMENT_INSTRUCTIONS.md`, `worker/__init__.py`, `worker/celery.py`.

## 2ba7cb6d — Update celery.py

- Date: 2025-11-03; type: non-merge.
- Evidence: [2ba7cb6d8c6e104896b223cf6ccba1bd7bf158bd](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2ba7cb6d8c6e104896b223cf6ccba1bd7bf158bd).
- Catalog: [TASK-03](2026-10-27-webodm-customization-inventory.md#task-03). Basis: explicit evidence reference.
- Changed paths: `worker/celery.py`.

## b6449eb4 — Add file path passing instead of images.

- Date: 2025-11-03; type: non-merge.
- Evidence: [b6449eb4baf406859f7c7307a1a6bb67ba3075a5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b6449eb4baf406859f7c7307a1a6bb67ba3075a5).
- Catalog: [DATA-04](2026-10-27-webodm-customization-inventory.md#data-04). Basis: explicit evidence reference.
- Changed paths: `nodeodm/jwt_node_wrapper.py`, `nodeodm/models.py`.

## 24fa4bd3 — Change Submission to path based submission instead of images

- Date: 2025-11-10; type: non-merge.
- Evidence: [24fa4bd3c54b6bea7614c62d04df4b387db98aec](https://github.com/In-For-Disaster-Analytics/WebODM/commit/24fa4bd3c54b6bea7614c62d04df4b387db98aec).
- Catalog: [DATA-04](2026-10-27-webodm-customization-inventory.md#data-04). Basis: explicit evidence reference.
- Changed paths: `.env`, `DEPLOYMENT_INSTRUCTIONS.md`, `app/models/task.py`, `docker-compose.yml`, `nodeodm/models.py`, `webodm/settings.py`.

## 50ee93df — Logs for paths

- Date: 2025-11-10; type: non-merge.
- Evidence: [50ee93dff0861a32762c52ef13f0e0f6df5d3b9a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/50ee93dff0861a32762c52ef13f0e0f6df5d3b9a).
- Catalog: [DATA-04](2026-10-27-webodm-customization-inventory.md#data-04), [UI-02](2026-10-27-webodm-customization-inventory.md#ui-02). Basis: explicit evidence reference.
- Changed paths: `app/models/task.py`, `nodeodm/models.py`.

## 06dbfadd — UUpdate map to have measuremnts

- Date: 2025-11-11; type: non-merge.
- Evidence: [06dbfadd8bc1e36311d9be1293d0770e1c7a433a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/06dbfadd8bc1e36311d9be1293d0770e1c7a433a).
- Catalog: [MAP-01](2026-10-27-webodm-customization-inventory.md#map-01). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/Map.jsx`, `app/static/app/js/css/Map.scss`.

## 9d56fdc1 — update auth expiration

- Date: 2025-11-11; type: non-merge.
- Evidence: [9d56fdc1b56408e6681ef1a0cbaaafd31416b008](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9d56fdc1b56408e6681ef1a0cbaaafd31416b008).
- Catalog: [AUTH-02](2026-10-27-webodm-customization-inventory.md#auth-02). Basis: explicit evidence reference.
- Changed paths: `TAPIS_OAUTH2_INTEGRATION.md`, `app/api/tapis_oauth2.py`, `app/models/oauth2.py`, `webodm/settings.py`.

## 058d5a0d — Update boot.py

- Date: 2025-12-18; type: non-merge.
- Evidence: [058d5a0dbafc94b7e9d0a824fe2e4531260bd45f](https://github.com/In-For-Disaster-Analytics/WebODM/commit/058d5a0dbafc94b7e9d0a824fe2e4531260bd45f).
- Catalog: [OPS-05](2026-10-27-webodm-customization-inventory.md#ops-05). Basis: explicit evidence reference.
- Changed paths: `app/boot.py`.

## a7009c67 — Ensure temp upload directories exist before file operations

- Date: 2025-12-18; type: non-merge.
- Evidence: [a7009c67e78576691152822509cc19b8cec85019](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a7009c67e78576691152822509cc19b8cec85019).
- Catalog: [DATA-06](2026-10-27-webodm-customization-inventory.md#data-06). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/models/task.py`, `setup.sh`.

## 7ebac2f4 — Update setup.sh

- Date: 2025-12-18; type: non-merge.
- Evidence: [7ebac2f44ed7c93f1acd96126b6672b88bef33f1](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ebac2f44ed7c93f1acd96126b6672b88bef33f1).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 9c84eb14 — Update setup.sh

- Date: 2025-12-18; type: non-merge.
- Evidence: [9c84eb147a3e9d39023da1865d3d9ca0e4d63225](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9c84eb147a3e9d39023da1865d3d9ca0e4d63225).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 44aae112 — Update setup.sh

- Date: 2025-12-18; type: non-merge.
- Evidence: [44aae112eabf87ae7ed0713d53cee175c41876dd](https://github.com/In-For-Disaster-Analytics/WebODM/commit/44aae112eabf87ae7ed0713d53cee175c41876dd).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 4e07f88d — Update setup.sh

- Date: 2025-12-18; type: non-merge.
- Evidence: [4e07f88deb53e519779ae5570e23f574e9f27719](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4e07f88deb53e519779ae5570e23f574e9f27719).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: explicit evidence reference.
- Changed paths: `setup.sh`.

## ea2bb01e — Update ModelView.jsx

- Date: 2026-01-13; type: non-merge.
- Evidence: [ea2bb01ee1f06f4f7bc7597bfc9c10d6770e8b63](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ea2bb01ee1f06f4f7bc7597bfc9c10d6770e8b63).
- Catalog: [VIEW-01](2026-10-27-webodm-customization-inventory.md#view-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## c1c4f941 — Update README.md

- Date: 2026-01-13; type: non-merge.
- Evidence: [c1c4f941d5aeeed49d4c93d35dea45619619ecb6](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c1c4f941d5aeeed49d4c93d35dea45619619ecb6).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `README.md`.

## 3e78d438 — Added potree v2 funcitonality

- Date: 2026-02-05; type: non-merge.
- Evidence: [3e78d4382880003f43c027dbe6da0b991156a810](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3e78d4382880003f43c027dbe6da0b991156a810).
- Catalog: [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## 9539781d — Update ModelView.jsx

- Date: 2026-02-05; type: non-merge.
- Evidence: [9539781ddb0c04317363328fad0f457aa22d8708](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9539781ddb0c04317363328fad0f457aa22d8708).
- Catalog: [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## 5b8c8622 — remove actions

- Date: 2026-02-05; type: non-merge.
- Evidence: [5b8c8622747d0bfb0ed79fdfe31db85d4afb64de](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5b8c8622747d0bfb0ed79fdfe31db85d4afb64de).
- Catalog: [DEV-02](2026-10-27-webodm-customization-inventory.md#dev-02). Basis: explicit evidence reference.
- Changed paths: `.github/workflows/build-and-publish.yml`, `.github/workflows/build-docs.yml`, `.github/workflows/issue-triage.yml`, `.github/workflows/test-docker.yml`, `app/static/app/js/ModelView.jsx`.

## f4138fdd — Update 3d_model_js.html

- Date: 2026-02-05; type: non-merge.
- Evidence: [f4138fdd2a90d87a0fd8de8e4c4c79d93d2b0e7a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f4138fdd2a90d87a0fd8de8e4c4c79d93d2b0e7a).
- Catalog: [VIEW-01](2026-10-27-webodm-customization-inventory.md#view-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/templates/app/3d_model_js.html`.

## f5f4a322 — Update ModelView.jsx

- Date: 2026-02-05; type: non-merge.
- Evidence: [f5f4a32298b06a6a2d718c7991d15358e97d040e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f5f4a32298b06a6a2d718c7991d15358e97d040e).
- Catalog: [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## e014d48e — Update ModelView.jsx

- Date: 2026-02-05; type: non-merge.
- Evidence: [e014d48e2001b8e5d9b1377d597a99cc853ddae9](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e014d48e2001b8e5d9b1377d597a99cc853ddae9).
- Catalog: [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## c43adc87 — Support HTTP range requests; prefer Potree v2

- Date: 2026-02-05; type: non-merge.
- Evidence: [c43adc87c274e6a115151f8454ecaad12dfff003](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c43adc87c274e6a115151f8454ecaad12dfff003).
- Catalog: [VIEW-02](2026-10-27-webodm-customization-inventory.md#view-02), [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/static/app/js/ModelView.jsx`.

## ebc7b4c5 — Update ModelView.jsx

- Date: 2026-02-05; type: non-merge.
- Evidence: [ebc7b4c5d321c7b904bb4e79ba212426f37e47ea](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ebc7b4c5d321c7b904bb4e79ba212426f37e47ea).
- Catalog: [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## 73432709 — Removed Potree v2 Functionality

- Date: 2026-02-06; type: non-merge.
- Evidence: [73432709c0dc433286301945d950b5e6096a68d9](https://github.com/In-For-Disaster-Analytics/WebODM/commit/73432709c0dc433286301945d950b5e6096a68d9).
- Catalog: [VIEW-02](2026-10-27-webodm-customization-inventory.md#view-02), [VIEW-03](2026-10-27-webodm-customization-inventory.md#view-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`, `app/templates/app/3d_model_js.html`.

## 08e22243 — Add ClusterODM admin redirect integration

- Date: 2026-02-06; type: non-merge.
- Evidence: [08e2224325f0cc9caf251c8293502f1748bfce18](https://github.com/In-For-Disaster-Analytics/WebODM/commit/08e2224325f0cc9caf251c8293502f1748bfce18).
- Catalog: [NODE-02](2026-10-27-webodm-customization-inventory.md#node-02). Basis: explicit evidence reference.
- Changed paths: `.env`, `app/templates/app/clusterodm_redirect.html`, `app/templates/app/logged_in_base.html`, `app/templatetags/settings.py`, `app/tests/test_clusterodm_admin.py`, `app/urls.py`, `app/views/app.py`, `docker-compose.yml`, `webodm/settings.py`.

## 6b4fef20 — Use JWT for ClusterODM redirect and validate token

- Date: 2026-02-06; type: non-merge.
- Evidence: [6b4fef20cef24c7432eb054057887232d1b20432](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6b4fef20cef24c7432eb054057887232d1b20432).
- Catalog: [NODE-02](2026-10-27-webodm-customization-inventory.md#node-02). Basis: explicit evidence reference.
- Changed paths: `app/templates/app/clusterodm_redirect.html`, `app/tests/test_clusterodm_admin.py`, `app/views/app.py`.

## 757e2e18 — Support categorical option domains & cluster nodes

- Date: 2026-05-06; type: non-merge.
- Evidence: [757e2e18a53943dd71d81d62b02de493e4e8e47b](https://github.com/In-For-Disaster-Analytics/WebODM/commit/757e2e18a53943dd71d81d62b02de493e4e8e47b).
- Catalog: [HPC-03](2026-10-27-webodm-customization-inventory.md#hpc-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/classes/PresetUtils.js`, `app/static/app/js/components/EditPresetDialog.jsx`, `app/static/app/js/components/EditTaskForm.jsx`.

## f4ed596b — Ensure ClusterODM visibility; pin nginx and update tests

- Date: 2026-05-17; type: non-merge.
- Evidence: [f4ed596bbbaebd7d4f3cb4e11995aebe789fddbf](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f4ed596bbbaebd7d4f3cb4e11995aebe789fddbf).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01), [OPS-04](2026-10-27-webodm-customization-inventory.md#ops-04). Basis: explicit evidence reference.
- Changed paths: `Dockerfile`, `app/boot.py`, `app/tests/test_app.py`, `nodeodm/models.py`, `nodeodm/tests.py`.

## 864caf55 — Add temporary WMS and tile map layers

- Date: 2026-05-22; type: non-merge.
- Evidence: [864caf5540a4c271172ab2b14b5fcfe6953537e5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/864caf5540a4c271172ab2b14b5fcfe6953537e5).
- Catalog: [MAP-02](2026-10-27-webodm-customization-inventory.md#map-02). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/LayersControlLayer.jsx`, `app/static/app/js/components/Map.jsx`, `app/static/app/js/components/TemporaryMapLayerDialog.jsx`, `app/static/app/js/components/tests/TemporaryMapLayerDialog.test.jsx`, `app/static/app/js/css/Map.scss`.

## 92a5407f — change layer level

- Date: 2026-05-22; type: non-merge.
- Evidence: [92a5407f1dc7a43e7512e6e27a02cb1f6dc275b4](https://github.com/In-For-Disaster-Analytics/WebODM/commit/92a5407f1dc7a43e7512e6e27a02cb1f6dc275b4).
- Catalog: [MAP-02](2026-10-27-webodm-customization-inventory.md#map-02). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/LayersControlLayer.jsx`, `app/static/app/js/components/Map.jsx`, `app/static/app/js/components/tests/LayersControlLayer.test.jsx`.

## 7ff6e4c8 — Add TAS allocations support and UI integration

- Date: 2026-05-27; type: non-merge.
- Evidence: [7ff6e4c8cb8fbbe90a403eddcfe9746786888d0a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ff6e4c8cb8fbbe90a403eddcfe9746786888d0a).
- Catalog: [HPC-01](2026-10-27-webodm-customization-inventory.md#hpc-01). Basis: explicit evidence reference.
- Changed paths: `README.md`, `app/api/tas_allocations.py`, `app/api/urls.py`, `app/services/tas_allocations.py`, `app/static/app/js/components/EditTaskForm.jsx`, `app/static/app/js/components/ProcessingNodeOption.jsx`, `app/tests/test_tas_allocations.py`, `webodm/settings.py`.

## 40c6f4de — Submit default Tapis task options

- Date: 2026-05-27; type: non-merge.
- Evidence: [40c6f4def0be886ab35da15f538a8e6f708de22b](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40c6f4def0be886ab35da15f538a8e6f708de22b).
- Catalog: [HPC-01](2026-10-27-webodm-customization-inventory.md#hpc-01). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/EditTaskForm.jsx`, `app/static/app/js/components/tests/EditTaskForm.test.jsx`.

## f3fca5d1 — Fetch ClusterODM options over HTTPS

- Date: 2026-05-27; type: non-merge.
- Evidence: [f3fca5d136aaf135459db28f15b6e2f77bea80d8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f3fca5d136aaf135459db28f15b6e2f77bea80d8).
- Catalog: [NODE-01](2026-10-27-webodm-customization-inventory.md#node-01). Basis: explicit evidence reference.
- Changed paths: `nodeodm/jwt_node_wrapper.py`.

## f6929fc0 — Pass TAS credentials to WebODM services

- Date: 2026-05-27; type: non-merge.
- Evidence: [f6929fc03a0b89e032edba9142b7b22756fc6634](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f6929fc03a0b89e032edba9142b7b22756fc6634).
- Catalog: [HPC-01](2026-10-27-webodm-customization-inventory.md#hpc-01). Basis: explicit evidence reference.
- Changed paths: `docker-compose.yml`.

## 4b8da204 — Allow restart fallback for offline tasks

- Date: 2026-06-01; type: non-merge.
- Evidence: [4b8da2043876e24674e9b8e6379bf78af274f686](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4b8da2043876e24674e9b8e6379bf78af274f686).
- Catalog: [TASK-01](2026-10-27-webodm-customization-inventory.md#task-01). Basis: explicit evidence reference.
- Changed paths: `app/models/task.py`.

## f44673ee — Add local checkpoint dev stack

- Date: 2026-06-01; type: non-merge.
- Evidence: [f44673ee073aaf8f30ec0d250a182a63f6175e0e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f44673ee073aaf8f30ec0d250a182a63f6175e0e).
- Catalog: [DEV-01](2026-10-27-webodm-customization-inventory.md#dev-01). Basis: explicit evidence reference.
- Changed paths: `local-dev/.gitignore`, `local-dev/README.md`, `local-dev/docker-compose.local.yml`, `local-dev/down.sh`, `local-dev/logs.sh`, `local-dev/up.sh`, `local-dev/webodm.env`, `nodeodm/models.py`.

## e60b44c3 — Add local checkpoint smoke stack

- Date: 2026-06-01; type: non-merge.
- Evidence: [e60b44c39f4936590558ac62cd1d3ff7652a97c3](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e60b44c39f4936590558ac62cd1d3ff7652a97c3).
- Catalog: [DEV-01](2026-10-27-webodm-customization-inventory.md#dev-01). Basis: explicit evidence reference.
- Changed paths: `app/api/authentication.py`, `app/localdev.py`, `local-dev/.gitignore`, `local-dev/README.md`, `local-dev/docker-compose.local.yml`, `local-dev/down.sh`, `local-dev/install-hosts.sh`, `local-dev/logs.sh`, `local-dev/restart-nodeodm-smoke.py`, `local-dev/up.sh`, `local-dev/webodm.env`, `scripts/entrypoint-tapis.sh`, `webodm/settings.py`.

## 038268b9 — Create .env.sample

- Date: 2026-06-01; type: non-merge.
- Evidence: [038268b94dc19d9a2c46a8a0ce58739e95711fd1](https://github.com/In-For-Disaster-Analytics/WebODM/commit/038268b94dc19d9a2c46a8a0ce58739e95711fd1).
- Catalog: [DEV-01](2026-10-27-webodm-customization-inventory.md#dev-01). Basis: explicit evidence reference.
- Changed paths: `.env.sample`.

## ba28b8e8 — Trim local Docker build context

- Date: 2026-06-01; type: non-merge.
- Evidence: [ba28b8e8e5571294ca77d9612460c49e50e920b0](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba28b8e8e5571294ca77d9612460c49e50e920b0).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: explicit evidence reference.
- Changed paths: `.dockerignore`.

## 9a1948b4 — updated security for uploading and running jobs to run through allocations.

- Date: 2026-06-22; type: non-merge.
- Evidence: [9a1948b49a2da6dec0a462a8f5c14ff95357251c](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9a1948b49a2da6dec0a462a8f5c14ff95357251c).
- Catalog: [HPC-02](2026-10-27-webodm-customization-inventory.md#hpc-02). Basis: explicit evidence reference.
- Changed paths: `.env.sample`, `app/api/permissions.py`, `app/api/projects.py`, `app/api/tasks.py`, `app/services/tas_allocations.py`, `app/tests/test_tas_allocations.py`, `docker-compose.yml`, `local-dev/webodm.env`, `webodm/settings.py`.

## 1ba6a303 — Change Tas Cache Time

- Date: 2026-06-22; type: non-merge.
- Evidence: [1ba6a3033e264227045dc1e0dda599609dd6e553](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1ba6a3033e264227045dc1e0dda599609dd6e553).
- Catalog: [HPC-02](2026-10-27-webodm-customization-inventory.md#hpc-02). Basis: explicit evidence reference.
- Changed paths: `.env.sample`, `webodm/settings.py`.

## d6252e13 — Own corral media as a service account via gosu; enforce group inheritance

- Date: 2026-07-01; type: non-merge.
- Evidence: [d6252e13e24e2f46b7231dce37e8615223396954](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d6252e13e24e2f46b7231dce37e8615223396954).
- Catalog: [OPS-02](2026-10-27-webodm-customization-inventory.md#ops-02). Basis: explicit evidence reference.
- Changed paths: `.env`, `.env.sample`, `Dockerfile`, `docker-compose.yml`, `setup.sh`, `start.sh`, `worker.sh`.

## 5b370bc0 — Use numeric uid:gid for WO_RUN_AS_USER; throttle setup perms sweep

- Date: 2026-07-01; type: non-merge.
- Evidence: [5b370bc029fdea454d7b2e770a28184f7b050fe5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5b370bc029fdea454d7b2e770a28184f7b050fe5).
- Catalog: [OPS-02](2026-10-27-webodm-customization-inventory.md#ops-02). Basis: explicit evidence reference.
- Changed paths: `.env.sample`, `setup.sh`.

## 4d3e7d66 — Merge pull request #5 from In-For-Disaster-Analytics/corral-ownership-gosu

- Date: 2026-07-01; type: merge.
- Evidence: [4d3e7d666db2452f1093ffd086fe73b3a6467dc6](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4d3e7d666db2452f1093ffd086fe73b3a6467dc6).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01), [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01), [OPS-04](2026-10-27-webodm-customization-inventory.md#ops-04), [TASK-03](2026-10-27-webodm-customization-inventory.md#task-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `.env`, `.env.sample`, `Dockerfile`, `docker-compose.yml`, `setup.sh`, `start.sh`, `worker.sh`.

## bbe12add — Fix PermissionError under gosu: chown coreplugins to the service account

- Date: 2026-07-06; type: non-merge.
- Evidence: [bbe12adda61b9db1791042ca334205c445f1a87a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bbe12adda61b9db1791042ca334205c445f1a87a).
- Catalog: [OPS-02](2026-10-27-webodm-customization-inventory.md#ops-02). Basis: explicit evidence reference.
- Changed paths: `start.sh`, `worker.sh`.

## 85eb8018 — Merge pull request #6 from In-For-Disaster-Analytics/corral-ownership-plugin-perms

- Date: 2026-07-06; type: merge.
- Evidence: [85eb8018c33a142fea629fb6535c37b6eec8f23d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/85eb8018c33a142fea629fb6535c37b6eec8f23d).
- Catalog: [OPS-04](2026-10-27-webodm-customization-inventory.md#ops-04), [TASK-03](2026-10-27-webodm-customization-inventory.md#task-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `start.sh`, `worker.sh`.

## 5b7a2a13 — Update setup.sh

- Date: 2026-07-01; type: non-merge.
- Evidence: [5b7a2a13abd97c32c7a22f51e6b6ba2cf0c33a12](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5b7a2a13abd97c32c7a22f51e6b6ba2cf0c33a12).
- Catalog: [OPS-02](2026-10-27-webodm-customization-inventory.md#ops-02). Basis: explicit evidence reference.
- Changed paths: `setup.sh`.

## ed86ff0f — Merge pull request #7 from In-For-Disaster-Analytics/corral-ownership-gosu

- Date: 2026-07-06; type: merge.
- Evidence: [ed86ff0fc2239d239b63fa6dc4619b4351ff79ca](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ed86ff0fc2239d239b63fa6dc4619b4351ff79ca).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## b4065c7b — Make the nightly backup cron opt-in (WEBODM_ENABLE_BACKUP_CRON)

- Date: 2026-07-06; type: non-merge.
- Evidence: [b4065c7b823cbb60457b9e9d6a7a6e46d6860c19](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b4065c7b823cbb60457b9e9d6a7a6e46d6860c19).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: explicit evidence reference.
- Changed paths: `setup.sh`.

## 94f3b2d5 — Merge pull request #11 from In-For-Disaster-Analytics/backup-cron-opt-in

- Date: 2026-07-06; type: merge.
- Evidence: [94f3b2d55cf37f68e432a16a9d526a2aa4a5bd19](https://github.com/In-For-Disaster-Analytics/WebODM/commit/94f3b2d55cf37f68e432a16a9d526a2aa4a5bd19).
- Catalog: [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `setup.sh`.

## 4578543c — Add scripts/backup-ctl.sh to manage backups without running setup.sh

- Date: 2026-07-06; type: non-merge.
- Evidence: [4578543c3c4ac25ebc242c671875d650cb917def](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4578543c3c4ac25ebc242c671875d650cb917def).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: explicit evidence reference.
- Changed paths: `scripts/backup-ctl.sh`.

## 490cc664 — Merge pull request #12 from In-For-Disaster-Analytics/backup-ctl-script

- Date: 2026-07-06; type: merge.
- Evidence: [490cc6646e5697e8b43418b2602d27998a5d93c9](https://github.com/In-For-Disaster-Analytics/WebODM/commit/490cc6646e5697e8b43418b2602d27998a5d93c9).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/backup-ctl.sh`.

## 56db916e — Backup: run as current user (not sudo) + lock-path fallback

- Date: 2026-07-06; type: non-merge.
- Evidence: [56db916e3e0221608276bcd06963dba6025913ea](https://github.com/In-For-Disaster-Analytics/WebODM/commit/56db916e3e0221608276bcd06963dba6025913ea).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: explicit evidence reference.
- Changed paths: `scripts/backup-ctl.sh`.

## 88d4f0c6 — Merge pull request #13 from In-For-Disaster-Analytics/backup-run-nosudo

- Date: 2026-07-06; type: merge.
- Evidence: [88d4f0c68fd83b180d4b9e30f24201d8ee44a3a7](https://github.com/In-For-Disaster-Analytics/WebODM/commit/88d4f0c68fd83b180d4b9e30f24201d8ee44a3a7).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/backup-ctl.sh`.

## 1d198eb9 — Backup media: stage to local disk first, then push to corral (no read+write on same mount)

- Date: 2026-07-06; type: non-merge.
- Evidence: [1d198eb95b2e735cca4b51cffcd4c246ffad30c4](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1d198eb95b2e735cca4b51cffcd4c246ffad30c4).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: explicit evidence reference.
- Changed paths: `scripts/backup-ctl.sh`.

## e23f3577 — Merge pull request #14 from In-For-Disaster-Analytics/backup-local-stage

- Date: 2026-07-06; type: merge.
- Evidence: [e23f357773f4aff1d5e12c212fc498038855ad8e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e23f357773f4aff1d5e12c212fc498038855ad8e).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/backup-ctl.sh`.

## b4db21c5 — Backup: hang-tolerant corral preflight (abort instead of wedging on a hung mount)

- Date: 2026-07-06; type: non-merge.
- Evidence: [b4db21c5f1e8f41fc457f611ee21ee36a1598240](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b4db21c5f1e8f41fc457f611ee21ee36a1598240).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: explicit evidence reference.
- Changed paths: `scripts/backup-ctl.sh`.

## cf07eab0 — Merge pull request #15 from In-For-Disaster-Analytics/backup-hang-tolerant

- Date: 2026-07-06; type: merge.
- Evidence: [cf07eab08879ce00cb85926b4897287411cd9e6c](https://github.com/In-For-Disaster-Analytics/WebODM/commit/cf07eab08879ce00cb85926b4897287411cd9e6c).
- Catalog: [OPS-03](2026-10-27-webodm-customization-inventory.md#ops-03). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `scripts/backup-ctl.sh`.

## f0ba3a43 — Add Upstream sensor overlay plugin with Tapis OAuth2 integration

- Date: 2026-07-14; type: non-merge.
- Evidence: [f0ba3a4349b4b1d67afe30350c7d4bcecfec3c50](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f0ba3a4349b4b1d67afe30350c7d4bcecfec3c50).
- Catalog: [PLUGIN-01](2026-10-27-webodm-customization-inventory.md#plugin-01), [PLUGIN-02](2026-10-27-webodm-customization-inventory.md#plugin-02). Basis: explicit evidence reference.
- Changed paths: `app/api/tapis_oauth2.py`, `app/boot.py`, `app/static/app/js/ModelView.jsx`, `app/static/app/js/classes/plugins/API.js`, `app/static/app/js/classes/plugins/Model.js`, `coreplugins/upstream/__init__.py`, `coreplugins/upstream/api.py`, `coreplugins/upstream/manifest.json`, `coreplugins/upstream/plugin.py`, `coreplugins/upstream/public/app.jsx`, `coreplugins/upstream/public/app.scss`, `coreplugins/upstream/public/main.js`, `coreplugins/upstream/public/model.jsx`, `coreplugins/upstream/public/package.json`, `webodm.sh`.

## 01011676 — Merge pull request #16 from In-For-Disaster-Analytics/feature/upstream-sensor-plugin

- Date: 2026-07-15; type: merge.
- Evidence: [01011676396b05908781e26e02aee7e9e083ff1c](https://github.com/In-For-Disaster-Analytics/WebODM/commit/01011676396b05908781e26e02aee7e9e083ff1c).
- Catalog: [AUTH-01](2026-10-27-webodm-customization-inventory.md#auth-01), [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01), [PLUGIN-01](2026-10-27-webodm-customization-inventory.md#plugin-01), [VIEW-01](2026-10-27-webodm-customization-inventory.md#view-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `app/api/tapis_oauth2.py`, `app/boot.py`, `app/static/app/js/ModelView.jsx`, `app/static/app/js/classes/plugins/API.js`, `app/static/app/js/classes/plugins/Model.js`, `coreplugins/upstream/__init__.py`, `coreplugins/upstream/api.py`, `coreplugins/upstream/manifest.json`, `coreplugins/upstream/plugin.py`, `coreplugins/upstream/public/app.jsx`, `coreplugins/upstream/public/app.scss`, `coreplugins/upstream/public/main.js`, `coreplugins/upstream/public/model.jsx`, `coreplugins/upstream/public/package.json`, `webodm.sh`.

## b318e6ec — upstream plugin: add Tapis login link, commit build artifacts

- Date: 2026-07-15; type: non-merge.
- Evidence: [b318e6ecfee5766ed7c3d146d130b724f430b721](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b318e6ecfee5766ed7c3d146d130b724f430b721).
- Catalog: [PLUGIN-01](2026-10-27-webodm-customization-inventory.md#plugin-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/upstream/api.py`, `coreplugins/upstream/public/app.jsx`, `coreplugins/upstream/public/build/app.css`, `coreplugins/upstream/public/build/app.js`, `coreplugins/upstream/public/build/model.js`, `coreplugins/upstream/public/build/model.js.LICENSE.txt`.

## c0b20497 — feat(ckan): add CKAN publish plugin with DSO agent integration

- Date: 2026-07-16; type: non-merge.
- Evidence: [c0b204974bb25e90f8c2bebbc7bad859e7d3eef6](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c0b204974bb25e90f8c2bebbc7bad859e7d3eef6).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `app/api/tapis_oauth2.py`, `app/migrations/0047_task_ckan_url.py`, `app/models/task.py`, `coreplugins/ckan/__init__.py`, `coreplugins/ckan/api_views.py`, `coreplugins/ckan/manifest.json`, `coreplugins/ckan/plugin.py`, `coreplugins/ckan/public/CKANPublishPanel.jsx`, `coreplugins/ckan/public/build/CKANPublishPanel.js`, `coreplugins/ckan/public/build/CKANPublishPanel.js.LICENSE.txt`, `coreplugins/ckan/publisher.py`, `coreplugins/ckan/templates/load_buttons.js`, `docker-compose.yml`, `docs/design/2026-07-08-publish-to-ckan.md`, `webodm/settings.py`.

## 86b39d90 — Add OpenWolf hooks, anatomy & tooling

- Date: 2026-07-16; type: non-merge.
- Evidence: [86b39d9038a35b9f6a593d75553a1cc97e4e75f7](https://github.com/In-For-Disaster-Analytics/WebODM/commit/86b39d9038a35b9f6a593d75553a1cc97e4e75f7).
- Catalog: [DEV-02](2026-10-27-webodm-customization-inventory.md#dev-02). Basis: explicit evidence reference.
- Changed paths: `.claude/rules/openwolf.md`, `.claude/settings.json`, `.wolf/OPENWOLF.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`, `.wolf/cerebrum.md`, `.wolf/config.json`, `.wolf/cron-manifest.json`, `.wolf/cron-state.json`, `.wolf/designqc-report.json`, `.wolf/hooks/_session.json`, `.wolf/hooks/package.json`, `.wolf/hooks/post-read.js`, `.wolf/hooks/post-write.js`, `.wolf/hooks/pre-read.js`, `.wolf/hooks/pre-write.js`, `.wolf/hooks/session-start.js`, `.wolf/hooks/shared.js`, `.wolf/hooks/stop.js`, `.wolf/identity.md`, `.wolf/memory.md`, `.wolf/reframe-frameworks.md`, `.wolf/suggestions.json`, `.wolf/token-ledger.json`, `CLAUDE.md`, `coreplugins/ckan/publisher.py`.

## f5bcdcae — fix(ckan): fix chat timeout and LLM path hallucination in CKAN plugin

- Date: 2026-07-16; type: non-merge.
- Evidence: [f5bcdcae5ffd0267f5e0ef4e8ca014a3dca03f43](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f5bcdcae5ffd0267f5e0ef4e8ca014a3dca03f43).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `.wolf/buglog.json`, `coreplugins/ckan/api_views.py`, `coreplugins/ckan/publisher.py`.

## 4c34f581 — fix(ckan): fall back to task.created_at for temporal coverage when stats.json lacks dates

- Date: 2026-07-16; type: non-merge.
- Evidence: [4c34f58146d45db07132d8ddb49ded19c9496fb5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4c34f58146d45db07132d8ddb49ded19c9496fb5).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/publisher.py`.

## ca9fd1e4 — fix(ckan): derive base URL from request, make task public, filter assets on publish

- Date: 2026-07-17; type: non-merge.
- Evidence: [ca9fd1e4c8dda9428677cbe00f15c29c2ca83316](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ca9fd1e4c8dda9428677cbe00f15c29c2ca83316).
- Catalog: [CKAN-02](2026-10-27-webodm-customization-inventory.md#ckan-02). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/api_views.py`, `coreplugins/ckan/publisher.py`.

## 688858a5 — feat(ckan): async phase messaging and apply error propagation

- Date: 2026-07-17; type: non-merge.
- Evidence: [688858a564795c043b892211cf2e5834573f8376](https://github.com/In-For-Disaster-Analytics/WebODM/commit/688858a564795c043b892211cf2e5834573f8376).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/api_views.py`, `coreplugins/ckan/public/CKANPublishPanel.jsx`, `coreplugins/ckan/publisher.py`.

## 0122b947 — fix(ckan): always scroll chat to bottom on new message

- Date: 2026-07-17; type: non-merge.
- Evidence: [0122b947908b407ee281ac12103d766e0fdb6575](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0122b947908b407ee281ac12103d766e0fdb6575).
- Catalog: [CKAN-02](2026-10-27-webodm-customization-inventory.md#ckan-02). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/public/CKANPublishPanel.jsx`.

## 7db3b4ee — fix(ckan): send GeoJSON spatial (not WKT); surface resource errors

- Date: 2026-07-17; type: non-merge.
- Evidence: [7db3b4ee8771dc460e28b37b9dea0b239393a761](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7db3b4ee8771dc460e28b37b9dea0b239393a761).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/publisher.py`.

## 829d2bb5 — fix(ckan): persist owner_org for re-publish; log agent error bodies

- Date: 2026-07-17; type: non-merge.
- Evidence: [829d2bb5d177836f3509940badb19d0e37203692](https://github.com/In-For-Disaster-Analytics/WebODM/commit/829d2bb5d177836f3509940badb19d0e37203692).
- Catalog: [CKAN-02](2026-10-27-webodm-customization-inventory.md#ckan-02). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/api_views.py`, `coreplugins/ckan/publisher.py`.

## dbc55f2d — Update nginx.conf.template

- Date: 2026-07-17; type: non-merge.
- Evidence: [dbc55f2d7ba8e52d12f22f0566a568259ade6b93](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dbc55f2d7ba8e52d12f22f0566a568259ade6b93).
- Catalog: [OPS-04](2026-10-27-webodm-customization-inventory.md#ops-04). Basis: explicit evidence reference.
- Changed paths: `nginx/nginx.conf.template`.

## ff72166f — Update nginx.conf.template

- Date: 2026-07-17; type: non-merge.
- Evidence: [ff72166f12338cae9b316b4bfa68036428e8e4a1](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ff72166f12338cae9b316b4bfa68036428e8e4a1).
- Catalog: [OPS-04](2026-10-27-webodm-customization-inventory.md#ops-04). Basis: explicit evidence reference.
- Changed paths: `nginx/nginx.conf.template`.

## fc5b8a88 — fix(ckan): use public task URLs for map and 3D viewer resources

- Date: 2026-07-17; type: non-merge.
- Evidence: [fc5b8a88ca3f1e2967926e366e9df3f0a1119d36](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fc5b8a88ca3f1e2967926e366e9df3f0a1119d36).
- Catalog: [CKAN-02](2026-10-27-webodm-customization-inventory.md#ckan-02). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/publisher.py`.

## 7b68b3b2 — fix(ckan): increase agent timeouts to 180s and clear interrupt flag on timeout

- Date: 2026-07-17; type: non-merge.
- Evidence: [7b68b3b237779f4f4d689347e7220d66dafc1e4a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7b68b3b237779f4f4d689347e7220d66dafc1e4a).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/api_views.py`.

## ff9c7478 — fix(ckan): harden URL prompt, add timestamps, tests, README, read-only ckan_url

- Date: 2026-07-17; type: non-merge.
- Evidence: [ff9c7478553d5178583f67147a4ef9be017e3a69](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ff9c7478553d5178583f67147a4ef9be017e3a69).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01), [CKAN-02](2026-10-27-webodm-customization-inventory.md#ckan-02). Basis: explicit evidence reference.
- Changed paths: `app/api/tasks.py`, `app/tests/test_ckan_plugin.py`, `coreplugins/ckan/README.md`, `coreplugins/ckan/api_views.py`, `coreplugins/ckan/publisher.py`.

## 189facec — fix(ckan): stop passing download URLs as source_urls; guard dataset url field

- Date: 2026-07-17; type: non-merge.
- Evidence: [189facec4fbc905e7c329ff6cdc1f0662b0f5e4e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/189facec4fbc905e7c329ff6cdc1f0662b0f5e4e).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/api_views.py`.

## 0b9a1325 — fix(ckan): add explicit fetch_remote_pdf first-call instruction for report.pdf

- Date: 2026-07-17; type: non-merge.
- Evidence: [0b9a13259b298762913070dd1ff8222ee2236715](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0b9a13259b298762913070dd1ff8222ee2236715).
- Catalog: [CKAN-01](2026-10-27-webodm-customization-inventory.md#ckan-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/ckan/api_views.py`.

## 8e0a58e4 — Update start.sh

- Date: 2026-07-20; type: non-merge.
- Evidence: [8e0a58e46099114fd3fda1cc027d94822378b8d5](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8e0a58e46099114fd3fda1cc027d94822378b8d5).
- Catalog: [OPS-02](2026-10-27-webodm-customization-inventory.md#ops-02), [OPS-04](2026-10-27-webodm-customization-inventory.md#ops-04). Basis: explicit evidence reference.
- Changed paths: `start.sh`.

## 89a8b5f0 — Update docker-compose.yml

- Date: 2026-07-20; type: non-merge.
- Evidence: [89a8b5f097ff266c3d53d1f993a2f949d8e69631](https://github.com/In-For-Disaster-Analytics/WebODM/commit/89a8b5f097ff266c3d53d1f993a2f949d8e69631).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `docker-compose.yml`.

## be4214c3 — Cap numpy/BLAS/GDAL thread pools to fix concurrent raster metadata slowdowns

- Date: 2026-07-20; type: non-merge.
- Evidence: [be4214c3e3389056e75a3f54c1a4614e560c50a1](https://github.com/In-For-Disaster-Analytics/WebODM/commit/be4214c3e3389056e75a3f54c1a4614e560c50a1).
- Catalog: [MAP-03](2026-10-27-webodm-customization-inventory.md#map-03). Basis: explicit evidence reference.
- Changed paths: `docker-compose.yml`.

## 42663435 — Disable detectRetina on imagery tile layers to cut concurrent tile-render load

- Date: 2026-07-20; type: non-merge.
- Evidence: [42663435ddf847065a537587fb2b2de4905e972d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/42663435ddf847065a537587fb2b2de4905e972d).
- Catalog: [MAP-03](2026-10-27-webodm-customization-inventory.md#map-03). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/Map.jsx`.

## dffcf1f6 — Cache tiler Metadata/Tiles responses in Redis to avoid recomputing per request

- Date: 2026-07-20; type: non-merge.
- Evidence: [dffcf1f6bd2334bf1456851410d2ac0e11087286](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dffcf1f6bd2334bf1456851410d2ac0e11087286).
- Catalog: [MAP-03](2026-10-27-webodm-customization-inventory.md#map-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tiler.py`.

## 3ee22ed9 — Fix 500s from unpicklable CRS object in tiler cache; make cache ops defensive

- Date: 2026-07-20; type: non-merge.
- Evidence: [3ee22ed9a903a09a67780e39bb0e3f772eda7cc2](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3ee22ed9a903a09a67780e39bb0e3f772eda7cc2).
- Catalog: [MAP-03](2026-10-27-webodm-customization-inventory.md#map-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tiler.py`.

## 2ab89b75 — Fix second unpicklable-object bug in tiler cache: dict_values from colormap

- Date: 2026-07-21; type: non-merge.
- Evidence: [2ab89b751e262443205161cfe5a8656a45255136](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2ab89b751e262443205161cfe5a8656a45255136).
- Catalog: [MAP-03](2026-10-27-webodm-customization-inventory.md#map-03). Basis: explicit evidence reference.
- Changed paths: `app/api/tiler.py`.

## df9681a0 — Add embeddings coreplugin skeleton and its design spec

- Date: 2026-07-22; type: non-merge.
- Evidence: [df9681a0a5d2039edbbaf855be8ebe120a042cde](https://github.com/In-For-Disaster-Analytics/WebODM/commit/df9681a0a5d2039edbbaf855be8ebe120a042cde).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01), [EMBED-07](2026-10-27-webodm-customization-inventory.md#embed-07). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/__init__.py`, `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/manifest.json`, `coreplugins/embeddings/plugin.py`, `coreplugins/embeddings/templates/index.html`, `coreplugins/embeddings/templates/load_buttons.js`, `coreplugins/embeddings/templates/model_diagnostics.html`, `coreplugins/embeddings/views.py`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## 32763117 — Implement label_studio_client.py; correct Label Studio credential model

- Date: 2026-07-22; type: non-merge.
- Evidence: [3276311720ae92598db29d226529abec6943e448](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3276311720ae92598db29d226529abec6943e448).
- Catalog: [EMBED-04](2026-10-27-webodm-customization-inventory.md#embed-04). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/label_studio_client.py`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `webodm/settings.py`.

## 2d52c9e6 — Record embeddingsdb going live (Decision 33)

- Date: 2026-07-23; type: non-merge.
- Evidence: [2d52c9e69d2fd9efb2c3e96264546495cfb9c191](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2d52c9e69d2fd9efb2c3e96264546495cfb9c191).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## 40f18d48 — Implement embeddings_client.py against the live embeddingsdb

- Date: 2026-07-23; type: non-merge.
- Evidence: [40f18d4858f02ab2934216a7313fe812b8820b54](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40f18d4858f02ab2934216a7313fe812b8820b54).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01), [EMBED-07](2026-10-27-webodm-customization-inventory.md#embed-07). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `webodm/settings.py`.

## 912d1ec2 — Record real Actor message contract + embed-generate DB writes (Decision 35)

- Date: 2026-07-23; type: non-merge.
- Evidence: [912d1ec235d6f4d97b3c21bca19d696c6357106d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/912d1ec235d6f4d97b3c21bca19d696c6357106d).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## 468887f4 — Correct Decision 35: Actor images use GHCR, not Docker Hub (Decision 36)

- Date: 2026-07-23; type: non-merge.
- Evidence: [468887f4541c8ccdd6f0ed2383e10f9f520b1f69](https://github.com/In-For-Disaster-Analytics/WebODM/commit/468887f4541c8ccdd6f0ed2383e10f9f520b1f69).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## df6f09ff — Wire real embed-generate Actor invocation; resolve Decision 30 for real

- Date: 2026-07-23; type: non-merge.
- Evidence: [df6f09ffc929115b0e97c5122d670d8ba93ba749](https://github.com/In-For-Disaster-Analytics/WebODM/commit/df6f09ffc929115b0e97c5122d670d8ba93ba749).
- Catalog: [EMBED-05](2026-10-27-webodm-customization-inventory.md#embed-05), [EMBED-07](2026-10-27-webodm-customization-inventory.md#embed-07). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `requirements.txt`, `webodm/settings.py`.

## 1337cc7f — Build real EmbeddingsPanel.jsx -- first actual plugin UI, not a placeholder

- Date: 2026-07-23; type: non-merge.
- Evidence: [1337cc7f25dc3b5b593cf483fa359dcf007b1170](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1337cc7f25dc3b5b593cf483fa359dcf007b1170).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js.LICENSE.txt`, `coreplugins/embeddings/public/webpack.config.js`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## d1ae3985 — Fix embeddings plugin routing bug; move embed-generate to a Tapis Job on ls6

- Date: 2026-07-24; type: non-merge.
- Evidence: [d1ae3985640c8250503ce0a16e97784dc4374529](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d1ae3985640c8250503ce0a16e97784dc4374529).
- Catalog: [EMBED-05](2026-10-27-webodm-customization-inventory.md#embed-05). Basis: explicit evidence reference.
- Changed paths: `.env.sample`, `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `coreplugins/embeddings/plugin.py`, `docker-compose.yml`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `webodm/settings.py`.

## 15a33275 — Decision 45 correction: ls6 App uses SINGULARITY runtime, not a custom ZIP script

- Date: 2026-07-24; type: non-merge.
- Evidence: [15a33275bc176aaaf5a41b7907995d8fe0f752e8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/15a33275bc176aaaf5a41b7907995d8fe0f752e8).
- Catalog: [EMBED-05](2026-10-27-webodm-customization-inventory.md#embed-05). Basis: explicit evidence reference.
- Changed paths: `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## 38332345 — Update stale corral-repl path in deployment doc

- Date: 2026-07-28; type: non-merge.
- Evidence: [38332345929889f0de6c705f31cb3db160577104](https://github.com/In-For-Disaster-Analytics/WebODM/commit/38332345929889f0de6c705f31cb3db160577104).
- Catalog: General reconciliation/documentation; inspect paths and patch for detail. Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `DEPLOYMENT_INSTRUCTIONS.md`.

## 652ebb81 — Base64-encode the ls6 Job's MSG payload; record 5 real job-run fixes

- Date: 2026-07-29; type: non-merge.
- Evidence: [652ebb81e0d2201d5c20586e500728665d3c24fe](https://github.com/In-For-Disaster-Analytics/WebODM/commit/652ebb81e0d2201d5c20586e500728665d3c24fe).
- Catalog: [EMBED-05](2026-10-27-webodm-customization-inventory.md#embed-05). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/embeddings_client.py`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## 3f178647 — Always use the task's highest-resolution zoom; restrict plugin to admins

- Date: 2026-07-29; type: non-merge.
- Evidence: [3f17864758daa72209a619d750e0f46fb73d1d75](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f17864758daa72209a619d750e0f46fb73d1d75).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/plugin.py`, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js.LICENSE.txt`, `coreplugins/embeddings/templates/load_buttons.js`, `coreplugins/embeddings/views.py`, `package.json`.

## a0473f2f — webodm.sh update: build from source, don't pull the public Docker Hub image

- Date: 2026-07-29; type: non-merge.
- Evidence: [a0473f2fa7200c6baea3c1f49d33cbb38a3e043b](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a0473f2fa7200c6baea3c1f49d33cbb38a3e043b).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: explicit evidence reference.
- Changed paths: `webodm.sh`.

## 981413d3 — Bump PyJWT to 1.7.1 -- required by tapipy, never actually committed

- Date: 2026-07-29; type: non-merge.
- Evidence: [981413d331a686218484873750c8fe89c4618abf](https://github.com/In-For-Disaster-Analytics/WebODM/commit/981413d331a686218484873750c8fe89c4618abf).
- Catalog: [BUILD-02](2026-10-27-webodm-customization-inventory.md#build-02). Basis: explicit evidence reference.
- Changed paths: `requirements.txt`.

## 808d6199 — Bump psycopg2-binary 2.8.6 -> 2.9.9: old bundled libpq can't handle PG17's direct-SSL negotiation

- Date: 2026-07-30; type: non-merge.
- Evidence: [808d61998c4c823b290374e300318ceff0241b89](https://github.com/In-For-Disaster-Analytics/WebODM/commit/808d61998c4c823b290374e300318ceff0241b89).
- Catalog: [BUILD-02](2026-10-27-webodm-customization-inventory.md#build-02). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/embeddings_client.py`, `requirements.txt`.

## 32471240 — Fix Django 2.2 / psycopg2 2.9 UTC assertion breaking db connection

- Date: 2026-07-30; type: non-merge.
- Evidence: [3247124010bdccfdd2aa94b7d48e5f81d4f4b0d1](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3247124010bdccfdd2aa94b7d48e5f81d4f4b0d1).
- Catalog: [BUILD-02](2026-10-27-webodm-customization-inventory.md#build-02). Basis: explicit evidence reference.
- Changed paths: `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `webodm/settings.py`.

## e1b4f2f0 — Fix embed-generate Job name exceeding Tapis's 64-char limit

- Date: 2026-07-30; type: non-merge.
- Evidence: [e1b4f2f08de2a01fd0ca977c7221231cae7b4a7a](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e1b4f2f08de2a01fd0ca977c7221231cae7b4a7a).
- Catalog: [EMBED-05](2026-10-27-webodm-customization-inventory.md#embed-05). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/embeddings_client.py`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## a0162a6a — Rewrite embeddings plugin UI text for end users, not developers

- Date: 2026-07-30; type: non-merge.
- Evidence: [a0162a6a92272458e11ef9752b1bbf902f121c8d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a0162a6a92272458e11ef9752b1bbf902f121c8d).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `coreplugins/embeddings/templates/index.html`, `coreplugins/embeddings/templates/model_diagnostics.html`.

## 574862d4 — Clean up two more user-facing embeddings error messages

- Date: 2026-07-30; type: non-merge.
- Evidence: [574862d477923ae0ef6b268b3a40b8754c2d4ae6](https://github.com/In-For-Disaster-Analytics/WebODM/commit/574862d477923ae0ef6b268b3a40b8754c2d4ae6).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01). Basis: path-based area suggestion; not a semantic claim.
- Changed paths: `coreplugins/embeddings/api_views.py`.

## 0e146bf9 — Implement real candidate-tile listing, site-scoped labeling, and a Label Studio webhook receiver

- Date: 2026-07-30; type: non-merge.
- Evidence: [0e146bf97eb08b78fb1efd5ec715f90f53aac120](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0e146bf97eb08b78fb1efd5ec715f90f53aac120).
- Catalog: [EMBED-02](2026-10-27-webodm-customization-inventory.md#embed-02), [EMBED-04](2026-10-27-webodm-customization-inventory.md#embed-04). Basis: explicit evidence reference.
- Changed paths: `.env.sample`, `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `coreplugins/embeddings/label_studio_client.py`, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `coreplugins/embeddings/tile_math.py`, `docker-compose.yml`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `webodm/settings.py`.

## 2ad37286 — Replace "Label a Sample"'s text input with a real map-based tile picker

- Date: 2026-07-30; type: non-merge.
- Evidence: [2ad372862dbcde0d5d3b036cd0dc5748d35a3bdc](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2ad372862dbcde0d5d3b036cd0dc5748d35a3bdc).
- Catalog: [EMBED-02](2026-10-27-webodm-customization-inventory.md#embed-02). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `coreplugins/embeddings/public/tileMath.js`.

## c2935995 — Label directly in the modal: two tabs, label palette, drag-to-paint

- Date: 2026-07-30; type: non-merge.
- Evidence: [c2935995ddf70f14038724602847f56d91add0eb](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c2935995ddf70f14038724602847f56d91add0eb).
- Catalog: [EMBED-03](2026-10-27-webodm-customization-inventory.md#embed-03). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `coreplugins/embeddings/label_studio_client.py`, `coreplugins/embeddings/plugin.py`, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## e105fb48 — Add "+ Add label class" UI and a real POST /sites endpoint

- Date: 2026-07-30; type: non-merge.
- Evidence: [e105fb483d5616557fc52f03a6ca123384077b67](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e105fb483d5616557fc52f03a6ca123384077b67).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01), [EMBED-03](2026-10-27-webodm-customization-inventory.md#embed-03). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## ba561511 — Default "New site" name to the task's own name

- Date: 2026-07-30; type: non-merge.
- Evidence: [ba5615110e7b0c68e6589dd568a346781189bd60](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba5615110e7b0c68e6589dd568a346781189bd60).
- Catalog: [EMBED-01](2026-10-27-webodm-customization-inventory.md#embed-01), [EMBED-03](2026-10-27-webodm-customization-inventory.md#embed-03). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## f1cd738a — Add an Eraser tool to undo a mistakenly painted label

- Date: 2026-07-30; type: non-merge.
- Evidence: [f1cd738a74c0e066fc2d312cf2d46224bfdb7abe](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f1cd738a74c0e066fc2d312cf2d46224bfdb7abe).
- Catalog: [EMBED-03](2026-10-27-webodm-customization-inventory.md#embed-03). Basis: explicit evidence reference.
- Changed paths: `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `coreplugins/embeddings/label_studio_client.py`, `coreplugins/embeddings/plugin.py`, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/public/build/EmbeddingsPanel.js`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`.

## 3f002ec7 — Fix Label Studio 401: exchange PAT for a real access token before use

- Date: 2026-08-04; type: non-merge.
- Evidence: [3f002ec77815aace70538ca685c61d3b5af9172d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f002ec77815aace70538ca685c61d3b5af9172d).
- Catalog: [EMBED-04](2026-10-27-webodm-customization-inventory.md#embed-04). Basis: explicit evidence reference.
- Changed paths: `.wolf/buglog.json`, `coreplugins/embeddings/label_studio_client.py`, `coreplugins/embeddings/tests.py`.

## bd1f8974 — chore: commit local changes

- Date: 2026-08-19; type: non-merge.
- Evidence: [bd1f8974ce120b199e8163b1e96ab463f2910fdf](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd1f8974ce120b199e8163b1e96ab463f2910fdf).
- Catalog: [EMBED-04](2026-10-27-webodm-customization-inventory.md#embed-04), [EMBED-06](2026-10-27-webodm-customization-inventory.md#embed-06), [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01), [BUILD-02](2026-10-27-webodm-customization-inventory.md#build-02), [DEV-02](2026-10-27-webodm-customization-inventory.md#dev-02). Basis: explicit evidence reference.
- Changed paths: `.wolf/anatomy.md`, `.wolf/buglog.json`, `.wolf/cerebrum.md`, `.wolf/memory.md`, `Dockerfile`, `coreplugins/embeddings/api_views.py`, `coreplugins/embeddings/embeddings_client.py`, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, `coreplugins/embeddings/tests.py`, `docker-compose.build.yml`, `docker-compose.dev.yml`, `docs/design/2026-07-22-geospatial-embeddings-classification.md`, `nginx/ssl.disabled/cert.pem`, `nginx/ssl.disabled/key.pem`, `webodm/settings.py`.

## ba134a99 — chore: update submodule references

- Date: 2026-08-19; type: non-merge.
- Evidence: [ba134a99a52ab94a0ea15c63f6a60d07cbe56726](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba134a99a52ab94a0ea15c63f6a60d07cbe56726).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01). Basis: explicit evidence reference.
- Changed paths: `locale`, `nodeodm/external/NodeODM`.

## 0c279a46 — feat: add Entwine Point Tile (EPT) support to 3D viewer

- Date: 2026-08-27; type: non-merge.
- Evidence: [0c279a46d1b16aad035825b9224a51c40e7c4e33](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0c279a46d1b16aad035825b9224a51c40e7c4e33).
- Catalog: [VIEW-01](2026-10-27-webodm-customization-inventory.md#view-01), [PLUGIN-02](2026-10-27-webodm-customization-inventory.md#plugin-02). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/ModelView.jsx`.

## fa3927cb — fix: add submission lock to prevent duplicate task processing

- Date: 2026-08-31; type: non-merge.
- Evidence: [fa3927cb174c7354d0f2bffea63e21b458c8fd05](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fa3927cb174c7354d0f2bffea63e21b458c8fd05).
- Catalog: [TASK-02](2026-10-27-webodm-customization-inventory.md#task-02). Basis: explicit evidence reference.
- Changed paths: `worker/tasks.py`.

## 341bdf94 — feat: remove Tapis JWT refresh, treat expiry as reauthentication boundary

- Date: 2026-08-31; type: non-merge.
- Evidence: [341bdf9436c149d918465fca4733698ec25ac4b8](https://github.com/In-For-Disaster-Analytics/WebODM/commit/341bdf9436c149d918465fca4733698ec25ac4b8).
- Catalog: [AUTH-02](2026-10-27-webodm-customization-inventory.md#auth-02). Basis: explicit evidence reference.
- Changed paths: `DEPLOYMENT_INSTRUCTIONS.md`, `TAPIS_OAUTH2_INTEGRATION.md`, `app/api/tapis_oauth2.py`, `app/api/urls.py`, `app/models/oauth2.py`, `app/models/task.py`, `app/services/tapis_storage.py`, `app/static/app/js/classes/TapisTokenManager.js`, `app/static/app/js/tests/TapisTokenManager.test.js`, `app/templatetags/tapis_tags.py`, `app/tests/test_clusterodm_admin.py`, `app/tests/test_tapis_oauth2_tokens.py`, `app/views/app.py`, `app/views/tapis_auth.py`, `coreplugins/ckan/publisher.py`, `coreplugins/embeddings/embeddings_client.py`, `coreplugins/embeddings/tests.py`, `coreplugins/upstream/api.py`, `docs/design/2026-08-28-tapis-jwt-expiry-logout.md`.

## c9425af8 — Add LS6 presets with TACC allocation settings

- Date: 2026-09-02; type: non-merge.
- Evidence: [c9425af8fc1b79aa87242e3f39d8f2fcb340429d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c9425af8fc1b79aa87242e3f39d8f2fcb340429d).
- Catalog: [HPC-04](2026-10-27-webodm-customization-inventory.md#hpc-04). Basis: explicit evidence reference.
- Changed paths: `app/boot.py`.

## 41509ceb — Add directory-based upload for images and GCP files

- Date: 2026-09-08; type: non-merge.
- Evidence: [41509cebe442ff8e4bddb0773ee0af9cf0f8dd3e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/41509cebe442ff8e4bddb0773ee0af9cf0f8dd3e).
- Catalog: [DATA-05](2026-10-27-webodm-customization-inventory.md#data-05). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/ProjectListItem.jsx`.

## fdad2f69 — Chain the directory picker so multiple folders can be added in one flow

- Date: 2026-09-08; type: non-merge.
- Evidence: [fdad2f698523003ced05222e70f24b9dc7be81dd](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fdad2f698523003ced05222e70f24b9dc7be81dd).
- Catalog: [DATA-05](2026-10-27-webodm-customization-inventory.md#data-05). Basis: explicit evidence reference.
- Changed paths: `app/static/app/js/components/ProjectListItem.jsx`, `app/static/app/js/components/tests/ProjectListItem.directoryUpload.test.jsx`.

## 004d0134 — chore: checkpoint pre-upstream merge state

- Date: 2026-10-05; type: non-merge.
- Evidence: [004d0134048a4dc406eb5b85c1e6eb54bdd58f8d](https://github.com/In-For-Disaster-Analytics/WebODM/commit/004d0134048a4dc406eb5b85c1e6eb54bdd58f8d).
- Catalog: [DATA-01](2026-10-27-webodm-customization-inventory.md#data-01), [DATA-02](2026-10-27-webodm-customization-inventory.md#data-02), [OPS-01](2026-10-27-webodm-customization-inventory.md#ops-01), [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01), [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `app/api/tapis_preferences.py`, `app/api/tapis_storage.py`, `nodeodm/external/NodeODM`, `setup_tapis_oauth2.py`.

## a3e9c41f — docs: specify WebODM upstream reconciliation

- Date: 2026-10-05; type: non-merge.
- Evidence: [a3e9c41f262309a0c5ee1f0cc4e74df217f5721e](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a3e9c41f262309a0c5ee1f0cc4e74df217f5721e).
- Catalog: [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md`.

## c79c488e — merge: reconcile upstream WebODM 3.1.2-era changes

- Date: 2026-10-05; type: merge.
- Evidence: [c79c488e5659bc90bfbf12583baa7155816eecb2](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c79c488e5659bc90bfbf12583baa7155816eecb2).
- Catalog: [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `.dockerignore`, `.github/workflows/build-docs.yml`, `.github/workflows/issue-triage.yml`, `Dockerfile`, `TRADEMARK.md`, `app/admin.py`, `app/api/admin.py`, `app/api/common.py`, `app/api/formulas.py`, `app/api/potree.py`, `app/api/projects.py`, `app/api/tasks.py`, `app/api/tiler.py`, `app/api/urls.py`, `app/boot.py`, `app/cogeo.py`, `app/fixtures/tiny_drone_image_multispec.tif`, `app/geoutils.py`, `app/management/commands/cluster.py`, `app/management/commands/ept.py`, `app/migrations/0048_profile_cluster_id.py`, `app/migrations/0049_redirect.py`, `app/migrations/0050_task_wkt.py`, `app/models/__init__.py`, `app/models/profile.py`, `app/models/project.py`, `app/models/redirect.py`, `app/models/setting.py`, `app/models/task.py`, `app/plugins/functions.py`, `app/pointcloud_utils.py`, `app/raster_utils.py`, `app/scripts/glbopti.js`, `app/scripts/unlock_all_tasks.py`, `app/static/app/css/main.scss`, `app/static/app/js/ModelView.jsx`, `app/static/app/js/classes/ColorMaps.js`, `app/static/app/js/classes/Gcp.js`, `app/static/app/js/classes/Units.js`, `app/static/app/js/classes/Utils.js`, `app/static/app/js/components/AssetDownloadButtons.jsx`, `app/static/app/js/components/EditTaskForm.jsx`, `app/static/app/js/components/ExportAssetDialog.jsx`, `app/static/app/js/components/ExportAssetPanel.jsx`, `app/static/app/js/components/FormDialog.jsx`, `app/static/app/js/components/ImagePopup.jsx`, `app/static/app/js/components/ImportTaskPanel.jsx`, `app/static/app/js/components/LayersControl.jsx`, `app/static/app/js/components/LayersControlLayer.jsx`, `app/static/app/js/components/Map.jsx`, `app/static/app/js/components/NewTaskPanel.jsx`, `app/static/app/js/components/PdfPopup.jsx`, `app/static/app/js/components/ProgressBar.jsx`, `app/static/app/js/components/ProjectListItem.jsx`, `app/static/app/js/components/Standby.jsx`, `app/static/app/js/components/SwitchModeButton.jsx`, `app/static/app/js/components/TaskListItem.jsx`, `app/static/app/js/components/Toggle.jsx`, `app/static/app/js/components/UploadProgressBar.jsx`, `app/static/app/js/components/tests/PdfPopup.test.jsx`, `app/static/app/js/components/tests/Units.test.jsx`, `app/static/app/js/css/ExportAssetPanel.scss`, `app/static/app/js/css/ImagePopup.scss`, `app/static/app/js/css/ModelView.scss`, `app/static/app/js/css/PdfPopup.scss`, `app/static/app/js/css/Standby.scss`, `app/static/app/js/css/TaskListItem.scss`, `app/static/app/js/css/Toggle.scss`, `app/static/app/js/icons/marker-cp.png`, `app/static/app/js/translations/odm_autogenerated.js`, `app/static/app/js/vendor/GLTFLoader.js`, `app/static/app/js/vendor/dropzone.js`, `app/static/app/js/vendor/potree/build/potree/potree.js`, `app/static/app/js/vendor/potree/build/potree/sidebar.html`, `app/templates/app/base.html`, `app/templates/app/dashboard.html`, `app/templatetags/settings.py`, `app/tests/test_api_admin.py`, `app/tests/test_api_export.py`, `app/tests/test_api_task.py`, `app/tests/test_api_task_import.py`, `app/tests/test_auto_login.py`, `app/tests/test_cluster.py`, `app/tests/test_quota.py`, `app/tests/test_task_wkt.py`, `app/tests/test_worker.py`, `app/translations/plugin_manifest_autogenerated.py`, `app/views/app.py`, `app/views/public.py`, `app/views/utils.py`, `contrib/Hard_Recovery_Guide.md`, `contrib/ubuntu_1604_install.sh`, `coreplugins/contours/api.py`, `coreplugins/contours/public/ContoursPanel.jsx`, `coreplugins/contours/public/ContoursPanel.scss`, `coreplugins/dronedb/api_views.py`, `coreplugins/dronedb/ddb.py`, `coreplugins/dronedb/plugin.py`, `coreplugins/dronedb/public/ShareButton.jsx`, `coreplugins/dronedb/public/components/ShareDialog.jsx`, `coreplugins/dronedb/public/components/ShareDialog.scss`, `coreplugins/hello-world/__init__.py`, `coreplugins/hello-world/disabled`, `coreplugins/hello-world/manifest.json`, `coreplugins/hello-world/plugin.py`, `coreplugins/hello-world/public/app.jsx`, `coreplugins/hello-world/public/app.scss`, `coreplugins/hello-world/public/main.js`, `coreplugins/hello-world/templates/hello.html`, `coreplugins/measure/volume.py`, `coreplugins/objdetect/api.py`, `coreplugins/osm-quickedit/public/main.js`, `docker-compose.nodeodm.yml`, `docs/.gitignore`, `docs/CNAME`, `docs/README.md`, `docs/astro.config.mjs`, `docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md`, `docs/examples/process_images.py`, `docs/examples/status_codes.py`, `docs/package-lock.json`, `docs/package.json`, `docs/public/favicon.svg`, `docs/src/assets/favicon.svg`, `docs/src/assets/logo.svg`, `docs/src/content.config.ts`, `docs/src/content/docs/architecture.md`, `docs/src/content/docs/common-tasks.md`, `docs/src/content/docs/contributing.md`, `docs/src/content/docs/faq.md`, `docs/src/content/docs/hardware-requirements.md`, `docs/src/content/docs/index.mdx`, `docs/src/content/docs/installation.md`, `docs/src/content/docs/plugin-development-guide.md`, `docs/src/content/docs/quickstart.md`, `docs/src/content/docs/reference/admin.md`, `docs/src/content/docs/reference/authentication.md`, `docs/src/content/docs/reference/handlingerrors.md`, `docs/src/content/docs/reference/permissions.md`, `docs/src/content/docs/reference/processingnode.md`, `docs/src/content/docs/reference/project.md`, `docs/src/content/docs/reference/task.md`, `docs/src/content/docs/roadmap.md`, `docs/src/content/docs/support-the-project.md`, `docs/src/styles/custom.css`, `docs/tsconfig.json`, `nginx/crontab`, `nginx/logrotate-nginx`, `nginx/nginx-ssl.conf.template`, `package.json`, `requirements.txt`, `slate/.github/ISSUE_TEMPLATE.md`, `slate/.github/PULL_REQUEST_TEMPLATE.md`, `slate/.gitignore`, `slate/.travis.yml`, `slate/CHANGELOG.md`, `slate/Dockerfile`, `slate/Gemfile`, `slate/Gemfile.lock`, `slate/LICENSE`, `slate/README.md`, `slate/Vagrantfile`, `slate/config.rb`, `slate/deploy.sh`, `slate/diagrams/README.md`, `slate/diagrams/WebODM.xml`, `slate/font-selection.json`, `slate/lib/multilang.rb`, `slate/run_server.bat`, `slate/source/fonts/slate.eot`, `slate/source/fonts/slate.svg`, `slate/source/fonts/slate.ttf`, `slate/source/fonts/slate.woff`, `slate/source/fonts/slate.woff2`, `slate/source/images/logo.png`, `slate/source/images/navbar.png`, `slate/source/includes/_introduction.md`, `slate/source/index.html.md`, `slate/source/javascripts/all.js`, `slate/source/javascripts/all_nosearch.js`, `slate/source/javascripts/app/_lang.js`, `slate/source/javascripts/app/_search.js`, `slate/source/javascripts/app/_toc.js`, `slate/source/javascripts/lib/_energize.js`, `slate/source/javascripts/lib/_imagesloaded.min.js`, `slate/source/javascripts/lib/_jquery.highlight.js`, `slate/source/javascripts/lib/_jquery.js`, `slate/source/javascripts/lib/_jquery.tocify.js`, `slate/source/javascripts/lib/_jquery_ui.js`, `slate/source/javascripts/lib/_lunr.js`, `slate/source/layouts/layout.erb`, `slate/source/stylesheets/_icon-font.scss`, `slate/source/stylesheets/_normalize.scss`, `slate/source/stylesheets/_variables.scss`, `slate/source/stylesheets/print.css.scss`, `slate/source/stylesheets/screen.css.scss`, `start.sh`, `webodm.sh`, `webodm/settings.py`, `worker/celery.py`, `worker/tasks.py`.

## 40023433 — docs: record WebODM upgrade validation

- Date: 2026-10-05; type: non-merge.
- Evidence: [40023433361102d49ce72f37aab3c7c47803db69](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40023433361102d49ce72f37aab3c7c47803db69).
- Catalog: [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md`.

## b060790e — test: stabilize WebODM upgrade coverage

- Date: 2026-10-05; type: non-merge.
- Evidence: [b060790ef31a5f5a5396090764552b594b425288](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b060790ef31a5f5a5396090764552b594b425288).
- Catalog: [AUTH-02](2026-10-27-webodm-customization-inventory.md#auth-02), [DATA-03](2026-10-27-webodm-customization-inventory.md#data-03), [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `app/tests/test_api_task_import.py`, `app/tests/test_task_wkt.py`, `docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md`.

## 3f957889 — test: make local ODM stack resilient

- Date: 2026-10-05; type: non-merge.
- Evidence: [3f95788942d49259de1ff210d1295292a6d1c98b](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f95788942d49259de1ff210d1295292a6d1c98b).
- Catalog: [DEV-01](2026-10-27-webodm-customization-inventory.md#dev-01), [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `local-dev/docker-compose.local.yml`, `local-dev/up.sh`.

## 8fe74e8b — build: use available WebODM locale revision

- Date: 2026-10-05; type: non-merge.
- Evidence: [8fe74e8b5bd7353982c3b142d5f208ef424a1501](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8fe74e8b5bd7353982c3b142d5f208ef424a1501).
- Catalog: [BUILD-01](2026-10-27-webodm-customization-inventory.md#build-01), [UPGRADE-01](2026-10-27-webodm-customization-inventory.md#upgrade-01). Basis: explicit evidence reference.
- Changed paths: `locale`.

## Net path differences from cached upstream

These are committed differences at the recorded HEAD, including additions, deletions, submodule pins, and renamed migrations. Net differences omit custom history that was later reverted; the ledger above retains that history. Sensitive artifact names are listed for completeness, without their contents.

- A: `.claude/rules/openwolf.md`
- A: `.claude/settings.json`
- M: `.dockerignore`
- D: `.env`
- A: `.env.sample`
- D: `.github/workflows/build-and-publish.yml`
- D: `.github/workflows/test-docker.yml`
- M: `.gitignore`
- A: `.wolf/OPENWOLF.md`
- A: `.wolf/anatomy.md`
- A: `.wolf/buglog.json`
- A: `.wolf/cerebrum.md`
- A: `.wolf/config.json`
- A: `.wolf/cron-manifest.json`
- A: `.wolf/cron-state.json`
- A: `.wolf/designqc-report.json`
- A: `.wolf/hooks/_session.json`
- A: `.wolf/hooks/package.json`
- A: `.wolf/hooks/post-read.js`
- A: `.wolf/hooks/post-write.js`
- A: `.wolf/hooks/pre-read.js`
- A: `.wolf/hooks/pre-write.js`
- A: `.wolf/hooks/session-start.js`
- A: `.wolf/hooks/shared.js`
- A: `.wolf/hooks/stop.js`
- A: `.wolf/identity.md`
- A: `.wolf/memory.md`
- A: `.wolf/reframe-frameworks.md`
- A: `.wolf/suggestions.json`
- A: `.wolf/token-ledger.json`
- A: `CLAUDE.md`
- A: `DEPLOYMENT_INSTRUCTIONS.md`
- A: `DOCKER_DEPLOYMENT.md`
- M: `Dockerfile`
- M: `README.md`
- A: `TAPIS_OAUTH2_INTEGRATION.md`
- A: `TAPIS_STORAGE_INTEGRATION.md`
- M: `app/admin.py`
- M: `app/api/authentication.py`
- A: `app/api/permissions.py`
- M: `app/api/projects.py`
- A: `app/api/tapis_oauth2.py`
- A: `app/api/tapis_preferences.py`
- A: `app/api/tapis_storage.py`
- A: `app/api/tas_allocations.py`
- M: `app/api/tasks.py`
- M: `app/api/tiler.py`
- M: `app/api/urls.py`
- A: `app/auth/tapis_oauth2.py`
- M: `app/boot.py`
- A: `app/contexts/tapis.py`
- A: `app/localdev.py`
- A: `app/management/__init__.py`
- A: `app/management/commands/__init__.py`
- A: `app/management/commands/discover_tapis_flights.py`
- A: `app/management/commands/wait_for_db.py`
- A: `app/migrations/0002_tapis_oauth2_models.py`
- A: `app/migrations/0045_merge_20250910_1747.py`
- A: `app/migrations/0046_auto_20250910_1902.py`
- A: `app/migrations/0047_task_ckan_url.py`
- R090: `app/migrations/0045_profile_cluster_id.py` → `app/migrations/0048_profile_cluster_id.py`
- R096: `app/migrations/0046_redirect.py` → `app/migrations/0049_redirect.py`
- R093: `app/migrations/0047_task_wkt.py` → `app/migrations/0050_task_wkt.py`
- M: `app/models/__init__.py`
- A: `app/models/oauth2.py`
- A: `app/models/tapis_preferences.py`
- M: `app/models/task.py`
- A: `app/services/tapis_storage.py`
- A: `app/services/tas_allocations.py`
- M: `app/static/app/js/ModelView.jsx`
- M: `app/static/app/js/classes/PresetUtils.js`
- A: `app/static/app/js/classes/TapisTokenManager.js`
- M: `app/static/app/js/classes/plugins/API.js`
- A: `app/static/app/js/classes/plugins/Model.js`
- M: `app/static/app/js/components/EditPresetDialog.jsx`
- M: `app/static/app/js/components/EditTaskForm.jsx`
- M: `app/static/app/js/components/ImportTaskPanel.jsx`
- M: `app/static/app/js/components/LayersControlLayer.jsx`
- M: `app/static/app/js/components/Map.jsx`
- M: `app/static/app/js/components/ProcessingNodeOption.jsx`
- M: `app/static/app/js/components/ProjectListItem.jsx`
- M: `app/static/app/js/components/TaskListItem.jsx`
- A: `app/static/app/js/components/TemporaryMapLayerDialog.jsx`
- M: `app/static/app/js/components/tests/EditTaskForm.test.jsx`
- M: `app/static/app/js/components/tests/LayersControlLayer.test.jsx`
- A: `app/static/app/js/components/tests/ProjectListItem.directoryUpload.test.jsx`
- A: `app/static/app/js/components/tests/TemporaryMapLayerDialog.test.jsx`
- M: `app/static/app/js/css/Map.scss`
- M: `app/static/app/js/css/TaskListItem.scss`
- M: `app/static/app/js/main.jsx`
- A: `app/static/app/js/tests/TapisTokenManager.test.js`
- A: `app/tasks/tapis_storage.py`
- M: `app/templates/app/3d_model_js.html`
- M: `app/templates/app/base.html`
- A: `app/templates/app/clusterodm_redirect.html`
- M: `app/templates/app/logged_in_base.html`
- M: `app/templates/app/registration/login.html`
- A: `app/templates/app/registration/tapis_login.html`
- M: `app/templatetags/settings.py`
- A: `app/templatetags/tapis_tags.py`
- M: `app/tests/test_api_task_import.py`
- M: `app/tests/test_app.py`
- A: `app/tests/test_ckan_plugin.py`
- A: `app/tests/test_clusterodm_admin.py`
- A: `app/tests/test_tapis_oauth2_tokens.py`
- A: `app/tests/test_tas_allocations.py`
- M: `app/tests/test_task_wkt.py`
- M: `app/urls.py`
- M: `app/views/app.py`
- A: `app/views/tapis_auth.py`
- A: `connect_clusterodm.sh`
- A: `cookies.txt`
- A: `coreplugins/ckan/README.md`
- A: `coreplugins/ckan/__init__.py`
- A: `coreplugins/ckan/api_views.py`
- A: `coreplugins/ckan/manifest.json`
- A: `coreplugins/ckan/plugin.py`
- A: `coreplugins/ckan/public/CKANPublishPanel.jsx`
- A: `coreplugins/ckan/public/build/CKANPublishPanel.js`
- A: `coreplugins/ckan/public/build/CKANPublishPanel.js.LICENSE.txt`
- A: `coreplugins/ckan/publisher.py`
- A: `coreplugins/ckan/templates/load_buttons.js`
- A: `coreplugins/embeddings/__init__.py`
- A: `coreplugins/embeddings/api_views.py`
- A: `coreplugins/embeddings/embeddings_client.py`
- A: `coreplugins/embeddings/label_studio_client.py`
- A: `coreplugins/embeddings/manifest.json`
- A: `coreplugins/embeddings/plugin.py`
- A: `coreplugins/embeddings/public/EmbeddingsPanel.jsx`
- A: `coreplugins/embeddings/public/build/EmbeddingsPanel.js`
- A: `coreplugins/embeddings/public/build/EmbeddingsPanel.js.LICENSE.txt`
- A: `coreplugins/embeddings/public/tileMath.js`
- A: `coreplugins/embeddings/public/webpack.config.js`
- A: `coreplugins/embeddings/templates/index.html`
- A: `coreplugins/embeddings/templates/load_buttons.js`
- A: `coreplugins/embeddings/templates/model_diagnostics.html`
- A: `coreplugins/embeddings/tests.py`
- A: `coreplugins/embeddings/tile_math.py`
- A: `coreplugins/embeddings/views.py`
- A: `coreplugins/upstream/__init__.py`
- A: `coreplugins/upstream/api.py`
- A: `coreplugins/upstream/manifest.json`
- A: `coreplugins/upstream/plugin.py`
- A: `coreplugins/upstream/public/app.jsx`
- A: `coreplugins/upstream/public/app.scss`
- A: `coreplugins/upstream/public/build/app.css`
- A: `coreplugins/upstream/public/build/app.js`
- A: `coreplugins/upstream/public/build/model.js`
- A: `coreplugins/upstream/public/build/model.js.LICENSE.txt`
- A: `coreplugins/upstream/public/main.js`
- A: `coreplugins/upstream/public/model.jsx`
- A: `coreplugins/upstream/public/package.json`
- M: `db/Dockerfile`
- A: `debug_clusterodm.py`
- M: `docker-compose.build.yml`
- M: `docker-compose.dev.yml`
- M: `docker-compose.yml`
- A: `docs/design/2026-07-08-publish-to-ckan.md`
- A: `docs/design/2026-07-22-geospatial-embeddings-classification.md`
- A: `docs/design/2026-08-28-tapis-jwt-expiry-logout.md`
- A: `docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md`
- A: `fix_clusterodm.py`
- A: `local-dev/.gitignore`
- A: `local-dev/README.md`
- A: `local-dev/docker-compose.local.yml`
- A: `local-dev/down.sh`
- A: `local-dev/install-hosts.sh`
- A: `local-dev/logs.sh`
- A: `local-dev/restart-nodeodm-smoke.py`
- A: `local-dev/up.sh`
- A: `local-dev/webodm.env`
- M: `locale`
- M: `nginx/nginx.conf.template`
- A: `nginx/ssl.disabled/cert.pem`
- A: `nginx/ssl.disabled/key.pem`
- M: `nodeodm/external/NodeODM`
- A: `nodeodm/jwt_node_wrapper.py`
- M: `nodeodm/models.py`
- M: `nodeodm/tests.py`
- M: `package.json`
- M: `requirements.txt`
- A: `scripts/backup-ctl.sh`
- A: `scripts/entrypoint-tapis.sh`
- A: `scripts/setup_tapis_oauth2.py`
- A: `setup.sh`
- A: `setup_tapis_oauth2.py`
- A: `ssl/cert.pem`
- A: `ssl/key.pem`
- M: `start.sh`
- M: `webodm.sh`
- M: `webodm/settings.py`
- M: `webodm/urls.py`
- M: `worker.sh`
- M: `worker/__init__.py`
- M: `worker/celery.py`
- M: `worker/tasks.py`
