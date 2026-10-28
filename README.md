# Sobre II

Sobre II es un proyecto en desarrollo para organizar la elaboración y el seguimiento de presupuestos de obra. La aplicación contempla información de costos, recursos, análisis de precios y planificación del trabajo. Este documento se irá actualizando a medida que se definan e implementen sus componentes.

## Stack

- **Backend:** Python con Flask
- **Base de datos:** SQLite (prevista, aún no implementada)
- **Frontend:** plantillas Jinja2 con Bootstrap 5

## Ejecución

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

La aplicación queda disponible en http://127.0.0.1:5000.

## Estructura del proyecto

```text
Sobre2/
├── app.py
├── requirements.txt
├── instance/
│   └── sobre_ii.sqlite3
├── tests/
│   ├── test_materiales.py
│   ├── test_mano_de_obra.py
│   ├── test_transportes.py
│   ├── test_equipos.py
│   └── test_cierre.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── analisis_de_precios.html
│   ├── biblioteca.html
│   ├── cierre.html
│   ├── costo_directo.html
│   ├── costo_indirecto.html
│   ├── curva_inversion.html
│   ├── equipos.html
│   ├── mano_de_obra.html
│   ├── materiales.html
│   ├── transportes.html
│   └── plan_de_trabajo.html
├── .gitignore
└── README.md
```

La estructura refleja los archivos presentes actualmente; se ampliará a medida que se incorporen nuevas partes de la aplicación.

## Módulos

- **Análisis de precios:** análisis y composición de precios unitarios.
- **Biblioteca:** consulta y organización de elementos reutilizables del presupuesto.
- **Cierre:** resumen y cierre del presupuesto.
- **Costo directo:** registro y cálculo de costos directos.
- **Costo indirecto:** registro y cálculo de costos indirectos.
- **Curva de inversión:** visualización de la inversión a lo largo del tiempo.
- **Equipos:** gestión de equipos y sus costos.
- **Mano de obra:** gestión de recursos humanos y sus costos.
- **Materiales:** gestión de materiales y sus costos.
- **Transportes:** cálculo de costos de traslado asociados a materiales.
- **Plan de trabajo:** planificación de actividades y tiempos de ejecución.

El módulo Materiales permite crear, editar y eliminar materiales. El porcentaje de pérdidas se ingresa como número (por ejemplo, `2` equivale a `2 %`). El costo de pérdidas es `costo por unidad × porcentaje / 100`, y el costo unitario final es la suma del costo base y las pérdidas.

El módulo Mano de obra permite gestionar categorías y salarios por hora, además de configurar los porcentajes comunes. El premio se calcula sobre el salario; mejoras sociales y ART, sobre el jornal directo; otros conceptos, sobre el jornal total.

El módulo Transportes vincula cada registro con un material para obtener su unidad y porcentaje de pérdidas. Calcula el costo sin pérdidas como `distancia × tarifa por unidad/km`; el costo con pérdidas suma a ese resultado el porcentaje de pérdidas del material.

El módulo Equipos mantiene un catálogo vacío y reutilizable, sin precargar los equipos del ejemplo. Permite editar la cotización USD, el valor residual (20 %), interés anual (8 %), reparaciones/repuestos (70 %) y lubricantes (30 %). Cada equipo calcula costo actual en pesos, valor residual, amortización e intereses por hora con la fórmula de la planilla, reparaciones, combustible, lubricantes y costo total por hora. La cotización inicial queda sin definir y debe cargarse antes de agregar equipos.

El módulo Cierre presenta una calculadora temporal del coeficiente de resumen, con porcentajes editables. Los valores iniciales (5 %, 10 %, 3 %, 21 % y 2,5 %) provienen de la planilla de ejemplo; actualmente se comparten y se guardan en SQLite, no están vinculados a una obra específica.

Los módulos implementados guardan sus datos en SQLite dentro de `instance/`, carpeta excluida de Git. Los demás módulos tienen una ruta, entrada en el menú y plantilla inicial; su comportamiento se documentará a medida que se implemente.
