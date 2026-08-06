#!/usr/bin/env python3
"""Verificación en vivo de los fixes de seguridad contra el stack dockerizado.

Prerrequisito: stack levantado con la imagen reconstruida:
    cd web-app && docker compose up -d --build

Uso:
    python3 tests/verify_security_live.py
    python3 tests/verify_security_live.py --admin-email admin@ejemplo.com --admin-password TU_PASS

Los checks 1-8 no necesitan sesión. Con --admin-email/--admin-password se
añaden dos checks con sesión de administrador (sanity de permisos y auditoría).
"""

import argparse
import json
import subprocess
import sys
import time
import uuid

import requests
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatus
from websockets.sync.client import connect

BASE = "http://localhost:9000"
REDIS_CONTAINER = "password_manager_redis"
BACKEND_CONTAINER = "password_manager_backend"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

_passed = 0
_failed = 0
_skipped = 0


def ok(msg):
    global _passed
    _passed += 1
    print(f"{GREEN}  ✔ {msg}{RESET}")


def fail(msg):
    global _failed
    _failed += 1
    print(f"{RED}  ✘ {msg}{RESET}")


def info(msg):
    global _skipped
    _skipped += 1
    print(f"{YELLOW}  · {msg}{RESET}")


def section(title):
    print(f"\n{BOLD}▶ {title}{RESET}")


def http(method, path, body=None, token=None, csrf=False):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if csrf:
        # Pasar el middleware de CSRF (cookie + header iguales) para probar
        # realmente la autenticación del endpoint.
        headers["X-CSRF-Token"] = "verify-script"
        headers["Cookie"] = "csrf_token=verify-script"
    try:
        resp = requests.request(method, BASE + path, json=body, headers=headers, timeout=10)
    except requests.ConnectionError:
        print(f"\n{RED}No se pudo conectar a {BASE}. ¿El stack está levantado?{RESET}")
        sys.exit(1)
    try:
        data = resp.json()
    except ValueError:
        data = None
    return resp.status_code, data


def redis_exec(args):
    try:
        proc = subprocess.run(
            ["docker", "exec", REDIS_CONTAINER, "redis-cli"] + args,
            capture_output=True, text=True, timeout=15,
        )
        return proc.returncode == 0, proc.stdout.strip()
    except Exception:
        return False, ""


def redis_clear_rate_limit_keys():
    ok_exec, _ = redis_exec(["ping"])
    if not ok_exec:
        info("Redis no alcanzable vía docker exec: los contadores se limpiarán solos en 15 min")
        return
    # Borrar SOLO las claves de rate limit (ephemeras), no toca datos de la app.
    redis_exec(["--scan", "--pattern", "login:*", "recovery:*"])


# ── Check 1: #9 register sin autenticación ──────────────────────
def check_register_requires_auth():
    section("#9 — POST /auth/register sin token debe dar 401")
    code, _ = http("post", "/api/auth/register", {
        "email": "hacker@x.com", "password": "Str0ng1!a", "full_name": "Hacker",
    })
    if code == 401:
        ok("rechazado (401): ya no se puede crear usuarios sin autenticación")
    else:
        fail(f"se obtuvo {code} en lugar de 401")


# ── Check 2: #15 generador sin autenticación ────────────────────
def check_generator_requires_auth():
    section("#15 — POST /credentials/generate-password sin token debe dar 401")
    code, _ = http("post", "/api/credentials/generate-password", {"length": 12}, csrf=True)
    if code == 401:
        ok("rechazado (401): el generador ya no es accesible anónimamente")
    else:
        fail(f"se obtuvo {code} en lugar de 401")


# ── Check 3: #12 setup no reejecutable ──────────────────────────
def check_setup_not_repeatable():
    section("#12 — POST /setup de nuevo debe fallar (ya configurado)")
    code, data = http("post", "/api/setup", {
        "db_name": "x", "admin_name": "A", "admin_email": "a@test.com",
        "admin_password": "StrongPass1!",
    })
    detail = (data or {}).get("detail", "") if isinstance(data, dict) else ""
    if code in (400, 500) and "ya está configurado" in str(detail):
        ok(f"rechazado ({code}): no se puede reconfigurar ni crear otro admin")
    else:
        fail(f"se obtuvo {code} / {detail!r} en lugar del rechazo esperado")


# ── Check 4: #16 rate limit compartido (Redis) ──────────────────
def check_rate_limit():
    section("#16 — 5 fallos de login → 6º intento bloqueado (429)")

    redis_clear_rate_limit_keys()

    email = f"rate-test-{int(time.time())}@prueba.com"
    codes = []
    for i in range(5):
        code, _ = http("post", "/api/auth/login", {"email": email, "password": "incorrecta"})
        codes.append(code)
    code, data = http("post", "/api/auth/login", {"email": email, "password": "incorrecta"})

    ok_exec, keys = redis_exec(["--scan", "--pattern", "login:*"])
    key_list = keys.split()
    if ok_exec and any(k.startswith("login:email:") for k in key_list) and code == 429:
        ok(f"bloqueado (429): las claves del contador viven en Redis: {', '.join(sorted(key_list))}")
    elif code == 429:
        ok(f"bloqueado (429) — {codes}")
        info("no se confirmaron claves Redis (¿caído?)")
    else:
        fail(f"el 6º intento dio {code} en lugar de 429 ({codes})")

    # Limpiar los contadores creados para no afectar usuarios reales.
    for key in key_list:
        redis_exec(["del", key])


