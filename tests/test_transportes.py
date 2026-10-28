import os
import tempfile
import unittest

from app import app, init_db


class TransportesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = app.config["DATABASE"]
        app.config.update(
            TESTING=True,
            DATABASE=os.path.join(self.temp_dir.name, "test.sqlite3"),
        )
        init_db()
        self.client = app.test_client()
        self.client.post(
            "/materiales",
            data={
                "action": "create",
                "name": "Cemento",
                "unit": "bolsa",
                "unit_cost": "100",
                "loss_percent": "2",
            },
        )

    def tearDown(self):
        app.config["DATABASE"] = self.original_database
        self.temp_dir.cleanup()

    def add_transport(self, **overrides):
        values = {
            "action": "create",
            "material_id": "1",
            "origin": "Cantera",
            "distance_km": "200",
            "rate_per_unit_km": "1,25",
        }
        values.update(overrides)
        return self.client.post("/transportes", data=values, follow_redirects=True)

    def test_create_calculates_cost_and_material_losses(self):
        response = self.add_transport()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Transporte agregado.", response.data)
        self.assertIn(b"Cantera", response.data)
        self.assertIn(b"bolsa", response.data)
        self.assertIn(b"250,00", response.data)
        self.assertIn(b"2,00", response.data)
        self.assertIn(b"5,00", response.data)
        self.assertIn(b"255,00", response.data)

    def test_transport_uses_current_material_loss_percentage(self):
        self.add_transport()

        self.client.post(
            "/materiales",
            data={
                "action": "update",
                "id": "1",
                "name": "Cemento",
                "unit": "bolsa",
                "unit_cost": "100",
                "loss_percent": "10",
            },
        )
        response = self.client.get("/transportes")

        self.assertIn(b"10,00", response.data)
        self.assertIn(b"25,00", response.data)
        self.assertIn(b"275,00", response.data)

    def test_transport_can_be_updated_and_deleted(self):
        self.add_transport()

        response = self.client.post(
            "/transportes",
            data={
                "action": "update",
                "id": "1",
                "material_id": "1",
                "origin": "Puerto",
                "distance_km": "100",
                "rate_per_unit_km": "2",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Transporte actualizado.", response.data)
        self.assertIn(b"Puerto", response.data)
        self.assertIn(b"200,00", response.data)
        self.assertIn(b"204,00", response.data)

        response = self.client.post(
            "/transportes",
            data={"action": "delete", "id": "1"},
            follow_redirects=True,
        )
        self.assertIn(b"Transporte eliminado.", response.data)
        self.assertIn(b"Todav\xc3\xada no hay transportes cargados.", response.data)

    def test_rejects_negative_distance(self):
        response = self.add_transport(distance_km="-1")

        self.assertIn(
            b"La distancia debe ser un n\xc3\xbamero igual o mayor que cero.",
            response.data,
        )
        self.assertIn(b"Todav\xc3\xada no hay transportes cargados.", response.data)

    def test_material_in_use_cannot_be_deleted(self):
        self.add_transport()

        response = self.client.post(
            "/materiales",
            data={"action": "delete", "id": "1"},
            follow_redirects=True,
        )

        self.assertIn(
            b"No se puede eliminar el material porque est\xc3\xa1 asociado a un transporte.",
            response.data,
        )
        self.assertIn(b"Cemento", response.data)
        self.assertIn(b"Cantera", self.client.get("/transportes").data)

    def test_requires_existing_material(self):
        self.client.post(
            "/materiales",
            data={"action": "delete", "id": "1"},
        )
        response = self.client.get("/transportes")

        self.assertIn(b"Primero carg\xc3\xa1 al menos un material", response.data)
        self.assertIn(b"/materiales", response.data)


if __name__ == "__main__":
    unittest.main()
