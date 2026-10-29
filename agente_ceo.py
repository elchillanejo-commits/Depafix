import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langgraph.prebuilt import create_react_agent
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from langchain_core.messages import SystemMessage

load_dotenv()
console = Console()

# 1. Modelo
llm = ChatOpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url="https://api.moonshot.ai/v1",
    model="kimi-k3.1-pro",
    temperature=0.7 # Un poco menos de temperatura para análisis más precisos
)

# 2. Cargar Embeddings
print("🧠 Cargando modelo de lenguaje local...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
CARPETA_DATA = "./data"

def _buscar_en_cerebro(archivo, query):
    try:
        ruta = os.path.join(CARPETA_DATA, archivo)
        if not os.path.exists(ruta):
            return f"El cerebro {archivo} no está disponible."
        
        vectorstore = FAISS.load_local(ruta, embeddings, allow_dangerous_deserialization=True)
        # AUMENTAMOS A K=5 PARA LEER MÁS CONTEXTO
        docs = vectorstore.similarity_search(query, k=5) 
        
        if not docs:
            return "No se encontró información relevante."
        return "\n\n".join([f"--- Fuente: {d.metadata.get('fuente', '?')} ---\n{d.page_content}" for d in docs])
    except Exception as e:
        return f"Error buscando en {archivo}: {e}"

# 3. Herramientas Mente 360
@tool
def buscar_en_tierra(query: str) -> str:
    """Busca en el cerebro TIERRA (Trade, mercados, trading, finanzas)."""
    return _buscar_en_cerebro("tierra.faiss", query)

@tool
def buscar_en_agua(query: str) -> str:
    """Busca en el cerebro AGUA (Dropshipping, e-commerce, ventas online, marketing digital)."""
    return _buscar_en_cerebro("agua.faiss", query)

@tool
def buscar_en_aire(query: str) -> str:
    """Busca en el cerebro AIRE (Ventas, persuasión, psicología, inmobiliario)."""
    return _buscar_en_cerebro("aire.faiss", query)

@tool
def buscar_en_fuego(query: str) -> str:
    """Busca en el cerebro FUEGO (IA, MCP, agentes, Python, programación)."""
    return _buscar_en_cerebro("fuego.faiss", query)

@tool
def buscar_en_metal(query: str) -> str:
    """Busca en el cerebro METAL (Filosofía, estoicismo, Sun Tzu, Eneagrama, estrategia)."""
    return _buscar_en_cerebro("metal.faiss", query)

# 4. Herramienta de Scraping Mejorada
@tool
def analizar_competencia(url: str) -> str:
    """Analiza la competencia leyendo una URL (web o perfil público). Extrae título, meta descripciones y el texto visible principal."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return f"No se pudo acceder a {url} (HTTP {response.status_code})."

        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string.strip() if soup.title and soup.title.string else "Sin título"
        
        description = ""
        for meta in soup.find_all('meta'):
            prop = (meta.get('property') or meta.get('name') or '').lower()
            if prop in ['og:description', 'description', 'og:title']:
                content = meta.get('content', '').strip()
                if content:
                    description += f"- {prop}: {content}\n"

        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        visible_text = soup.get_text(separator=' ', strip=True)
        visible_text = ' '.join(visible_text.split())

        # AUMENTAMOS A 5000 CARACTERES DE TEXTO VISIBLE
        resultado = f"TÍTULO: {title}\n\nMETA:\n{description}\n\nTEXTO VISIBLE:\n{visible_text[:5000]}"
        return resultado.strip()
    except Exception as e:
        return f"Error analizando {url}: {e}"

# 5. EL SYSTEM PROMPT (El Secreto del Éxito)
SYSTEM_PROMPT = """Eres un Consultor de Negocios Senior, experto en Marketing Digital, Ventas y Estrategia.
Tu objetivo es auditar negocios de forma DESPIADADA y PROFUNDA. No des respuestas tibias ni genéricas.
Usa las herramientas a tu disposición para leer la web del cliente y buscar en tu base de conocimientos (Mente 360).
Siempre que analices una web o un negocio, debes estructurar tu respuesta así:
1. **Propuesta de Valor Actual**: Qué venden y cómo lo comunican (sé crítico).
2. **Puntos Débiles**: Qué le falta, qué está mal en su mensaje.
3. **Cruce con mis Manuales**: Qué dice la teoría (Aire/Agua/Metal) que le falta a este negocio.
4. **Plan de Acción**: 3 pasos concretos para mejorar (cita los manuales).
Si la información de la web es poca, dilo, pero exprime hasta la última coma."""

# 6. Crear el agente
tools = [buscar_en_tierra, buscar_en_agua, buscar_en_aire, buscar_en_fuego, buscar_en_metal, analizar_competencia]
agent = create_react_agent(llm, tools)

# 7. Ejecución
if __name__ == "__main__":
    console.print(Panel.fit("[bold green]🤖 Agente CEO (Radar Táctico) Iniciado[/bold green]\nEscribe [bold red]'salir'[/bold red] para terminar.", title="DepaFix", border_style="blue"))
    
    while True:
        pregunta = console.input("\n[bold cyan]👤 Tú:[/bold cyan] ").strip()
        if pregunta.lower() in ['salir', 'exit', 'quit']:
            break
        if not pregunta:
            continue
            
        console.print("[yellow]🧠 Auditando y cruzando información...[/yellow]")
        try:
            # Inyectamos el System Prompt al inicio de la conversación
            mensajes = [
                SystemMessage(content=SYSTEM_PROMPT),
                ("user", pregunta)
            ]
            resultado = agent.invoke({"messages": mensajes})
            respuesta = resultado["messages"][-1].content
            console.print("\n[bold green]🤖 Agente:[/bold green]")
            console.print(Markdown(respuesta))
        except Exception as e:
            console.print(f"[bold red]❌ Error:[/bold red] {e}")

