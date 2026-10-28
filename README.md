# Buscador de suplementos (DSLD) · Dietary supplement label search

**English summary.** An interactive **Streamlit app** to search the NIH [Dietary Supplement Label Database (DSLD)](https://dsld.od.nih.gov/): **214,780 U.S. supplement labels** of every product type. It opens filtered to botanical (herbal) products and a filter lets you switch to vitamins, minerals, amino acids, fats and the rest. Built for product developers: search by ingredient, title keyword, brand, form or label claim (vegan, organic…), get reference dose ranges by form, spot ingredient × form gaps and compare brands. Built with Python, pandas, Altair and Streamlit.

**App:** [abrir el buscador](https://TU-APP.streamlit.app) <!-- reemplaza con el link de tu app -->

![Buscador](app/capturas/buscador.png)

## Qué hay aquí

```
├── app/                       ← app de Streamlit
│   ├── app.py
│   ├── datos/                 ← datos ya preparados en Parquet (~19 MB)
│   └── capturas/
├── utilidades/
│   ├── dsld_extract_json.py   ← extrae campos del JSON del DSLD
│   └── preparar_datos.py      ← genera los Parquet de la app
├── requirements.txt           ← dependencias de la app
└── DESPLIEGUE.md              ← cómo publicar la app gratis en Streamlit Community Cloud
```

## La app

Pensada para **desarrollo de producto**. La app abre con los productos **botánicos** (*Botanical* y *Botanical with Nutrients*, 67,449 etiquetas); el filtro **Tipo de producto** abre el resto (vitaminas, minerales, aminoácidos, grasas, otras combinaciones…). Los filtros de la barra lateral (tipo, ingrediente, palabra del título, marca, forma, atributos, estatus y año) se aplican a cuatro secciones:

- **Buscador:** indicadores, formas, marcas, con qué se combina, atributos declarados, dosis y palabras de los títulos, más la lista de productos con link a la etiqueta original y descarga en CSV.
- **Dosis de referencia:** rango de dosis declaradas de un ingrediente por forma (P10, Q1, mediana, Q3, P90), en la unidad más usada del ingrediente.
- **Huecos de mercado:** mapa ingrediente × forma con el número de etiquetas; las celdas claras son combinaciones poco exploradas.
- **Comparar marcas:** hasta tres marcas lado a lado (formas, atributos e ingredientes principales).

Para correrla en tu computadora:

```bash
pip install -r requirements.txt
streamlit run app/app.py
```

Para regenerar los datos (por ejemplo, con una descarga más reciente del DSLD):

```bash
python utilidades/dsld_extract_json.py DSLD-full-database-JSON.zip dsld_json_extra.csv
python utilidades/preparar_datos.py DSLD-full-database-CSV/ dsld_json_extra.csv
```

## Decisiones que conviene conocer

- **Cargas masivas:** cuatro marcas (TerraVita Premium Collection, TerraVita, Herbal Terra y Hawaii Pharm) subieron miles de etiquetas por lotes y distorsionan los resultados; la app las excluye por defecto.
- **Año de entrada ≠ lanzamiento:** es la fecha en que se capturó la etiqueta en el DSLD.
- **Etiquetas, no productos:** una misma presentación puede tener varias etiquetas (tamaños, sabores).
- **Nombres de ingredientes:** se limpian de forma aproximada (*turmeric root extract* cuenta como *turmeric*) y las vitaminas con varios nombres se agrupan (*ascorbic acid* = *vitamin C*).
- **Información nutrimental:** las filas de calorías, grasa total, carbohidratos y azúcares se quitan de la lista de ingredientes.
- **Dosis:** son las de la etiqueta por porción; la vitamina D se convierte de IU a mcg, y las IU de las vitaminas A y E no se comparan porque dependen de la forma química.

## Limitaciones

- Los datos son lo **declarado en etiquetas**; el NIH no verifica su exactitud.
- No hay ventas ni demanda: el proyecto describe qué existe, no qué se vende ni qué funciona.
- Son datos de EE. UU.; no equivalen al mercado mexicano.

## Fuente de los datos

NIH Office of Dietary Supplements, Dietary Supplement Label Database (DSLD), descarga completa de enero de 2026 (214,780 etiquetas).
