#!/usr/bin/env python3
"""
Conector con listmonk — plataforma de emailing MktBs.

Une lo que ya produce el motor de contenido con la plataforma:

    segmentos.py  → CSV por versión  → `listas`   crea/actualiza las listas por sector
    campana.py    → HTML por versión → `campana`  deja una campaña en BORRADOR por versión

y suma lo que antes no había:

    `retarget`   arma una lista con quienes NO abrieron o SÍ hicieron clic en una campaña
    `exportar`   saca una lista a CSV (públicos de Meta / LinkedIn)
    `estado`     enviados, aperturas, clics y rebotes de una campaña

Nada se envía desde aquí: las campañas quedan en borrador y se lanzan desde el
panel, después del envío de prueba.

Credenciales (el entorno gana sobre el archivo):
    ~/.config/haiku/listmonk.env
        LISTMONK_URL=https://correo.mktbs.pe
        LISTMONK_USER=motor            (usuario API creado en Ajustes → Usuarios)
        LISTMONK_TOKEN=xxxxxxxx

Uso:
    python3 listmonk.py listas   <campana.yaml> <carpeta-csv>
    python3 listmonk.py campana  <campana.yaml> [--remitente "Expo Perú Industrial <boletin@envios.mktbs.pe>"]
    python3 listmonk.py retarget <id-campaña> (--no-abrieron | --clic) --lista <nombre>
    python3 listmonk.py exportar <nombre-lista> <salida.csv>
    python3 listmonk.py estado   <id-campaña>
"""
import argparse
import csv
import html as html_mod
import io
import json
import os
import re
import sys
import time
from pathlib import Path

CONFIG = "~/.config/haiku/listmonk.env"
CLAVES = ("LISTMONK_URL", "LISTMONK_USER", "LISTMONK_TOKEN")
REMITENTE = "Expo Perú Industrial <boletin@envios.mktbs.pe>"
PLANTILLA = "MktBs sin marco"


# ------------------------------------------------------------------ config y API

def cargar_config(ruta=CONFIG):
    """Lee KEY=valor. El entorno gana sobre el archivo."""
    datos = {}
    ruta = Path(ruta).expanduser()
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            datos[k.strip()] = v.strip().strip('"').strip("'")
    for k in CLAVES:
        if os.environ.get(k):
            datos[k] = os.environ[k]
    faltan = [k for k in CLAVES if not datos.get(k)]
    if faltan:
        raise SystemExit(f"Faltan credenciales: {', '.join(faltan)}. Creá {ruta} (ver emailing/README.md).")
    return datos


class Listmonk:
    def __init__(self, cfg):
        import requests
        self.base = cfg["LISTMONK_URL"].rstrip("/") + "/api"
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"token {cfg['LISTMONK_USER']}:{cfg['LISTMONK_TOKEN']}"
        self.s.headers["User-Agent"] = "haiku-motor-emailing/1.0"

    def __call__(self, metodo, ruta, **kw):
        r = self.s.request(metodo, self.base + ruta, timeout=120, **kw)
        if r.status_code >= 400:
            raise SystemExit(f"listmonk {metodo} {ruta} → {r.status_code}: {r.text[:300]}")
        return r.json().get("data") if r.content else None

    def listas(self):
        return {l["name"]: l for l in self("GET", "/lists", params={"per_page": "all"})["results"]}

    def lista(self, nombre, crear=True, etiquetas=()):
        existentes = self.listas()
        if nombre in existentes:
            return existentes[nombre]
        if not crear:
            raise SystemExit(f"No existe la lista «{nombre}».")
        return self("POST", "/lists", json={"name": nombre, "type": "private", "optin": "single",
                                             "tags": list(etiquetas)})

    def plantilla_sin_marco(self):
        """El HTML de campana.py ya trae su diseño: la plantilla solo lo deja pasar."""
        for t in self("GET", "/templates"):
            if t["name"] == PLANTILLA:
                return t
        return self("POST", "/templates", json={"name": PLANTILLA, "type": "campaign",
                                                 "body": '{{ template "content" . }}'})


