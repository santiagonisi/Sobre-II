import os
import secrets
import sqlite3
from decimal import Decimal, InvalidOperation

from flask import Flask, current_app, flash, g, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["DATABASE"] = os.path.join(app.instance_path, "sobre_ii.sqlite3")

# (endpoint, titulo, descripcion); el orden define el menu de navegacion
MODULES = [
    ("materiales", "Materiales", "Gestión de materiales y sus costos."),
    ("transportes", "Transportes", "Costos de transporte asociados a materiales."),
    ("mano_de_obra", "Mano de obra", "Gestión de recursos humanos y sus costos."),
    ("equipos", "Equipos", "Gestión de equipos y sus costos."),
    ("analisis_de_precios", "Análisis de precios", "Composición de precios unitarios."),
    ("biblioteca", "Biblioteca", "Elementos reutilizables del presupuesto."),
    ("costo_directo", "Costo directo", "Registro y cálculo de costos directos."),
    ("costo_indirecto", "Costo indirecto", "Registro y cálculo de costos indirectos."),
    ("plan_de_trabajo", "Plan de trabajo", "Planificación de actividades y tiempos."),
    ("curva_inversion", "Curva de inversión", "Inversión a lo largo del tiempo."),
    ("cierre", "Cierre", "Resumen y cierre del presupuesto."),
]


@app.context_processor
def inject_modules():
    return {"modules": MODULES}


