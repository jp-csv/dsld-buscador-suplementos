# Cómo publicar el proyecto (gratis)

## Si ya publicaste la v1

No necesitas repositorio nuevo: en tu repositorio, sube el contenido de esta carpeta encima (reemplaza `app`, `utilidades`, `README.md` y los demás). Borra la carpeta `notebooks`, que ya no va. La app se actualiza sola en unos minutos.

## 1. Subir el repositorio a GitHub

1. Entra a [github.com](https://github.com) y crea un repositorio nuevo, **público**, por ejemplo `dsld-buscador-suplementos`. No marques «Add a README» (este proyecto ya trae uno).
2. En la página del repositorio vacío, elige **uploading an existing file**.
3. Arrastra **el contenido** de esta carpeta (no la carpeta en sí): `app`, `utilidades`, `README.md`, `DESPLIEGUE.md`, `requirements.txt`, `.gitignore` y la carpeta `.streamlit`.
   - Las carpetas que empiezan con punto (`.streamlit`, `.gitignore`) a veces no se ven en tu explorador de archivos. En Mac, muéstralas con **Cmd + Shift + .**
4. Escribe un mensaje (por ejemplo «Primera versión») y pulsa **Commit changes**.

## 2. Publicar la app en Streamlit Community Cloud

1. Entra a [share.streamlit.io](https://share.streamlit.io) y elige **Continue with GitHub**. Acepta los permisos.
2. Pulsa **Create app** → **Deploy a public app from GitHub**.
3. Llena:
   - **Repository:** tu repositorio (`tu-usuario/dsld-buscador-suplementos`)
   - **Branch:** `main`
   - **Main file path:** `app/app.py`
   - **App URL:** el nombre que quieras, por ejemplo `buscador-suplementos`
4. En **Advanced settings**, elige **Python 3.12**.
5. Pulsa **Deploy**. La primera vez tarda unos minutos en instalar todo.

Cuando termine, tendrás un link como `https://buscador-suplementos.streamlit.app`. Ese es el que le pasas a tu compañero.

## 3. Últimos ajustes en el README

En `README.md`, reemplaza `https://TU-APP.streamlit.app` por el link real de tu app (puedes editarlo directo en GitHub con el ícono del lápiz).

## Notas

- Si nadie abre la app en 12 horas, se duerme. Al abrirla aparece un botón para despertarla; tarda alrededor de un minuto.
- Cada vez que subas cambios a GitHub, la app se actualiza sola.
- Si la app muestra un error, en share.streamlit.io abre **Manage app** (abajo a la derecha de la app) para ver el registro.
