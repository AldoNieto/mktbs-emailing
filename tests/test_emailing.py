"""Pruebas del conector con listmonk (solo las transformaciones, sin red)."""

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import listmonk as lm  # noqa: E402


class PrepararHtml(unittest.TestCase):
    def test_mide_enlaces_y_agrega_pixel_y_baja(self):
        html = '<a href="https://fimmperu.com/?utm_source=boletin">FIMM</a><a href="mailto:x@y.pe">x</a>'
        out = lm.preparar_html(html, "Lo mejor de 2026 & más")
        self.assertIn('href="https://fimmperu.com/?utm_source=boletin@TrackLink"', out)
        self.assertIn('href="mailto:x@y.pe"', out)
        self.assertIn("{{ UnsubscribeURL }}", out)
        self.assertIn("{{ TrackView }}", out)
        self.assertIn("Lo mejor de 2026 &amp; más", out)

    def test_rechaza_llaves_dobles(self):
        with self.assertRaises(ValueError):
            lm.preparar_html("<p>{{ algo }}</p>")


class CsvALista(unittest.TestCase):
    def test_convierte_columnas_y_atributos(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "energia.csv"
            ruta.write_text("email,name,empresa,sector,presente_en\n"
                            " Ana@Ejemplo.PE ,Ana Pérez,ACME,Energía,2025\n"
                            ",sin correo,,,\n"
                            "luis@ejemplo.pe,,,,\n", encoding="utf-8")
            datos, n = lm.csv_a_listmonk(ruta)
        filas = list(csv.DictReader(io.StringIO(datos)))
        self.assertEqual(n, 2)
        self.assertEqual(filas[0]["email"], "ana@ejemplo.pe")
        self.assertEqual(json.loads(filas[0]["attributes"]),
                         {"empresa": "ACME", "sector": "Energía", "presente_en": "2025"})
        self.assertEqual(filas[1]["name"], "luis")


class ConsultaRetarget(unittest.TestCase):
    def test_no_abrieron(self):
        q = lm.consulta_retarget(7, [3, 4], "no-abrieron")
        self.assertIn("list_id IN (3,4)", q)
        self.assertIn("NOT IN (SELECT subscriber_id FROM campaign_views WHERE campaign_id = 7", q)

    def test_clic(self):
        q = lm.consulta_retarget("7", [3], "clic")
        self.assertIn("FROM link_clicks WHERE campaign_id = 7", q)

    def test_solo_enteros(self):
        with self.assertRaises(ValueError):
            lm.consulta_retarget("7; DROP TABLE x", [3], "clic")


if __name__ == "__main__":
    unittest.main()