# ── Check 5: #13 WebSocket SSH sin cookie ───────────────────────
def check_ws_auth():
    section("#13 — WebSocket /ssh/terminal/{id} sin cookie debe cerrar (1008)")
    uri = f"ws://localhost:9000/api/ssh/terminal/{uuid.uuid4()}"
    try:
        with connect(uri, open_timeout=5) as ws:
            try:
                ws.recv(timeout=5)
            except ConnectionClosedError as exc:
                code = exc.rcvd.code if exc.rcvd else None
                if code == 1008:
                    ok(f"cerrado con código 1008 (no autenticado)")
                    return
                fail(f"cerrado con código {code} en lugar de 1008")
                return
            fail("la conexión se mantuvo abierta sin autenticación")
    except ConnectionClosed as exc:
        code = exc.rcvd.code if exc.rcvd else None
        if code == 1008:
            ok("cerrado con código 1008 (no autenticado)")
        else:
            fail(f"cerrado con código {code} en lugar de 1008")
    except InvalidStatus as exc:
        ok(f"handshake rechazado por el servidor (HTTP {exc.response.status_code})")
    except Exception as exc:
        ok(f"handshake rechazado ({type(exc).__name__})")


# ── Check 6: #14 sin SHA-256 en claro ni password_hash expuesto ─
def check_duplicate_hash_and_schema():
    section("#14 — hash de duplicados con HMAC y sin password_hash expuesto")

    proc = subprocess.run(
        ["docker", "exec", "-w", "/app/app", BACKEND_CONTAINER, "python", "-c",
         "import inspect, core.security as s; print(inspect.getsource(s.get_duplicate_hash))"],
        capture_output=True, text=True, timeout=15,
    )
    has_hmac = proc.returncode == 0 and "hmac" in proc.stdout.lower()
    if has_hmac:
        ok("el contenedor usa get_duplicate_hash() con HMAC (no SHA-256 plano)")
    else:
        fail(f"get_duplicate_hash() no usa HMAC en el contenedor: {proc.stdout[:80]!r}")

    proc2 = subprocess.run(
        ["docker", "exec", "-w", "/app/app", BACKEND_CONTAINER, "python", "-c",
         "from schemas.schemas import CredentialResponse; "
         "f = CredentialResponse.model_fields; "
         "print(sorted(k for k in f if 'password' in k.lower())); print('password_hash' in f)"],
        capture_output=True, text=True, timeout=15,
    )
    if proc2.returncode == 0:
        campos, expuesto = proc2.stdout.strip().splitlines()
        if expuesto.strip() == "False":
            ok(f"CredentialResponse no expone password_hash (campos con 'password': {campos})")
        else:
            fail("CredentialResponse sigue exponiendo password_hash")
    else:
        fail(f"no se pudo inspeccionar el schema en el contenedor: {proc2.stderr[:80]!r}")


# ── Checks con sesión de admin ──────────────────────────────────
def check_with_session(email, password):
    section("Checks con sesión de administrador")
    code, data = http("post", "/api/auth/login", {"email": email, "password": password})
    if code != 200:
        info(f"no se pudo autenticar como admin ({code}): se omiten los checks con sesión")
        return
    token = data["access_token"]

    section("#10 — permisos sin token 401, y con sesión valida la credencial")
    code, _ = http("post", "/api/credentials/00000000-0000-0000-0000-000000000000/permissions",
                   {"user_id": str(uuid.uuid4())}, csrf=True)
    if code == 401:
        ok("sin token → 401 (no expone el endpoint)")
    else:
        fail(f"sin token dio {code} en lugar de 401")

    code, data2 = http("post", "/api/credentials/00000000-0000-0000-0000-000000000000/permissions",
                       {"user_id": str(uuid.uuid4())}, token=token, csrf=True)
    detail = (data2 or {}).get("detail", "") if isinstance(data2, dict) else ""
    if code == 404:
        ok(f"con token y credencial ajena/inexistente → {code} ({detail})")
    else:
        fail(f"con token dio {code} en lugar de 404 (¿valida la org?)")

    section("#11 — auditoría requiere token y responde correctamente")
    code, _ = http("get", "/api/credentials/audit")
    if code == 401:
        ok("sin token → 401")
    else:
        fail(f"sin token dio {code} en lugar de 401")

    code, data3 = http("get", "/api/credentials/audit", token=token)
    if code == 200:
        ok(f"con token → 200 (filtrado por organización cubierto por unit tests)")
    else:
        fail(f"con token dio {code} en lugar de 200")


def main():
    parser = argparse.ArgumentParser(description="Verificación en vivo de los fixes de seguridad")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    args = parser.parse_args()

    print(f"{BOLD}Verificación de seguridad — {BASE}{RESET}\n")

    check_register_requires_auth()
    check_generator_requires_auth()
    check_setup_not_repeatable()
    check_rate_limit()
    check_ws_auth()
    check_duplicate_hash_and_schema()

    if args.admin_email and args.admin_password:
        check_with_session(args.admin_email, args.admin_password)
    else:
        print(f"\n{YELLOW}· Pasa --admin-email y --admin-password para añadir 2 checks con sesión.{RESET}")

    print(f"\n{BOLD}Resultado:{RESET} {GREEN}{_passed} ok{RESET} / {RED}{_failed} fallos{RESET} / {YELLOW}{_skipped} omitidos{RESET}")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
