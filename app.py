from flask import Flask, render_template

app = Flask(__name__)

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


def make_view(endpoint, title, description):
    def view():
        return render_template(f"{endpoint}.html", title=title, description=description)

    view.__name__ = endpoint
    return view


for _endpoint, _title, _description in MODULES:
    app.add_url_rule(
        f"/{_endpoint.replace('_', '-')}",
        _endpoint,
        make_view(_endpoint, _title, _description),
    )


if __name__ == "__main__":
    app.run(debug=True)