# ------------------------------------------------------------------ transformaciones (sin red)

def nombre_lista(slug):
    """Una lista permanente por sector: las campañas pasan, el sector queda."""
    return f"sector-{slug}"


def csv_a_listmonk(ruta_csv):
    """CSV de segmentos.py (email,name,empresa,sector,presente_en) → CSV de importación de listmonk."""
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["email", "name", "attributes"])
    n = 0
    with open(ruta_csv, newline="", encoding="utf-8") as fh:
        for fila in csv.DictReader(fh):
            correo = (fila.get("email") or "").strip().lower()
            if not correo:
                continue
            nombre = (fila.get("name") or "").strip() or correo.split("@")[0]
            attrs = {k: fila[k] for k in ("empresa", "sector", "presente_en") if fila.get(k)}
            w.writerow([correo, nombre, json.dumps(attrs, ensure_ascii=False)])
            n += 1
    return salida.getvalue(), n


ENLACE = re.compile(r'href="(https?://[^"]+)"')


def preparar_html(html, preheader=""):
    """HTML de campana.py → cuerpo de campaña listmonk.

    - cada enlace http(s) se mide (sufijo @TrackLink de listmonk)
    - píxel de apertura ({{ TrackView }})
    - pie con baja en un clic ({{ UnsubscribeURL }}), exigido por la Ley 29733
    """
    if "{{" in html:
        raise ValueError("El HTML trae '{{', que listmonk leería como plantilla.")
    cuerpo = ENLACE.sub(lambda m: f'href="{m.group(1)}@TrackLink"', html)
    oculto = (f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html_mod.escape(preheader)}</div>\n'
              if preheader else "")
    pie = ('\n<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
           '<td align="center" style="padding:16px 12px 28px;font-family:Arial,sans-serif;font-size:12px;'
           'line-height:1.5;color:#777777;">Recibes este correo por tu relación con las ferias de MKT BS. '
           '<a href="{{ UnsubscribeURL }}" style="color:#777777;">Darse de baja</a></td></tr></table>\n'
           '{{ TrackView }}\n')
    return oculto + cuerpo + pie


def consulta_retarget(campana_id, listas_ids, modo):
    """Expresión SQL (sobre subscribers) que listmonk acepta en /subscribers/query/lists."""
    cid = int(campana_id)
    ids = ",".join(str(int(i)) for i in listas_ids) or "0"
    en_campana = (f"subscribers.id IN (SELECT subscriber_id FROM subscriber_lists "
                  f"WHERE list_id IN ({ids}) AND status != 'unsubscribed')")
    if modo == "no-abrieron":
        filtro = (f"subscribers.id NOT IN (SELECT subscriber_id FROM campaign_views "
                  f"WHERE campaign_id = {cid} AND subscriber_id IS NOT NULL)")
    elif modo == "clic":
        filtro = (f"subscribers.id IN (SELECT subscriber_id FROM link_clicks "
                  f"WHERE campaign_id = {cid} AND subscriber_id IS NOT NULL)")
    else:
        raise ValueError(modo)
    return f"{en_campana} AND {filtro} AND subscribers.status = 'enabled'"


# ------------------------------------------------------------------ comandos

def cmd_listas(api, a):
    import yaml
    camp = yaml.safe_load(Path(a.yaml).read_text(encoding="utf-8"))
    carpeta = Path(a.carpeta)
    for v in camp["versiones"]:
        ruta = carpeta / f"{v['slug']}.csv"
        if not ruta.exists():
            print(f"{v['slug']:15} sin CSV, se salta")
            continue
        lista = api.lista(nombre_lista(v["slug"]), etiquetas=["sector"])
        datos, n = csv_a_listmonk(ruta)
        params = {"mode": "subscribe", "subscription_status": "confirmed", "delim": ",",
                  "lists": [lista["id"]], "overwrite": True}
        api("POST", "/import/subscribers", data={"params": json.dumps(params)},
            files={"file": (ruta.name, datos.encode("utf-8"), "text/csv")})
        while True:  # listmonk importa de a una
            st = api("GET", "/import/subscribers")
            if st["status"] in ("finished", "failed", "stopped", "none"):
                break
            time.sleep(2)
        print(f"{v['slug']:15} {n:>7,} → {lista['name']} ({st['status']})".replace(",", "."))


