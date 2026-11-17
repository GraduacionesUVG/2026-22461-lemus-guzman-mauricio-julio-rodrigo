from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import socket
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
RESULTS = ROOT / "resultados"
EVIDENCES = RESULTS / "11_EVIDENCIAS"
YAML_PATH = ROOT / "configuraciones" / "veltrix_commerce_completa.yaml"
QA_URL = os.getenv("QA_URL", "http://127.0.0.1:5000")
ECOM_API = os.getenv("VELTRIX_API_URL", "http://127.0.0.1:8000")
ECOM_FRONT = os.getenv("VELTRIX_FRONT_URL", "http://127.0.0.1:5350")
QA_USER = os.getenv("QA_ADMIN_EMAIL", "usuario@example.invalid")
QA_PASSWORD = os.getenv("QA_ADMIN_PASSWORD", "REEMPLAZAR_SECRETO_LOCAL")
OWNER_EMAIL = os.getenv("VELTRIX_OWNER_EMAIL", "usuario@example.invalid")
OWNER_PASSWORD = os.getenv("VELTRIX_OWNER_PASSWORD", "")


SCENARIOS = {
    "CP-01": "Autenticacion exitosa",
    "CP-02": "Autenticacion incorrecta",
    "CP-03": "Navegacion entre modulos",
    "CP-04": "Registro y consulta de producto",
    "CP-05": "Registro de venta",
    "CP-06": "Cancelacion de venta",
    "CP-07": "Consulta de catalogo publico",
    "CP-08": "Monitoreo HTTP",
    "CP-09": "Monitoreo TCP",
    "CP-10": "Deteccion de indisponibilidad",
    "CP-11": "Deteccion de fallo funcional",
    "CP-12": "Alertas y notificaciones",
}


@dataclass
class Measurement:
    campaign_id: str
    scenario: str
    objective: str
    approach: str
    repetition: int
    expected: str
    observed: str
    status: str
    failure_present: bool
    failure_detected: bool
    start: str
    end: str
    duration_ms: int
    detection_ms: int = 0
    notification_ms: int = 0
    localization_ms: int = 0
    review_ms: int = 0
    evidence_required: bool = True
    evidence_recoverable: bool = False
    screenshots: str = ""
    logs: str = ""
    alerts: str = ""
    execution_id: str = ""
    observations: str = ""


class WebhookHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        WebhookHandler.received.append({
            "path": self.path,
            "body": body,
            "received_at": now_iso(),
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ms_since(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def ensure_dirs(campaign_id: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    EVIDENCES.mkdir(parents=True, exist_ok=True)
    campaign_dir = EVIDENCES / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)
    return campaign_dir


def check_url(url: str) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=5)
        return r.ok, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as exc:
        return False, str(exc)


def require_lab() -> list[str]:
    checks = [
        f"{ECOM_API}/api/health",
        f"{QA_URL}/api/salud",
        ECOM_FRONT,
        os.getenv("QA_FRONT_URL", "http://127.0.0.1:5173"),
    ]
    issues = []
    for url in checks:
        ok, detail = check_url(url)
        if not ok:
            issues.append(f"{url} no disponible: {detail}")
    if not OWNER_PASSWORD:
        issues.append("Falta VELTRIX_OWNER_PASSWORD. No se ejecutan pruebas autenticadas sin secreto local.")
    return issues


def qa_session() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{QA_URL}/api/autenticacion/iniciar-sesion",
        json={"correo": QA_USER, "contrasena": QA_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return s


def ecom_session() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{ECOM_API}/api/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


def api_json(session: requests.Session, method: str, url: str, **kwargs):
    method_upper = method.upper()
    if method_upper not in {"GET", "HEAD", "OPTIONS"}:
        csrf = session.cookies.get("csrf_access_token")
        if csrf:
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("X-CSRF-TOKEN", csrf)
            kwargs["headers"] = headers
    timeout = kwargs.pop("timeout", 180)
    r = session.request(method, url, timeout=timeout, **kwargs)
    if not r.ok:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text[:400]}")
    return r.json() if r.text else {}


def post_evaluation(qa: requests.Session, project_id: str, item: Measurement):
    payload = {
        "proyecto_id": project_id,
        "escenario": item.scenario,
        "enfoque": item.approach,
        "fallos_esperados": 1 if item.failure_present else 0,
        "fallos_detectados": 1 if item.failure_detected else 0,
        "tiempo_deteccion_milisegundos": item.detection_ms,
        "tiempo_notificacion_milisegundos": item.notification_ms,
        "tiempo_consulta_milisegundos": item.localization_ms,
        "resultados_almacenados": 1 if item.execution_id or item.status in {"exitosa", "fallida", "bloqueada"} else 0,
        "evidencias_generadas": 1 if item.evidence_recoverable else 0,
        "observaciones": f"{item.campaign_id}; rep={item.repetition}; estado={item.status}; {item.observations}",
    }
    try:
        api_json(qa, "POST", f"{QA_URL}/api/evaluaciones", json=payload)
    except Exception as exc:
        item.observations += f" | No se pudo registrar medicion QA: {exc}"


def import_yaml_and_prepare(qa: requests.Session) -> tuple[str, str, dict]:
    shutil.copyfile(YAML_PATH, PROJECT_ROOT / "configuraciones" / "ejemplos" / "veltrix_commerce.yaml")
    content = YAML_PATH.read_text(encoding="utf-8")
    api_json(qa, "POST", f"{QA_URL}/api/configuraciones-yaml/validar", json={"contenido": content})
    imported = api_json(qa, "POST", f"{QA_URL}/api/configuraciones-yaml/importar", json={"contenido": content})
    project_id = imported["proyecto_id"]
    envs = api_json(qa, "GET", f"{QA_URL}/api/proyectos/{project_id}/entornos")["elementos"]
    env_id = envs[0]["id"]
    api_json(qa, "POST", f"{QA_URL}/api/proyectos/{project_id}/secretos", json={
        "nombre": "veltrix_owner_password",
        "tipo": "password",
        "valor": OWNER_PASSWORD,
    })
    db_url = read_ecommerce_db_url()
    if db_url:
        api_json(qa, "POST", f"{QA_URL}/api/monitores", json={
            "proyecto_id": project_id,
            "entorno_id": env_id,
            "nombre": "Base de datos ecommerce lectura segura",
            "tipo": "base_datos",
            "configuracion": {"cadena_conexion": db_url, "consulta": "SELECT 1"},
            "intervalo_recomendado_segundos": 300,
        })
    return project_id, env_id, imported


def read_ecommerce_db_url() -> str:
    env_path = PROJECT_ROOT.parent / "ecommerce" / "backend" / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            value = line.split("=", 1)[1].strip()
            if "localhost" in value or "127.0.0.1" in value:
                return value
    return ""


def get_named(items: list[dict], name: str) -> dict:
    for item in items:
        if item.get("nombre") == name:
            return item
    raise KeyError(name)


def execute_pipeline(qa: requests.Session, env_id: str, pipeline: dict) -> dict:
    data = api_json(qa, "POST", f"{QA_URL}/api/pipelines/{pipeline['id']}/ejecutar", json={
        "entorno_id": env_id,
        "procesar_ahora": True,
    })
    return api_json(qa, "GET", f"{QA_URL}/api/ejecuciones/{data['id']}")


def record_pipeline_results(campaign_id: str, execution: dict, repetition: int) -> list[Measurement]:
    started = execution.get("fecha_inicio") or execution.get("fecha_encolado") or now_iso()
    ended = execution.get("fecha_fin") or now_iso()
    duration = int(execution.get("duracion_milisegundos") or 0)
    evidences = execution.get("evidencias", [])
    evidence_names = ",".join(e.get("nombre_archivo", "") for e in evidences)
    items: list[Measurement] = []
    scenario_map = {
        "CP-01": "CP-01",
        "CP-02": "CP-02",
        "CP-03": "CP-03",
        "CP-08": "CP-08",
        "CP-09": "CP-09",
        "CP-10": "CP-10",
        "CP-11": "CP-11",
        "CP-12": "CP-12",
    }
    grouped: dict[str, list[dict]] = {}
    for result in execution.get("resultados", []):
        text = json.dumps(result, ensure_ascii=False)
        code = next((cp for key, cp in scenario_map.items() if key in text), None)
        if not code:
            if "TCP" in text:
                code = "CP-09"
            elif "Salud API" in text:
                code = "CP-08"
            elif "Falla controlada" in text:
                code = "CP-10"
        if not code:
            continue
        grouped.setdefault(code, []).append(result)
    for code, results in grouped.items():
        expected_failure = code in {"CP-10", "CP-11", "CP-12"}
        has_failure = any(r.get("estado") in {"fallida", "error_tecnico"} for r in results)
        detected = has_failure if expected_failure else not has_failure
        status = "exitosa" if detected else "fallida"
        result = next((r for r in results if r.get("estado") in {"fallida", "error_tecnico"}), results[-1])
        items.append(Measurement(
            campaign_id, code, SCENARIOS[code], "integrado", repetition,
            "Cumplir criterio del escenario",
            result.get("mensaje") or result.get("estado", ""),
            status,
            expected_failure,
            detected,
            started,
            ended,
            duration,
            detection_ms=int(execution.get("duracion_milisegundos") or result.get("duracion_milisegundos") or 0),
            evidence_recoverable=bool(evidences),
            screenshots=evidence_names,
            alerts="pendiente" if expected_failure else "",
            execution_id=execution.get("id", ""),
        ))
    return items


def setup_ecommerce_data(ecom: requests.Session, campaign_id: str) -> dict:
    suffix = campaign_id[-8:]
    category_name = f"UVG Campania {suffix}"
    sku = f"UVG-{suffix}"
    product_name = f"Producto UVG {suffix}"
    categories = api_json(ecom, "GET", f"{ECOM_API}/api/categories")
    category = next((c for c in categories if c["name"] == category_name), None)
    if not category:
        category = api_json(ecom, "POST", f"{ECOM_API}/api/categories", json={"name": category_name})
    products = api_json(ecom, "GET", f"{ECOM_API}/api/products", params={"search": sku})
    product = next((p for p in products if p["sku"] == sku), None)
    if not product:
        product = api_json(ecom, "POST", f"{ECOM_API}/api/products", json={
            "sku": sku,
            "name": product_name,
            "description": "Dato ficticio de campania UVG",
            "price": 25.5,
            "cost": 10,
            "stock": 12,
            "low_stock_threshold": 2,
            "category_id": category["id"],
            "is_active": True,
        })
    customer = api_json(ecom, "POST", f"{ECOM_API}/api/customers", json={
        "name": f"Cliente UVG {suffix}",
        "email": f"cliente.uvg.{suffix}@example.test",
        "phone": "00000000",
    })
    return {"category": category, "product": product, "customer": customer, "sku": sku}


def run_api_business_cases(campaign_id: str, ecom: requests.Session, qa: requests.Session, project_id: str, repetition: int, campaign_dir: Path) -> list[Measurement]:
    items = []
    start = time.perf_counter()
    started = now_iso()
    try:
        data = setup_ecommerce_data(ecom, campaign_id + f"R{repetition}")
        product = api_json(ecom, "GET", f"{ECOM_API}/api/products/{data['product']['id']}")
        evidence = campaign_dir / f"CP04_R{repetition}_producto.json"
        evidence.write_text(json.dumps(product, indent=2, ensure_ascii=False), encoding="utf-8")
        ok = product["sku"] == data["sku"] and int(product["stock"]) >= 12
        items.append(Measurement(campaign_id, "CP-04", SCENARIOS["CP-04"], "integrado", repetition, "Producto persistido", product["sku"], "exitosa" if ok else "fallida", False, ok, started, now_iso(), ms_since(start), evidence_recoverable=True, screenshots=str(evidence), observations="Registro por API autenticada del ecommerce y medicion centralizada."))

        stock_initial = int(product["stock"])
        order = api_json(ecom, "POST", f"{ECOM_API}/api/orders", json={
            "customer_id": data["customer"]["id"],
            "items": [{"product_id": product["id"], "quantity": 2}],
            "status": "paid",
            "payment_method": "cash_on_delivery",
            "shipping_address": "Direccion ficticia UVG",
            "shipping_area": "capital",
            "shipping_fee": 0,
        })
        product_after_sale = api_json(ecom, "GET", f"{ECOM_API}/api/products/{product['id']}")
        sale_ok = order["status"] == "paid" and int(product_after_sale["stock"]) == stock_initial - 2
        sale_ev = campaign_dir / f"CP05_R{repetition}_venta.json"
        sale_ev.write_text(json.dumps({"order": order, "stock_inicial": stock_initial, "stock_final": product_after_sale["stock"]}, indent=2, ensure_ascii=False), encoding="utf-8")
        items.append(Measurement(campaign_id, "CP-05", SCENARIOS["CP-05"], "integrado", repetition, "Venta registrada y stock reducido", order["status"], "exitosa" if sale_ok else "fallida", False, sale_ok, started, now_iso(), ms_since(start), evidence_recoverable=True, screenshots=str(sale_ev), observations="Venta ficticia sobre producto de campania."))

        cancelled = api_json(ecom, "POST", f"{ECOM_API}/api/orders/{order['id']}/cancel")
        product_after_cancel = api_json(ecom, "GET", f"{ECOM_API}/api/products/{product['id']}")
        cancel_ok = cancelled["status"] == "cancelled" and int(product_after_cancel["stock"]) == stock_initial
        cancel_ev = campaign_dir / f"CP06_R{repetition}_cancelacion.json"
        cancel_ev.write_text(json.dumps({"order": cancelled, "stock_restaurado": product_after_cancel["stock"]}, indent=2, ensure_ascii=False), encoding="utf-8")
        items.append(Measurement(campaign_id, "CP-06", SCENARIOS["CP-06"], "integrado", repetition, "Venta cancelada y stock restituido", cancelled["status"], "exitosa" if cancel_ok else "fallida", False, cancel_ok, started, now_iso(), ms_since(start), evidence_recoverable=True, screenshots=str(cancel_ev), observations="Cancelacion sobre venta creada por campania."))

        public = requests.get(f"{ECOM_API}/api/public/aurora/products", timeout=15)
        public_ev = campaign_dir / f"CP07_R{repetition}_catalogo.json"
        public_ev.write_text(public.text, encoding="utf-8")
        public_ok = public.status_code == 200 and data["sku"] in public.text
        items.append(Measurement(campaign_id, "CP-07", SCENARIOS["CP-07"], "integrado", repetition, "Catalogo publico responde y muestra producto activo", f"HTTP {public.status_code}", "exitosa" if public_ok else "fallida", False, public_ok, started, now_iso(), ms_since(start), evidence_recoverable=True, screenshots=str(public_ev), observations="Consulta endpoint publico real."))
    except Exception as exc:
        items.append(Measurement(campaign_id, "CP-04", SCENARIOS["CP-04"], "integrado", repetition, "Datos ficticios preparados", str(exc), "error_tecnico", False, False, started, now_iso(), ms_since(start), observations=str(exc)))
    for item in items:
        post_evaluation(qa, project_id, item)
    return items


def browser() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def traditional_login(campaign_id: str, repetition: int, campaign_dir: Path, valid: bool) -> Measurement:
    code = "CP-01" if valid else "CP-02"
    started = now_iso()
    start = time.perf_counter()
    shot = campaign_dir / f"{code}_tradicional_R{repetition}.png"
    d = browser()
    try:
        d.get(f"{ECOM_FRONT}/login")
        wait = WebDriverWait(d, 15)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email']"))).send_keys(OWNER_EMAIL if valid else "invalid@example.test")
        d.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(OWNER_PASSWORD if valid else "no-valida")
        d.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        if valid:
            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(normalize-space(.), 'Aurora Boutique')]")))
            observed = "Dashboard Aurora visible"
        else:
            time.sleep(2)
            if "login" not in d.current_url:
                raise RuntimeError("Credenciales invalidas permitieron salir del login")
            if d.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'Aurora Boutique')]"):
                raise RuntimeError("Dashboard visible despues de credenciales invalidas")
            observed = "Rechazo correcto: continua en login sin dashboard autenticado"
        d.save_screenshot(str(shot))
        ok = True
    except Exception as exc:
        observed = str(exc)
        ok = False
        try:
            d.save_screenshot(str(shot))
        except Exception:
            pass
    finally:
        d.quit()
    return Measurement(campaign_id, code, SCENARIOS[code], "tradicional", repetition, "Criterio UI validado", observed, "exitosa" if ok else "fallida", not valid, ok, started, now_iso(), ms_since(start), detection_ms=ms_since(start), evidence_recoverable=shot.exists(), screenshots=str(shot), observations="Selenium directo sin centralizacion QA.")


