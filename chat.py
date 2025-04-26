import streamlit as st
import hashlib
import random
import time
import uuid
import json
import os
import base64
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from PIL import Image
import io

# Configuração da página
st.set_page_config(page_title="Chat Secreto", page_icon="🔒", layout="wide")

# Esconder elementos padrão do Streamlit
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 0rem; padding-bottom: 0rem;}
    .css-18e3th9 {padding-top: 0rem; padding-bottom: 0rem;}
    .css-1d391kg {padding-top: 0rem; padding-bottom: 0rem;}
</style>
""", unsafe_allow_html=True)

# Arquivo para armazenar as salas
ROOMS_FILE = "chat_rooms.json"
# Pasta para armazenar imagens
IMAGES_FOLDER = "chat_images"

# Criar pasta de imagens se não existir
if not os.path.exists(IMAGES_FOLDER):
    os.makedirs(IMAGES_FOLDER)


# Função para carregar salas do arquivo
def load_rooms():
    if os.path.exists(ROOMS_FILE):
        try:
            with open(ROOMS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


# Função para salvar salas no arquivo
def save_rooms(rooms):
    with open(ROOMS_FILE, 'w') as f:
        json.dump(rooms, f)


# Função para salvar imagem
def save_image(image_file, room_hash):
    # Gerar um nome único para a imagem
    image_id = str(uuid.uuid4())
    # Definir o caminho da imagem
    image_path = os.path.join(IMAGES_FOLDER, f"{room_hash}_{image_id}.png")

    # Ler e salvar a imagem
    img = Image.open(image_file)
    img.save(image_path)

    return image_path


# Inicialização de variáveis de estado
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.page = "home"
    st.session_state.current_room = None
    st.session_state.user_id = str(uuid.uuid4())
    st.session_state.last_message_count = 0
    st.session_state.upload_key = "image_upload_0"  # Chave inicial para o uploader
    # Lista de cores para os usuários
    colors = ["#FF5733", "#33FF57", "#3357FF", "#F033FF", "#FF33A8",
              "#33FFF6", "#FFD433", "#8C33FF", "#FF8C33", "#33FFBD"]
    st.session_state.user_color = random.choice(colors)

# Carregar salas do arquivo
rooms = load_rooms()


# Função para limpar salas inativas (mais de 2 horas sem atividade)
def clean_inactive_rooms():
    current_time = time.time()
    inactive_rooms = []

    for room_hash, room_data in list(rooms.items()):
        # Aumentar o tempo para 2 horas (7200 segundos)
        if "last_activity" in room_data and current_time - room_data["last_activity"] > 7200:
            inactive_rooms.append(room_hash)

    for room_hash in inactive_rooms:
        del rooms[room_hash]

    save_rooms(rooms)


# Limpar salas inativas
clean_inactive_rooms()


# Função para gerar hash da sala
def generate_room_hash():
    random_string = str(uuid.uuid4())
    return hashlib.sha256(random_string.encode()).hexdigest()[:12]


# Função para atualizar a atividade da sala
def update_room_activity(room_hash):
    if room_hash in rooms:
        rooms[room_hash]["last_activity"] = time.time()
        save_rooms(rooms)


# Função para garantir que o usuário esteja na sala
def ensure_user_in_room(room_hash):
    if room_hash in rooms:
        if st.session_state.user_id not in rooms[room_hash]["users"]:
            rooms[room_hash]["users"][st.session_state.user_id] = st.session_state.user_color
            save_rooms(rooms)


# Função para criar uma nova sala
def create_new_room():
    room_hash = generate_room_hash()
    rooms[room_hash] = {
        "messages": [],
        "users": {st.session_state.user_id: st.session_state.user_color},
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_activity": time.time()
    }
    st.session_state.current_room = room_hash
    st.session_state.page = "chat"
    st.session_state.last_message_count = 0
    save_rooms(rooms)
    return room_hash


# Função para entrar em uma sala existente
def join_room(room_hash):
    # Verificar se a sala existe
    if room_hash in rooms:
        if st.session_state.user_id not in rooms[room_hash]["users"]:
            rooms[room_hash]["users"][st.session_state.user_id] = st.session_state.user_color
        st.session_state.current_room = room_hash
        st.session_state.page = "chat"
        st.session_state.last_message_count = len(rooms[room_hash]["messages"])
        update_room_activity(room_hash)
        save_rooms(rooms)
        return True
    return False


# Função para enviar mensagem e limpar campos
def send_message_and_clear():
    room_hash = st.session_state.current_room
    user_message = st.session_state.message_input
    uploaded_image = st.session_state[
        st.session_state.upload_key] if st.session_state.upload_key in st.session_state else None

    image_path = None

    # Processar imagem se houver
    if uploaded_image is not None:
        image_path = save_image(uploaded_image, room_hash)

    # Enviar mensagem (com ou sem imagem)
    if user_message or image_path:
        # Garantir que o usuário esteja na sala
        ensure_user_in_room(room_hash)

        msg_data = {
            "user_id": st.session_state.user_id,
            "content": user_message,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

        if image_path:
            msg_data["image"] = image_path

        rooms[room_hash]["messages"].append(msg_data)
        st.session_state.last_message_count = len(rooms[room_hash]["messages"])
        update_room_activity(room_hash)
        save_rooms(rooms)

        # Limpar o campo de texto
        st.session_state.message_input = ""

        # Gerar uma nova chave para o uploader (isso forçará a criação de um novo componente)
        st.session_state.upload_key = f"image_upload_{uuid.uuid4()}"


# Função para sair da sala explicitamente
def leave_room():
    room_hash = st.session_state.current_room
    if room_hash in rooms:
        if st.session_state.user_id in rooms[room_hash]["users"]:
            del rooms[room_hash]["users"][st.session_state.user_id]

        # Se a sala estiver vazia, limpar o histórico
        if len(rooms[room_hash]["users"]) == 0:
            rooms[room_hash]["messages"] = []

            # Limpar imagens da sala
            for file in os.listdir(IMAGES_FOLDER):
                if file.startswith(f"{room_hash}_"):
                    os.remove(os.path.join(IMAGES_FOLDER, file))

        save_rooms(rooms)

    st.session_state.current_room = None
    st.session_state.page = "home"


# Função para verificar novas mensagens
def check_new_messages(room_hash):
    if room_hash in rooms:
        current_count = len(rooms[room_hash]["messages"])
        if current_count > st.session_state.last_message_count:
            # Há novas mensagens
            has_new = True
            st.session_state.last_message_count = current_count
            return True
    return False


# Função para converter imagem para base64 (para exibição)
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None


# Estilos CSS personalizados
st.markdown("""
<style>
    /* Estilo para o container de mensagens */
    .chat-message {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 12px;
        position: relative;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }

    /* Estilo para o nome do usuário */
    .user-name {
        font-weight: bold;
        margin-bottom: 5px;
    }

    /* Estilo para o timestamp */
    .timestamp {
        position: absolute;
        top: 12px;
        right: 12px;
        font-size: 0.8em;
        color: #888;
    }

    /* Estilo para o conteúdo da mensagem */
    .message-content {
        margin-top: 8px;
        word-wrap: break-word;
    }

    /* Estilo para imagens */
    .message-image {
        max-width: 100%;
        max-height: 300px;
        margin-top: 10px;
        border-radius: 5px;
    }

    /* Estilo para o campo de entrada */
    .input-container {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 20px;
    }

    /* Estilo para o botão de upload */
    .upload-button {
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Configurar a atualização automática (1000 ms = 1 segundo)
if st.session_state.page == "chat":
    count = st_autorefresh(interval=1000, key="chat_autorefresh")

    # Garantir que o usuário permaneça na sala durante as atualizações
    if st.session_state.current_room in rooms:
        ensure_user_in_room(st.session_state.current_room)

# Interface da tela inicial
if st.session_state.page == "home":
    st.title("🔒 Chat Secreto")

    # Espaçamento para centralizar os botões
    st.markdown("<br><br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### Escolha uma opção:")

        # Botão para criar nova sala
        if st.button("Nova Sala", use_container_width=True, key="new_room_btn"):
            room_hash = create_new_room()
            st.success(f"Sala criada! Hash: {room_hash}")
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Campo para entrar em sala existente
        st.markdown("### Ou entre em uma sala existente:")
        room_hash_input = st.text_input("Hash da Sala", key="room_hash_input")

        if st.button("Entrar na Sala", use_container_width=True, key="join_room_btn"):
            if room_hash_input:
                clean_hash = room_hash_input.strip()
                if join_room(clean_hash):
                    st.success(f"Entrando na sala {clean_hash}...")
                    st.rerun()
                else:
                    st.error(f"Sala não encontrada: {clean_hash}")
            else:
                st.warning("Por favor, insira o hash da sala")

# Interface da sala de chat
elif st.session_state.page == "chat":
    room_hash = st.session_state.current_room

    # Recarregar as salas para obter as atualizações mais recentes
    rooms = load_rooms()

    if room_hash not in rooms:
        st.error("Sala não encontrada!")
        st.session_state.page = "home"
        st.rerun()

    # Garantir que o usuário esteja na sala
    ensure_user_in_room(room_hash)

    # Cabeçalho com informações da sala
    col1, col2, col3 = st.columns([3, 6, 3])

    with col1:
        if st.button("← Voltar"):
            leave_room()
            st.rerun()

    with col2:
        st.title(f"Sala: {room_hash}")

    with col3:
        st.info(f"Usuários ativos: {len(rooms[room_hash]['users'])}")

    # Verificar novas mensagens
    has_new_messages = check_new_messages(room_hash)

    # Container para mensagens
    chat_container = st.container()

    # Container para entrada de mensagem
    input_container = st.container()

    with input_container:
        # Área para upload de imagem com chave dinâmica
        uploaded_image = st.file_uploader("Enviar imagem (opcional)", type=["png", "jpg", "jpeg"],
                                          key=st.session_state.upload_key)

        # Área para mensagem de texto e botão de enviar
        col1, col2 = st.columns([6, 1])

        with col1:
            user_message = st.text_input("Digite sua mensagem:", key="message_input")

        with col2:
            # Alinhar o botão com o campo de texto
            st.markdown("<div style='margin-top: 23px;'></div>", unsafe_allow_html=True)

            # Botão de enviar com callback para limpar os campos
            if st.button("Enviar", use_container_width=True, on_click=send_message_and_clear):
                # A função send_message_and_clear será chamada quando o botão for clicado
                pass

    # Exibir mensagens (apenas as últimas 4)
    with chat_container:
        st.markdown("### Mensagens")

        # Obter apenas as últimas 4 mensagens
        messages = rooms[room_hash]["messages"][-4:] if rooms[room_hash]["messages"] else []

        if not messages:
            st.info("Nenhuma mensagem ainda. Seja o primeiro a enviar!")

        for msg in messages:
            user_color = rooms[room_hash]["users"].get(msg["user_id"], "#CCCCCC")

            # Verificar se há imagem na mensagem
            image_html = ""
            if "image" in msg and msg["image"]:
                image_base64 = get_image_base64(msg["image"])
                if image_base64:
                    image_html = f'<img src="data:image/png;base64,{image_base64}" class="message-image" />'

            # Criar um estilo CSS para o nome do usuário com a cor correspondente
            st.markdown(
                f"""
                <div class="chat-message" style="border-left: 5px solid {user_color}; background-color: rgba({int(user_color[1:3], 16)}, {int(user_color[3:5], 16)}, {int(user_color[5:7], 16)}, 0.1);">
                    <div class="user-name" style="color: {user_color};">Guest</div>
                    <div class="timestamp">{msg["timestamp"]}</div>
                    <div class="message-content">{msg["content"]}</div>
                    {image_html}
                </div>
                """,
                unsafe_allow_html=True
            )

    # Mostrar o hash da sala para compartilhamento
    st.sidebar.header("Compartilhar Sala")
    st.sidebar.code(room_hash)
    st.sidebar.info("Compartilhe este código com seus amigos para que eles possam entrar na sala.")

    # Botão para copiar o hash
    if st.sidebar.button("Copiar Hash"):
        st.sidebar.success("Hash copiado!")
        # Usando JavaScript para copiar para a área de transferência
        st.sidebar.markdown(f"""
        <script>
        const copyToClipboard = str => {{
            const el = document.createElement('textarea');
            el.value = str;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
        }};
        copyToClipboard('{room_hash}');
        </script>
        """, unsafe_allow_html=True)

    # Informações adicionais
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Informações")
    st.sidebar.markdown("• Você é identificado como 'Guest'")
    st.sidebar.markdown("• Apenas as últimas 4 mensagens são exibidas")
    st.sidebar.markdown("• A sala é limpa quando fica vazia")
    st.sidebar.markdown("• Novos usuários não veem mensagens anteriores")

    # Atualizar a atividade da sala
    update_room_activity(room_hash)

    # Configurações de atualização
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Configurações de Atualização")
    st.sidebar.success("Atualização automática a cada 1 segundo está ativa")

    # Botão de atualização manual
    if st.sidebar.button("Atualizar Agora", use_container_width=True):
        st.rerun()

    # Adicionar um elemento para reproduzir som quando houver novas mensagens
    if has_new_messages and st.session_state.user_id != rooms[room_hash]["messages"][-1]["user_id"]:
        # Tentar reproduzir um som simples
        st.markdown("""
        <audio autoplay>
          <source src="data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU" type="audio/wav">
        </audio>
        """, unsafe_allow_html=True)
