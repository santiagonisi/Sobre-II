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


def make_view(endpoint, title, description):
    def view():
        return render_template(f"{endpoint}.html", title=title, description=description)

    view.__name__ = endpoint
    return view


for _endpoint, _title, _description in MODULES:
    if _endpoint in {"materiales", "mano_de_obra"}:
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
