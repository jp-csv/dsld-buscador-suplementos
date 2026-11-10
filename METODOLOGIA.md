# Metodología: cómo se agrupan los nombres de ingredientes

Este documento explica, paso a paso, cómo se convierten los nombres que escriben los fabricantes en las etiquetas del DSLD en los ingredientes que se buscan y se cuentan en la app. Es un método **por reglas**: se puede leer, auditar y corregir. No es perfecto, y abajo están sus límites.

## 1. El problema

Cada etiqueta escribe el ingrediente como quiere. Ejemplos reales de la base:

- Vitamina C: *Vitamin C*, *Ascorbic Acid*, *Calcium Ascorbate*, *Ascorbyl Palmitate*… (20 nombres originales distintos).
- Glutamina: *L-Glutamine*, *Glutamine*, *L Glutamine*.
- CoQ10: *Coenzyme Q10*, *Coenzyme Q-10*, *CoQ10*, *Co-Enzyme Q 10*, *Ubiquinone*…
- Familia NAD+: *NAD*, *NAD+*, *Nicotinamide Adenine Dinucleotide*, *Beta-Nicotinamide Adenine Dinucleotide*, *NADH*, *NMN*, *Niagen Nicotinamide Riboside*…

Si se cuentan tal cual, la misma sustancia queda repartida en muchas filas y cualquier ranking, porcentaje o búsqueda sale subestimado. La base completa tiene **76,390 nombres originales** distintos (1.8 millones de filas de ingredientes en 214,780 etiquetas).

## 2. El método en tres capas

El código está en `utilidades/preparar_datos.py`. Las capas se aplican en este orden, y cada una trabaja sobre el resultado de la anterior.

### Capa 1: limpieza de ruido

Se aplica a cada nombre original, sin tablas de ingredientes:

1. Se pasa a minúsculas.
2. Se quita todo lo que va **entre paréntesis** (suele ser la fuente: *Vitamin C (as ascorbic acid)* → *vitamin c*).
3. Se quitan signos raros (se conservan letras, números, espacios, guion y apóstrofo).
4. Se unifica *hydrochloride* / *monohydrochloride* → *hcl* (solo ortografía) y las abreviaturas del género bacteriano (*L. acidophilus* → *lactobacillus acidophilus*, *B. lactis* → *bifidobacterium lactis*).
5. Se quitan las palabras de `utilidades/calificadores.csv`, según su **ámbito**:
   - *general* (todas las categorías): *organic, certified, raw, dried, powder, standardized, anhydrous, monohydrate, micronized, natural, pure, total, usp…* (grado de hidratación, tratamiento físico, origen, pureza).
   - *botánico* (la categoría la trae el DSLD): partes de la planta y forma de preparación, *root, leaf, extract, liquid, glycerite, supercritical, CO2, freeze, pdr, mushroom…*, y los números sueltos (razones de extracto como *10:1* o porcentajes como *95 %*). Así *Turmeric Root Extract*, *Turmeric Powder* y *Turmeric 95 %* cuentan como *turmeric*.
   - *bacteria*: *subsp, ssp, animalis* (*Bifidobacterium animalis subsp. lactis* = *B. lactis*).
   - *aminoácido*: *hcl* (*L-lysine HCl* = *L-lysine*), con la excepción del ácido glutámico (el HCl de glutámico se vende como ácido digestivo).
6. En los **no botánicos** se conserva *oil* y demás: *fish oil* no se vuelve *fish*.
7. Se pegan los guiones con espacios sueltos (*alpha -lipoic* → *alpha-lipoic*) y se colapsan espacios.

Resultado: de 76,390 nombres quedan **41,903**.