@app.route("/")
def index():
    return render_template("index.html")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    db = sqlite3.connect(app.config["DATABASE"])
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_cost TEXT NOT NULL,
                loss_percent TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS transports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
                origin TEXT NOT NULL,
                distance_km TEXT NOT NULL,
                rate_per_unit_km TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS labor_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hourly_salary TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS labor_rates (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                attendance_bonus TEXT NOT NULL,
                social_benefits TEXT NOT NULL,
                art TEXT NOT NULL,
                other_costs TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                exchange_rate TEXT NOT NULL,
                residual_percent TEXT NOT NULL,
                annual_interest_percent TEXT NOT NULL,
                repair_percent TEXT NOT NULL,
                lubricant_percent TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                designation TEXT NOT NULL,
                horsepower TEXT NOT NULL,
                cost_usd TEXT NOT NULL,
                useful_life_hours TEXT NOT NULL,
                annual_use_hours TEXT NOT NULL,
                fuel_type TEXT NOT NULL,
                fuel_price_per_liter TEXT NOT NULL,
                fuel_consumption_per_hour TEXT NOT NULL
            )
            """
        )
        category_count = db.execute(
            "SELECT COUNT(*) FROM labor_categories"
        ).fetchone()[0]
        if category_count == 0:
            db.executemany(
                "INSERT INTO labor_categories (name, hourly_salary) VALUES (?, ?)",
                [
                    ("Oficial Esp.", "420.79"),
                    ("Oficial", "358.55"),
                    ("Medio Oficial", "330.59"),
                    ("Ayudante", "303.49"),
                ],
            )
        db.execute(
            """
            INSERT OR IGNORE INTO labor_rates
                (id, attendance_bonus, social_benefits, art, other_costs)
            VALUES (1, '20', '98', '14', '5')
            """
        )
        db.execute(
            """
            INSERT OR IGNORE INTO equipment_settings
                (id, exchange_rate, residual_percent, annual_interest_percent,
                 repair_percent, lubricant_percent)
            VALUES (1, '0', '20', '8', '70', '30')
            """
        )
        db.commit()
    finally:
        db.close()


def parse_decimal(value, field_name):
    normalized = value.strip()
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", ".")

    try:
        number = Decimal(normalized)
    except (InvalidOperation, AttributeError):
        raise ValueError(f"{field_name} debe ser un número válido.") from None

    if not number.is_finite() or number < 0:
        raise ValueError(f"{field_name} debe ser un número igual o mayor que cero.")
    return number


def format_number(value):
    formatted = f"{Decimal(value):,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


@app.route("/materiales", methods=["GET", "POST"])
def materiales():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "delete":
                material_id = int(request.form["id"])
                db.execute("DELETE FROM materials WHERE id = ?", (material_id,))
                db.commit()
                flash("Material eliminado.", "success")
            elif action in {"create", "update"}:
                name = request.form.get("name", "").strip()
                unit = request.form.get("unit", "").strip()
                if not name or not unit:
                    raise ValueError("Completá el material y la unidad.")

                unit_cost = parse_decimal(request.form.get("unit_cost", ""), "El costo")
                loss_percent = parse_decimal(
                    request.form.get("loss_percent", ""), "El porcentaje de pérdidas"
                )
                values = (name, unit, format(unit_cost, "f"), format(loss_percent, "f"))

                if action == "create":
                    db.execute(
                        """
                        INSERT INTO materials (name, unit, unit_cost, loss_percent)
                        VALUES (?, ?, ?, ?)
                        """,
                        values,
                    )
                    flash("Material agregado.", "success")
                else:
                    material_id = int(request.form["id"])
                    cursor = db.execute(
                        """
                        UPDATE materials
                        SET name = ?, unit = ?, unit_cost = ?, loss_percent = ?
                        WHERE id = ?
                        """,
                        (*values, material_id),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("No se encontró el material para actualizar.")
                    flash("Material actualizado.", "success")
                db.commit()
            else:
                raise ValueError("La operación solicitada no es válida.")
        except (KeyError, ValueError) as error:
            flash(str(error) or "El identificador del material no es válido.", "danger")
        except sqlite3.IntegrityError:
            db.rollback()
            flash(
                "No se puede eliminar el material porque está asociado a un transporte.",
                "danger",
            )

        return redirect(url_for("materiales"))

    materials = []
    for row in db.execute("SELECT * FROM materials ORDER BY name COLLATE NOCASE"):
        unit_cost = Decimal(row["unit_cost"])
        loss_percent = Decimal(row["loss_percent"])
        loss_cost = unit_cost * loss_percent / Decimal("100")
        materials.append(
            {
                **dict(row),
                "loss_cost": format_number(loss_cost),
                "total_unit_cost": format_number(unit_cost + loss_cost),
                "unit_cost_display": format_number(unit_cost),
                "loss_percent_display": format_number(loss_percent),
            }
        )

    return render_template(
        "materiales.html",
        title="Materiales",
        description="Gestión de materiales y sus costos.",
        materials=materials,
    )


@app.route("/transportes", methods=["GET", "POST"])
def transportes():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "delete":
                transport_id = int(request.form["id"])
                cursor = db.execute("DELETE FROM transports WHERE id = ?", (transport_id,))
                if cursor.rowcount == 0:
                    raise ValueError("No se encontró el transporte para eliminar.")
                flash("Transporte eliminado.", "success")
            elif action in {"create", "update"}:
                try:
                    material_id = int(request.form.get("material_id", ""))
                except ValueError:
                    raise ValueError("Seleccioná un material válido.") from None
                material = db.execute(
                    "SELECT id FROM materials WHERE id = ?", (material_id,)
                ).fetchone()
                if material is None:
                    raise ValueError("Seleccioná un material válido.")

                origin = request.form.get("origin", "").strip()
                if not origin:
                    raise ValueError("Completá el origen.")
                distance = parse_decimal(
                    request.form.get("distance_km", ""), "La distancia"
                )
                rate = parse_decimal(
                    request.form.get("rate_per_unit_km", ""),
                    "El costo de transporte por unidad y kilómetro",
                )
                values = (
                    material_id,
                    origin,
                    format(distance, "f"),
                    format(rate, "f"),
                )

                if action == "create":
                    db.execute(
                        """
                        INSERT INTO transports
                            (material_id, origin, distance_km, rate_per_unit_km)
                        VALUES (?, ?, ?, ?)
                        """,
                        values,
                    )
                    flash("Transporte agregado.", "success")
                else:
                    transport_id = int(request.form["id"])
                    cursor = db.execute(
                        """
                        UPDATE transports
                        SET material_id = ?, origin = ?, distance_km = ?,
                            rate_per_unit_km = ?
                        WHERE id = ?
                        """,
                        (*values, transport_id),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("No se encontró el transporte para actualizar.")
                    flash("Transporte actualizado.", "success")
            else:
                raise ValueError("La operación solicitada no es válida.")
            db.commit()
        except (KeyError, ValueError) as error:
            flash(str(error) or "El identificador del transporte no es válido.", "danger")

        return redirect(url_for("transportes"))

    materials = db.execute(
        "SELECT id, name, unit FROM materials ORDER BY name COLLATE NOCASE"
    ).fetchall()
    transports = []
    rows = db.execute(
        """
        SELECT t.*, m.name AS material_name, m.unit, m.loss_percent
        FROM transports AS t
        JOIN materials AS m ON m.id = t.material_id
        ORDER BY m.name COLLATE NOCASE, t.origin COLLATE NOCASE, t.id
        """
    )
    for row in rows:
        distance = Decimal(row["distance_km"])
        rate = Decimal(row["rate_per_unit_km"])
        loss_percent = Decimal(row["loss_percent"])
        cost_without_losses = distance * rate
        loss_cost = cost_without_losses * loss_percent / Decimal("100")
        transports.append(
            {
                **dict(row),
                "distance_display": format_number(distance),
                "rate_display": format_number(rate),
                "loss_percent_display": format_number(loss_percent),
                "cost_without_losses": format_number(cost_without_losses),
                "loss_cost": format_number(loss_cost),
                "cost_with_losses": format_number(cost_without_losses + loss_cost),
            }
        )

    return render_template(
        "transportes.html",
        title="Transportes",
        description="Costos de transporte por material, origen y distancia.",
        materials=materials,
        transports=transports,
    )


@app.route("/mano-de-obra", methods=["GET", "POST"])
def mano_de_obra():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "delete":
                category_id = int(request.form["id"])
                cursor = db.execute(
                    "DELETE FROM labor_categories WHERE id = ?", (category_id,)
                )
                if cursor.rowcount == 0:
                    raise ValueError("No se encontró la categoría para eliminar.")
                flash("Categoría eliminada.", "success")
            elif action in {"create", "update"}:
                name = request.form.get("name", "").strip()
                if not name:
                    raise ValueError("Completá la categoría.")
                salary = parse_decimal(
                    request.form.get("hourly_salary", ""), "El salario por hora"
                )
                values = (name, format(salary, "f"))

                if action == "create":
                    db.execute(
                        "INSERT INTO labor_categories (name, hourly_salary) VALUES (?, ?)",
                        values,
                    )
                    flash("Categoría agregada.", "success")
                else:
                    category_id = int(request.form["id"])
                    cursor = db.execute(
                        """
                        UPDATE labor_categories SET name = ?, hourly_salary = ?
                        WHERE id = ?
                        """,
                        (*values, category_id),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("No se encontró la categoría para actualizar.")
                    flash("Categoría actualizada.", "success")
            elif action == "save_rates":
                rates = (
                    parse_decimal(
                        request.form.get("attendance_bonus", ""),
                        "El porcentaje de premio por asistencia",
                    ),
                    parse_decimal(
                        request.form.get("social_benefits", ""),
                        "El porcentaje de mejoras sociales",
                    ),
                    parse_decimal(request.form.get("art", ""), "El porcentaje de ART"),
                    parse_decimal(
                        request.form.get("other_costs", ""),
                        "El porcentaje de otros conceptos",
                    ),
                )
                db.execute(
                    """
                    UPDATE labor_rates
                    SET attendance_bonus = ?, social_benefits = ?, art = ?, other_costs = ?
                    WHERE id = 1
                    """,
                    tuple(format(rate, "f") for rate in rates),
                )
                flash("Porcentajes actualizados.", "success")
            else:
                raise ValueError("La operación solicitada no es válida.")
            db.commit()
        except (KeyError, ValueError) as error:
            flash(str(error) or "El identificador de la categoría no es válido.", "danger")

        return redirect(url_for("mano_de_obra"))

    rates_row = db.execute("SELECT * FROM labor_rates WHERE id = 1").fetchone()
    rates = {key: Decimal(rates_row[key]) for key in rates_row.keys() if key != "id"}
    categories = []
    for row in db.execute(
        "SELECT * FROM labor_categories ORDER BY id"
    ):
        salary = Decimal(row["hourly_salary"])
        attendance_bonus = salary * rates["attendance_bonus"] / Decimal("100")
        direct_journal = salary + attendance_bonus
        social_benefits = direct_journal * rates["social_benefits"] / Decimal("100")
        art = direct_journal * rates["art"] / Decimal("100")
        total_journal = direct_journal + social_benefits + art
        other_costs = total_journal * rates["other_costs"] / Decimal("100")
        categories.append(
            {
                **dict(row),
                "salary_display": format_number(salary),
                "attendance_bonus_display": format_number(attendance_bonus),
                "direct_journal_display": format_number(direct_journal),
                "social_benefits_display": format_number(social_benefits),
                "art_display": format_number(art),
                "total_journal_display": format_number(total_journal),
                "other_costs_display": format_number(other_costs),
                "total_cost_display": format_number(total_journal + other_costs),
            }
        )

    return render_template(
        "mano_de_obra.html",
        title="Mano de obra",
        description="Categorías de personal y costo total por hora.",
        categories=categories,
        rates={key: format_number(value) for key, value in rates.items()},
    )


@app.route("/equipos", methods=["GET", "POST"])
def equipos():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "delete":
                equipment_id = int(request.form["id"])
                cursor = db.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
                if cursor.rowcount == 0:
                    raise ValueError("No se encontró el equipo para eliminar.")
                flash("Equipo eliminado del catálogo.", "success")
            elif action == "save_settings":
                settings = (
                    parse_decimal(
                        request.form.get("exchange_rate", ""),
                        "La cotización del dólar",
                    ),
                    parse_decimal(
                        request.form.get("residual_percent", ""),
                        "El porcentaje de valor residual",
                    ),
                    parse_decimal(
                        request.form.get("annual_interest_percent", ""),
                        "La tasa anual de interés",
                    ),
                    parse_decimal(
                        request.form.get("repair_percent", ""),
                        "El porcentaje de reparaciones y repuestos",
                    ),
                    parse_decimal(
                        request.form.get("lubricant_percent", ""),
                        "El porcentaje de lubricantes",
                    ),
                )
                if settings[0] == 0:
                    raise ValueError("La cotización del dólar debe ser mayor que cero.")
                if settings[1] > 100:
                    raise ValueError("El valor residual no puede superar el 100 %.")
                db.execute(
                    """
                    UPDATE equipment_settings
                    SET exchange_rate = ?, residual_percent = ?,
                        annual_interest_percent = ?, repair_percent = ?,
                        lubricant_percent = ?
                    WHERE id = 1
                    """,
                    tuple(format(value, "f") for value in settings),
                )
                flash("Parámetros de equipos actualizados.", "success")
            elif action in {"create", "update"}:
                designation = request.form.get("designation", "").strip()
                fuel_type = request.form.get("fuel_type", "").strip()
                if not designation or not fuel_type:
                    raise ValueError("Completá la designación y el tipo de combustible.")

                horsepower = parse_decimal(request.form.get("horsepower", ""), "HP")
                cost_usd = parse_decimal(
                    request.form.get("cost_usd", ""), "El costo actual en USD"
                )
                useful_life = parse_decimal(
                    request.form.get("useful_life_hours", ""),
                    "La vida útil",
                )
                annual_use = parse_decimal(
                    request.form.get("annual_use_hours", ""),
                    "El uso anual",
                )
                fuel_price = parse_decimal(
                    request.form.get("fuel_price_per_liter", ""),
                    "El precio del combustible por litro",
                )
                fuel_consumption = parse_decimal(
                    request.form.get("fuel_consumption_per_hour", ""),
                    "El consumo de combustible por hora",
                )
                if useful_life == 0 or annual_use == 0:
                    raise ValueError("La vida útil y el uso anual deben ser mayores que cero.")

                settings_row = db.execute(
                    "SELECT exchange_rate FROM equipment_settings WHERE id = 1"
                ).fetchone()
                if Decimal(settings_row["exchange_rate"]) == 0:
                    raise ValueError("Configurá la cotización del dólar antes de cargar equipos.")

                values = (
                    designation,
                    format(horsepower, "f"),
                    format(cost_usd, "f"),
                    format(useful_life, "f"),
                    format(annual_use, "f"),
                    fuel_type,
                    format(fuel_price, "f"),
                    format(fuel_consumption, "f"),
                )
                if action == "create":
                    db.execute(
                        """
                        INSERT INTO equipment
                            (designation, horsepower, cost_usd, useful_life_hours,
                             annual_use_hours, fuel_type, fuel_price_per_liter,
                             fuel_consumption_per_hour)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                    flash("Equipo agregado al catálogo.", "success")
                else:
                    equipment_id = int(request.form["id"])
                    cursor = db.execute(
                        """
                        UPDATE equipment
                        SET designation = ?, horsepower = ?, cost_usd = ?,
                            useful_life_hours = ?, annual_use_hours = ?, fuel_type = ?,
                            fuel_price_per_liter = ?, fuel_consumption_per_hour = ?
                        WHERE id = ?
                        """,
                        (*values, equipment_id),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("No se encontró el equipo para actualizar.")
                    flash("Equipo actualizado.", "success")
            else:
                raise ValueError("La operación solicitada no es válida.")
            db.commit()
        except (KeyError, ValueError) as error:
            flash(str(error) or "El identificador del equipo no es válido.", "danger")

        return redirect(url_for("equipos"))

    settings_row = db.execute(
        "SELECT * FROM equipment_settings WHERE id = 1"
    ).fetchone()
    settings = {
        key: Decimal(settings_row[key])
        for key in settings_row.keys()
        if key != "id"
    }
    exchange_rate = settings["exchange_rate"]
    equipment_list = []
    for row in db.execute("SELECT * FROM equipment ORDER BY designation COLLATE NOCASE"):
        cost_usd = Decimal(row["cost_usd"])
        useful_life = Decimal(row["useful_life_hours"])
        annual_use = Decimal(row["annual_use_hours"])
        fuel_price = Decimal(row["fuel_price_per_liter"])
        fuel_consumption = Decimal(row["fuel_consumption_per_hour"])

        current_cost = cost_usd * exchange_rate
        residual_value = current_cost * settings["residual_percent"] / Decimal("100")
        depreciable_value = current_cost - residual_value
        depreciation_per_hour = depreciable_value / useful_life
        amortization_and_interest = depreciation_per_hour + (
            depreciable_value
            * settings["annual_interest_percent"]
            / Decimal("100")
            * Decimal("0.5")
            / annual_use
        )
        repairs_per_hour = (
            depreciation_per_hour * settings["repair_percent"] / Decimal("100")
        )
        fuel_cost_per_hour = (
            fuel_price * fuel_consumption
            if row["fuel_type"].strip().casefold() == "diesel"
            else Decimal("0")
        )
        lubricant_cost_per_hour = (
            fuel_cost_per_hour * settings["lubricant_percent"] / Decimal("100")
        )
        fuel_and_lubricants = fuel_cost_per_hour + lubricant_cost_per_hour
        total_cost_per_hour = (
            amortization_and_interest + repairs_per_hour + fuel_and_lubricants
        )
        equipment_list.append(
            {
                **dict(row),
                "horsepower_display": format_number(Decimal(row["horsepower"])),
                "cost_usd_display": format_number(cost_usd),
                "current_cost_display": format_number(current_cost),
                "residual_value_display": format_number(residual_value),
                "useful_life_display": format_number(useful_life),
                "annual_use_display": format_number(annual_use),
                "amortization_and_interest_display": format_number(
                    amortization_and_interest
                ),
                "repairs_per_hour_display": format_number(repairs_per_hour),
                "fuel_price_display": format_number(fuel_price),
                "fuel_consumption_display": format_number(fuel_consumption),
                "fuel_cost_per_hour_display": format_number(fuel_cost_per_hour),
                "lubricant_cost_per_hour_display": format_number(
                    lubricant_cost_per_hour
                ),
                "fuel_and_lubricants_display": format_number(fuel_and_lubricants),
                "total_cost_per_hour_display": format_number(total_cost_per_hour),
            }
        )

    return render_template(
        "equipos.html",
        title="Equipos",
        description="Catálogo reutilizable de equipos y cálculo de su costo por hora.",
        equipment=equipment_list,
        settings={
            key: format_number(value) for key, value in settings.items()
        },
        exchange_rate_configured=exchange_rate > 0,
    )


def make_view(endpoint, title, description):
    def view():
        return render_template(f"{endpoint}.html", title=title, description=description)

    view.__name__ = endpoint
    return view


for _endpoint, _title, _description in MODULES:
    if _endpoint in {"materiales", "transportes", "mano_de_obra", "equipos"}:
        continue
    app.add_url_rule(
        f"/{_endpoint.replace('_', '-')}",
        _endpoint,
        make_view(_endpoint, _title, _description),
    )


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
