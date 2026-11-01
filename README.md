# ⚖️ Metal - Procurador Virtual

Aplicación de Streamlit que recupera contexto desde Supabase mediante la función RPC
`match_metal_knowledge` y genera documentos con OpenAI. Permite copiar el resultado y
descargarlo como archivo de texto (`.txt`).

## Requisitos

- Python 3.10 o superior.
- Una API Key de OpenAI.
- Un proyecto de Supabase con la tabla `metal_knowledge` y la función RPC
  `match_metal_knowledge` configurada.

## Configuración local

1. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

2. Crea un archivo `.env` en la raíz del proyecto con tus valores reales:

   ```dotenv
   OPENAI_API_KEY=tu_api_key_de_openai
   SUPABASE_URL=https://tu-proyecto.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key_de_supabase
   ```

3. Ejecuta la aplicación:

   ```bash
   streamlit run app_metal.py
   ```

El archivo `.env` contiene secretos, está excluido mediante `.gitignore` y **no debe
subirse a GitHub**.

## Configurar Secrets en Streamlit Community Cloud

1. Sube este repositorio a GitHub sin incluir el archivo `.env`.
2. En Streamlit Community Cloud, selecciona **Create app**.
3. Indica el repositorio, la rama y `app_metal.py` como archivo principal.
4. Abre **Advanced settings** y pega lo siguiente en **Secrets**, reemplazando los
   valores de ejemplo por tus credenciales reales:

   ```toml
   OPENAI_API_KEY = "tu_api_key_de_openai"
   SUPABASE_URL = "https://tu-proyecto.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "tu_service_role_key_de_supabase"
   ```

5. Guarda los Secrets y despliega o reinicia la aplicación.

La aplicación lee primero las variables de entorno locales y, si no están disponibles,
utiliza `st.secrets`. No agregues estos valores al código ni a archivos versionados.

## Despliegue posterior

Si la aplicación ya estaba desplegada, abre su menú de administración en Streamlit
Community Cloud, entra en **Settings > Secrets**, guarda las credenciales y selecciona
**Reboot** para cargar la nueva configuración.

## Docker para Mente 360 y FAISS

`mente_360.py` necesita los cerebros FAISS ubicados en `data/` y la clave
`MOONSHOT_API_KEY`. El Dockerfile instala las dependencias, copia los cerebros y deja
predescargado el modelo de embeddings `all-MiniLM-L6-v2`.

```bash
docker build -t depafix-mente .
docker run --rm -it --env-file .env depafix-mente
```

Notas:

- El build debe ejecutarse desde la raíz del repositorio y requiere que existan
  `data/tierra.faiss`, `data/metal.faiss`, `data/agua.faiss`, `data/aire.faiss` y
  `data/fuego.faiss`. Esos directorios están excluidos de Git por `.gitignore`.
- El contenedor es interactivo porque `mente_360.py` solicita preguntas por consola.
- No copies `.env` dentro de la imagen. Docker lo recibe en tiempo de ejecución con
  `--env-file .env` y el archivo está excluido por `.dockerignore`.
- El primer build descarga dependencias y el modelo de embeddings; puede tardar varios
  minutos.

## Radar diario con GitHub Actions y Telegram

El workflow `.github/workflows/deploy.yml` ejecuta `radar_pymes.py`, guarda el log y
envía un resumen por Telegram mediante `notificador_telegram.py`.

### Secrets y variables en GitHub

En el repositorio de GitHub, abre **Settings > Secrets and variables > Actions**.

1. En **Secrets**, crea:
   - `TELEGRAM_BOT_TOKEN`: token del bot de Telegram.
   - `TELEGRAM_CHAT_ID`: ID del chat o canal que recibirá el resumen.
2. En **Variables**, crea:
   - `RADAR_URLS`: URLs que analizará el radar, separadas por espacios.

Ejemplo de `RADAR_URLS`:

```text
https://sitio1.cl https://sitio2.cl https://sitio3.cl
```

El workflow no instala las dependencias pesadas de Mente 360: solo instala
`requests` y `beautifulsoup4` para el radar. El Dockerfile se encarga del entorno de
FAISS.

### Horario

GitHub Actions programa en UTC. El workflow tiene dos ejecuciones programadas
(`11:00` y `12:00` UTC) y una comprobación de la hora local de Chile: solo continúa
cuando en `America/Santiago` son las 08:00. Así se mantiene la hora durante el horario
de verano e invierno. También puedes ejecutarlo manualmente desde **Actions > Radar
diario de PYMES > Run workflow**; la ejecución manual omite la comprobación horaria.

### Prueba local del notificador

```bash
python notificador_telegram.py \
  --log logs/modo_nocturno_2026-10-28_18-27-23.log \
  --estado 0 \
  --dry-run
```

Quita `--dry-run` para enviar el mensaje. Si la ruta indicada en `--log` no existe, el
notificador envía un aviso de error. Las credenciales se leen del entorno o de `.env`.