def traditional_monitor(campaign_id: str, repetition: int, campaign_dir: Path) -> list[Measurement]:
    items = []
    for code, action in [
        ("CP-08", lambda: requests.get(f"{ECOM_API}/api/health", timeout=5).status_code == 200),
        ("CP-09", lambda: socket.create_connection(("127.0.0.1", 8000), timeout=5).close() is None),
        ("CP-10", lambda: requests.get("http://127.0.0.1:8766/health", timeout=2).status_code == 200),
    ]:
        started = now_iso()
        start = time.perf_counter()
        failure_present = code == "CP-10"
        try:
            ok_raw = bool(action())
            detected = (not ok_raw) if failure_present else ok_raw
            observed = "fallo detectado" if failure_present and detected else str(ok_raw)
        except Exception as exc:
            detected = failure_present
            observed = str(exc)
        ev = campaign_dir / f"{code}_tradicional_R{repetition}.log"
        ev.write_text(observed, encoding="utf-8")
        items.append(Measurement(campaign_id, code, SCENARIOS[code], "tradicional", repetition, "Verificacion independiente", observed, "exitosa" if detected else "fallida", failure_present, detected, started, now_iso(), ms_since(start), detection_ms=ms_since(start), evidence_recoverable=True, logs=str(ev), observations="Monitor independiente sin historial centralizado."))
    return items


