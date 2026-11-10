#!/usr/bin/env python3
"""
preparar_datos.py - Genera los archivos Parquet que usa la app de Streamlit (toda la base del DSLD).

Uso:
    python utilidades/preparar_datos.py CARPETA_CSV DSLD_JSON_EXTRA.csv [CARPETA_SALIDA]

(desde la raíz del repositorio)

CARPETA_CSV            carpeta con los CSV descomprimidos de la descarga completa del DSLD
DSLD_JSON_EXTRA.csv    archivo generado por utilidades/dsld_extract_json.py (atributos de etiqueta)
CARPETA_SALIDA         por defecto app/datos

Genera:
    etiquetas.parquet     una fila por etiqueta (todos los tipos de producto)
    ingredientes.parquet  una fila por ingrediente declarado (sin las filas de información nutrimental)
    atributos.parquet     una fila por etiqueta y atributo (Vegan, Organic, Gluten Free...)
    agrupaciones.csv      tabla de auditoría: cada nombre original, a qué ingrediente quedó y con qué regla

El nombre de cada ingrediente se normaliza en tres capas (ver METODOLOGIA.md):
    1. limpieza de ruido (minúsculas, sin paréntesis ni palabras como "organic" o "extract")
    2. sinónimos curados a mano (utilidades/sinonimos.csv)
    3. clave de comparación automática (ignora guiones, orden de palabras y el prefijo l-/dl-)
"""
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

CARGA_MASIVA = ["TerraVita Premium Collection", "TerraVita", "Herbal Terra", "Hawaii Pharm"]
FORMA_ES = {
    "Capsule": "Cápsula", "Liquid": "Líquido", "Powder": "Polvo", "Tablet or Pill": "Tableta o pastilla",
    "Softgel Capsule": "Cápsula blanda", "Gummy or Jelly": "Gomita o jalea",
    "Other (e.g. tea bag)": "Otra (p. ej., té)", "Lozenge": "Pastilla para chupar",
    "Unknown": "Desconocida", "Bar": "Barra",
}
TIPO_ES = {
    "Botanical": "Botánico",
    "Botanical with Nutrients": "Botánico con nutrientes",
    "Vitamin": "Vitamina",
    "Mineral": "Mineral",
    "Multi-Vitamin and Mineral (MVM)": "Multivitamínico y mineral",
    "Single Vitamin and Mineral": "Vitamina y mineral (individual)",
    "Amino acid/Protein": "Aminoácido o proteína",
    "Fat/Fatty Acid": "Grasa o ácido graso",
    "Fiber and Other Nutrients": "Fibra y otros nutrientes",
    "Non-Nutrient/Non-Botanical": "Otro no nutriente (no botánico)",
    "Other Combinations": "Otras combinaciones",
}

# Filas de la tabla de información nutrimental (no son ingredientes del suplemento).
NUTRIMENTAL = {
    "calories", "total calories", "calories from fat", "energy", "total fat", "saturated fat", "trans fat",
    "polyunsaturated fat", "monounsaturated fat", "fat", "cholesterol", "total carbohydrates",
    "total carbohydrate", "carbohydrates", "carbohydrate", "other carbohydrates", "sugar", "sugars",
    "total sugars", "added sugars", "includes added sugars",
}

# Capa 1: palabras que se quitan del nombre. Ya no están escritas aquí: viven en utilidades/calificadores.csv, que sale
# de una revisión de los datos (ver candidatos_calificadores.py). Cada palabra tiene un ámbito:
#   general    -> todas las categorías      botanico   -> solo ingredientes botánicos
#   bacteria   -> solo bacterias            aminoacido -> solo aminoácidos
# Las filas "no_fusionar" documentan palabras que se revisaron y se decidió NO quitar (y por qué).
RUTA_CALIFICADORES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calificadores.csv")
CATEGORIA_DE_AMBITO = {"botanico": "botanical", "bacteria": "bacteria", "aminoacido": "amino acid"}


def _regex(palabras):
    return re.compile(r"(?<![\w-])(?:" + "|".join(sorted(palabras, key=len, reverse=True)) + r")(?![\w-])")


def cargar_calificadores(ruta=RUTA_CALIFICADORES):
    t = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    quitar = t[t["decision"] == "quitar"]
    por_categoria = {CATEGORIA_DE_AMBITO[a]: _regex(g["palabra"]) for a, g in quitar.groupby("ambito")
                     if a in CATEGORIA_DE_AMBITO and a != "aminoacido"}
    general = _regex(quitar.loc[quitar["ambito"] == "general", "palabra"])
    normalizar = [(re.compile(r"(?<![\w-])(?:" + p + r")(?![\w-])"), r) for p, r in
                  zip(t.loc[t["decision"] == "normalizar", "palabra"], t.loc[t["decision"] == "normalizar", "reemplazo"])]
    amino = quitar[quitar["ambito"] == "aminoacido"]
    amino = [(re.compile(r"(.+?)[ -](?:" + p + ")"), re.compile(e) if e else None)
             for p, e in zip(amino["palabra"], amino["excepto"])]
    return general, por_categoria, normalizar, amino


