# MKT BS Emailing — instrucciones para Claude

Plataforma propia de envío de correos de MKT BS: listmonk + Amazon SES. Se trabaja en español.
Guía completa en `README.md`; propuesta y fases en
https://claude.ai/code/artifact/3ea1bdd6-e0f3-4557-a566-2d7766c73bba

## Reglas que no se rompen

1. **Nada sale a públicos sin Aldo.** Los scripts dejan campañas en borrador; el lanzamiento
   es siempre manual desde el panel, después del envío de prueba.
2. **Credenciales** solo en `~/.config/haiku/` del Mac mini o en `servidor/.env` del VPS;
   nunca en el repo ni en el chat.
3. **Datos personales** (CSV de listas, exportaciones) viven en el Mac mini, nunca en el repo.
4. **No tocar el SPF ni el DMARC de `mktbs.pe`** (son del correo de Zoho); el envío usa el
   subdominio `envios.mktbs.pe`.
5. **Baja en cada correo y supresión permanente** (Ley 29733).
6. **Firma** de todo documento: Aldo Nieto Bromley, Productor General. Acuerdos legales:
   Carlos Nieto Bromley, Gerente General (detenerse y preguntar).

## Dónde corre
- VPS público: listmonk, PostgreSQL, Caddy (`servidor/`).
- Mac mini (siempre encendido, vía Remote Control): genera campañas con haiku-web-engine,
  corre `listmonk.py` y el respaldo diario.

Pruebas: `python3 -m unittest discover tests` (requiere PyYAML para `listas`/`campana`).
