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


def make_view(endpoint, title, description):
    def view():
        return render_template(f"{endpoint}.html", title=title, description=description)

    view.__name__ = endpoint
    return view


for _endpoint, _title, _description in MODULES:
    if _endpoint == "materiales":
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
