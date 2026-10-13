# Solicitud de acceso a producción de Amazon SES

Se pega en la consola de SES → *Get set up* → *Request production access*.
Tipo de correo: **Marketing**. Sitio web: `https://expoperuindustrial.com`.
Revisar las cifras antes de enviar; Amazon responde en uno o dos días y puede pedir más datos.

---

MKT BS is a trade fair organizer in Lima, Peru (Expo Perú Industrial, FIMM, Expo
Energética, Mining Tech and related industrial fairs). We will use Amazon SES to send
our own newsletters and event communications to professionals who registered as
visitors or exhibitors at our fairs, or who requested information from us.

Volume: about 33,000 recipients, twice a week (around 300,000 emails per month),
plus occasional event announcements.

List management: recipients come from our own event registrations. Every email
includes a one-click unsubscribe link and the List-Unsubscribe headers; unsubscribes
are processed immediately and kept on a permanent suppression list, as required by
Peruvian data protection law (Ley 29733). We send through listmonk, a self-hosted
mailing list manager.

Bounces and complaints: SES bounce and complaint notifications are delivered through
SNS to listmonk, which blocklists hard bounces and complaints on the first event and
soft bounces after three. We will ramp up volume gradually over the first days,
starting with our most recent contacts, and monitor bounce and complaint rates after
each batch.

Sending domain: envios.mktbs.pe, authenticated with Easy DKIM, a custom MAIL FROM
domain and DMARC.
