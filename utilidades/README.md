# Utilidades

## `dsld_extract_json.py`

Extrae de la descarga completa **en JSON** del DSLD los campos que no vienen en el CSV (atributos como *Vegan* u *Organic*, fechas de salida del mercado, relaciones entre etiquetas, porciones), y los guarda en un CSV pequeño, una fila por etiqueta. Solo usa la librería estándar de Python.

```bash
python utilidades/dsld_extract_json.py RUTA_AL_ZIP_O_CARPETA_JSON dsld_json_extra.csv
```

Columnas: `dsld_id`, `off_market`, `entry_date`, `off_market_date`, `other_events`, `claims`, `target_groups` (atributos y público, separados por « | »), `relaciones`, `n_relaciones`, `net_qty`, `net_unit`, `serving_unit`, `serving_min_qty`, `serving_max_qty`, `daily_servings_min`, `daily_servings_max`.

## `preparar_datos.py`

Genera los tres Parquet que usa la app (`app/datos/`) a partir de los CSV de la descarga completa y de `dsld_json_extra.csv`. Tarda menos de un minuto. Agrupa los nombres de ingredientes en tres capas (limpieza con las palabras de `calificadores.csv`, `sinonimos.csv` y comparación automática de escritura; ver `METODOLOGIA.md`), quita las filas de información nutrimental, normaliza las unidades y escribe `agrupaciones.csv` para auditar. Para corregir o agregar un sinónimo, edita `sinonimos.csv`; para una palabra que sobra, `calificadores.csv`; y vuelve a correrlo. `candidatos_calificadores.py` lista las palabras que más sobran en los ingredientes más comunes, para revisarlas.

```bash
python utilidades/preparar_datos.py DSLD-full-database-CSV/ dsld_json_extra.csv
```

Requiere pandas y pyarrow (`pip install -r requirements.txt`).