# Abreviaturas de género bacteriano: "l acidophilus" = "lactobacillus acidophilus".
ABREV_GENERO = {"l": ("lactobacillus", r"acidophilus|rhamnosus|plantarum|casei|paracasei|bulgaricus|salivarius|reuteri|"
                                       r"gasseri|brevis|fermentum|helveticus|johnsonii|crispatus|delbrueckii"),
                "b": ("bifidobacterium", r"bifidum|longum|lactis|breve|infantis|animalis|adolescentis|bifidus"),
                "s": ("streptococcus", r"thermophilus")}
RE_ABREV = re.compile(r"^([lbs])\.? (" + "|".join(v[1] for v in ABREV_GENERO.values()) + r")\b")


# Capa 2: sinónimos curados a mano. Cada regla es (grupo, patrón); el patrón debe coincidir con TODO el nombre ya
# limpio (re.fullmatch) y gana la primera regla que coincida. Se editan en utilidades/sinonimos.csv.
RUTA_SINONIMOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sinonimos.csv")


def cargar_sinonimos(ruta=RUTA_SINONIMOS):
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    return [(g, re.compile(p)) for g, p in zip(tabla["grupo"], tabla["patron"])]


MASA_A_MCG = {"mg": 1000.0, "Gram(s)": 1e6, "g": 1e6, "grams": 1e6, "mcg": 1.0, "ug": 1.0, "ng": 0.001}
UNIDAD_ALIAS = {
    "UI": "IU", "mg alpha-TE": "mg α-TE", "mg {alpha}-TE": "mg α-TE", "mg AT": "mg α-TE", "mg a-tocopherol": "mg α-TE",
    "mcg RE": "mcg RAE", "mg DFE": "mcg DFE", "{Calories}": "Calorie(s)", "Kcal": "Calorie(s)", "Kcal(s)": "Calorie(s)",
    "Calories": "Calorie(s)", "{microorganisms}": "CFU", "{Organisms}": "CFU", "Organism(s)": "CFU",
    "Viable Cell(s)": "CFU", "Cell(s)": "CFU",
}


CAL_GENERAL, CAL_POR_CATEGORIA, CAL_NORMALIZAR, CAL_AMINO = cargar_calificadores()


def limpiar(nombre, categoria=""):
    s = nombre.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9\s'-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for patron, reemplazo in CAL_NORMALIZAR:
        s = patron.sub(reemplazo, s)
    s = RE_ABREV.sub(lambda m: ABREV_GENERO[m.group(1)][0] + " " + m.group(2), s)
    s = CAL_GENERAL.sub(" ", s)
    if categoria in CAL_POR_CATEGORIA:
        s = CAL_POR_CATEGORIA[categoria].sub(" ", s)
    s = re.sub(r"\s*-\s*", "-", s)  # "alpha -lipoic" y "l- citrulline" -> "alpha-lipoic", "l-citrulline"
    s = re.sub(r"\s+", " ", s).strip(" -")
    if categoria == "amino acid":
        for patron, excepto in CAL_AMINO:
            m = patron.fullmatch(s)
            if m and not (excepto and excepto.fullmatch(m.group(1))):
                s = m.group(1)
    return s or None


def sinonimo(nombre, reglas):
    """Capa 2: grupo curado al que pertenece el nombre limpio, o None."""
    for grupo, patron in reglas:
        if patron.fullmatch(nombre):
            return grupo
    return None


def clave(nombre):
    """Capa 3: clave de comparación. Dos nombres con la misma clave son el mismo ingrediente.

    Cambia guiones, + y / por espacios, pega la letra suelta con su número ("q 10" -> "q10"), quita los prefijos
    l- (L-glutamine = glutamine; dl- y d- NO se quitan: son mezclas racémicas o formas distintas) y ordena las palabras (lactobacillus acidophilus = acidophilus lactobacillus).
    Solo sirve para comparar: el nombre que se muestra es otro (ver elegir_nombres)."""
    t = re.sub(r"[-+/]", " ", nombre)
    t = re.sub(r"\b([a-z])\s+(\d+)\b", r"\1\2", t)
    return " ".join(sorted(w for w in t.split() if w != "l"))