def start_webhook() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 8765), WebhookHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def create_webhook_channel(qa: requests.Session, project_id: str):
    return api_json(qa, "POST", f"{QA_URL}/api/proyectos/{project_id}/canales-notificacion", json={
        "nombre": "Webhook local UVG",
        "tipo": "webhook",
        "activo": True,
        "configuracion": {"url": "http://127.0.0.1:8765/notificaciones", "metodo": "POST"},
    })


def write_csv(measurements: list[Measurement]):
    path = RESULTS / "09_DATOS_EXPORTADOS.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(measurements[0]).keys()) if measurements else list(Measurement.__dataclass_fields__.keys()))
        writer.writeheader()
        for item in measurements:
            writer.writerow(asdict(item))


def compute_indicators(measurements: list[Measurement]) -> list[dict]:
    rows = []
    for approach in sorted({m.approach for m in measurements}):
        group = [m for m in measurements if m.approach == approach]
        total = len(group)
        success = sum(m.status == "exitosa" for m in group)
        failures = sum(m.status == "fallida" for m in group)
        errors = sum(m.status == "error_tecnico" for m in group)
        required = sum(m.evidence_required for m in group)
        recoverable = sum(m.evidence_recoverable for m in group)
        expected_failures = sum(m.failure_present for m in group)
        detected = sum(1 for m in group if m.failure_present and m.failure_detected)
        rows.append({
            "enfoque": approach,
            "total": total,
            "exitosas": success,
            "fallidas": failures,
            "errores_tecnicos": errors,
            "tasa_exito": round(success / total * 100, 2) if total else 0,
            "fallos_esperados": expected_failures,
            "fallos_detectados": detected,
            "tasa_deteccion": round(detected / expected_failures * 100, 2) if expected_failures else 100,
            "evidencias_requeridas": required,
            "evidencias_recuperables": recoverable,
            "disponibilidad_evidencia": round(recoverable / required * 100, 2) if required else 0,
            "duracion_promedio_ms": round(sum(m.duration_ms for m in group) / total, 2) if total else 0,
            "notificacion_promedio_ms": round(sum(m.notification_ms for m in group) / total, 2) if total else 0,
        })
    with (RESULTS / "10_INDICADORES.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["enfoque"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_reports(campaign_id: str, measurements: list[Measurement], indicators: list[dict], blockages: list[str]):
    by_cp = {cp: [m for m in measurements if m.scenario == cp] for cp in SCENARIOS}
    summary_lines = [
        f"# Resumen ejecutivo\n\nCampaña: `{campaign_id}`\n",
        f"Total de mediciones: {len(measurements)}.\n",
        "Bloqueos: " + ("; ".join(blockages) if blockages else "sin bloqueos criticos") + "\n",
    ]
    (RESULTS / "01_RESUMEN_EJECUTIVO.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (RESULTS / "02_RESULTADOS_SELENIUM.md").write_text(format_section("Selenium", by_cp, ["CP-01", "CP-02", "CP-03", "CP-04", "CP-05", "CP-06", "CP-07", "CP-11"]), encoding="utf-8")
    (RESULTS / "03_RESULTADOS_MONITOREO.md").write_text(format_section("Monitoreo", by_cp, ["CP-08", "CP-09", "CP-10"]), encoding="utf-8")
    (RESULTS / "04_RESULTADOS_PIPELINES.md").write_text(format_pipelines(measurements), encoding="utf-8")
    (RESULTS / "05_RESULTADOS_ALERTAS.md").write_text(format_section("Alertas", by_cp, ["CP-10", "CP-11", "CP-12"]), encoding="utf-8")
    (RESULTS / "06_RESULTADOS_TRAZABILIDAD.md").write_text(format_traceability(measurements), encoding="utf-8")
    (RESULTS / "07_COMPARACION_EXPERIMENTAL.md").write_text(format_comparison(indicators), encoding="utf-8")
    (RESULTS / "08_CUMPLIMIENTO_OBJETIVOS.md").write_text(format_objectives(measurements), encoding="utf-8")
    (RESULTS / "12_INSTRUCCIONES_REPRODUCCION.md").write_text(reproduction_text(), encoding="utf-8")


def format_section(title: str, by_cp: dict, cps: list[str]) -> str:
    lines = [f"# {title}\n", "| Escenario | Mediciones | Exitosas | Evidencias | Observaciones |", "|---|---:|---:|---:|---|"]
    for cp in cps:
        group = by_cp.get(cp, [])
        lines.append(f"| {cp} {SCENARIOS[cp]} | {len(group)} | {sum(m.status == 'exitosa' for m in group)} | {sum(m.evidence_recoverable for m in group)} | {'; '.join(sorted({m.observations for m in group if m.observations}))[:180]} |")
    return "\n".join(lines) + "\n"


def format_pipelines(measurements: list[Measurement]) -> str:
    integrated = [m for m in measurements if m.approach == "integrado"]
    lines = ["# Resultados de pipelines\n", "| Escenario | Ejecucion | Estado | Duracion ms | Evidencia |", "|---|---|---|---:|---|"]
    for m in integrated:
        lines.append(f"| {m.scenario} | {m.execution_id} | {m.status} | {m.duration_ms} | {m.screenshots or m.logs} |")
    return "\n".join(lines) + "\n"


def format_traceability(measurements: list[Measurement]) -> str:
    lines = ["# Trazabilidad\n", "| Escenario | Enfoque | Repeticion | Ejecucion | Evidencia recuperable | Capturas/logs |", "|---|---|---:|---|---|---|"]
    for m in measurements:
        lines.append(f"| {m.scenario} | {m.approach} | {m.repetition} | {m.execution_id} | {m.evidence_recoverable} | {m.screenshots or m.logs} |")
    return "\n".join(lines) + "\n"


def format_comparison(indicators: list[dict]) -> str:
    lines = ["# Comparacion experimental\n", "| Enfoque | Total | Exitosas | Tasa deteccion | Evidencia disponible | Duracion promedio ms |", "|---|---:|---:|---:|---:|---:|"]
    for row in indicators:
        lines.append(f"| {row['enfoque']} | {row['total']} | {row['exitosas']} | {row['tasa_deteccion']} | {row['disponibilidad_evidencia']} | {row['duracion_promedio_ms']} |")
    lines.append("\nLa muestra es de laboratorio local; no se afirma significancia estadistica.")
    return "\n".join(lines) + "\n"


def format_objectives(measurements: list[Measurement]) -> str:
    rows = [
        ("Objetivo general", "CP-01 a CP-12", "Mediciones integradas y comparativas", f"{len(measurements)} registros", "09_DATOS_EXPORTADOS.csv"),
        ("OE1", "Procedimiento tradicional", "Tiempos y evidencias separadas", f"{sum(m.approach == 'tradicional' for m in measurements)} registros", "11_EVIDENCIAS"),
        ("OE2", "Trazabilidad", "Evidencias recuperables", f"{sum(m.evidence_recoverable for m in measurements)} evidencias", "06_RESULTADOS_TRAZABILIDAD.md"),
        ("OE3", "Alertas", "Notificaciones y fallos controlados", f"{sum(1 for m in measurements if m.scenario in {'CP-10','CP-11','CP-12'})} mediciones", "05_RESULTADOS_ALERTAS.md"),
        ("OE4", "Comparacion", "Indicadores por enfoque", "Calculado", "10_INDICADORES.csv"),
    ]
    lines = ["# Cumplimiento de objetivos\n", "| Objetivo | Escenario | Indicador | Resultado | Evidencia |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def reproduction_text() -> str:
    return """# Instrucciones de reproduccion

1. Iniciar `ecommerce/INICIAR_ECOMMERCE.bat`.
2. Iniciar `proyecto de graduacion/INICIAR_SISTEMA_QA.bat`.
3. En una ventana `cmd`, configurar el secreto sin guardarlo en YAML:
   `set /p VELTRIX_OWNER_PASSWORD=Clave owner Aurora:`
4. Ejecutar `proyecto de graduacion/evaluacion_veltrix/EJECUTAR_CAMPANA_WINDOWS.bat --mode full --repetitions 3`.
5. Revisar `proyecto de graduacion/evaluacion_veltrix/resultados`.
"""


def run(mode: str, repetitions: int, case: str | None, owner_password: str | None = None):
    global OWNER_PASSWORD
    if owner_password:
        OWNER_PASSWORD = owner_password
    campaign_id = os.getenv("CAMPAIGN_ID") or "UVG_VELTRIX_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    campaign_dir = ensure_dirs(campaign_id)
    blockages = require_lab()
    if blockages:
        raise SystemExit("\n".join(blockages))

    qa = qa_session()
    ecom = ecom_session()
    project_id, env_id, _ = import_yaml_and_prepare(qa)
    webhook = start_webhook()
    create_webhook_channel(qa, project_id)
    pipelines = api_json(qa, "GET", f"{QA_URL}/api/pipelines")["elementos"]
    pipeline_by_name = {p["nombre"]: p for p in pipelines if p["proyecto_id"] == project_id}
    measurements: list[Measurement] = []

    selected_pipelines = []
    if mode in {"full", "smoke"}:
        selected_pipelines.append("Pipeline 01 Autenticacion y navegacion")
    if mode in {"full", "monitors", "smoke"}:
        selected_pipelines.append("Pipeline 03 Monitoreo")
    if mode in {"full"}:
        selected_pipelines.extend(["Pipeline 02 Inventario ventas catalogo", "Pipeline 04 Deteccion y alertas"])

    for rep in range(1, repetitions + 1):
        if mode in {"full", "smoke"}:
            measurements.extend(run_api_business_cases(campaign_id, ecom, qa, project_id, rep, campaign_dir))
        for name in selected_pipelines:
            execution = execute_pipeline(qa, env_id, pipeline_by_name[name])
            measurements.extend(record_pipeline_results(campaign_id, execution, rep))
        if mode in {"full", "comparison", "smoke"}:
            measurements.append(traditional_login(campaign_id, rep, campaign_dir, True))
            measurements.append(traditional_login(campaign_id, rep, campaign_dir, False))
            measurements.extend(traditional_monitor(campaign_id, rep, campaign_dir))

    time.sleep(1)
    notification_ms = 0
    if WebhookHandler.received:
        notification_ms = 1
        notif_path = campaign_dir / "CP12_webhook_recibido.json"
        notif_path.write_text(json.dumps(WebhookHandler.received, indent=2, ensure_ascii=False), encoding="utf-8")
        measurements.append(Measurement(campaign_id, "CP-12", SCENARIOS["CP-12"], "integrado", 1, "Webhook local recibe notificacion", "notificacion recibida", "exitosa", True, True, now_iso(), now_iso(), 1, notification_ms=notification_ms, evidence_recoverable=True, logs=str(notif_path), observations="Canal webhook local activo."))
    else:
        measurements.append(Measurement(campaign_id, "CP-12", SCENARIOS["CP-12"], "integrado", 1, "Webhook local recibe notificacion", "sin recepcion comprobable", "fallida", True, False, now_iso(), now_iso(), 1, observations="No se recibio webhook durante la ventana de observacion."))

    webhook.shutdown()
    for item in measurements:
        if item.scenario == "CP-12":
            post_evaluation(qa, project_id, item)
    write_csv(measurements)
    indicators = compute_indicators(measurements)
    write_reports(campaign_id, measurements, indicators, blockages)
    print(json.dumps({"campaign_id": campaign_id, "measurements": len(measurements), "results": str(RESULTS)}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full", "case", "monitors", "comparison", "export"], default="full")
    parser.add_argument("--case")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--owner-password", default="")
    args = parser.parse_args()
    run(args.mode, args.repetitions, args.case, args.owner_password)


if __name__ == "__main__":
    main()