def cmd_campana(api, a):
    import yaml
    ruta = Path(a.yaml)
    camp = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    plantilla = api.plantilla_sin_marco()
    for v in camp["versiones"]:
        html_ruta = ruta.parent / v["slug"] / "email-pegar.html"
        if not html_ruta.exists():
            raise SystemExit(f"Falta {html_ruta}: corré antes campana.py {ruta}")
        lista = api.lista(nombre_lista(v["slug"]), crear=False)
        cuerpo = preparar_html(html_ruta.read_text(encoding="utf-8"), v.get("preheader", ""))
        c = api("POST", "/campaigns", json={
            "name": f"{camp['campana']} · {v['slug']}", "subject": v["asunto"],
            "lists": [lista["id"]], "from_email": a.remitente, "content_type": "html",
            "body": cuerpo, "template_id": plantilla["id"], "messenger": "email", "type": "regular",
            "tags": [camp["campana"], v["slug"]],
        })
        print(f"{v['slug']:15} borrador #{c['id']} → {lista['name']} ({lista.get('subscriber_count', '?')})")
    print("Revisá cada borrador, mandá la prueba desde el panel y recién ahí lanzá.")


def cmd_retarget(api, a):
    c = api("GET", f"/campaigns/{a.campana}")
    modo = "no-abrieron" if a.no_abrieron else "clic"
    destino = api.lista(a.lista, etiquetas=["retarget", modo])
    api("PUT", "/subscribers/query/lists", json={
        "query": consulta_retarget(a.campana, [l["id"] for l in c["lists"]], modo),
        "action": "add", "target_list_ids": [destino["id"]], "status": "confirmed",
    })
    final = api.listas()[destino["name"]]
    print(f"«{c['name']}» {modo} → lista «{final['name']}» ({final.get('subscriber_count', '?')})")


def cmd_exportar(api, a):
    lista = api.lista(a.lista, crear=False)
    filas = api("GET", "/subscribers", params={"list_id": lista["id"], "per_page": "all"})["results"]
    salida = Path(a.salida)
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["email", "fn", "ln", "country"])  # columnas que reconocen Meta y LinkedIn
        for s in filas:
            if s["status"] != "enabled":
                continue
            partes = (s.get("name") or "").split(" ", 1)
            w.writerow([s["email"], partes[0], partes[1] if len(partes) > 1 else "", "PE"])
    print(f"{len(filas)} contactos → {salida} (datos personales: no subir al repo)")


def cmd_estado(api, a):
    c = api("GET", f"/campaigns/{a.campana}")
    enviados = c.get("sent") or 0
    pct = lambda x: f"{100 * x / enviados:.1f} %" if enviados else "—"
    print(f"{c['name']}  [{c['status']}]")
    print(f"  enviados  {enviados:>7}")
    for clave, rotulo in (("views", "aperturas"), ("clicks", "clics"), ("bounces", "rebotes")):
        x = c.get(clave) or 0
        print(f"  {rotulo:9} {x:>7}  {pct(x)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("listas"); s.add_argument("yaml"); s.add_argument("carpeta")
    s = sub.add_parser("campana"); s.add_argument("yaml"); s.add_argument("--remitente", default=REMITENTE)
    s = sub.add_parser("retarget"); s.add_argument("campana", type=int)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--no-abrieron", action="store_true"); g.add_argument("--clic", action="store_true")
    s.add_argument("--lista", required=True)
    s = sub.add_parser("exportar"); s.add_argument("lista"); s.add_argument("salida")
    s = sub.add_parser("estado"); s.add_argument("campana", type=int)
    a = p.parse_args(argv)
    api = Listmonk(cargar_config())
    {"listas": cmd_listas, "campana": cmd_campana, "retarget": cmd_retarget,
     "exportar": cmd_exportar, "estado": cmd_estado}[a.cmd](api, a)


if __name__ == "__main__":
    sys.exit(main())
