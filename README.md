# MKT BS Emailing — listmonk + Amazon SES

Plataforma propia de envío de MKT BS, decidida el 13-oct-2026 (en lugar de Brevo y
StudioXperto). Proyecto independiente; usa el generador de campañas de
[haiku-web-engine](https://github.com/AldoNieto/haiku-web-engine) (`contenido/campana.py`
y `contenido/segmentos.py`).

```
Mac mini                     servidor público (VPS)            Amazon SES
segmentos.py → listas ──API──▶ listmonk + PostgreSQL ──SMTP──▶ entrega
campana.py   → borradores      panel, píxel, clics, bajas ◀── rebotes y quejas (SNS)
listmonk.py  → retarget          correo.mktbs.pe                    │
respaldo.sh  ◀── volcado diario                                     ▼
                              ◀── aperturas, clics y bajas ── destinatarios
```

La dirección `https://correo.mktbs.pe` lleva directo a la pantalla de acceso del panel
(usuario y contraseña; cada usuario ve lo que su rol le permite). Lo único público son
la página de baja y «ver en el navegador», a las que se llega desde el correo.

El servidor tiene que estar en internet las 24 horas: ahí caen las aperturas, los
clics y las bajas. El hosting compartido de Hostinger no corre listmonk; por eso un
VPS chico. Todo lo demás corre en el Mac mini.

## Producción (desde el 22-oct-2026)