def elegir_nombres(nombres, etiquetas_por_nombre, canonicos):
    """Para cada clave elige el nombre que se muestra: el grupo curado si lo hay; si no, el más frecuente."""
    df = pd.DataFrame({"nombre": nombres})
    df["clave"] = df["nombre"].map(clave)
    df["n"] = df["nombre"].map(etiquetas_por_nombre).fillna(0)
    df["canonico"] = df["nombre"].isin(canonicos)
    df = df.sort_values(["clave", "canonico", "n"], ascending=[True, False, False])
    return df.groupby("clave")["nombre"].first(), df.set_index("nombre")["clave"]


def cargar(carpeta, prefijo, columnas=None):
    archivos = sorted(glob.glob(os.path.join(carpeta, f"{prefijo}_*.csv")))
    if not archivos:
        sys.exit(f"No se encontraron {prefijo}_*.csv en {carpeta}")
    return pd.concat((pd.read_csv(f, dtype=str, keep_default_na=False, usecols=columnas) for f in archivos),
                     ignore_index=True)


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    carpeta, extra_csv = sys.argv[1], sys.argv[2]
    salida = sys.argv[3] if len(sys.argv) == 4 else os.path.join("app", "datos")
    os.makedirs(salida, exist_ok=True)
    quitar_codigo = lambda s: s.str.replace(r"\s*\[.*\]$", "", regex=True)

    # --- Etiquetas -------------------------------------------------------------------
    p = cargar(carpeta, "ProductOverview")
    tipo = quitar_codigo(p["Product Type [LanguaL]"])
    forma = quitar_codigo(p["Supplement Form [LanguaL]"])
    etiquetas = pd.DataFrame({
        "dsld_id": p["DSLD ID"].astype("int64"),
        "producto": p["Product Name"].str.strip(),
        "marca": p["Brand Name"].str.strip(),
        "tipo": tipo.map(TIPO_ES).fillna(tipo),
        "forma": forma.map(FORMA_ES).fillna(forma),
        "estatus": p["Market Status"].map({"On Market": "En mercado", "Off Market": "Descontinuado"}),
        "anio_entrada": p["Date Entered into DSLD"].str[:4].astype("int16"),
        "porcion": p["Serving Size"].str.strip(),
        "contenido": p["Net Contents"].str.strip(),
        "url": p["URL"],
    })
    etiquetas["carga_masiva"] = etiquetas["marca"].isin(CARGA_MASIVA)

    # --- Ingredientes ----------------------------------------------------------------
    cols = ["DSLD ID", "Ingredient", "DSLD Ingredient Categories", "Amount Per Serving", "Amount Per Serving Unit"]
    i = cargar(carpeta, "DietarySupplementFacts", cols)
    i["original"] = i["Ingredient"].str.strip()
    i = i[~i["original"].str.lower().isin(NUTRIMENTAL)]
    # Se limpia una sola vez cada par (nombre, categoría) distinto: mucho más rápido que fila por fila.
    reglas = cargar_sinonimos()
    canonicos = {g for g, _ in reglas}
    pares = i[["original", "DSLD Ingredient Categories"]].drop_duplicates().reset_index(drop=True)
    pares["limpio"] = [limpiar(n, c) for n, c in zip(pares["original"], pares["DSLD Ingredient Categories"])]
    pares = pares.dropna(subset=["limpio"])
    # Capa 2: sinónimos curados (se resuelven una vez por cada nombre limpio distinto).
    grupo_de = {n: sinonimo(n, reglas) for n in pares["limpio"].unique()}
    pares["paso2"] = pares["limpio"].map(grupo_de).fillna(pares["limpio"])
    i = i.merge(pares[["original", "DSLD Ingredient Categories", "limpio", "paso2"]],
                on=["original", "DSLD Ingredient Categories"], how="inner")
    # Capa 3: clave de comparación; se muestra el grupo curado si lo hay y si no el nombre más frecuente.
    por_nombre = i.groupby("paso2")["DSLD ID"].nunique()
    nombre_de_clave, clave_de = elegir_nombres(pares["paso2"].unique(), por_nombre, canonicos)
    final_de = {n: nombre_de_clave[k] for n, k in clave_de.items()}
    pares["ingrediente"] = pares["paso2"].map(final_de)
    pares["regla"] = np.where(pares["limpio"].map(grupo_de).notna(), "sinónimo curado",
                              np.where(pares["ingrediente"] != pares["limpio"], "clave de comparación", "solo limpieza"))
    i["ingrediente"] = i["paso2"].map(final_de)
    # Tabla de auditoría: qué se hizo con cada nombre original.
    audit = (i.groupby(["original", "DSLD Ingredient Categories"])["DSLD ID"].nunique().rename("etiquetas").reset_index()
               .merge(pares[["original", "DSLD Ingredient Categories", "limpio", "ingrediente", "regla"]],
                      on=["original", "DSLD Ingredient Categories"])
               .rename(columns={"DSLD Ingredient Categories": "categoria", "limpio": "nombre_limpio",
                                "ingrediente": "ingrediente_final"})
               .sort_values("etiquetas", ascending=False))
    audit[["original", "categoria", "nombre_limpio", "ingrediente_final", "regla", "etiquetas"]].to_csv(
        os.path.join(salida, "agrupaciones.csv"), index=False)

    unidad = i["Amount Per Serving Unit"].str.strip().replace(UNIDAD_ALIAS)
    cantidad = pd.to_numeric(i["Amount Per Serving"], errors="coerce")
    factor = unidad.map(MASA_A_MCG)
    es_masa = factor.notna()
    # valor: masa en mcg (así los números pequeños de vitaminas no se pierden); otras unidades, tal cual.
    valor = np.where(es_masa, cantidad * factor, cantidad)
    unidad_base = np.where(es_masa, "mcg", unidad.replace("", np.nan))
    ingredientes = pd.DataFrame({
        "dsld_id": i["DSLD ID"].astype("int64").to_numpy(),
        "original": i["original"].to_numpy(),
        "ingrediente": i["ingrediente"].to_numpy(),
        "categoria": i["DSLD Ingredient Categories"].to_numpy(),
        "valor": valor.astype("float32"),
        "unidad": unidad_base,
    })
    # Vitamina D: 1 IU = 0.025 mcg (equivalencia fija), así que se pasa a masa como el resto.
    # Las IU de vitaminas A y E dependen de la forma química, por eso se dejan en IU.
    vit_d = (ingredientes["ingrediente"] == "vitamin d (cholecalciferol)") & (ingredientes["unidad"] == "IU")
    ingredientes.loc[vit_d, "valor"] = ingredientes.loc[vit_d, "valor"] * 0.025
    ingredientes.loc[vit_d, "unidad"] = "mcg"
    ingredientes.loc[ingredientes["valor"].isna(), "unidad"] = np.nan
    ingredientes.loc[ingredientes["valor"] <= 0, ["valor", "unidad"]] = np.nan

    resumen = ingredientes.groupby("dsld_id").agg(
        n_ingredientes=("ingrediente", "size"),
        tiene_mezcla=("categoria", lambda s: (s == "blend").any()))
    etiquetas = etiquetas.merge(resumen, left_on="dsld_id", right_index=True, how="left")
    etiquetas["n_ingredientes"] = etiquetas["n_ingredientes"].fillna(0).astype("int16")
    etiquetas["tiene_mezcla"] = etiquetas["tiene_mezcla"].fillna(False).astype(bool)

    # --- Atributos (del JSON) --------------------------------------------------------
    x = pd.read_csv(extra_csv, dtype=str, keep_default_na=False, usecols=["dsld_id", "target_groups"])
    atributos = (x.assign(atributo=x["target_groups"].str.split(r" \| "))
                  .explode("atributo")[["dsld_id", "atributo"]])
    atributos = atributos[atributos["atributo"].str.strip() != ""]
    atributos["dsld_id"] = atributos["dsld_id"].astype("int64")
    atributos["atributo"] = atributos["atributo"].str.strip()
    atributos = atributos[atributos["dsld_id"].isin(etiquetas["dsld_id"])]

    # --- Guardar (categorías para que pese poco) ------------------------------------
    for df, cats in ((etiquetas, ["marca", "tipo", "forma", "estatus"]),
                     (ingredientes, ["original", "ingrediente", "categoria", "unidad"]),
                     (atributos, ["atributo"])):
        for c in cats:
            df[c] = df[c].astype("category")
    etiquetas.to_parquet(os.path.join(salida, "etiquetas.parquet"), index=False)
    ingredientes.to_parquet(os.path.join(salida, "ingredientes.parquet"), index=False, compression="zstd")
    atributos.to_parquet(os.path.join(salida, "atributos.parquet"), index=False)
    print(f"Etiquetas: {len(etiquetas):,} | ingredientes: {len(ingredientes):,} | atributos: {len(atributos):,}")
    print(f"Nombres originales: {audit['original'].nunique():,} | tras la limpieza: {audit['nombre_limpio'].nunique():,} "
          f"| ingredientes finales: {audit['ingrediente_final'].nunique():,}")
    print("Guardado en", salida)


if __name__ == "__main__":
    main()
