#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEBODM_ROOT = ROOT.parent
SUITE_ROOT = WEBODM_ROOT.parent
CLUSTERODM_IMAGES_DIR = SUITE_ROOT / "ClusterODM" / "testData" / "images"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker-compose.local.yml")]
DEFAULT_STAGE_MARKERS = [
    "opensfm",
    "openmvs",
    "odm_meshing",
    "mvs_texturing",
    "odm_georeferencing",
    "odm_dem",
    "odm_orthophoto",
]
LOW_MEMORY_RESIZE_TO = 2048
LOW_MEMORY_OPTIONS = [
    ("max-concurrency", "4"),
    ("min-num-features", "4000"),
    ("feature-quality", "low"),
    ("pc-quality", "low"),
    ("mesh-size", "50000"),
    ("orthophoto-resolution", "10"),
    ("dem-resolution", "10"),
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


def compose(*args, capture=False, check=True):
    kwargs = {
        "cwd": str(ROOT),
        "text": True,
    }
    if capture:
        kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT})

    result = subprocess.run(COMPOSE + list(args), **kwargs)
    if check and result.returncode != 0:
        output = result.stdout if capture else ""
        raise RuntimeError("docker compose {} failed\n{}".format(" ".join(args), output))
    return result


def wait_for_compose_probe(args, label, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = compose(*args, capture=True, check=False)
        if result.returncode == 0:
            return
        time.sleep(3)
    raise RuntimeError("{} did not become ready within {} seconds".format(label, timeout))


def encode_multipart(fields, files):
    boundary = "----webodm-local-dev-{}".format(uuid.uuid4().hex)
    body = bytearray()

    for name, value in fields.items():
        body.extend(("--{}\r\n".format(boundary)).encode("utf-8"))
        body.extend(('Content-Disposition: form-data; name="{}"\r\n\r\n'.format(name)).encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for name, path in files:
        path = Path(path)
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body.extend(("--{}\r\n".format(boundary)).encode("utf-8"))
        body.extend(
            (
                'Content-Disposition: form-data; name="{}"; filename="{}"\r\n'
                "Content-Type: {}\r\n\r\n"
            ).format(name, path.name, content_type).encode("utf-8")
        )
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    body.extend(("--{}--\r\n".format(boundary)).encode("utf-8"))
    return bytes(body), "multipart/form-data; boundary={}".format(boundary)


def api_request(base_url, method, path, data=None, files=None, timeout=30):
    url = base_url.rstrip("/") + path
    headers = {}
    body = None

    if files:
        body, content_type = encode_multipart(data or {}, files)
        headers["Content-Type"] = content_type
    elif data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        response_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError("{} {} failed with HTTP {}:\n{}".format(method, url, e.code, response_body))

    if "application/json" in content_type:
        return json.loads(response_body)
    return response_body


def wait_for_webodm(base_url, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            api_request(base_url, "GET", "/api/", timeout=5)
            return
        except Exception:
            time.sleep(3)
    raise RuntimeError("WebODM API did not become ready within {} seconds".format(timeout))


def assert_local_auth_enabled():
    result = compose(
        "exec",
        "-T",
        "webapp",
        "python",
        "manage.py",
        "shell",
        "-c",
        "from webodm import settings; print(settings.LOCAL_DEV_SKIP_AUTH)",
        capture=True,
    )
    if not result.stdout.rstrip().endswith("True"):
        raise RuntimeError(
            "WO_LOCAL_DEV_SKIP_AUTH is not active in the webapp container. "
            "Run ./up.sh after rebuilding the local-dev stack."
        )


def register_processing_node():
    compose("exec", "-T", "webapp", "python", "manage.py", "addnode", "clusterodm", "3000", "--label", "clusterodm-local")


def restart_nodeodm(stop_seconds, timeout):
    print("Stopping NodeODM")
    compose("stop", "node-odm")
    time.sleep(stop_seconds)

    print("Starting NodeODM")
    compose("start", "node-odm")
    wait_for_compose_probe(
        ("exec", "-T", "clusterodm", "curl", "-fsS", "http://node-odm:3000/info"),
        "NodeODM",
        timeout,
    )
    wait_for_compose_probe(
        ("exec", "-T", "webapp", "curl", "-fsS", "http://clusterodm:3000/info"),
        "ClusterODM",
        timeout,
    )


def create_project(base_url):
    project = api_request(
        base_url,
        "POST",
        "/api/projects/",
        {
            "name": "Local NodeODM Restart Smoke {}".format(uuid.uuid4().hex[:8]),
            "description": "Local auth-bypass restart smoke test",
        },
    )
    print("Created project {}".format(project["id"]))
    return project["id"]


def parse_odm_option(option):
    if "=" not in option:
        raise RuntimeError("Invalid ODM option '{}'. Use name=value.".format(option))
    name, value = option.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not name or not value:
        raise RuntimeError("Invalid ODM option '{}'. Use name=value.".format(option))
    return name, value


def build_task_fields(iteration, options, resize_to):
    fields = {"name": "nodeodm restart smoke {}".format(iteration)}
    if options:
        fields["options"] = json.dumps([{"name": name, "value": value} for name, value in options])
    if resize_to:
        fields["resize_to"] = str(resize_to)
    return fields


def submit_task(base_url, project_id, iteration, images, options, resize_to):
    task = api_request(
        base_url,
        "POST",
        "/api/projects/{}/tasks/".format(project_id),
        data=build_task_fields(iteration, options, resize_to),
        files=[("images", image) for image in images],
        timeout=120,
    )
    print("Created task {}".format(task["id"]))
    return task["id"]


def get_task(base_url, project_id, task_id):
    return api_request(base_url, "GET", "/api/projects/{}/tasks/{}/".format(project_id, task_id), timeout=15)


def wait_for_task_routing(base_url, project_id, task_id, timeout):
    deadline = time.time() + timeout
    last = None

    while time.time() < deadline:
        task = get_task(base_url, project_id, task_id)
        last = task
        print(
            "Task {} status={} node={} uuid={} error={}".format(
                task_id,
                task.get("status"),
                task.get("processing_node"),
                task.get("uuid") or "",
                task.get("last_error") or "",
            )
        )

        if task.get("uuid"):
            return task
        if task.get("last_error"):
            raise RuntimeError("Task {} failed before routing: {}".format(task_id, task["last_error"]))

        time.sleep(5)

    raise RuntimeError("Task {} did not receive a NodeODM UUID. Last state: {}".format(task_id, last))


def get_task_output_lines(base_url, project_id, task_id, start_line):
    output = api_request(
        base_url,
        "GET",
        "/api/projects/{}/tasks/{}/output?line={}&f=raw".format(project_id, task_id, start_line),
        timeout=30,
    )
    if not output:
        return []
    return output.splitlines()


def restart_task(base_url, project_id, task_id):
    api_request(base_url, "POST", "/api/projects/{}/tasks/{}/restart/".format(project_id, task_id), timeout=30)
    print("Restart requested for task {}".format(task_id))


def cancel_task(base_url, project_id, task_id):
    api_request(base_url, "POST", "/api/projects/{}/tasks/{}/cancel/".format(project_id, task_id), timeout=30)
    print("Cancel requested for task {}".format(task_id))


def wait_for_stage_marker(base_url, project_id, task_id, stage, trigger, timeout):
    marker = "{} {} stage".format(trigger.capitalize(), stage)
    deadline = time.time() + timeout
    line = 0
    last_task = None

    print("Waiting for stage marker: {}".format(marker))
    while time.time() < deadline:
        task = get_task(base_url, project_id, task_id)
        last_task = task

        if task.get("last_error"):
            raise RuntimeError("Task {} failed while waiting for {}: {}".format(task_id, marker, task["last_error"]))

        output_lines = get_task_output_lines(base_url, project_id, task_id, line)
        if output_lines:
            for output_line in output_lines:
                print(output_line)
                if marker in output_line:
                    return task
            line += len(output_lines)

        if task.get("status") in (30, 40, 50):
            raise RuntimeError(
                "Task {} reached terminal status {} before marker {}. Last state: {}".format(
                    task_id,
                    task.get("status"),
                    marker,
                    task,
                )
            )

        time.sleep(5)

    raise RuntimeError("Timed out waiting for {}. Last state: {}".format(marker, last_task))


def run_stage_restart_sequence(base_url, project_id, task_id, stages, trigger, stop_seconds, timeout, routing_timeout):
    task = wait_for_task_routing(base_url, project_id, task_id, routing_timeout)
    print("Task {} routed to NodeODM UUID {}".format(task_id, task["uuid"]))

    for stage in stages:
        wait_for_stage_marker(base_url, project_id, task_id, stage, trigger, timeout)
        print("Restarting NodeODM after {} {} marker".format(trigger, stage))
        restart_nodeodm(stop_seconds, timeout)
        restart_task(base_url, project_id, task_id)
        wait_for_task_routing(base_url, project_id, task_id, routing_timeout)


def default_images():
    cluster_images = sorted(CLUSTERODM_IMAGES_DIR.glob("*.JPG"))
    if cluster_images:
        return cluster_images

    return [
        WEBODM_ROOT / "app" / "fixtures" / "tiny_drone_image.jpg",
        WEBODM_ROOT / "app" / "fixtures" / "tiny_drone_image_2.jpg",
    ]


def main():
    parser = argparse.ArgumentParser(description="Submit local WebODM tasks and restart NodeODM during checkpoint stages.")
    default_webodm_url = os.environ.get(
        "WEBODM_LOCAL_DEV_URL",
        "http://webodm.local.test:{}".format(os.environ.get("LOCAL_DEV_WEBODM_PORT", "18000")),
    )
    parser.add_argument("--webodm-url", default=default_webodm_url)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--routing-timeout", type=int, default=300)
    parser.add_argument("--stop-seconds", type=int, default=5)
    parser.add_argument(
        "--profile",
        choices=("low-memory", "full"),
        default="low-memory",
        help="low-memory resizes images and lowers ODM settings for laptop Docker runs; full leaves ODM defaults unchanged.",
    )
    parser.add_argument(
        "--resize-to",
        type=int,
        default=None,
        help="Resize uploaded images to this max dimension before NodeODM processing. Defaults to 2048 for low-memory profile.",
    )
    parser.add_argument(
        "--odm-option",
        action="append",
        dest="odm_options",
        default=[],
        help="ODM option as name=value. Repeat to add or override profile options.",
    )
    parser.add_argument(
        "--restart-mode",
        choices=("stage", "between-tasks"),
        default="stage",
        help="stage restarts NodeODM at ODM stage markers; between-tasks restarts after each task is routed.",
    )
    parser.add_argument(
        "--stage-trigger",
        choices=("running", "finished"),
        default="finished",
        help="Stage log marker that triggers a NodeODM restart.",
    )
    parser.add_argument(
        "--stage",
        action="append",
        dest="stages",
        default=[],
        help="ODM stage marker to restart after. Repeat to override the default stage list.",
    )
    parser.add_argument("--keep-running", action="store_true", help="Do not cancel tasks after they receive a NodeODM UUID.")
    parser.add_argument(
        "--image-dir",
        default=None,
        help="Directory of JPG images to upload. Defaults to ClusterODM/testData/images.",
    )
    parser.add_argument(
        "--image",
        action="append",
        dest="images",
        default=[],
        help="Image path to upload. Pass at least two. Overrides --image-dir and the default 20-image fixture set.",
    )
    args = parser.parse_args()

    if args.images:
        images = [Path(image).resolve() for image in args.images]
    elif args.image_dir:
        images = sorted(Path(args.image_dir).resolve().glob("*.JPG"))
        images += sorted(Path(args.image_dir).resolve().glob("*.jpg"))
        images += sorted(Path(args.image_dir).resolve().glob("*.jpeg"))
    else:
        images = default_images()

    if len(images) < 2:
        raise RuntimeError("At least two images are required")

    for image in images:
        if not image.exists():
            raise RuntimeError("Missing image: {}".format(image))

    if args.profile == "low-memory":
        options = list(LOW_MEMORY_OPTIONS)
        resize_to = args.resize_to if args.resize_to is not None else LOW_MEMORY_RESIZE_TO
    else:
        options = []
        resize_to = args.resize_to

    option_names = {name: index for index, (name, _) in enumerate(options)}
    for raw_option in args.odm_options:
        name, value = parse_odm_option(raw_option)
        if name in option_names:
            options[option_names[name]] = (name, value)
        else:
            option_names[name] = len(options)
            options.append((name, value))

    wait_for_webodm(args.webodm_url, args.timeout)
    assert_local_auth_enabled()
    register_processing_node()

    stages = args.stages or DEFAULT_STAGE_MARKERS
    print("Using {} images".format(len(images)))
    print("First image: {}".format(images[0]))
    print("Profile: {}".format(args.profile))
    print("Resize to: {}".format(resize_to if resize_to else "disabled"))
    print("ODM options: {}".format(", ".join(["{}={}".format(name, value) for name, value in options]) or "defaults"))
    print("Routing timeout: {} seconds".format(args.routing_timeout))
    print("Restart mode: {}".format(args.restart_mode))
    if args.restart_mode == "stage":
        print("Stage trigger: {}".format(args.stage_trigger))
        print("Stages: {}".format(", ".join(stages)))

    project_id = create_project(args.webodm_url)

    for iteration in range(1, args.iterations + 1):
        print("")
        print("Iteration {}".format(iteration))
        task_id = submit_task(args.webodm_url, project_id, iteration, images, options, resize_to)

        if args.restart_mode == "stage":
            run_stage_restart_sequence(
                args.webodm_url,
                project_id,
                task_id,
                stages,
                args.stage_trigger,
                args.stop_seconds,
                args.timeout,
                args.routing_timeout,
            )
        else:
            task = wait_for_task_routing(args.webodm_url, project_id, task_id, args.routing_timeout)
            print("Task {} routed to NodeODM UUID {}".format(task_id, task["uuid"]))
            restart_nodeodm(args.stop_seconds, args.timeout)

        if not args.keep_running:
            cancel_task(args.webodm_url, project_id, task_id)

    print("")
    print("NodeODM restart smoke test completed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        sys.exit(1)
