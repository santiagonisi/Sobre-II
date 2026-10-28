import os
import tempfile
import unittest

from app import app, init_db


class ManoDeObraTestCase(unittest.TestCase):
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

    def test_default_categories_and_cost_calculation(self):
        response = self.client.get("/mano-de-obra")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Oficial Esp.", response.data)
        self.assertIn(b"420,79", response.data)
        self.assertIn(b"84,16", response.data)
        self.assertIn(b"504,95", response.data)
        self.assertIn(b"494,85", response.data)
        self.assertIn(b"70,69", response.data)
        self.assertIn(b"1.070,49", response.data)
        self.assertIn(b"53,52", response.data)
        self.assertIn(b"1.124,01", response.data)

    def test_category_create_update_and_delete(self):
        response = self.client.post(
            "/mano-de-obra",
            data={
                "action": "create",
                "name": "Capataz",
                "hourly_salary": "100",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Categor\xc3\xada agregada.", response.data)
        self.assertIn(b"267,12", response.data)

        response = self.client.post(
            "/mano-de-obra",
            data={
                "action": "update",
                "id": "5",
                "name": "Capataz principal",
                "hourly_salary": "200",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Capataz principal", response.data)
        self.assertIn(b"534,24", response.data)

        response = self.client.post(
            "/mano-de-obra",
            data={"action": "delete", "id": "5"},
            follow_redirects=True,
        )
        self.assertIn(b"Categor\xc3\xada eliminada.", response.data)
        self.assertNotIn(b"Capataz principal", response.data)

    def test_shared_rates_can_be_updated(self):
        response = self.client.post(
            "/mano-de-obra",
            data={
                "action": "save_rates",
                "attendance_bonus": "10",
                "social_benefits": "20",
                "art": "5",
                "other_costs": "2",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Porcentajes actualizados.", response.data)
        self.assertIn(b"10,00", response.data)
        self.assertIn(b"590,16", response.data)

    def test_rejects_negative_salary(self):
        response = self.client.post(
            "/mano-de-obra",
            data={
                "action": "create",
                "name": "Capataz",
                "hourly_salary": "-1",
            },
            follow_redirects=True,
        )

        self.assertIn(
            b"El salario por hora debe ser un n\xc3\xbamero igual o mayor que cero.",
            response.data,
        )
        self.assertNotIn(b"Capataz", response.data)


if __name__ == "__main__":
    unittest.main()
