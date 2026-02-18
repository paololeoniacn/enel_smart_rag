import streamlit as st
import sys
import os

# Add project root to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config  # Import configuration explicitly

# from orchestrator import Orchestrator  <-- Import spostato dentro la funzione lazy

# Configurazione Pagina
st.set_page_config(
    page_title="Agentic RAG System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS per estetica (rispetta le regole 'Design Aesthetics' anche se è Streamlit)
st.markdown("""
<style>
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🤖 Agentic System Local")
# Inizializzazione Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Funzione per caricare l'Orchestratore (cached per evitare ricaricamenti)
@st.cache_resource(show_spinner="Caricamento Sistema Agentico e Knowledge Base...")
def load_orchestrator():
    # Importiamo qui dentro per non bloccare l'UI iniziale
    import time
    from orchestrator import Orchestrator
    return Orchestrator()

# Header
st.title("⚡ Enel Smart RAG")
st.caption(f"Sistema Agentico Locale • {config.model_name}")

# Caricamento Modello con Feedback Visivo
if "orchestrator" not in st.session_state:
    with st.status("🚀 Inizializzazione Sistema...", expanded=True) as status:
        st.write("Caricamento Knowledge Base...")
        orchestrator_instance = load_orchestrator()
        st.session_state.orchestrator = orchestrator_instance
        status.update(label="✅ Sistema Pronto!", state="complete", expanded=False)

# Sidebar
with st.sidebar:
    st.header("Gestione")
    if st.button("Pulisci Chat"):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.info(f"Modello: {config.model_name}")

# Display Chat History
for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    
    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(content)
    elif role == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)

# Chat Input
if prompt := st.chat_input("Scrivi la tua domanda qui..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant", avatar="🤖"):
        if "orchestrator" in st.session_state:
            response_placeholder = st.empty()
            full_response = ""
            
            # Callback function to update UI in real-time inside the status container
            # Usiamo un placeholder vuoto inizialmente, che verrà riempito da st.status
            status_container = st.status("🤔 Analisi in corso...", expanded=True)
            
            def ui_callback(msg):
                status_container.write(msg)

            try:
                # L'orchestratore è sincrono, lo chiamiamo direttamente
                response = st.session_state.orchestrator.query(prompt, callback=ui_callback)
                
                # Chiudiamo lo status con successo
                status_container.update(label="✅ Analisi Completata", state="complete", expanded=False)
                
                # Mostriamo la risposta finale
                response_placeholder.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                status_container.update(label="❌ Errore", state="error")
                st.error(f"Errore durante la generazione: {e}")
        else:
            st.error("Orchestrator non inizializzato.")
