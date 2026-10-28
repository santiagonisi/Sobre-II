import os
import tempfile
import unittest

from app import app, init_db


class CierreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = app.config["DATABASE"]
        app.config.update(
            TESTING=True,
            DATABASE=os.path.join(self.temp_dir.name, "test.sqlite3"),
        )
        init_db()
        self.client = app.test_client()

    def tearDown(self):
        app.config["DATABASE"] = self.original_database
        self.temp_dir.cleanup()

    def test_default_rates_and_coefficient(self):
        response = self.client.get("/cierre")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"value=\"5,00\"", response.data)
        self.assertIn(b"value=\"10,00\"", response.data)
        self.assertIn(b"value=\"3,00\"", response.data)
        self.assertIn(b"value=\"21,00\"", response.data)
        self.assertIn(b"value=\"2,50\"", response.data)
        self.assertIn(b"1,4653", response.data)

    def test_editing_rates_recalculates_coefficient(self):
        response = self.client.post(
            "/cierre",
            data={
                "general_expenses": "10",
                "benefits": "0",
                "financial_costs": "0",
                "vat": "0",
                "gross_receipts": "0",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Porcentajes del coeficiente actualizados.", response.data)
        self.assertIn(b"value=\"10,00\"", response.data)
        self.assertIn(b"1,1000", response.data)

    def test_rates_are_persisted_after_loading_another_page(self):
        self.client.post(
            "/cierre",
            data={
                "general_expenses": "12,5",
                "benefits": "0",
                "financial_costs": "0",
                "vat": "0",
                "gross_receipts": "0",
            },
        )

        response = self.client.get("/cierre")

        self.assertIn(b"value=\"12,50\"", response.data)
        self.assertIn(b"1,1250", response.data)

    def test_rejects_negative_rate_without_saving(self):
        response = self.client.post(
            "/cierre",
            data={
                "general_expenses": "-1",
                "benefits": "10",
                "financial_costs": "3",
                "vat": "21",
                "gross_receipts": "2,5",
            },
            follow_redirects=True,
        )

        self.assertIn(
            b"El porcentaje de gastos generales debe ser un n\xc3\xbamero igual o mayor que cero.",
            response.data,
        )
        self.assertIn(b"value=\"5,00\"", response.data)


if __name__ == "__main__":
    unittest.main()
