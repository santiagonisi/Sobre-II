import os
import tempfile
import unittest

from app import app, init_db


class MaterialesTestCase(unittest.TestCase):
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

    def add_material(self, **overrides):
        values = {
            "action": "create",
            "name": "Cemento",
            "unit": "bolsa",
            "unit_cost": "100,00",
            "loss_percent": "2",
        }
        values.update(overrides)
        return self.client.post("/materiales", data=values, follow_redirects=True)

    def test_create_calculates_loss_and_final_unit_cost(self):
        response = self.add_material()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Material agregado.", response.data)
        self.assertIn(b"2,00", response.data)
        self.assertIn(b"102,00", response.data)

    def test_update_and_delete_material(self):
        response = self.add_material()
        self.assertIn(b"102,00", response.data)

        response = self.client.post(
            "/materiales",
            data={
                "action": "update",
                "id": "1",
                "name": "Cemento actualizado",
                "unit": "kg",
                "unit_cost": "200",
                "loss_percent": "5",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Cemento actualizado", response.data)
        self.assertIn(b"210,00", response.data)

        response = self.client.post(
            "/materiales",
            data={"action": "delete", "id": "1"},
            follow_redirects=True,
        )
        self.assertIn(b"Material eliminado.", response.data)
        self.assertIn(b"Todav\xc3\xada no hay materiales cargados.", response.data)

    def test_rejects_negative_cost(self):
        response = self.add_material(unit_cost="-1")

        self.assertIn(b"El costo debe ser un n\xc3\xbamero igual o mayor que cero.", response.data)
        self.assertIn(b"Todav\xc3\xada no hay materiales cargados.", response.data)

    def test_formatted_thousands_can_be_saved_again(self):
        response = self.add_material(unit_cost="160000", loss_percent="2")
        self.assertIn(b"163.200,00", response.data)

        response = self.client.post(
            "/materiales",
            data={
                "action": "update",
                "id": "1",
                "name": "Cemento",
                "unit": "bolsa",
                "unit_cost": "160.000,00",
                "loss_percent": "2,00",
            },
            follow_redirects=True,
        )

        self.assertIn(b"Material actualizado.", response.data)
        self.assertIn(b"163.200,00", response.data)


if __name__ == "__main__":
    unittest.main()
