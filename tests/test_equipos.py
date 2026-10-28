import os
import tempfile
import unittest

from app import app, init_db


class EquiposTestCase(unittest.TestCase):
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

    def configure(self, **overrides):
        values = {
            "action": "save_settings",
            "exchange_rate": "1000",
            "residual_percent": "20",
            "annual_interest_percent": "8",
            "repair_percent": "70",
            "lubricant_percent": "30",
        }
        values.update(overrides)
        return self.client.post("/equipos", data=values, follow_redirects=True)

    def add_equipment(self, **overrides):
        values = {
            "action": "create",
            "designation": "Equipo de prueba",
            "horsepower": "100",
            "cost_usd": "10000",
            "useful_life_hours": "10000",
            "annual_use_hours": "2000",
            "fuel_type": "diesel",
            "fuel_price_per_liter": "1200",
            "fuel_consumption_per_hour": "0,12",
        }
        values.update(overrides)
        return self.client.post("/equipos", data=values, follow_redirects=True)

    def test_catalog_starts_empty_without_example_equipment(self):
        response = self.client.get("/equipos")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"El cat\xc3\xa1logo est\xc3\xa1 vac\xc3\xado.", response.data)
        self.assertIn(b"Configur\xc3\xa1 la cotizaci\xc3\xb3n del d\xc3\xb3lar", response.data)
        self.assertNotIn(b"Aplanadora vibrante", response.data)

    def test_equipment_requires_exchange_rate(self):
        response = self.add_equipment()

        self.assertIn(
            b"Configur\xc3\xa1 la cotizaci\xc3\xb3n del d\xc3\xb3lar antes de cargar equipos.",
            response.data,
        )
        self.assertNotIn(b"Equipo de prueba", response.data)

    def test_create_calculates_costs_using_row_values_and_formula(self):
        self.configure()
        response = self.add_equipment()

        self.assertIn(b"Equipo agregado al cat\xc3\xa1logo.", response.data)
        self.assertIn(b"10.000.000,00", response.data)
        self.assertIn(b"2.000.000,00", response.data)
        self.assertIn(b"960,00", response.data)
        self.assertIn(b"560,00", response.data)
        self.assertIn(b"144,00", response.data)
        self.assertIn(b"43,20", response.data)
        self.assertIn(b"187,20", response.data)
        self.assertIn(b"1.707,20", response.data)

    def test_equipment_can_be_updated_and_deleted(self):
        self.configure()
        self.add_equipment()

        response = self.client.post(
            "/equipos",
            data={
                "action": "update",
                "id": "1",
                "designation": "Equipo actualizado",
                "horsepower": "120",
                "cost_usd": "20000",
                "useful_life_hours": "10000",
                "annual_use_hours": "2000",
                "fuel_type": "diesel",
                "fuel_price_per_liter": "1200",
                "fuel_consumption_per_hour": "0,12",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Equipo actualizado", response.data)
        self.assertIn(b"3.227,20", response.data)

        response = self.client.post(
            "/equipos",
            data={"action": "delete", "id": "1"},
            follow_redirects=True,
        )
        self.assertIn(b"Equipo eliminado del cat\xc3\xa1logo.", response.data)
        self.assertIn(b"El cat\xc3\xa1logo est\xc3\xa1 vac\xc3\xado.", response.data)

    def test_non_diesel_equipment_does_not_add_fuel_or_lubricant_costs(self):
        self.configure()
        response = self.add_equipment(fuel_type="-----")

        self.assertIn(b"0,00", response.data)
        self.assertIn(b"1.520,00", response.data)

    def test_settings_are_editable_and_recalculate_existing_equipment(self):
        self.configure()
        self.add_equipment()
        response = self.configure(
            exchange_rate="2000",
            residual_percent="10",
            annual_interest_percent="5",
            repair_percent="50",
            lubricant_percent="20",
        )

        self.assertIn(b"Par\xc3\xa1metros de equipos actualizados.", response.data)
        self.assertIn(b"20.000.000,00", response.data)
        self.assertIn(b"2.000.000,00", response.data)
        self.assertIn(b"2.025,00", response.data)
        self.assertIn(b"900,00", response.data)
        self.assertIn(b"28,80", response.data)
        self.assertIn(b"3.097,80", response.data)

    def test_rejects_zero_useful_life(self):
        self.configure()
        response = self.add_equipment(useful_life_hours="0")

        self.assertIn(
            b"La vida \xc3\xbatil y el uso anual deben ser mayores que cero.",
            response.data,
        )
        self.assertNotIn(b"Equipo de prueba", response.data)

    def test_rejects_zero_exchange_rate(self):
        response = self.configure(exchange_rate="0")

        self.assertIn(
            b"La cotizaci\xc3\xb3n del d\xc3\xb3lar debe ser mayor que cero.",
            response.data,
        )
        self.assertIn(b"value=\"0,00\"", response.data)


if __name__ == "__main__":
    unittest.main()
