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
