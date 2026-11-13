"""
Logs into the Vivosun cloud API, pulls the GrowCam's LAN RTSP credentials
(plaintext in setting.jf.devUser / devPass on the device-list response),
and pushes the resulting RTSP source into a running go2rtc server via
its dynamic stream API. Runs once per REFRESH_INTERVAL_SECONDS, forever.

No credentials are ever printed. Configure everything via environment
variables (see ../.env).
"""
import base64
import json
import os
import time
import uuid
import urllib.request
import urllib.error
from urllib.parse import quote, urlencode

VIVOSUN_BASE = "https://api-prod.next.vivosun.com"
LOGIN_PATH = "/user/login"
DEVICE_LIST_PATH = "/iot/device/getTotalList"

BASE_HEADERS = {
    "Content-Type": "application/json",
    "Server-Platform": "android",
    "Api-Version": "1.0.5",
    "App-Version": "4.72.0",
}


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and v is None:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def vivosun_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(VIVOSUN_BASE + path, data=data, headers=BASE_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def vivosun_get(path, headers):
    h = dict(BASE_HEADERS)
    h.update(headers)
    req = urllib.request.Request(VIVOSUN_BASE + path, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def vivosun_login(email, password):
    payload = {
        "email": email,
        "password": password,
        "spAppId": "com.vivosun.android",
        "spClientId": str(uuid.uuid4()),
        "spSessionId": str(uuid.uuid4()),
    }
    resp = vivosun_post(LOGIN_PATH, payload)
    if not resp.get("success"):
        raise RuntimeError(f"Vivosun login failed: {resp.get('message')}")
    data = resp["data"]
    return {"login-token": data["loginToken"], "access-token": data["accessToken"]}


def get_camera_credentials(tokens, name_match):
    resp = vivosun_get(DEVICE_LIST_PATH, tokens)
    if not resp.get("success"):
        raise RuntimeError(f"getTotalList failed: {resp.get('message')}")
    device_group = resp["data"].get("deviceGroup", {})
    for devices in device_group.values():
        if not isinstance(devices, list):
            continue
        for dev in devices:
            if name_match.lower() not in (dev.get("name") or "").lower():
                continue
            jf = (dev.get("setting") or {}).get("jf") or {}
            user, pwd = jf.get("devUser"), jf.get("devPass")
            if user and pwd:
                return user, pwd
    raise RuntimeError(f"No device matching '{name_match}' with devUser/devPass found")


def _go2rtc_request(url, method, api_user, api_pass):
    req = urllib.request.Request(url, method=method)
    if api_user and api_pass:
        token = base64.b64encode(f"{api_user}:{api_pass}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    return req


def go2rtc_upsert_stream(api_base, api_user, api_pass, stream_name, rtsp_source):
    """PUT /api/streams?name=X&src=Y adds/replaces a source on stream X."""
    query = urlencode({"name": stream_name, "src": rtsp_source})
    req = _go2rtc_request(f"{api_base}/api/streams?{query}", "PUT", api_user, api_pass)
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def go2rtc_stream_exists(api_base, api_user, api_pass, stream_name):
    """True if go2rtc currently knows the stream (it is lost on Frigate/go2rtc restart)."""
    req = _go2rtc_request(f"{api_base}/api/streams", "GET", api_user, api_pass)
    with urllib.request.urlopen(req, timeout=10) as resp:
        streams = json.loads(resp.read().decode())
    return stream_name in streams


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def push_to_targets(targets, api_user, api_pass, stream_name):
    """Log in once, then update the stream on every given go2rtc/Frigate target.
    Returns the set of targets that were updated successfully."""
    email = env("VIVOSUN_EMAIL", required=True)
    password = env("VIVOSUN_PASSWORD", required=True)
    name_match = env("CAMERA_NAME_MATCH", "GrowCam")
    camera_ip = env("CAMERA_IP", required=True)
    rtsp_path = env("CAMERA_RTSP_PATH", "/")  # e.g. /cam/realmonitor?channel=1&subtype=0

    tokens = vivosun_login(email, password)
    user, pwd = get_camera_credentials(tokens, name_match)
    rtsp_source = f"rtsp://{quote(user, safe='')}:{quote(pwd, safe='')}@{camera_ip}:554{rtsp_path}"

    ok = set()
    for target in targets:
        try:
            go2rtc_upsert_stream(target, api_user, api_pass, stream_name, rtsp_source)
            ok.add(target)
            log(f"OK - stream '{stream_name}' updated on {target} "
                f"(camera_ip={camera_ip}, user-len={len(user)}, pass-len={len(pwd)})")
        except Exception as e:
            log(f"ERROR: {target}: {e}")
    return ok


def main():
    interval = int(env("REFRESH_INTERVAL_SECONDS", "21600"))  # full refresh, 6h default
    check = int(env("CHECK_INTERVAL_SECONDS", "60"))  # cheap "is the stream still there?" check
    # One or more targets, comma-separated, e.g. http://go2rtc:1984,http://frigate:1984
    targets = [t.strip().rstrip("/") for t in env("GO2RTC_API_URL", "http://go2rtc:1984").split(",") if t.strip()]
    stream_name = env("STREAM_NAME", "growcam")
    api_user = env("STREAM_VIEW_USER")
    api_pass = env("STREAM_VIEW_PASS")

    last_push = {t: 0.0 for t in targets}
    while True:
        due = []
        for t in targets:
            if time.time() - last_push[t] >= interval:
                due.append(t)
                continue
            try:
                # go2rtc/Frigate restart wipes API-created streams -> push again right away
                if not go2rtc_stream_exists(t, api_user, api_pass, stream_name):
                    due.append(t)
            except Exception as e:
                log(f"ERROR: {t}: {e}")
        if due:
            try:
                for t in push_to_targets(due, api_user, api_pass, stream_name):
                    last_push[t] = time.time()
            except Exception as e:
                log(f"ERROR: {e}")
        time.sleep(check)


if __name__ == "__main__":
    main()