**De dónde sale la lista de palabras.** No se eligió de memoria: `utilidades/candidatos_calificadores.py` toma los 1,000 ingredientes más comunes (85 % de todas las filas de ingredientes) y, para cada uno, busca los demás nombres que lo contienen más alguna palabra (*ginkgo* → *ginkgo biloba*, *ginkgo phytosome*…). Cuenta en cuántos ingredientes base distintos aparece cada palabra extra: las muy repetidas (*liquid*, *glycerite*, *anhydrous*…) son calificadores genéricos; las poco repetidas son marcas, cepas o variedades. Se revisaron las ~250 palabras más repetidas y cada decisión está en `calificadores.csv` con su criterio: *quitar*, *normalizar* o **no fusionar** (con el motivo: sales como *citrate*/*oxide* porque la dosis es de la sal; colores y regiones como *red*/*wild*/*chinese* porque suelen ser otra especie; marcas y cepas; mezclas).

### Capa 2: sinónimos

Hay nombres que la limpieza no puede unir porque son palabras distintas (*ascorbic acid* y *vitamin c*, *ginkgo* y *ginkgo biloba*, *gaba* y *gamma-aminobutyric acid*). Para esos hay una tabla en `utilidades/sinonimos.csv` con cuatro columnas:

- `grupo`: el nombre con el que se mostrará (por ejemplo *vitamin c (ascorbic acid)*).
- `patron`: una expresión regular que debe coincidir con **todo** el nombre ya limpio (no con un pedazo). La primera regla que coincide gana.
- `nota`: qué se dejó fuera.
- `criterio`: por qué se agrupa. Son cinco criterios:
  - **A** misma molécula (ortografía, sal estabilizada o marca de la misma molécula: resveratrol/Resvida, luteína/Lutemax…).
  - **B** nombre común = nombre científico en plantas y hongos (*turmeric* = *curcuma longa*, *reishi* = *ganoderma lucidum*). El grupo se muestra con el nombre común y el científico queda en la columna `nota`.
  - **C** familia NAD+ (el caso que originó la revisión, abajo).
  - **D** las 13 vitaminas con requerimiento nutricional (A, C, D, E, K, B1, B2, B3, B5, B6, B7, B9, B12).
  - **E** siglas y nombre químico del mismo compuesto (*GABA*, *MSM*, *PABA*, *DIM*, *alpha-GPC*).

La tabla tiene **94 reglas** (48 de tipo B, 23 A, 13 D, 6 E, 4 C). Se llegó a ellas revisando los ingredientes más comunes uno por uno (los ~330 no botánicos y los ~260 botánicos más frecuentes), en vez de agregar solo los casos que se me ocurrieron. Los casos revisados que **no** se fusionaron también tienen su razón (por ejemplo *silica* ≠ *silicon*, *choline bitartrate* ≠ *choline*, *cinnamon* ≠ *cassia*, *passion* a secas es ambiguo).

### Capa 3: comparación automática de escritura

Para los demás nombres se calcula una **clave de comparación**. Dos nombres con la misma clave se consideran el mismo ingrediente. La clave:

1. Cambia guiones, signos + y diagonales por espacios.
2. Pega una letra suelta con su número (*q 10* → *q10*).
3. Quita el prefijo **l-** (*L-glutamine* = *glutamine*).
4. Ordena las palabras alfabéticamente (*Lactobacillus acidophilus* = *acidophilus Lactobacillus*).

La clave solo sirve para comparar. El nombre que se muestra es, en este orden: el grupo curado de la capa 2 si lo hay; si no, el nombre más frecuente del grupo.

Se decidió **no** quitar `dl-` ni `d-`: la DL-fenilalanina (mezcla racémica) es otro producto que la L-fenilalanina, y tratarlas igual inflaría la segunda. Es una decisión consciente que se puede cambiar en la función `clave()`.

### Cifras (base completa, enero de 2026)

Se cuentan pares *(nombre original, categoría)*, que es lo que se agrupa:

- 78,049 pares en total.
- 69,517 quedan solo con la limpieza de la capa 1.
- 2,328 se unen por la clave de la capa 3.
- 6,204 se unen por una regla de la capa 2.
- Los 76,390 nombres originales terminan en **39,753 ingredientes finales** (antes de la revisión sistemática eran 44,439). De ellos, 1,977 tienen al menos 50 etiquetas y son los que aparecen como opción «agrupado» en la lista de la app; los nombres sin agrupar («término») aparecen si tienen al menos 5 etiquetas (19,445).
- Los 100 ingredientes más comunes concentran 57 % de todas las filas de ingredientes; los 500, 79 %; los 1,000, 85 %.

Las reglas de sinónimos tocan las filas más grandes: unos 530 mil de los 1.8 millones de ingredientes declarados pasan por la capa 2.

## 3. Caso de estudio: buscar «NAD»

Fue el error que reveló que el método tenía huecos, así que sirve para explicarlo.

**Qué pasaba antes.** La limpieza quitaba lo que iba entre paréntesis y no había ninguna regla para NAD. Quedaban como ingredientes separados *nad*, *nad trihydrate*, *nicotinamide adenine dinucleotide*, *beta-nicotinamide adenine dinucleotide*, *nadh*, *nicotinamide adenine dinucleotide hydride*… Al escribir «nad» en el cuadro de ingredientes solo aparecían *nadh* (56 etiquetas), *nad* (37) y *nad trihydrate* (8), mezclados con *vanadium* o *phytonadione* (que contienen «nad» dentro de la palabra). El nombre completo (*Nicotinamide Adenine Dinucleotide*, la escritura más común), el NMN y la nicotinamida ribósido no aparecían: se veían unas **100 etiquetas** de las unas **510** que hay en la base.

**Qué se hizo.** Se agregaron cuatro reglas en `sinonimos.csv` (criterio C). Después, para no depender de que yo conociera el caso, se hizo la revisión sistemática de la capa 1 y 2 descrita arriba, que encontró más casos del mismo tipo (*l acidophilus* separado de *lactobacillus acidophilus*, *GABA* y su nombre químico, *alpha-GPC*, nombres latinos de plantas…). Se separaron los compuestos porque no son lo mismo, pero los dos precursores llevan «nad+» en el nombre para que la búsqueda *nad* los encuentre:

- **NAD+** (*nad+ (nicotinamide adenine dinucleotide)*): *NAD*, *NAD+*, *NAD trihydrate*, el nombre completo y sus variantes beta/b y sal sódica. 111 etiquetas, 6 nombres que antes estaban separados.
- **NADH** (*nadh (reduced nad+)*): forma reducida, incluidos *dinucleotide hydride*, *+ hydrogen* y *reduced*, y las marcas Enada y Co-E1. 119 etiquetas.
- **NMN** (*nmn (nicotinamide mononucleotide, nad+ precursor)*): precursor de NAD+. 96 etiquetas.
- **Nicotinamida ribósido** (*nicotinamide riboside (nr, nad+ precursor)*): precursor de NAD+, incluye cloruro, malato y la marca Niagen. 191 etiquetas.

**Resultado.** Al escribir «nad» aparecen ahora los cuatro compuestos, cada uno con todas sus escrituras. Elegidos juntos (con la opción de «cualquiera de los ingredientes») suman **509 etiquetas**. El desplegable «¿Qué nombres de las etiquetas cuentan como este ingrediente?» muestra, por ejemplo, que NAD+ junta 9 nombres originales en 111 etiquetas. Las fórmulas que usan «NAD» como nombre comercial (*NAD+ Complete*, *NAD+ Defender Formula*) no se tocan: son productos mezcla, no el compuesto, y tienen menos de 5 etiquetas cada una.

**Decisión de diseño.** Se podrían haber juntado los cuatro compuestos como «NAD», pero se decidió no hacerlo porque NADH, NMN y la nicotinamida ribósido son sustancias distintas con claims distintos, y mezclarlos falsearía los conteos por ingrediente.

## 4. Cómo comprobar un resultado (auditoría)

- **En la app:** al elegir un ingrediente en el Buscador aparece el desplegable «¿Qué nombres de las etiquetas cuentan como este ingrediente?». Muestra los nombres originales que se agruparon, con su número de etiquetas. Es la forma más rápida de revisar un caso.
- **Tabla completa:** `app/datos/agrupaciones.csv` tiene una fila por nombre original con: categoría, nombre limpio, ingrediente final, qué capa lo agrupó (*solo limpieza*, *clave de comparación* o *sinónimo curado*) y número de etiquetas. Se puede abrir en Excel y filtrar.
- **Revisión que se hizo:** se listaron todos los grupos que la capa 3 unió automáticamente (los 60 más grandes se revisaron a mano) buscando falsas fusiones. De ahí salió quitar `dl-` de la clave y pegar guiones con espacios.

## 5. Cómo agregar o corregir una regla

1. **Una palabra que sobra** (un calificador): agrega una fila a `utilidades/calificadores.csv` con su ámbito, decisión (*quitar*) y criterio. Para ver candidatos: `python utilidades/candidatos_calificadores.py app/datos 1000`.
2. **Dos nombres distintos del mismo compuesto**: agrega una fila a `utilidades/sinonimos.csv` (`grupo`, `patron` sobre el nombre ya limpio y que coincida con todo, `nota`, `criterio`). Las reglas más específicas van antes: gana la primera.
3. Vuelve a correr `python utilidades/preparar_datos.py CARPETA_CSV DSLD_JSON_EXTRA.csv` (menos de un minuto) y sube los archivos nuevos de `app/datos/`.
4. Revisa el resultado en `agrupaciones.csv` o con el desplegable de la app.

## 6. Límites (lo que el método no hace)

- **Extracto ≠ polvo.** En botánicos, *turmeric extract*, *turmeric powder* y *turmeric root* se cuentan como un solo ingrediente. Son preparaciones distintas (un extracto concentra y el polvo es la planta molida), pero separarlas multiplicaría los ingredientes y haría imposible contar «cuántos productos llevan cúrcuma». Para distinguirlos, el filtro **Ingrediente** de la app ofrece dos tipos de opción: 🧬 **(agrupado)**, que junta todas las escrituras (*turmeric*: 7,255 etiquetas), y 🔍 **(término)**, que es un nombre tal como lo escribió la etiqueta, sin agrupar (por ejemplo *turmeric powder*: 151 etiquetas). Los términos son los nombres originales (en minúsculas) con al menos 5 etiquetas. El desplegable «¿Qué nombres de las etiquetas coinciden con lo que buscaste?» y la dosis funcionan con ambos tipos.
- **No une palabras distintas que son lo mismo** si no hay una regla: *curcumin* y *curcuminoids* quedan separados.
- **Las marcas comerciales** solo se agrupan si están en la tabla (Niagen, Suntheanine, KSM-66, Lutemax…). Muchas otras (*Kaneka ubiquinol*, *CoQsol*, *Longvida*) siguen apareciendo aparte.
- **No une sales, ésteres ni formas** distintas (citrato, óxido, bitartrato…): la dosis es de la sal y a veces cambia el producto (betaína HCl es ácido digestivo; betaína anhidra es TMG). Se pueden buscar con el filtro de término.
- **Los grupos de vitaminas son amplios a propósito**: *vitamin c* incluye ácido ascórbico y sus sales y ésteres; *folate* incluye ácido fólico y metilfolato; *niacin* incluye niacinamida.
- **Revisión acotada.** La revisión sistemática cubre los ~1,000 ingredientes más comunes (85 % de las filas). Los ingredientes raros se revisaron menos.
- **Es una aproximación por reglas, no una validación química.** Las dosis usan los nombres ya agrupados; la estandarización de unidades está en la sección *Dosis de referencia* de la app.

## 7. Cómo mejorarlo (siguientes pasos)

- **Usar el campo de grupo de ingrediente del propio DSLD.** Según la documentación del DSLD, el JSON de cada etiqueta trae un grupo de ingrediente estandarizado por el NIH. Los CSV de la descarga no lo traen, y en esta sesión no se verificó en el JSON. Si existe, se podría usar como referencia para validar y completar este método.
- **Ampliar la revisión** más allá del top 1,000 con el mismo procedimiento, y detectar candidatos con coincidencia aproximada de texto (distancia entre cadenas), siempre con revisión manual.
- **Ontologías externas** (por ejemplo ChEBI o UNII) para los compuestos químicos.
- **Revisión con una muestra aleatoria:** revisar a mano unas cientos de agrupaciones y reportar el porcentaje de acierto.

## 8. Cómo explicarlo en un minuto

> Las etiquetas escriben el mismo ingrediente de muchas formas, así que primero limpio el nombre (minúsculas, sin paréntesis, sin palabras como *organic* o *extract* en botánicos). Las palabras que quito salen de revisar los 1,000 ingredientes más comunes y ver qué sobra con más frecuencia, con una decisión y un motivo escritos por palabra. Luego uso una tabla de sinónimos, de cerca de 100 reglas con criterio explícito, para lo que no se puede deducir, como *ascorbic acid* = *vitamin C*, *ginkgo* = *ginkgo biloba* o la familia NAD+. Por último comparo la escritura de forma automática: ignoro guiones, orden de palabras y el prefijo L-, y así *L-glutamine* y *glutamine* cuentan igual. Decidí que fuera por reglas y no con un modelo para poder auditar cada decisión: hay una tabla que dice a qué ingrediente fue cada nombre y con qué regla. Sé que tiene límites, como las marcas comerciales que no están en la tabla, y los documenté.

### Preguntas probables

- **¿Por qué reglas y no un modelo o coincidencia aproximada?** Porque en química las falsas coincidencias importan (NMN y NADH no son NAD+; DL-fenilalanina no es L-fenilalanina) y con reglas puedo explicar y corregir cada caso. La coincidencia aproximada es un siguiente paso para encontrar candidatos, no para decidir.
- **¿Qué tan exacto es?** No lo medí con una muestra aleatoria; revisé de forma sistemática los 1,000 ingredientes más comunes (85 % de las filas). Lo mejor que puedo decir es que cubre los casos más frecuentes y que cada agrupación se puede auditar.
- **¿Por qué extracto y polvo cuentan como uno?** Es una decisión: sirve para contar productos por planta. Lo documenté y agregué opciones de «término» (el nombre original sin agrupar) en el filtro de ingrediente para separarlos.
- **¿Cómo sabes que no te faltan casos como NAD?** No puedo asegurar que no falte ninguno, pero no dependo de mi intuición: revisé los ingredientes más comunes con un procedimiento reproducible (`candidatos_calificadores.py`) y dejé registrado qué se fusionó y qué se revisó y se descartó.
- **¿Qué hiciste cuando encontraste un error?** El caso de NAD: documenté el problema (la búsqueda alcanzaba unas 100 etiquetas de unas 510 reales), agregué reglas para los compuestos relacionados y verifiqué el resultado en la tabla de auditoría.