| Pieza | Qué corre |
|---|---|
| Servidor | VPS KVM 2 de Hostinger `srv2087545`, IP 2.25.96.12, compartido con el CRM |
| Aplicación | Plantilla «Listmonk» del Docker manager: proyecto `listmonk-ome7` con listmonk v6.0.0 y PostgreSQL 18 |
| HTTPS | Proyecto `traefik` (Let's Encrypt), compartido con `crm.mktbs.pe` |
| Panel | `https://correo.mktbs.pe` |
| Envío | Amazon SES, us-east-1 |
| Dominio de envío | `boletin.mktbs.pe` (DKIM, MAIL FROM `rebotes.boletin.mktbs.pe`) |
| Remitente | `MKT BS <noticias@boletin.mktbs.pe>` |
| Resultados al CRM | `crm-ferias/scripts/listmonk-sync.sh` copia campañas, aperturas y clics |

El detalle de la configuración aplicada está en `mktbs-direccion`, `plataforma/comunidad/emailing/README.md`.
La carpeta `servidor/` y la «Puesta en marcha» de abajo son la receta original (listmonk v4.1.0 con Caddy en
`envios.mktbs.pe`): sirven de referencia para montar otra instancia, no describen la que corre.

```
servidor/docker-compose.yml   listmonk v4.1.0 + PostgreSQL 16 + Caddy (HTTPS automático)
servidor/Caddyfile            proxy del dominio a listmonk
servidor/.env.example         dominio y claves (copiar a .env en el servidor)
servidor/respaldo.sh          volcado diario de la base hacia el Mac mini
listmonk.py                   conector: listas, campañas, retargeting, exportar, estado
SES-SOLICITUD.md              texto para pedir a Amazon la salida del modo de prueba
```

## Puesta en marcha original (receta con Caddy, no es la de producción)

1. **DNS en Hostinger (mktbs.pe).** No tocar el SPF ni el DMARC de `mktbs.pe`: son del
   correo de Zoho. Todo va en el subdominio `envios.mktbs.pe`:

   | Tipo | Nombre | Valor |
   |---|---|---|
   | A | `envios` | IP del VPS |
   | CNAME ×3 | `xxxx._domainkey.envios` | los tres que da SES (Easy DKIM) |
   | MX | `rebotes.envios` | `10 feedback-smtp.us-east-1.amazonses.com` |
   | TXT | `rebotes.envios` | `v=spf1 include:amazonses.com ~all` |

   El DMARC de `mktbs.pe` (`p=none`, alineación relajada) ya cubre el subdominio.

2. **SES** (región `us-east-1`): verificar el dominio `envios.mktbs.pe` con Easy DKIM,
   MAIL FROM personalizado `rebotes.envios.mktbs.pe`, crear credenciales SMTP y pedir la
   salida del modo de prueba con el texto de `SES-SOLICITUD.md`.

3. **Servidor.** En el VPS, con Docker:
   ```bash
   git clone … && cd mktbs-emailing/servidor
   cp .env.example .env   # completar DB_PASSWORD y ADMIN_PASSWORD
   docker compose up -d
   ```
   Caddy saca el certificado solo cuando el registro A ya apunta al VPS.

4. **Ajustes en el panel** (`https://envios.mktbs.pe/admin`):
   - *Ajustes → SMTP*: `email-smtp.us-east-1.amazonaws.com`, puerto 587, STARTTLS,
     usuario y clave SMTP de SES.
   - *Ajustes → Rebotes*: activar SES. En SNS, un tema con suscripción HTTPS a
     `https://envios.mktbs.pe/webhooks/service/ses` (listmonk la confirma solo) y
     enlazarlo a los avisos de *Bounce* y *Complaint* del dominio en SES. Rebote duro:
     bloquear al primero; blando: al tercero; queja: bloquear.
   - *Ajustes → Privacidad*: activar la cabecera `List-Unsubscribe` (baja en un clic, que
     Gmail y Yahoo exigen) y **activar el seguimiento individual**. Sin eso las aperturas
     y clics se cuentan pero no por persona, y `retarget` no encuentra a nadie.
   - *Ajustes → Rendimiento*: ventana de envío para el calentamiento (abajo).
   - *Usuarios*: crear un usuario de tipo API (`motor`) y guardar su token en el Mac mini.

5. **Mac mini.** `~/.config/haiku/listmonk.env` (nunca en el repo):
   ```
   LISTMONK_URL=https://correo.mktbs.pe
   LISTMONK_USER=motor
   LISTMONK_TOKEN=…
   ```
   y el respaldo diario por launchd: `SERVIDOR=usuario@ip servidor/respaldo.sh`.

## Una campaña

```bash
M=~/Proyectos/haiku-web-engine      # generador de campañas
E=~/Proyectos/mktbs-emailing        # esta plataforma
Y=~/MktBs-Direccion/plataforma/post-show-2026/email/campana.yaml

python3 $M/contenido/segmentos.py $Y <base.xlsx> <carpeta-csv>   # una lista por sector
python3 $E/listmonk.py listas  $Y <carpeta-csv>           # crea/actualiza sector-<slug>
python3 $M/contenido/campana.py $Y                                 # HTML por versión
python3 $E/listmonk.py campana $Y                         # un borrador por versión
```

Los borradores se revisan en el panel, se manda la prueba y se lanzan desde ahí. El
script nunca envía. Cada enlace queda medido, con píxel de apertura y baja en un clic.

Después del envío:

```bash
python3 $E/listmonk.py estado   <id>                                  # aperturas, clics, rebotes
python3 $E/listmonk.py retarget <id> --no-abrieron --lista reenvio-<slug>  # reenviar a 72 h
python3 $E/listmonk.py retarget <id> --clic        --lista interes-<slug>  # pieza 2
python3 $E/listmonk.py exportar interes-<slug> ~/…/publico-meta.csv        # Meta / LinkedIn
```

Los CSV exportados tienen datos personales: viven en el Mac mini, nunca en el repo.

## Calentamiento

Una cuenta nueva de SES con una base de años puede rebotar mucho. Primero los contactos
más recientes, y entre tanda y tanda mirar `estado`:

| Día | Tope diario (ventana de envío) | Seguir si |
|---|---|---|
| 1 | 2.000 | rebotes < 3 %, quejas < 0,1 % |
| 2 | 5.000 | igual |
| 3 | 10.000 | igual |
| 4 en adelante | sin tope | rebotes < 2 % |

SES revisa la cuenta con rebotes sobre 5 % o quejas sobre 0,1 %.

## Pruebas

`python3 -m unittest discover tests` prueba las transformaciones sin red. El
conector completo se probó contra listmonk v4.1.0 en Docker (producción corre v6.0.0) (listas, importación,
borradores con enlaces medidos, píxel y baja, retarget y exportación).
