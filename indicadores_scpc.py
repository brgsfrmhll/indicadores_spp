
import schedule
import time
import threading
import streamlit as st
import os
import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import base64
from io import BytesIO
import plotly.express as px
import locale
from cryptography.fernet import Fernet
from pathlib import Path  # Adicione esta linha

DATA_DIR = "data"
INDICATORS_FILE = os.path.join(DATA_DIR, "indicators.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
BACKUP_LOG_FILE = os.path.join(DATA_DIR, "backup_log.json")
INDICATOR_LOG_FILE = os.path.join(DATA_DIR, "indicator_log.json")
USER_LOG_FILE = os.path.join(DATA_DIR, "user_log.json")
KEY_FILE = "secret.key"


# Funções para converter a imagem para Base64 (DEFINIÇÃO GLOBAL)
def img_to_bytes(img_path):
    try:
        img_bytes = Path(img_path).read_bytes()
        encoded = base64.b64encode(img_bytes).decode()
        return encoded
    except FileNotFoundError:
        st.error(f"Arquivo não encontrado: {img_path}")
        return None
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return None

def img_to_html(img_path):
    img_bytes = img_to_bytes(img_path)
    if img_bytes:
        img_html = "<img src='data:image/png;base64,{}' class='img-fluid' width='150' style='display: block; margin: 0 auto;'>".format(
            img_bytes
        )
        return img_html
    else:
        return ""


def backup_job(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE, cipher):
    try:
        backup_file = backup_data(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE,
                                  INDICATOR_LOG_FILE, USER_LOG_FILE, cipher, tipo_backup="seguranca")

        if backup_file:
            print(f"Backup automático criado: {backup_file}")
            config = load_config(CONFIG_FILE)
            config["last_backup_date"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            save_config(config, CONFIG_FILE)
            keep_last_backups("backups", 3)
        else:
            print("Falha ao criar o backup automático.")
    except Exception as e:
        print(f"Erro durante o backup: {e}")

def initialize_session_state():
    """Inicializa o estado da sessão do Streamlit."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

def configure_locale():
    """Configura o locale para português do Brasil."""
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

def configure_page():
    """Configura a página do Streamlit."""
    st.set_page_config(
        page_title="Portal de Indicadores",
        page_icon="📊",
        layout="wide"
    )

def create_data_directory(DATA_DIR):
    """Cria o diretório de dados se não existir."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def initialize_json_files(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE):
    """Inicializa os arquivos JSON se não existirem."""
    if not os.path.exists(INDICATORS_FILE):
        with open(INDICATORS_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"theme": "padrao"}, f)

    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": hashlib.sha256("6105/*".encode()).hexdigest(),
                "tipo": "Administrador",
                "setor": "Todos"  # Admin tem acesso a todos os setores
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default_users, f)

def define_default_theme():
    """Define o tema padrão."""
    TEMA_PADRAO = {
        "name": "Padrão",
        "primary_color": "#1E88E5",
        "secondary_color": "#26A69A",
        "background_color": "#FFFFFF",
        "text_color": "#37474F",
        "accent_color": "#FF5252",
        "chart_colors": ["#1E88E5", "#26A69A", "#FFC107", "#7E57C2", "#EC407A"],
        "is_dark": False
    }
    return TEMA_PADRAO

def define_lists():
    """Define as listas de setores e tipos de gráficos."""
    SETORES = ["RH", "Financeiro", "Operações", "Marketing", "Comercial", "TI", "Logística", "Produção"]
    TIPOS_GRAFICOS = ["Linha", "Barra", "Pizza", "Área", "Dispersão"]
    return SETORES, TIPOS_GRAFICOS

def define_menu_icons():
    """Define os ícones para o menu."""
    MENU_ICONS = {
        "Dashboard": "📈",
        "Criar Indicador": "➕",
        "Editar Indicador": "✏️",
        "Preencher Indicador": "📝",
        "Visão Geral": "📊",
        "Gerenciar Usuários": "👥",
        "Configurações": "⚙️"
    }
    return MENU_ICONS

def generate_key(KEY_FILE):
    """Gera uma nova chave de criptografia."""
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
        return key
    return None

def load_key(KEY_FILE):
    """Carrega a chave de criptografia do arquivo ou gera uma nova."""
    try:
        with open(KEY_FILE, "rb") as key_file:
            return key_file.read()
    except FileNotFoundError:
        st.error("Arquivo de chave não encontrado. Execute a função generate_key primeiro.")
        return None

def initialize_cipher(KEY_FILE):
    """Inicializa o objeto Fernet para criptografia."""
    key = load_key(KEY_FILE)
    if key:
        return Fernet(key)
    return None

def backup_data(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, cipher, tipo_backup="user"):
    """Cria um arquivo de backup criptografado com todos os dados."""
    if not cipher:
        st.error("Objeto de criptografia não inicializado.")
        return None

    all_data = {
        "indicators": load_indicators(INDICATORS_FILE),
        "results": load_results(RESULTS_FILE),
        "config": load_config(CONFIG_FILE),
        "users": load_users(USERS_FILE),
        "backup_log": load_backup_log(BACKUP_LOG_FILE),
        "indicator_log": load_indicator_log(INDICATOR_LOG_FILE),
        "user_log": load_user_log(USER_LOG_FILE)
    }

    # Converter todos os dados para string antes de criptografar
    all_data_str = json.dumps(all_data, indent=4, default=str).encode()

    encrypted_data = cipher.encrypt(all_data_str)

    # Adicionar identificador ao nome do arquivo
    if tipo_backup == "user":
        BACKUP_FILE = os.path.join("backups", f"backup_user_{datetime.now().strftime('%Y%m%d%H%M%S')}.bkp")
    else:
        BACKUP_FILE = os.path.join("backups", f"backup_seguranca_{datetime.now().strftime('%Y%m%d%H%M%S')}.bkp")

    # Cria o diretório de backups se não existir
    if not os.path.exists("backups"):
        os.makedirs("backups")

    try:
        with open(BACKUP_FILE, "wb") as backup_file:
            backup_file.write(encrypted_data)
        log_backup_action("Backup criado", BACKUP_FILE, BACKUP_LOG_FILE)  # Registrar ação de backup
        return BACKUP_FILE
    except Exception as e:
        st.error(f"Erro ao criar o backup: {e}")
        return None
def keep_last_backups(BACKUP_DIR, num_backups):
    """Mantém apenas os últimos backups no diretório."""
    # Cria o diretório de backups se não existir
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".bkp")],
                     key=os.path.getmtime, reverse=True)
    if len(backups) > num_backups:
        for backup in backups[num_backups:]:
            try:
                os.remove(backup)
                print(f"Backup removido: {backup}")
            except Exception as e:
                print(f"Erro ao remover backup: {backup} - {e}")

def agendar_backup(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE, cipher):
    config = load_config(CONFIG_FILE)
    backup_hour = config["backup_hour"]

    schedule.clear()  # Limpa qualquer agendamento anterior

    schedule.every().day.at(backup_hour).do(backup_job, INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE, cipher)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Verifica a cada minuto

def restore_data(backup_file, INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, cipher):
    """Restaura os dados a partir de um arquivo de backup criptografado."""
    if not cipher:
        st.error("Objeto de criptografia não inicializado.")
        return False

    try:
        with open(backup_file, "rb") as file:
            encrypted_data = file.read()

        decrypted_data_str = cipher.decrypt(encrypted_data).decode()
        restored_data = json.loads(decrypted_data_str)

        save_indicators(restored_data["indicators"], INDICATORS_FILE)
        save_results(restored_data["results"], RESULTS_FILE)
        save_config(restored_data["config"], CONFIG_FILE)
        save_users(restored_data["users"], USERS_FILE)
        save_backup_log(restored_data["backup_log"], BACKUP_LOG_FILE)
        save_indicator_log(restored_data["indicator_log"], INDICATOR_LOG_FILE)
        save_user_log(restored_data["user_log"], USER_LOG_FILE)

        log_backup_action("Backup restaurado", backup_file, BACKUP_LOG_FILE)  # Registrar ação de restauração
        return True
    except Exception as e:
        st.error(f"Erro ao restaurar o backup: {e}")
        return False
def load_backup_log(BACKUP_LOG_FILE):
    """Carrega o log de backup do arquivo."""
    try:
        with open(BACKUP_LOG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.warning("Erro ao decodificar o arquivo de log de backup. O arquivo pode estar corrompido.")
        return []

def save_backup_log(log_data, BACKUP_LOG_FILE):
    """Salva o log de backup no arquivo."""
    try:
        with open(BACKUP_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=4, default=str)
    except Exception as e:
        st.error(f"Erro ao salvar o log de backup: {e}")

def log_backup_action(action, file_name, BACKUP_LOG_FILE):
    """Registra uma ação de backup no log."""
    log = load_backup_log(BACKUP_LOG_FILE)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "file_name": file_name,
        "user": st.session_state.get("username", "System")
    }
    log.append(log_entry)
    save_backup_log(log, BACKUP_LOG_FILE)

def load_indicators(INDICATORS_FILE):
    """Carrega os indicadores do arquivo."""
    try:
        with open(INDICATORS_FILE, "r") as f:
            indicators = json.load(f)
            return indicators
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def save_indicators(indicators, INDICATORS_FILE):
    """Salva os indicadores no arquivo."""
    try:
        with open(INDICATORS_FILE, "w") as f:
            json.dump(indicators, f, indent=4)
    except Exception as e:
        st.error(f"Erro ao salvar o arquivo de indicadores: {e}")

def log_indicator_action(action, indicator_id, INDICATOR_LOG_FILE):
    """Registra uma ação de indicador no log."""
    log = load_indicator_log(INDICATOR_LOG_FILE)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "indicator_id": indicator_id,
        "user": st.session_state.get("username", "System")
    }
    log.append(log_entry)
    save_indicator_log(log, INDICATOR_LOG_FILE)

def load_users(USERS_FILE):
    """Carrega os usuários do arquivo."""
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        default_users = {
            "admin": {
                "password": hashlib.sha256("6105/*".encode()).hexdigest(),
                "tipo": "Administrador",
                "setor": "Todos"
            }
        }
        save_users(default_users, USERS_FILE)
        return default_users
    except json.JSONDecodeError:
        st.error("Erro ao decodificar o arquivo de usuários. O arquivo pode estar corrompido.")
        return {}

def save_user_log(log_data, USER_LOG_FILE):
    """Salva o log de usuários no arquivo."""
    try:
        with open(USER_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=4, default=str)
    except Exception as e:
        st.error(f"Erro ao salvar o log de usuários: {e}")

def log_user_action(action, username, USER_LOG_FILE):
    """Registra uma ação de usuário no log."""
    log = load_user_log(USER_LOG_FILE)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "username": username,
        "user": st.session_state.get("username", "System")
    }
    log.append(log_entry)
    save_user_log(log, USER_LOG_FILE)

def delete_user(username, USERS_FILE, USER_LOG_FILE):
    """Exclui um usuário do arquivo de usuários."""
    users = load_users(USERS_FILE)
    if username in users:
        del users[username]
        save_users(users, USERS_FILE)
        log_user_action("Usuário excluído", username, USER_LOG_FILE)  # Registrar ação de exclusão
        return True
    return False

def load_user_log(USER_LOG_FILE):
    """Carrega o log de usuários do arquivo."""
    try:
        with open(USER_LOG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.warning("Erro ao decodificar o arquivo de log de usuários. O arquivo pode estar corrompido.")
        return []

def save_users(users, USERS_FILE):
    """Salva os usuários no arquivo."""
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        st.error(f"Erro ao salvar o arquivo de usuários: {e}")

def load_indicator_log(INDICATOR_LOG_FILE):
    """Carrega o log de indicadores do arquivo."""
    try:
        with open(INDICATOR_LOG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.warning("Erro ao decodificar o arquivo de log de indicadores. O arquivo pode estar corrompido.")
        return []

def save_indicator_log(log_data, INDICATOR_LOG_FILE):
    """Salva o log de indicadores no arquivo."""
    try:
        with open(INDICATOR_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=4, default=str)
    except Exception as e:
        st.error(f"Erro ao salvar o log de indicadores: {e}")

def delete_indicator(indicator_id, INDICATORS_FILE, RESULTS_FILE, INDICATOR_LOG_FILE):
    """Exclui um indicador e seus resultados associados."""
    indicators = load_indicators(INDICATORS_FILE)
    results = load_results(RESULTS_FILE)

    # Remover indicador
    indicators = [ind for ind in indicators if ind["id"] != indicator_id]
    save_indicators(indicators, INDICATORS_FILE)

    # Remover resultados associados
    results = [r for r in results if r["indicator_id"] != indicator_id]
    save_results(results, RESULTS_FILE)

    log_indicator_action("Indicador excluído", indicator_id, INDICATOR_LOG_FILE)  # Registrar ação de exclusão
    st.success(f"Indicador com ID '{indicator_id}' e seus resultados associados foram excluídos com sucesso!")

def load_results(RESULTS_FILE):
    """Carrega os resultados do arquivo."""
    try:
        with open(RESULTS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.error("Erro ao decodificar o arquivo de resultados. O arquivo pode estar corrompido.")
        return []

def save_results(results, RESULTS_FILE):
    """Salva os resultados no arquivo."""
    try:
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=4)
    except Exception as e:
        st.error(f"Erro ao salvar o arquivo de resultados: {e}")

def load_config(CONFIG_FILE):
    """Carrega a configuração do arquivo."""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Garante que a chave 'backup_hour' exista
            if "backup_hour" not in config:
                config["backup_hour"] = "00:00"
            # Garante que a chave 'last_backup_date' exista
            if "last_backup_date" not in config:
                config["last_backup_date"] = ""
            return config
    except FileNotFoundError:
        config = {"theme": "padrao", "backup_hour": "00:00", "last_backup_date": ""}
        save_config(config, CONFIG_FILE)
        return config
    except json.JSONDecodeError:
        st.error("Erro ao decodificar o arquivo de configuração. O arquivo pode estar corrompido.")
        return {"theme": "padrao", "backup_hour": "00:00", "last_backup_date": ""}

def save_config(config, CONFIG_FILE):
    """Salva a configuração no arquivo."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        st.error(f"Erro ao salvar o arquivo de configuração: {e}")
def verify_credentials(username, password, USERS_FILE):
    """Verifica as credenciais do usuário."""
    users = load_users(USERS_FILE)
    if username in users:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if isinstance(users[username], dict):
            return hashed_password == users[username].get("password", "")
        else:
            # Compatibilidade com formato antigo
            return hashed_password == users[username]
    return False

def get_user_type(username, USERS_FILE):
    """Obtém o tipo de usuário."""
    users = load_users(USERS_FILE)
    if username in users:
        if isinstance(users[username], dict):
            return users[username].get("tipo", "Visualizador")
        else:
            # Compatibilidade com formato antigo - assume admin para usuários antigos
            return "Administrador" if username == "admin" else "Visualizador"
    return "Visualizador"  # Padrão para segurança

def get_user_sector(username, USERS_FILE):
    """Obtém o setor do usuário."""
    users = load_users(USERS_FILE)
    if username in users:
        if isinstance(users[username], dict):
            return users[username].get("setor", "Todos")
        else:
            # Compatibilidade com formato antigo
            return "Todos"
    return "Todos"  # Padrão para segurança

def generate_id():
    """Gera um ID único baseado na data e hora."""
    return datetime.now().strftime("%Y%m%d%H%M%S")

def format_date_as_month_year(date):
    """Formata a data como mês/ano."""
    try:
        return date.strftime("%b/%Y")
    except:
        try:
            return date.strftime("%m/%Y")
        except:
            return str(date)

def to_excel(df):
    """Converte um DataFrame para um arquivo Excel em memória."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    processed_data = output.getvalue()
    return processed_data

def get_download_link(df, filename):
    """Gera um link para download de um arquivo Excel."""
    val = to_excel(df)
    b64 = base64.b64encode(val).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" style="display: inline-block; padding: 0.5rem 1rem; background-color: #1E88E5; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">Baixar Excel</a>'

def base64_image(image_path):
    """Codifica uma imagem para base64."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""  # Retornar uma string vazia se a imagem não for encontrada

def create_chart(indicator_id, chart_type, INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO):
    """Cria um gráfico com base no tipo especificado."""
    # Carregar resultados
    results = load_results(RESULTS_FILE)

    # Filtrar resultados para o indicador específico
    indicator_results = [r for r in results if r["indicator_id"] == indicator_id]

    if not indicator_results:
        return None

    # Preparar dados para o gráfico
    df = pd.DataFrame(indicator_results)
    df["data_referencia"] = pd.to_datetime(df["data_referencia"])
    df = df.sort_values("data_referencia")

    # Criar coluna formatada para exibição nos gráficos
    df["data_formatada"] = df["data_referencia"].apply(format_date_as_month_year)

    # Encontrar o indicador para obter informações adicionais
    indicators = load_indicators(INDICATORS_FILE)
    indicator = next((ind for ind in indicators if ind["id"] == indicator_id), None)

    if not indicator:
        return None

    # Obter cores do tema padrão
    chart_colors = TEMA_PADRAO["chart_colors"]
    is_dark = TEMA_PADRAO["is_dark"]
    background_color = TEMA_PADRAO["background_color"]
    text_color = TEMA_PADRAO["text_color"]

    # Criar gráfico com base no tipo
    if chart_type == "Linha":
        fig = px.line(
            df,
            x="data_formatada",
            y="resultado",
            title=f"Evolução do Indicador: {indicator['nome']}",
            color_discrete_sequence=[chart_colors[0]],
            markers=True
        )
        # Adicionar linha de meta
        fig.add_hline(
            y=float(indicator["meta"]),
            line_dash="dash",
            line_color=chart_colors[4],
            annotation_text="Meta"
        )

    elif chart_type == "Barra":
        fig = px.bar(
            df,
            x="data_formatada",
            y="resultado",
            title=f"Evolução do Indicador: {indicator['nome']}",
            color_discrete_sequence=[chart_colors[0]]
        )
        # Adicionar linha de meta
        fig.add_hline(
            y=float(indicator["meta"]),
            line_dash="dash",
            line_color=chart_colors[4],
            annotation_text="Meta"
        )

    elif chart_type == "Pizza":
        # Para gráfico de pizza, usamos o último resultado vs meta
        last_result = df.iloc[-1]["resultado"]
        fig = px.pie(
            names=["Resultado Atual", "Meta"],
            values=[last_result, float(indicator["meta"])],
            title=f"Último Resultado vs Meta: {indicator['nome']}",
            color_discrete_sequence=[chart_colors[0], chart_colors[1]],
            hole=0.4  # Transforma em donut chart para melhor visualização
        )

    elif chart_type == "Área":
        fig = px.area(
            df,
            x="data_formatada",
            y="resultado",
            title=f"Evolução do Indicador: {indicator['nome']}",
            color_discrete_sequence=[chart_colors[0]]
        )
        # Adicionar linha de meta
        fig.add_hline(
            y=float(indicator["meta"]),
            line_dash="dash",
            line_color=chart_colors[4],
            annotation_text="Meta"
        )

    elif chart_type == "Dispersão":
        fig = px.scatter(
            df,
            x="data_formatada",
            y="resultado",
            title=f"Evolução do Indicador: {indicator['nome']}",
            color_discrete_sequence=[chart_colors[0]],
            size_max=15
        )
        # Adicionar linha de meta
        fig.add_hline(
            y=float(indicator["meta"]),
            line_dash="dash",
            line_color=chart_colors[4],
            annotation_text="Meta"
        )

    # Personalizar layout
    fig.update_layout(
        xaxis_title="Data de Referência",
        yaxis_title="Resultado",
        template="plotly_white"
    )

    # Ajustar para tema escuro se necessário
    if is_dark:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=background_color,
            plot_bgcolor="#1E1E1E",
            font=dict(color=text_color)
        )

    return fig

def show_login_page():
    """Mostra a página de login."""

    # CSS minimalista e eficaz
    st.markdown("""
    <style>
    /* Ocultar elementos padrão do Streamlit */
    #MainMenu, header, footer {display: none;}

    /* Estilo geral da página */
    .main {
        background-color: #f8f9fa;
        padding: 0;
    }

    /* Remover o menu de deploy */
    [data-testid="stToolbar"] {
        display: none !important;
    }

    /* Remover a borda colorida */
    [data-testid="stAppViewContainer"] {
        border: none !important;
    }

    /* Remover o rodapé do Streamlit */
    footer {
        display: none !important;
    }

    /* Remover o ícone de hambúrguer e menu principal */
    #MainMenu {
        visibility: hidden !important;
    }

    /* Remover o header com informações do Streamlit */
    header {
        display: none !important;
    }

    /* Estilo para inputs */
    .stTextInput > div > div > input {
        border-radius: 6px;
        border: 1px solid #E0E0E0;
        padding: 10px 15px;
        font-size: 15px;
    }

    /* Estilo para botão de login */
    div[data-testid="stForm"] button[type="submit"] {
        background-color: #1E88E5;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 15px;
        font-size: 16px;
        font-weight: 500;
        width: 100%;
    }

    /* Espaçamento para o card */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 450px;
    }

    /* Estilo para mensagens */
    .stAlert {
        border-radius: 6px;
    }

    /* Fundo da página */
    .stApp {
        background-color: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)

    # Card de login usando elementos nativos
    with st.container():
        # Centralizar logo
        image_path = "logo.png"  # Verifique se o arquivo está no mesmo diretório ou ajuste o caminho
        if os.path.exists(image_path):
            st.markdown(f"<div style='text-align: center;'>{img_to_html(image_path)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align: center; font-size: 50px;'>📊</h1>", unsafe_allow_html=True)

        # Títulos centralizados
        st.markdown("<h1 style='text-align: center; font-size: 30px; color: #1E88E5;'>Portal de Indicadores</h1>",
                    unsafe_allow_html=True)
        st.markdown(
            "<h2 style='text-align: center; font-size: 26px; color: #546E7A; margin-bottom: 20px;'>Santa Casa - Poços de Caldas</h2>",
            unsafe_allow_html=True)

        # Separador simples
        st.markdown("<hr style='height: 2px; background: #E0E0E0; border: none; margin: 20px 0;'>",
                    unsafe_allow_html=True)

        # Formulário de login
        st.markdown("<h3 style='font-size: 18px; color: #455A64; margin-bottom: 15px;'>Acesse sua conta</h3>",
                    unsafe_allow_html=True)

        # Formulário com componentes nativos
        with st.form("login_form"):
            username = st.text_input("Nome de usuário", placeholder="Digite seu nome de usuário")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")

            submit = st.form_submit_button("Entrar")

            if submit:
                if username and password:
                    with st.spinner("Verificando..."):
                        time.sleep(0.5)

                        # Get the file paths from the global scope
                        DATA_DIR, INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE = define_data_directories()

                        if verify_credentials(username, password, USERS_FILE):
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.success("Login realizado com sucesso!")
                            time.sleep(0.8)
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")
                else:
                    st.error("Por favor, preencha todos os campos.")

        # Rodapé simples
        st.markdown(
            "<p style='text-align: center; font-size: 12px; color: #78909C; margin-top: 30px;'>© 2025 Portal de Indicadores - Santa Casa</p>",
            unsafe_allow_html=True)

def create_indicator(SETORES, TIPOS_GRAFICOS, INDICATORS_FILE, INDICATOR_LOG_FILE):
    """Mostra a página de criação de indicador."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Criar Novo Indicador")

    # Limpar variáveis de sessão específicas do Dashboard
    if 'dashboard_data' in st.session_state:
        del st.session_state['dashboard_data']

    # Formulário para criar indicador
    with st.form("criar_indicador"):
        nome = st.text_input("Nome do Indicador", placeholder="Ex: Taxa de Turnover")
        objetivo = st.text_area("Objetivo", placeholder="Descreva o objetivo deste indicador")
        calculo = st.text_area("Fórmula de Cálculo",
                               placeholder="Ex: (Número de Demissões / Número Total de Funcionários) * 100")
        meta = st.number_input("Meta", step=0.01)
        comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"])
        tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS)
        responsavel = st.selectbox("Setor Responsável", SETORES)

        submitted = st.form_submit_button("➕ Criar")

        if submitted:
            if nome and objetivo and calculo and meta:
                # Efeito de carregamento
                with st.spinner("Criando indicador..."):
                    time.sleep(0.5)  # Pequeno delay para efeito visual

                    # Carregar indicadores existentes
                    indicators = load_indicators(INDICATORS_FILE)

                    # Verificar se já existe um indicador com o mesmo nome
                    if any(ind["nome"] == nome for ind in indicators):
                        st.error(f"Já existe um indicador com o nome '{nome}'.")
                    else:
                        # Criar novo indicador
                        new_indicator = {
                            "id": generate_id(),
                            "nome": nome,
                            "objetivo": objetivo,
                            "calculo": calculo,
                            "meta": meta,
                            "comparacao": comparacao,
                            "tipo_grafico": tipo_grafico,
                            "responsavel": responsavel,
                            "data_criacao": datetime.now().isoformat(),
                            "data_atualizacao": datetime.now().isoformat()
                        }

                        # Adicionar à lista e salvar
                        indicators.append(new_indicator)
                        save_indicators(indicators, INDICATORS_FILE)
                        log_indicator_action("Indicador criado", new_indicator["id"], INDICATOR_LOG_FILE)  # Registrar ação de criação

                        st.success(f"Indicador '{nome}' criado com sucesso!")
            else:
                st.warning("Todos os campos são obrigatórios.")
    st.markdown('</div>', unsafe_allow_html=True)

def edit_indicator(SETORES, TIPOS_GRAFICOS, INDICATORS_FILE, INDICATOR_LOG_FILE, RESULTS_FILE):
    """Mostra a página de edição de indicador."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Editar Indicador")

    # Carregar indicadores (sempre)
    st.session_state["indicators"] = load_indicators(INDICATORS_FILE)

    indicators = st.session_state["indicators"]

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Selecionar indicador para editar
    indicator_names = [ind["nome"] for ind in indicators]
    selected_indicator_name = st.selectbox("Selecione um indicador para editar:", indicator_names)

    # Encontrar o indicador selecionado
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        # Formulário para editar indicador
        with st.form(key=f"edit_form_{selected_indicator['id']}"):
            nome = st.text_input("Nome do Indicador", value=selected_indicator["nome"])
            objetivo = st.text_area("Objetivo", value=selected_indicator["objetivo"])
            calculo = st.text_area("Fórmula de Cálculo", value=selected_indicator["calculo"])
            meta = st.number_input("Meta", value=float(selected_indicator["meta"]), step=0.01)
            comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"],
                                      index=0 if selected_indicator["comparacao"] == "Maior é melhor" else 1)
            tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS,
                                        index=TIPOS_GRAFICOS.index(selected_indicator["tipo_grafico"]))
            responsavel = st.selectbox("Setor Responsável", SETORES,
                                       index=SETORES.index(selected_indicator["responsavel"]))

            # Criar colunas para os botões
            col1, col2, col3 = st.columns([1, 3, 1])  # Ajuste das proporções

            # Aplicar estilo para alinhar o botão "Excluir" à direita na coluna 3
            st.markdown(
                """
                <style>
                [data-testid="stForm"] div:nth-child(3) > div:first-child {
                    text-align: right;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            with col1:
                submitted = st.form_submit_button("💾 Salvar")
            with col3:
                delete = st.form_submit_button("🗑️ Excluir", type="secondary")
                if delete:
                    st.session_state[f"deleting_indicator_{selected_indicator['id']}"] = True

            if submitted:
                if nome and objetivo and calculo and meta:
                    # Verificar se o nome foi alterado e se já existe outro indicador com esse nome
                    if nome != selected_indicator["nome"] and any(
                            ind["nome"] == nome for ind in indicators if ind["id"] != selected_indicator["id"]):
                        st.error(f"Já existe um indicador com o nome '{nome}'.")
                    else:
                        # Atualizar indicador
                        for ind in indicators:
                            if ind["id"] == selected_indicator["id"]:
                                ind["nome"] = nome
                                ind["objetivo"] = objetivo
                                ind["calculo"] = calculo
                                ind["meta"] = meta
                                ind["comparacao"] = comparacao
                                ind["tipo_grafico"] = tipo_grafico
                                ind["responsavel"] = responsavel
                                ind["data_atualizacao"] = datetime.now().isoformat()

                        # Salvar alterações
                        save_indicators(indicators, INDICATORS_FILE)
                        st.session_state["indicators"] = load_indicators(INDICATORS_FILE)  # Recarrega os indicadores
                        st.success(f"Indicador '{nome}' atualizado com sucesso!")
                        st.rerun()
                else:
                    st.warning("Todos os campos são obrigatórios.")

        # Bloco para exclusão
        if st.session_state.get(f"deleting_indicator_{selected_indicator['id']}", False):
            st.warning(f"Tem certeza que deseja excluir o indicador '{selected_indicator['nome']}'?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Sim, Excluir", key=f"confirm_delete_{selected_indicator['id']}"):
                    # Excluir indicador
                    delete_indicator(selected_indicator["id"], INDICATORS_FILE, RESULTS_FILE, INDICATOR_LOG_FILE)
                    st.success(f"Indicador '{selected_indicator['nome']}' excluído com sucesso!")

                    # Remover o indicador da lista
                    indicators = [ind for ind in indicators if ind["id"] != selected_indicator["id"]]

                    # Atualizar o estado da sessão e o arquivo JSON
                    st.session_state["indicators"] = indicators
                    save_indicators(indicators, INDICATORS_FILE)

                     # Limpar estado de exclusão
                    if f"deleting_indicator_{selected_indicator['id']}" in st.session_state:
                        del st.session_state[f"deleting_indicator_{selected_indicator['id']}"]

                    # Recarrega a página para atualizar a lista
                    st.rerun()
            with col2:
                if st.button("❌ Cancelar", key=f"cancel_delete_{selected_indicator['id']}"):
                    st.info("Exclusão cancelada.")
                     # Limpar estado de exclusão
                    if f"deleting_indicator_{selected_indicator['id']}" in st.session_state:
                        del st.session_state[f"deleting_indicator_{selected_indicator['id']}"]
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

def fill_indicator(SETORES, INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO):
    """Mostra a página de preenchimento de indicador."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Preencher Indicador")

    # Carregar indicadores
    indicators = load_indicators(INDICATORS_FILE)

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtrar indicadores pelo setor do usuário (se for operador)
    user_type = st.session_state.user_type
    user_sector = st.session_state.user_sector
    # Nome do usuário para registro em log
    user_name = st.session_state.get("user_name", "Usuário não identificado")

    if user_type == "Operador":
        indicators = [ind for ind in indicators if ind["responsavel"] == user_sector]
        if not indicators:
            st.info(f"Não há indicadores associados ao seu setor ({user_sector}).")
            st.markdown('</div>', unsafe_allow_html=True)
            return

    # Selecionar indicador para preencher
    indicator_names = [ind["nome"] for ind in indicators]
    selected_indicator_name = st.selectbox("Selecione um indicador para preencher:", indicator_names)
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        st.subheader(f"Informações do Indicador: {selected_indicator['nome']}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Objetivo:** {selected_indicator['objetivo']}")
            st.markdown(f"**Fórmula de Cálculo:** {selected_indicator['calculo']}")
        with col2:
            st.markdown(f"**Meta:** {selected_indicator['meta']}")
            st.markdown(f"**Comparação:** {selected_indicator['comparacao']}")
            st.markdown(f"**Setor Responsável:** {selected_indicator['responsavel']}")
        st.markdown("---")

        # Carregar resultados existentes para verificar meses já preenchidos
        results = load_results(RESULTS_FILE)
        indicator_results = [r for r in results if r["indicator_id"] == selected_indicator["id"]]

        # Criar um conjunto de meses/anos já preenchidos
        filled_periods = set()
        for result in indicator_results:
            if "data_referencia" in result:
                try:
                    date_ref = pd.to_datetime(result["data_referencia"].split('T')[0])
                    filled_periods.add((date_ref.month, date_ref.year))
                except:
                    pass

        # Verificar se há períodos disponíveis para preenchimento
        current_year = datetime.now().year
        available_periods = []

        # Considerar os últimos 5 anos para possíveis preenchimentos
        for year in range(current_year - 5, current_year + 1):
            for month in range(1, 13):
                # Não permitir preenchimento de meses futuros
                if year == current_year and month > datetime.now().month:
                    continue
                if (month, year) not in filled_periods:
                    available_periods.append((month, year))

        if not available_periods:
            st.info("Todos os períodos relevantes já foram preenchidos para este indicador.")
        else:
            st.subheader("Adicionar Novo Resultado")
            with st.form("adicionar_resultado"):
                # Ordenar períodos disponíveis (mais recentes primeiro)
                available_periods.sort(key=lambda x: (x[1], x[0]), reverse=True)

                # Criar opções para o selectbox
                period_options = [f"{datetime(year, month, 1).strftime('%B/%Y')}" for month, year in available_periods]
                selected_period = st.selectbox("Selecione o período para preenchimento:", period_options)

                # Extrair mês e ano do período selecionado
                selected_month, selected_year = None, None
                for i, period_str in enumerate(period_options):
                    if period_str == selected_period:
                        selected_month, selected_year = available_periods[i]
                        break

                resultado = st.number_input("Resultado", step=0.01)
                observacoes = st.text_area("Observações (opcional)",
                                           placeholder="Adicione informações relevantes sobre este resultado")
                # Análise Crítica 5W2H
                st.markdown("### Análise Crítica (5W2H)")
                st.markdown("""
                <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                    <p style="margin: 0; font-size: 14px;">
                        A metodologia 5W2H ajuda a estruturar a análise crítica de forma completa, 
                        abordando todos os aspectos relevantes da situação.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                what = st.text_area("O que (What)",
                                    placeholder="O que está acontecendo? Qual é a situação atual do indicador?")
                why = st.text_area("Por que (Why)",
                                   placeholder="Por que isso está acontecendo? Quais são as causas?")
                who = st.text_area("Quem (Who)",
                                   placeholder="Quem é responsável? Quem está envolvido?")
                when = st.text_area("Quando (When)",
                                    placeholder="Quando isso aconteceu? Qual é o prazo para resolução?")
                where = st.text_area("Onde (Where)",
                                     placeholder="Onde ocorre a situação? Em qual processo ou área?")
                how = st.text_area("Como (How)",
                                   placeholder="Como resolver a situação? Quais ações devem ser tomadas?")
                howMuch = st.text_area("Quanto custa (How Much)",
                                       placeholder="Quanto custará implementar a solução? Quais recursos são necessários?")
                submitted = st.form_submit_button("✔️ Salvar")

            if submitted and selected_month and selected_year:
                if resultado is not None:
                    data_referencia = datetime(selected_year, selected_month, 1).isoformat()
                    analise_critica = {
                        "what": what, "why": why, "who": who, "when": when,
                        "where": where, "how": how, "howMuch": howMuch
                    }

                    # Verificar o status de preenchimento da análise crítica
                    campos_preenchidos = sum(1 for campo in analise_critica.values() if campo.strip())
                    total_campos = len(analise_critica)

                    if campos_preenchidos == 0:
                        status_analise = "❌ Não preenchida"
                    elif campos_preenchidos == total_campos:
                        status_analise = "✅ Preenchida completamente"
                    else:
                        status_analise = f"⚠️ Preenchida parcialmente ({campos_preenchidos}/{total_campos})"

                    # Adicionar o status ao dicionário para armazenar no JSON
                    analise_critica["status_preenchimento"] = status_analise

                    analise_critica_json = json.dumps(analise_critica)

                    # Verificar se já existe um resultado para este período (não deveria, mas por segurança)
                    existing_result = next(
                        (r for r in results
                         if r["indicator_id"] == selected_indicator["id"] and r["data_referencia"] == data_referencia),
                        None)

                    if existing_result:
                        st.warning(
                            f"Já existe um resultado para {datetime(selected_year, selected_month, 1).strftime('%B/%Y')}. Este período não deveria estar disponível para preenchimento.")
                    else:
                        new_result = {
                            "indicator_id": selected_indicator["id"],
                            "data_referencia": data_referencia,
                            "resultado": resultado,
                            "observacao": observacoes,
                            "analise_critica": analise_critica_json,
                            "data_criacao": datetime.now().isoformat(),
                            "data_atualizacao": datetime.now().isoformat(),
                            "usuario": user_name,  # REGISTRO
                            "status_analise": status_analise  # Adicionar status da análise
                        }
                        results.append(new_result)
                        save_results(results, RESULTS_FILE)
                        st.success(
                            f"Resultado adicionado com sucesso para {datetime(selected_year, selected_month, 1).strftime('%B/%Y')}!")
                        # Recarregar a página para atualizar a lista de períodos disponíveis
                        st.rerun()
                else:
                    st.warning("Por favor, informe o resultado.")

        # Exibir resultados anteriores
        st.subheader("Resultados Anteriores")
        if indicator_results:
            df_results = pd.DataFrame(indicator_results)
            # Limpar as strings e converter para datetime
            df_results["data_referencia"] = df_results["data_referencia"].str.split('T').str[0]
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"], format='%Y-%m-%d')
            df_results = df_results.sort_values("data_referencia", ascending=False)
            df_display = df_results.copy()
            df_display["Período"] = df_display["data_referencia"].apply(lambda x: x.strftime("%B/%Y"))
            df_display["Resultado"] = df_display["resultado"]
            if "observacao" in df_display.columns:
                df_display["Observações"] = df_display["observacao"]
            else:
                df_display["Observações"] = ""
            if "data_atualizacao" in df_display.columns:
                df_display["Data de Atualização"] = pd.to_datetime(df_display["data_atualizacao"]).dt.strftime(
                    "%d/%m/%Y %H:%M")
            else:
                df_display["Data de Atualização"] = "N/A"

            # Verificar o status da análise crítica para cada resultado
            if "analise_critica" in df_display.columns:
                df_display["Análise Crítica"] = df_display.apply(
                    lambda row: row.get("status_analise", "") if "status_analise" in row else (
                        get_analise_status(row["analise_critica"]) if row["analise_critica"] else "❌ Não preenchida"
                    ), axis=1
                )
            else:
                df_display["Análise Crítica"] = "❌ Não preenchida"

            df_display = df_display[["Período", "Resultado", "Observações", "Análise Crítica", "Data de Atualização"]]
            st.dataframe(df_display, use_container_width=True)

            # Substituir a seção de edição por visualização apenas
            st.subheader("Visualizar Análise Crítica")
            periodos = df_results["data_referencia"].dt.strftime("%B/%Y").tolist()
            selected_periodo = st.selectbox("Selecione um período:", periodos)
            selected_result = df_results[df_results["data_referencia"].dt.strftime("%B/%Y") == selected_periodo].iloc[0]

            has_analise = False
            analise_dict = {"what": "", "why": "", "who": "", "when": "", "where": "", "how": "", "howMuch": ""}
            if "analise_critica" in selected_result and selected_result["analise_critica"]:
                try:
                    analise_dict = json.loads(selected_result["analise_critica"])
                    has_analise = any(v.strip() for k, v in analise_dict.items() if k != "status_preenchimento")
                except:
                    pass

            with st.expander("Análise Crítica 5W2H", expanded=True):
                if has_analise:
                    st.info(f"Visualizando análise crítica para o período {selected_periodo}")

                    # Exibir campos como texto estático, não como campos editáveis
                    st.markdown("#### O que (What)")
                    st.text(analise_dict.get("what", ""))

                    st.markdown("#### Por que (Why)")
                    st.text(analise_dict.get("why", ""))

                    st.markdown("#### Quem (Who)")
                    st.text(analise_dict.get("who", ""))

                    st.markdown("#### Quando (When)")
                    st.text(analise_dict.get("when", ""))

                    st.markdown("#### Onde (Where)")
                    st.text(analise_dict.get("where", ""))

                    st.markdown("#### Como (How)")
                    st.text(analise_dict.get("how", ""))

                    st.markdown("#### Quanto custa (How Much)")
                    st.text(analise_dict.get("howMuch", ""))

                    # Exibir status do preenchimento
                    status = analise_dict.get("status_preenchimento", selected_result.get("status_analise", ""))
                    if status:
                        st.markdown(f"**Status do preenchimento:** {status}")
                else:
                    st.warning(f"Não há análise crítica para o período {selected_periodo}.")

            st.subheader("Gráfico de Evolução")
            fig = create_chart(selected_indicator["id"], selected_indicator["tipo_grafico"], INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Não foi possível gerar o gráfico.")
            if st.button("📤 Exportar para Excel"):
                export_df = df_display.copy()
                download_link = get_download_link(export_df,
                                                  f"resultados_{selected_indicator['nome'].replace(' ', '_')}.xlsx")
                st.markdown(download_link, unsafe_allow_html=True)
        else:
            st.info("Nenhum resultado registrado para este indicador.")

        # --------------- LOG DE PREENCHIMENTO (NOVO BLOCO) ---------------
        st.markdown("---")
        # Carregar todos os resultados após possíveis atualizações
        all_results = load_results(RESULTS_FILE)
        log_results = [r for r in all_results if r["indicator_id"] == selected_indicator["id"]]
        log_results = sorted(log_results, key=lambda x: x.get("data_atualizacao", ""), reverse=True)
        if log_results:
            log_df = pd.DataFrame(log_results)
            # Aplica a função format_date para garantir formatação consistente
            log_df["Data do Preenchimento"] = [
                format_date_as_month_year(r.get("data_atualizacao", r.get("data_criacao", datetime.now().isoformat())))
                for r in log_results]
            log_df["Valor Preenchido"] = log_df["resultado"]
            if "usuario" in log_df.columns:
                log_df["Usuário"] = log_df["usuario"]
            else:
                log_df["Usuário"] = user_name
            log_df["Período"] = pd.to_datetime(log_df["data_referencia"]).dt.strftime("%B/%Y")

            # Adicionar status da análise crítica ao log
            if "status_analise" in log_df.columns:
                log_df["Status Análise Crítica"] = log_df["status_analise"]
            else:
                # Verificar o status da análise crítica para cada resultado
                log_df["Status Análise Crítica"] = log_df["analise_critica"].apply(get_analise_status)

            exibir_log = log_df[
                ["Período", "Valor Preenchido", "Usuário", "Status Análise Crítica", "Data do Preenchimento"]]
            exibir_log = exibir_log.drop_duplicates(subset=["Período", "Valor Preenchido", "Usuário"], keep='first')
        else:
            exibir_log = pd.DataFrame(
                columns=["Período", "Valor Preenchido", "Usuário", "Status Análise Crítica", "Data do Preenchimento"]
            )
        with st.expander("📜 Log de Preenchimentos (clique para visualizar)", expanded=False):
            if exibir_log.empty:
                st.info("Nenhum registro de preenchimento encontrado para este indicador.")
            else:
                st.dataframe(exibir_log, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

def get_analise_status(analise_json):
    """Função auxiliar para verificar o status de preenchimento da análise crítica."""
    if not analise_json or analise_json.strip() == "{}":
        return "❌ Não preenchida"

    try:
        analise_dict = json.loads(analise_json)
        # Se já tiver o status salvo, retorna ele
        if "status_preenchimento" in analise_dict:
            return analise_dict["status_preenchimento"]

        # Caso contrário, calcula o status
        campos_relevantes = ["what", "why", "who", "when", "where", "how", "howMuch"]
        campos_preenchidos = sum(
            1 for campo in campos_relevantes if campo in analise_dict and analise_dict[campo].strip())
        total_campos = len(campos_relevantes)

        if campos_preenchidos == 0:
            return "❌ Não preenchida"
        elif campos_preenchidos == total_campos:
            return "✅ Preenchida completamente"
        else:
            return f"⚠️ Preenchida parcialmente ({campos_preenchidos}/{total_campos})"
    except:
        return "❌ Não preenchida"

def show_dashboard(INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO, SETORES):
    """Mostra o dashboard de indicadores."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Dashboard de Indicadores")

    # Carregar indicadores e resultados
    indicators = load_indicators(INDICATORS_FILE)
    results = load_results(RESULTS_FILE)

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtros em uma única linha
    col1, col2 = st.columns(2)

    with col1:
        # Filtrar por setor (considerando permissões do usuário)
        if st.session_state.user_type == "Operador" and st.session_state.user_sector != "Todos":
            # Operadores só podem ver seu próprio setor
            setor_filtro = st.session_state.user_sector
            st.info(f"Visualizando indicadores do setor: {setor_filtro}")
        else:
            # Administradores e Visualizadores podem selecionar o setor
            setores_disponiveis = ["Todos"] + list(set(ind["responsavel"] for ind in indicators))
            setor_filtro = st.selectbox("Filtrar por Setor:", setores_disponiveis)

    with col2:
        # Filtrar por status
        status_options = ["Todos", "Acima da Meta", "Abaixo da Meta", "Sem Resultados"]
        status_filtro = st.multiselect("Filtrar por Status:", status_options, default=["Todos"])

    # Aplicar filtro de setor
    if setor_filtro != "Todos":
        filtered_indicators = [ind for ind in indicators if ind["responsavel"] == setor_filtro]
    else:
        filtered_indicators = indicators

    # Se não houver indicadores após filtro
    if not filtered_indicators:
        st.warning(f"Nenhum indicador encontrado para o setor {setor_filtro}.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Resumo em cards horizontais
    st.subheader("Resumo dos Indicadores")

    # Calcular estatísticas
    total_indicators = len(filtered_indicators)
    indicators_with_results = 0
    indicators_above_target = 0
    indicators_below_target = 0

    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        if ind_results:
            indicators_with_results += 1

            # Pegar o resultado mais recente
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)

            last_result = float(df_results.iloc[0]["resultado"])
            meta = float(ind["meta"])

            if ind["comparacao"] == "Maior é melhor":
                if last_result >= meta:
                    indicators_above_target += 1
                else:
                    indicators_below_target += 1
            else:  # Menor é melhor
                if last_result <= meta:
                    indicators_above_target += 1
                else:
                    indicators_below_target += 1

    # Cards de resumo em uma única linha
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:#1E88E5;">{total_indicators}</h3>
            <p style="margin:0;">Total de Indicadores</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:#1E88E5;">{indicators_with_results}</h3>
            <p style="margin:0;">Com Resultados</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background-color:#26A69A; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:white;">{indicators_above_target}</h3>
            <p style="margin:0; color:white;">Acima da Meta</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="background-color:#FF5252; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:white;">{indicators_below_target}</h3>
            <p style="margin:0; color:white;">Abaixo da Meta</p>
        </div>
        """, unsafe_allow_html=True)

    # Gráfico de status dos indicadores
    st.subheader("Status dos Indicadores")

    # Dados para o gráfico de pizza
    status_data = {
        "Status": ["Acima da Meta", "Abaixo da Meta", "Sem Resultados"],
        "Quantidade": [
            indicators_above_target,
            indicators_below_target,
            total_indicators - indicators_with_results
        ]
    }

    # Criar DataFrame
    df_status = pd.DataFrame(status_data)

    # Criar gráfico de pizza
    fig_status = px.pie(
        df_status,
        names="Status",
        values="Quantidade",
        title="Distribuição de Status dos Indicadores",
        color="Status",
        color_discrete_map={
            "Acima da Meta": "#26A69A",
            "Abaixo da Meta": "#FF5252",
            "Sem Resultados": "#9E9E9E"
        }
    )

    # Mostrar gráfico
    st.plotly_chart(fig_status, use_container_width=True)

    # Mostrar indicadores individualmente em uma única coluna
    st.subheader("Indicadores")

    # Aplicar filtro de status aos indicadores
    indicator_data = []

    for ind in filtered_indicators:
        # Obter resultados do indicador
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]

        if ind_results:
            # Pegar o resultado mais recente
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)

            last_result = df_results.iloc[0]["resultado"]
            last_date = df_results.iloc[0]["data_referencia"]

            # Calcular status
            try:
                meta = float(ind["meta"])
                resultado = float(last_result)

                if ind["comparacao"] == "Maior é melhor":
                    status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else:  # Menor é melhor
                    status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"

                # Calcular variação percentual
                variacao = ((resultado / meta) - 1) * 100
                if ind["comparacao"] == "Menor é melhor":
                    variacao = -variacao  # Inverter para exibição correta

            except:
                status = "N/A"
                variacao = 0

            # Formatar data
            data_formatada = format_date_as_month_year(last_date)

        else:
            last_result = "N/A"
            data_formatada = "N/A"
            status = "Sem Resultados"
            variacao = 0

        # Adicionar à lista de dados
        indicator_data.append({
            "indicator": ind,
            "last_result": last_result,
            "data_formatada": data_formatada,
            "status": status,
            "variacao": variacao,
            "results": ind_results
        })

    # Aplicar filtro de status se necessário
    if status_filtro and "Todos" not in status_filtro:
        indicator_data = [d for d in indicator_data if d["status"] in status_filtro]

    # Se não houver indicadores após filtro de status
    if not indicator_data:
        st.warning("Nenhum indicador encontrado com os filtros selecionados.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Mostrar cada indicador individualmente em uma única coluna
    st.subheader("Indicadores")

    # Aplicar filtro de status aos indicadores
    indicator_data = []

    for ind in filtered_indicators:
        # Obter resultados do indicador
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]

        if ind_results:
            # Pegar o resultado mais recente
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)

            last_result = df_results.iloc[0]["resultado"]
            last_date = df_results.iloc[0]["data_referencia"]

            # Calcular status
            try:
                meta = float(ind["meta"])
                resultado = float(last_result)

                if ind["comparacao"] == "Maior é melhor":
                    status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else:  # Menor é melhor
                    status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"

                # Calcular variação percentual
                variacao = ((resultado / meta) - 1) * 100
                if ind["comparacao"] == "Menor é melhor":
                    variacao = -variacao  # Inverter para exibição correta

            except:
                status = "N/A"
                variacao = 0

            # Formatar data
            data_formatada = format_date_as_month_year(last_date)

        else:
            last_result = "N/A"
            data_formatada = "N/A"
            status = "Sem Resultados"
            variacao = 0

        # Adicionar à lista de dados
        indicator_data.append({
            "indicator": ind,
            "last_result": last_result,
            "data_formatada": data_formatada,
            "status": status,
            "variacao": variacao,
            "results": ind_results
        })

    # Aplicar filtro de status se necessário
    if status_filtro and "Todos" not in status_filtro:
        indicator_data = [d for d in indicator_data if d["status"] in status_filtro]

    # Se não houver indicadores após filtro de status
    if not indicator_data:
        st.warning("Nenhum indicador encontrado com os filtros selecionados.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Mostrar cada indicador em um card individual
    for i, data in enumerate(indicator_data):
        ind = data["indicator"]

        # Card para o indicador
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:20px;">
            <h3 style="margin:0; color:#1E88E5;">{ind['nome']}</h3>
            <p style="margin:5px 0; color:#546E7A;">Setor: {ind['responsavel']}</p>
        </div>
        """, unsafe_allow_html=True)

        # Criar gráfico para o indicador
        if data["results"]:
            fig = create_chart(ind["id"], ind["tipo_grafico"], INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO)
            st.plotly_chart(fig, use_container_width=True)

            # Mostrar meta e último resultado
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"""
                <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;">
                    <p style="margin:0; font-size:12px; color:#666;">Meta</p>
                    <p style="margin:0; font-weight:bold; font-size:18px;">{ind['meta']}</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                status_color = "#26A69A" if data["status"] == "Acima da Meta" else "#FF5252"
                st.markdown(f"""
                <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;">
                    <p style="margin:0; font-size:12px; color:#666;">Último Resultado</p>
                    <p style="margin:0; font-weight:bold; font-size:18px; color:{status_color};">{data['last_result']}</p>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                variacao_color = "#26A69A" if (data["variacao"] >= 0 and ind["comparacao"] == "Maior é melhor") or \
                                            (data["variacao"] <= 0 and ind["comparacao"] == "Menor é melhor") else "#FF5252"
                variacao_text = f"{data['variacao']:.2f}%" if isinstance(data['variacao'], (int, float)) else "N/A"
                st.markdown(f"""
                <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;">
                    <p style="margin:0; font-size:12px; color:#666;">Variação vs Meta</p>
                    <p style="margin:0; font-weight:bold; font-size:18px; color:{variacao_color};">{variacao_text}</p>
                </div>
                """, unsafe_allow_html=True)

            # Expandir para mostrar série histórica e análise crítica
            with st.expander("Ver Série Histórica e Análise Crítica"):
                # Criar tabela de série histórica
                if data["results"]:
                    df_hist = pd.DataFrame(data["results"])
                    df_hist["data_referencia"] = pd.to_datetime(df_hist["data_referencia"])
                    df_hist = df_hist.sort_values("data_referencia", ascending=False)

                    # Adicionar colunas de status e análise
                    df_hist["status"] = df_hist.apply(lambda row:
                                                      "Acima da Meta" if (float(row["resultado"]) >= float(
                                                          ind["meta"]) and ind["comparacao"] == "Maior é melhor") or
                                                                         (float(row["resultado"]) <= float(
                                                                             ind["meta"]) and ind[
                                                                              "comparacao"] == "Menor é melhor")
                                                      else "Abaixo da Meta", axis=1)

                    # Formatar para exibição - Corrigindo o erro da coluna 'observacoes'
                    df_display = df_hist[["data_referencia", "resultado", "status"]].copy()

                    # Verificar se a coluna 'observacao' existe no DataFrame
                    if "observacao" in df_hist.columns:
                        df_display["observacao"] = df_hist["observacao"]
                    else:
                        df_display["observacao"] = ""  # Adicionar coluna vazia se não existir

                    df_display["data_referencia"] = df_display["data_referencia"].apply(
                        lambda x: x.strftime("%d/%m/%Y"))
                    df_display.columns = ["Data de Referência", "Resultado", "Status", "Observações"]

                    st.dataframe(df_display, use_container_width=True)

                    # Análise de tendência
                    if len(df_hist) > 1:
                        # Verificar tendência dos últimos resultados
                        ultimos_resultados = df_hist.sort_values("data_referencia")["resultado"].astype(float).tolist()

                        if len(ultimos_resultados) >= 3:
                            # Verificar se os últimos 3 resultados estão melhorando ou piorando
                            if ind["comparacao"] == "Maior é melhor":
                                tendencia = "crescente" if ultimos_resultados[-1] > ultimos_resultados[-2] > \
                                                           ultimos_resultados[-3] else \
                                    "decrescente" if ultimos_resultados[-1] < ultimos_resultados[-2] < \
                                                     ultimos_resultados[-3] else \
                                        "estável"
                            else:  # Menor é melhor
                                tendencia = "crescente" if ultimos_resultados[-1] < ultimos_resultados[-2] < \
                                                           ultimos_resultados[-3] else \
                                    "decrescente" if ultimos_resultados[-1] > ultimos_resultados[-2] > \
                                                     ultimos_resultados[-3] else \
                                        "estável"

                            # Cor da tendência
                            tendencia_color = "#26A69A" if (tendencia == "crescente" and ind[
                                "comparacao"] == "Maior é melhor") or \
                                                           (tendencia == "crescente" and ind[
                                                               "comparacao"] == "Menor é melhor") else \
                                "#FF5252" if (tendencia == "decrescente" and ind["comparacao"] == "Maior é melhor") or \
                                             (tendencia == "decrescente" and ind["comparacao"] == "Menor é melhor") else \
                                    "#FFC107"  # Estável

                            st.markdown(f"""
                            <div style="margin-top:15px;">
                                <h4>Análise de Tendência</h4>
                                <p>Este indicador apresenta uma tendência <span style="color:{tendencia_color}; font-weight:bold;">{tendencia}</span> nos últimos 3 períodos.</p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Análise crítica automática
                            st.markdown("<h4>Análise Automática</h4>", unsafe_allow_html=True)

                            # Gerar análise com base na tendência e status
                            if tendencia == "crescente" and ind["comparacao"] == "Maior é melhor":
                                st.success(
                                    "O indicador apresenta evolução positiva, com resultados crescentes nos últimos períodos.")
                                if float(data["last_result"]) >= float(ind["meta"]):
                                    st.success(
                                        "O resultado atual está acima da meta estabelecida, demonstrando bom desempenho.")
                                else:
                                    st.warning(
                                        "Apesar da evolução positiva, o resultado ainda está abaixo da meta estabelecida.")
                            elif tendencia == "decrescente" and ind["comparacao"] == "Maior é melhor":
                                st.error(
                                    "O indicador apresenta tendência de queda, o que é preocupante para este tipo de métrica.")
                                if float(data["last_result"]) >= float(ind["meta"]):
                                    st.warning(
                                        "Embora o resultado atual ainda esteja acima da meta, a tendência de queda requer atenção.")
                                else:
                                    st.error(
                                        "O resultado está abaixo da meta e com tendência de queda, exigindo ações corretivas urgentes.")
                            elif tendencia == "crescente" and ind["comparacao"] == "Menor é melhor":
                                st.error(
                                    "O indicador apresenta tendência de aumento, o que é negativo para este tipo de métrica.")
                                if float(data["last_result"]) <= float(ind["meta"]):
                                    st.warning(
                                        "Embora o resultado atual ainda esteja dentro da meta, a tendência de aumento requer atenção.")
                                else:
                                    st.error(
                                        "O resultado está acima da meta e com tendência de aumento, exigindo ações corretivas urgentes.")
                            elif tendencia == "decrescente" and ind["comparacao"] == "Menor é melhor":
                                st.success(
                                    "O indicador apresenta evolução positiva, com resultados decrescentes nos últimos períodos.")
                                if float(data["last_result"]) <= float(ind["meta"]):
                                    st.success(
                                        "O resultado atual está dentro da meta estabelecida, demonstrando bom desempenho.")
                                else:
                                    st.warning(
                                        "Apesar da evolução positiva, o resultado ainda está acima da meta estabelecida.")
                            else:  # Estável
                                if (float(data["last_result"]) >= float(ind["meta"]) and ind[
                                    "comparacao"] == "Maior é melhor") or \
                                        (float(data["last_result"]) <= float(ind["meta"]) and ind[
                                            "comparacao"] == "Menor é melhor"):
                                    st.info("O indicador apresenta estabilidade e está dentro da meta estabelecida.")
                                else:
                                    st.warning(
                                        "O indicador apresenta estabilidade, porém está fora da meta estabelecida.")
                        else:
                            st.info(
                                "Não há dados suficientes para análise de tendência (mínimo de 3 períodos necessários).")
                    else:
                        st.info("Não há dados históricos suficientes para análise de tendência.")

                    # Adicionar análise crítica no formato 5W2H
                    st.markdown("<h4>Análise Crítica 5W2H</h4>", unsafe_allow_html=True)

                    # Verificar se existe análise crítica para o último resultado
                    ultimo_resultado = df_hist.iloc[0]

                    # Verificar se o resultado tem análise crítica
                    has_analysis = False

                    # Verificar se a análise crítica existe nos dados
                    if "analise_critica" in ultimo_resultado:
                        analise = ultimo_resultado["analise_critica"]
                        has_analysis = analise is not None and analise != ""

                    if has_analysis:
                        # Exibir análise crítica existente
                        analise = ultimo_resultado["analise_critica"]

                        # Tentar converter de JSON se for uma string
                        if isinstance(analise, str):
                            try:
                                analise_dict = json.loads(analise)
                            except:
                                analise_dict = {
                                    "what": "", "why": "", "who": "", "when": "", "where": "",
                                    "how": "", "howMuch": ""
                                }
                        else:
                            analise_dict = analise

                        # Exibir os campos da análise crítica
                        st.markdown("**O que (What):** " + analise_dict.get("what", ""))
                        st.markdown("**Por que (Why):** " + analise_dict.get("why", ""))
                        st.markdown("**Quem (Who):** " + analise_dict.get("who", ""))
                        st.markdown("**Quando (When):** " + analise_dict.get("when", ""))
                        st.markdown("**Onde (Where):** " + analise_dict.get("where", ""))
                        st.markdown("**Como (How):** " + analise_dict.get("how", ""))
                        st.markdown("**Quanto custa (How Much):** " + analise_dict.get("howMuch", ""))
                    else:
                        # Mostrar mensagem informando que não há análise crítica
                        st.info(
                            "Não há análise crítica registrada para o último resultado. Utilize a opção 'Preencher Indicador' para adicionar uma análise crítica no formato 5W2H.")

                        # Explicar o formato 5W2H
                        with st.expander("O que é a análise 5W2H?"):
                            st.markdown("""
                            **5W2H** é uma metodologia de análise que ajuda a estruturar o pensamento crítico sobre um problema ou situação:

                            - **What (O quê)**: O que está acontecendo? Qual é o problema ou situação?
                            - **Why (Por quê)**: Por que isso está acontecendo? Quais são as causas?
                            - **Who (Quem)**: Quem é responsável? Quem está envolvido?
                            - **When (Quando)**: Quando isso aconteceu? Qual é o prazo para resolução?
                            - **Where (Onde)**: Onde ocorre o problema? Em qual setor ou processo?
                            - **How (Como)**: Como resolver o problema? Quais ações devem ser tomadas?
                            - **How Much (Quanto custa)**: Quanto custará implementar a solução? Quais recursos são necessários?

                            Esta metodologia ajuda a garantir que todos os aspectos importantes sejam considerados na análise e no plano de ação.
                            """)
                else:
                    st.info("Não há resultados registrados para este indicador.")
        else:
            # Indicador sem resultados
            st.info("Este indicador ainda não possui resultados registrados.")

            # Mostrar meta
            st.markdown(f"""
            <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0; width: 200px; margin: 10px auto;">
                <p style="margin:0; font-size:12px; color:#666;">Meta</p>
                <p style="margin:0; font-weight:bold; font-size:18px;">{ind['meta']}</p>
            </div>
            """, unsafe_allow_html=True)

        # Separador entre indicadores
        st.markdown("<hr style='margin: 30px 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)

    # Botão para exportar todos os dados
    if st.button("📤 Exportar Tudo"):
        # Preparar dados para exportação
        export_data = []

        for data in indicator_data:
            ind = data["indicator"]

            # Adicionar à lista de dados
            export_data.append({
                "Nome": ind["nome"],
                "Setor": ind["responsavel"],
                "Meta": ind["meta"],
                "Último Resultado": data["last_result"],
                "Período": data["data_formatada"],
                "Status": data["status"],
                "Variação (%)": f"{data['variacao']:.2f}%" if isinstance(data['variacao'], (int, float)) else "N/A"
            })

        # Criar DataFrame
        df_export = pd.DataFrame(export_data)

        # Criar link de download
        download_link = get_download_link(df_export, "indicadores_dashboard.xlsx")
        st.markdown(download_link, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def show_overview(INDICATORS_FILE, RESULTS_FILE):
    """Mostra a visão geral dos indicadores."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Visão Geral dos Indicadores")

    # Carregar indicadores e resultados
    indicators = load_indicators(INDICATORS_FILE)
    results = load_results(RESULTS_FILE)

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtros
    col1, col2 = st.columns(2)

    with col1:
        # Filtro por setor
        setores_disponiveis = sorted(list(set([ind["responsavel"] for ind in indicators])))
        setor_filtro = st.multiselect(
            "Filtrar por Setor",
            options=["Todos"] + setores_disponiveis,
            default=["Todos"]
        )

    with col2:
        # Filtro por status (acima/abaixo da meta)
        status_filtro = st.multiselect(
            "Status",
            options=["Todos", "Acima da Meta", "Abaixo da Meta", "Sem Resultados"],
            default=["Todos"]
        )

    # Aplicar filtros
    filtered_indicators = indicators

    if setor_filtro and "Todos" not in setor_filtro:
        filtered_indicators = [ind for ind in filtered_indicators if ind["responsavel"] in setor_filtro]

    # Criar DataFrame para visão geral
    overview_data = []

    for ind in filtered_indicators:
        # Obter resultados para este indicador
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]

        if ind_results:
            # Ordenar por data e pegar o mais recente
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)

            last_result = df_results.iloc[0]["resultado"]
            last_date = df_results.iloc[0]["data_referencia"]

            # Calcular status
            try:
                meta = float(ind["meta"])
                resultado = float(last_result)

                if ind["comparacao"] == "Maior é melhor":
                    status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else:  # Menor é melhor
                    status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"

                # Calcular variação percentual
                variacao = ((resultado / meta) - 1) * 100
                if ind["comparacao"] == "Menor é melhor":
                    variacao = -variacao  # Inverter para exibição correta

            except:
                status = "N/A"
                variacao = 0

            # Formatar data
            data_formatada = format_date_as_month_year(last_date)

        else:
            last_result = "N/A"
            data_formatada = "N/A"
            status = "Sem Resultados"
            variacao = 0

        # Adicionar à lista de dados
        overview_data.append({
            "Nome": ind["nome"],
            "Setor": ind["responsavel"],
            "Meta": ind["meta"],
            "Último Resultado": last_result,
            "Período": data_formatada,
            "Status": status,
            "Variação (%)": f"{variacao:.2f}%" if isinstance(variacao, (int, float)) else "N/A"
        })

    # Aplicar filtro de status
    if status_filtro and "Todos" not in status_filtro:
        overview_data = [d for d in overview_data if d["Status"] in status_filtro]

    # Criar DataFrame
    df_overview = pd.DataFrame(overview_data)

    if not df_overview.empty:
        # Exibir visão geral
        st.dataframe(df_overview, use_container_width=True)

        # Botão para exportar dados
        if st.button("📤 Exportar para Excel"):
            download_link = get_download_link(df_overview, "visao_geral_indicadores.xlsx")
            st.markdown(download_link, unsafe_allow_html=True)

        # Gráfico de resumo por setor
        st.subheader("Resumo por Setor")

        # Contar indicadores por setor
        setor_counts = df_overview["Setor"].value_counts().reset_index()
        setor_counts.columns = ["Setor", "Quantidade de Indicadores"]

        # Gráfico de barras para contagem por setor
        fig_setor = px.bar(
            setor_counts,
            x="Setor",
            y="Quantidade de Indicadores",
            title="Quantidade de Indicadores por Setor",
            color="Setor"
        )

        st.plotly_chart(fig_setor, use_container_width=True)

        # Gráfico de status
        st.subheader("Status dos Indicadores")

        # Contar indicadores por status
        status_counts = df_overview["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Quantidade"]

        # Gráfico de pizza para status
        fig_status = px.pie(
            status_counts,
            names="Status",
            values="Quantidade",
            title="Distribuição de Status dos Indicadores",
            color="Status",
            color_discrete_map={
                "Acima da Meta": "#26A69A",
                "Abaixo da Meta": "#FF5252",
                "Sem Resultados": "#9E9E9E"
            }
        )

        st.plotly_chart(fig_status, use_container_width=True)
    else:
        st.warning("Nenhum indicador encontrado com os filtros selecionados.")

    st.markdown('</div>', unsafe_allow_html=True)


def show_settings(USERS_FILE, INDICATORS_FILE, RESULTS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE,
                  KEY_FILE, cipher, CONFIG_FILE):
    """Mostra a página de configurações."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Configurações")

    # Cria o diretório de backups se não existir
    if not os.path.exists("backups"):
        os.makedirs("backups")

    # Carregar configurações
    config = load_config(CONFIG_FILE)

    # Informações sobre o sistema
    st.subheader("Informações do Sistema")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Versão do Portal:** 1.2.0

        **Data da Última Atualização:** 22/04/2025

        **Desenvolvido por:** Equipe de Desenvolvimento
        """)

    with col2:
        st.markdown("""
        **Suporte Técnico:**

        Email: suporte@portalindicadores.com

        Telefone: (11) 1234-5678
        """)

    # Horário de backup automático
    st.subheader("Backup Automático")

    # Se o horário de backup não estiver definido, define como 00:00
    if "backup_hour" not in config:
        config["backup_hour"] = "00:00"

    # Converte o horário para um objeto datetime.time
    try:
        backup_hour = datetime.strptime(config["backup_hour"], "%H:%M").time()
    except ValueError:
        # Se o formato estiver incorreto, define como 00:00 e salva no arquivo
        config["backup_hour"] = "00:00"
        save_config(config, CONFIG_FILE)
        backup_hour = datetime.time(0, 0)

    new_backup_hour = st.time_input("Horário do backup automático", backup_hour)

    # Salvar novo horário de backup
    if new_backup_hour != backup_hour:
        config["backup_hour"] = new_backup_hour.strftime("%H:%M")
        save_config(config, CONFIG_FILE)
        st.success("Horário de backup automático atualizado com sucesso!")

    # Mostrar data do último backup automático
    if "last_backup_date" in config:
        st.markdown(f"**Último backup automático:** {config['last_backup_date']}")
    else:
        st.markdown("**Último backup automático:** Nunca executado")

    # Botão para criar backup manual (fora do expander)
    if st.button("⟳ Criar novo backup manual", help="Cria um backup manual de todos os dados do sistema."):
        with st.spinner("Criando backup manual..."):
            backup_file = backup_data(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE,
                                      INDICATOR_LOG_FILE, USER_LOG_FILE, cipher, tipo_backup="user")
            if backup_file:
                st.success(f"Backup manual criado: {backup_file}")
            else:
                st.error("Falha ao criar o backup manual.")

    # Botão para restaurar backup (fora do expander)
    backup_files = [f for f in os.listdir("backups") if f.startswith("backup_") and f.endswith(".bkp")]
    if backup_files:
        selected_backup = st.selectbox("Selecione o backup para restaurar", backup_files)
        if st.button("⚙️ Restaurar arquivo de backup ️",
                     help="Restaura os dados do sistema a partir de um arquivo de backup."):
            # Criar um backup antes de restaurar
            with st.spinner("Criando backup de segurança..."):
                backup_file_antes_restauracao = backup_data(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE,
                                                            BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE,
                                                            cipher, tipo_backup="seguranca")
                if backup_file_antes_restauracao:
                    st.success(f"Backup de segurança criado: {backup_file_antes_restauracao}")
                else:
                    st.error("Falha ao criar o backup de segurança.")

            # Restaurar o backup
            try:
                with st.spinner("Restaurando backup..."):
                    if restore_data(os.path.join("backups", selected_backup), INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE,
                                    BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, cipher):
                        st.success("Backup restaurado com sucesso!")
                    else:
                        st.error("Falha ao restaurar o backup.")
            except Exception as e:
                st.error(f"Ocorreu um erro durante a restauração: {e}")
    else:
        st.info("Nenhum arquivo de backup encontrado.")

    # Botão para limpar dados (apenas para admin)
    if st.session_state.username == "admin":
        st.subheader("Administração do Sistema")

        # Expander para as opções de limpeza da base
        with st.expander("Opções Avançadas de Limpeza"):
            st.warning("⚠️ Estas opções podem causar perda de dados. Use com cuidado.")

            if st.button("🗑️ Limpar resultados", help="Exclui todos os resultados dos indicadores."):
                try:
                    if "confirm_limpar_resultados" not in st.session_state:
                        st.session_state.confirm_limpar_resultados = False

                    if not st.session_state.confirm_limpar_resultados:
                        st.warning(
                            "Tem certeza que deseja limpar todos os resultados? Esta ação não pode ser desfeita.")
                        st.session_state.confirm_limpar_resultados = True
                        st.rerun()
                    else:
                        with st.spinner("Limpando resultados..."):
                            try:
                                with open(RESULTS_FILE, "w") as f:
                                    json.dump([], f)
                                st.success("Resultados excluídos com sucesso!")
                            except Exception as e:
                                st.error(f"Erro ao excluir resultados: {e}")
                        st.session_state.confirm_limpar_resultados = False
                except Exception as e:
                    st.error(f"Ocorreu um erro ao limpar os resultados: {e}")

            if st.button("🧹 Excluir tudo!", help="Exclui todos os indicadores e resultados do sistema."):
                try:
                    if "confirm_limpar_tudo" not in st.session_state:
                        st.session_state.confirm_limpar_tudo = False

                    if not st.session_state.confirm_limpar_tudo:
                        st.warning(
                            "Tem certeza que deseja limpar todos os indicadores e resultados? Esta ação não pode ser desfeita.")
                        st.session_state.confirm_limpar_tudo = True
                        st.rerun()
                    else:
                        with st.spinner("Limpando tudo..."):
                            try:
                                with open(INDICATORS_FILE, "w") as f:
                                    json.dump([], f)
                                with open(RESULTS_FILE, "w") as f:
                                    json.dump([], f)
                                st.success("Indicadores e resultados excluídos com sucesso!")
                            except Exception as e:
                                st.error(f"Erro ao excluir indicadores e resultados: {e}")
                        st.session_state.confirm_limpar_tudo = False
                except Exception as e:
                    st.error(f"Ocorreu um erro ao excluir tudo: {e}")

    st.markdown('</div>', unsafe_allow_html=True)


def show_user_management(SETORES, USERS_FILE, USER_LOG_FILE):
    """Mostra a página de gerenciamento de usuários."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Gerenciamento de Usuários")

    users = load_users(USERS_FILE)

    # Verificar e migrar usuários para o novo formato se necessário
    migrated = False
    for user, data in list(users.items()):
        if not isinstance(data, dict):
            users[user] = {
                "password": data,
                "tipo": "Administrador" if user == "admin" else "Visualizador",
                "setor": "Todos",
                "nome_completo": "",
                "email": ""
            }
            migrated = True
        elif "setor" not in data:
            users[user]["setor"] = "Todos"
            migrated = True
        elif "nome_completo" not in data:
            users[user]["nome_completo"] = ""
            migrated = True
        elif "email" not in data:
            users[user]["email"] = ""
            migrated = True

    if migrated:
        save_users(users, USERS_FILE)
        st.success("Dados de usuários foram atualizados para o novo formato.")

    # Estatísticas de usuários
    total_users = len(users)
    admin_count = sum(
        1 for user, data in users.items() if isinstance(data, dict) and data.get("tipo") == "Administrador")
    operator_count = sum(1 for user, data in users.items() if isinstance(data, dict) and data.get("tipo") == "Operador")
    viewer_count = sum(
        1 for user, data in users.items() if isinstance(data, dict) and data.get("tipo") == "Visualizador")

    # Mostrar estatísticas em cards
    st.subheader("Visão Geral de Usuários")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:#1E88E5;">{total_users}</h3>
            <p style="margin:0;">Total de Usuários</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#26A69A; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:white;">{admin_count}</h3>
            <p style="margin:0; color:white;">Administradores</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background-color:#FFC107; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:white;">{operator_count}</h3>
            <p style="margin:0; color:white;">Operadores</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="background-color:#7E57C2; padding:15px; border-radius:5px; text-align:center;">
            <h3 style="margin:0; color:white;">{viewer_count}</h3>
            <p style="margin:0; color:white;">Visualizadores</p>
        </div>
        """, unsafe_allow_html=True)

    # Criar novo usuário
    st.subheader("Adicionar Novo Usuário")

    with st.form("add_user_form"):
        # Informações pessoais
        st.markdown("#### Informações Pessoais")

        col1, col2 = st.columns(2)
        with col1:
            nome_completo = st.text_input("Nome Completo", placeholder="Digite o nome completo do usuário")
            email = st.text_input("Email", placeholder="Digite o email do usuário")

        with col2:
            # Adicionar seleção de tipo de usuário
            user_type = st.selectbox(
                "Tipo de Usuário",
                options=["Administrador", "Operador", "Visualizador"],
                index=2,  # Padrão: Visualizador
                help="Administrador: acesso total; Operador: gerencia indicadores de um setor; Visualizador: apenas visualização"
            )

            # Adicionar seleção de setor (relevante principalmente para Operadores)
            user_sector = st.selectbox(
                "Setor",
                options=["Todos"] + SETORES,
                index=0,  # Padrão: Todos
                help="Para Operadores, define o setor que podem gerenciar. Administradores têm acesso a todos os setores."
            )

        # Informações de acesso
        st.markdown("#### Informações de Acesso")

        col1, col2 = st.columns(2)
        with col1:
            login = st.text_input("Login", placeholder="Digite o login para acesso ao sistema")

        with col2:
            new_password = st.text_input("Senha", type="password", placeholder="Digite a senha")
            confirm_password = st.text_input("Confirmar Senha", type="password", placeholder="Confirme a senha")

        # Mostrar explicação dos tipos de usuário
        st.markdown("""
        <div style="background-color:#f8f9fa; padding:10px; border-radius:5px; margin-top:10px;">
            <p style="margin:0; font-size:14px;"><strong>Tipos de usuário:</strong></p>
            <ul style="margin:5px 0 0 15px; padding:0; font-size:13px;">
                <li><strong>Administrador:</strong> Acesso total ao sistema</li>
                <li><strong>Operador:</strong> Gerencia indicadores de um setor específico</li>
                <li><strong>Visualizador:</strong> Apenas visualiza indicadores e resultados</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Desabilitar a opção "Todos" para Operadores
        if user_type == "Operador" and user_sector == "Todos":
            st.warning("⚠️ Operadores devem ser associados a um setor específico.")

        submit = st.form_submit_button("➕ Adicionar")

    if submit:
        # Validar campos obrigatórios
        if not login or not new_password:
            st.error("❌ Login e senha são obrigatórios.")
        elif login in users:
            st.error(f"❌ O login '{login}' já existe.")
        elif new_password != confirm_password:
            st.error("❌ As senhas não coincidem.")
        elif user_type == "Operador" and user_sector == "Todos":
            st.error("❌ Operadores devem ser associados a um setor específico.")
        elif not nome_completo:
            st.error("❌ Nome completo é obrigatório.")
        elif email and "@" not in email:  # Validação básica de email
            st.error("❌ Formato de email inválido.")
        else:
            # Criar novo usuário com todos os campos
            users[login] = {
                "password": hashlib.sha256(new_password.encode()).hexdigest(),
                "tipo": user_type,
                "setor": user_sector,
                "nome_completo": nome_completo,
                "email": email,
                "data_criacao": datetime.now().isoformat()
            }
            save_users(users, USERS_FILE)
            log_user_action("Usuário criado", login, USER_LOG_FILE)  # Registrar ação de criação
            st.success(
                f"✅ Usuário '{nome_completo}' (login: {login}) adicionado com sucesso como {user_type} do setor {user_sector}!")
            time.sleep(1)
            st.rerun()

    # Listar e gerenciar usuários existentes
    st.subheader("Usuários Cadastrados")

    # Adicionar filtros
    col1, col2 = st.columns(2)
    with col1:
        filter_type = st.multiselect(
            "Filtrar por Tipo",
            options=["Todos", "Administrador", "Operador", "Visualizador"],
            default=["Todos"]
        )

    with col2:
        filter_sector = st.multiselect(
            "Filtrar por Setor",
            options=["Todos"] + SETORES,
            default=["Todos"]
        )

    # Adicionar campo de busca
    search_query = st.text_input("🔍 Buscar usuário por nome, login ou email", placeholder="Digite para buscar...")

    # Aplicar filtros
    filtered_users = {}
    for user, data in users.items():
        # Obter tipo e setor
        if isinstance(data, dict):
            user_type = data.get("tipo", "Visualizador")
            user_sector = data.get("setor", "Todos")
            nome_completo = data.get("nome_completo", "")
            email = data.get("email", "")
            data_criacao = data.get("data_criacao", "N/A")
            if data_criacao != "N/A":
                try:
                    data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
                except:
                    pass
        else:
            user_type = "Administrador" if user == "admin" else "Visualizador"
            user_sector = "Todos"
            nome_completo = ""
            email = ""
            data_criacao = "N/A"

        # Aplicar busca
        if search_query and search_query.lower() not in user.lower() and search_query.lower() not in nome_completo.lower() and search_query.lower() not in email.lower():
            continue

        # Aplicar filtro de tipo
        if "Todos" in filter_type or user_type in filter_type:
            # Aplicar filtro de setor
            if "Todos" in filter_sector or user_sector in filter_sector:
                filtered_users[user] = data

    # Mostrar usuários em uma tabela mais moderna
    if filtered_users:
        # Preparar dados para a tabela
        user_data_list = []
        for user, data in filtered_users.items():
            if isinstance(data, dict):
                user_type = data.get("tipo", "Visualizador")
                user_sector = data.get("setor", "Todos")
                nome_completo = data.get("nome_completo", "")
                email = data.get("email", "")
                data_criacao = data.get("data_criacao", "N/A")
                if data_criacao != "N/A":
                    try:
                        data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
                    except:
                        pass
            else:
                user_type = "Administrador" if user == "admin" else "Visualizador"
                user_sector = "Todos"
                nome_completo = ""
                email = ""
                data_criacao = "N/A"

            # Determinar cor do tipo
            if user_type == "Administrador":
                type_color = "#26A69A"
            elif user_type == "Operador":
                type_color = "#FFC107"
            else:
                type_color = "#7E57C2"

            # Adicionar à lista
            user_data_list.append({
                "Login": user,
                "Nome": nome_completo or "Não informado",
                "Email": email or "Não informado",
                "Tipo": user_type,
                "Setor": user_sector,
                "Criado em": data_criacao,
                "type_color": type_color,
                "is_current": user == st.session_state.username,
                "is_admin": user == "admin"
            })

        # Criar DataFrame para exibição
        df_users = pd.DataFrame(user_data_list)

        # Exibir cada usuário em um card
        for i, row in df_users.iterrows():
            login = row["Login"]
            nome = row["Nome"]
            email = row["Email"]
            user_type = row["Tipo"]
            user_sector = row["Setor"]
            type_color = row["type_color"]
            is_current = row["is_current"]
            is_admin = row["is_admin"]

            # Criar card para o usuário
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:10px; border-left: 4px solid {type_color};">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <h3 style="margin:0; color:#37474F;">{nome} {' (você)' if is_current else ''}</h3>
                        <p style="margin:5px 0 0 0; color:#546E7A;">Login: <strong>{login}</strong></p>
                        <p style="margin:3px 0 0 0; color:#546E7A;">Email: {email}</p>
                        <p style="margin:3px 0 0 0; color:#546E7A;">Criado em: {row['Criado em']}</p>
                    </div>
                    <div>
                        <span style="background-color:{type_color}; color:white; padding:5px 10px; border-radius:15px; font-size:12px;">{user_type}</span>
                        <span style="background-color:#90A4AE; color:white; padding:5px 10px; border-radius:15px; font-size:12px; margin-left:5px;">{user_sector}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Opções de edição e exclusão
            if not is_admin and not is_current:  # Não permitir alterar o admin ou a si mesmo
                col1, col2 = st.columns(2)

                with col1:
                    # Botão de edição
                    if st.button("✏️ Editar", key=f"edit_{login}"):
                        st.session_state[f"editing_{login}"] = True

                with col2:
                    # Botão de exclusão
                    if st.button("🗑️ Excluir", key=f"del_{login}"):
                        st.session_state[f"deleting_{login}"] = True

                # Formulário de edição
                if st.session_state.get(f"editing_{login}", False):
                    with st.form(key=f"edit_form_{login}"):
                        st.subheader(f"Editar Usuário: {nome}")

                        # Informações pessoais
                        st.markdown("#### Informações Pessoais")

                        col1, col2 = st.columns(2)
                        with col1:
                            new_nome = st.text_input("Nome Completo",
                                                     value=nome if nome != "Não informado" else "",
                                                     key=f"new_nome_{login}")

                            new_email = st.text_input("Email",
                                                      value=email if email != "Não informado" else "",
                                                      key=f"new_email_{login}")

                        with col2:
                            new_type = st.selectbox(
                                "Tipo de Usuário",
                                options=["Administrador", "Operador", "Visualizador"],
                                index=["Administrador", "Operador", "Visualizador"].index(user_type),
                                key=f"new_type_{login}"
                            )

                            new_sector = st.selectbox(
                                "Setor",
                                options=["Todos"] + SETORES,
                                index=(["Todos"] + SETORES).index(user_sector) if user_sector in [
                                    "Todos"] + SETORES else 0,
                                key=f"new_sector_{login}"
                            )

                        # Opção para redefinir senha
                        st.markdown("#### Informações de Acesso")
                        reset_password = st.checkbox("Redefinir senha", key=f"reset_pwd_{login}")

                        if reset_password:
                            new_password = st.text_input("Nova senha", type="password", key=f"new_pwd_{login}")
                            confirm_password = st.text_input("Confirmar nova senha", type="password",
                                                             key=f"confirm_pwd_{login}")

                        # Validar combinação de tipo e setor
                        is_valid = True
                        if new_type == "Operador" and new_sector == "Todos":
                            st.error("❌ Operadores devem ser associados a um setor específico.")
                            is_valid = False

                        if new_email and "@" not in new_email:
                            st.error("❌ Formato de email inválido.")
                            is_valid = False

                        col1, col2 = st.columns(2)
                        with col1:
                            submit = st.form_submit_button("Salvar Alterações")
                        with col2:
                            cancel = st.form_submit_button("Cancelar")

                        if submit and is_valid:
                            # Validar senha se estiver redefinindo
                            if reset_password:
                                if not new_password:
                                    st.error("❌ A nova senha é obrigatória.")
                                    return
                                if new_password != confirm_password:
                                    st.error("❌ As senhas não coincidem.")
                                    return

                            # Atualizar usuário
                            if isinstance(users[login], dict):
                                users[login]["tipo"] = new_type
                                users[login]["setor"] = new_sector
                                users[login]["nome_completo"] = new_nome
                                users[login]["email"] = new_email
                                if reset_password:
                                    users[login]["password"] = hashlib.sha256(new_password.encode()).hexdigest()
                            else:
                                users[login] = {
                                    "password": hashlib.sha256(new_password.encode()).hexdigest() if reset_password else
                                    users[login],
                                    "tipo": new_type,
                                    "setor": new_sector,
                                    "nome_completo": new_nome,
                                    "email": new_email
                                }

                            # Salvar alterações
                            save_users(users, USERS_FILE)
                            st.success(f"✅ Usuário '{new_nome}' atualizado com sucesso!")
                            log_user_action("Usuário atualizado", login, USER_LOG_FILE)  # Registrar ação de atualização

                            # Limpar estado de edição
                            del st.session_state[f"editing_{login}"]
                            time.sleep(1)
                            st.rerun()

                        if cancel:
                            # Limpar estado de edição
                            del st.session_state[f"editing_{login}"]
                            st.rerun()

                # Confirmação de exclusão
                if st.session_state.get(f"deleting_{login}", False):
                    st.warning(
                        f"⚠️ Tem certeza que deseja excluir o usuário '{nome}' (login: {login})? Esta ação não pode ser desfeita.")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Sim, excluir", key=f"confirm_del_{login}"):
                            delete_user(login, USERS_FILE, USER_LOG_FILE)
                            st.success(f"✅ Usuário '{nome}' excluído com sucesso!")

                            # Limpar estado de exclusão
                            del st.session_state[f"deleting_{login}"]
                            time.sleep(1)
                            st.rerun()

                    with col2:
                        if st.button("❌ Cancelar", key=f"cancel_del_{login}"):
                            # Limpar estado de exclusão
                            del st.session_state[f"deleting_{login}"]
                            st.rerun()

            st.markdown("<hr style='margin: 20px 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)
    else:
        st.info("Nenhum usuário encontrado com os filtros selecionados.")

    # Adicionar exportação de usuários (apenas para admin)
    if st.session_state.username == "admin":
        if st.button("📤 Exportar Lista"):
            # Preparar dados para exportação (sem senhas)
            export_data = []
            for user, data in users.items():
                if isinstance(data, dict):
                    user_type = data.get("tipo", "Visualizador")
                    user_sector = data.get("setor", "Todos")
                    nome_completo = data.get("nome_completo", "")
                    email = data.get("email", "")
                    data_criacao = data.get("data_criacao", "N/A")
                else:
                    user_type = "Administrador" if user == "admin" else "Visualizador"
                    user_sector = "Todos"
                    nome_completo = ""
                    email = ""
                    data_criacao = "N/A"

                export_data.append({
                    "Login": user,
                    "Nome Completo": nome_completo,
                    "Email": email,
                    "Tipo": user_type,
                    "Setor": user_sector,
                    "Data de Criação": data_criacao
                })

            # Criar DataFrame
            df_export = pd.DataFrame(export_data)

            # Criar link de download
            download_link = get_download_link(df_export, "usuarios_sistema.xlsx")
            st.markdown(download_link, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

def logout():
    """Realiza o logout do usuário."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def define_data_directories():

    # Criar diretório de dados se não existir
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # Inicializar arquivos JSON se não existirem
    if not os.path.exists(INDICATORS_FILE):
        with open(INDICATORS_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"theme": "padrao"}, f)

    # Inicializar arquivo de usuários com a nova estrutura se não existir
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": hashlib.sha256("6105/*".encode()).hexdigest(),
                "tipo": "Administrador",
                "setor": "Todos"  # Admin tem acesso a todos os setores
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default_users, f)

    if not os.path.exists(BACKUP_LOG_FILE):
        with open(BACKUP_LOG_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(INDICATOR_LOG_FILE):
        with open(INDICATOR_LOG_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(USER_LOG_FILE):
        with open(USER_LOG_FILE, "w") as f:
            json.dump([], f)

    return DATA_DIR, INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE

def main():
    # Inicializar o estado da sessão
    initialize_session_state()

    # Get the file paths from the global scope
    DATA_DIR, INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE = define_data_directories()

    # Definição do tema padrão
    TEMA_PADRAO = {
        "name": "Padrão",
        "primary_color": "#1E88E5",
        "secondary_color": "#26A69A",
        "background_color": "#FFFFFF",
        "text_color": "#37474F",
        "accent_color": "#FF5252",
        "chart_colors": ["#1E88E5", "#26A69A", "#FFC107", "#7E57C2", "#EC407A"],
        "is_dark": False
    }

    # Lista de setores para seleção
    SETORES = ["RH", "Financeiro", "Operações", "Marketing", "Comercial", "TI", "Logística", "Produção"]

    # Lista de tipos de gráficos
    TIPOS_GRAFICOS = ["Linha", "Barra", "Pizza", "Área", "Dispersão"]

    # Definir ícones do menu
    MENU_ICONS = define_menu_icons()

    # Inicializar objeto de criptografia
    generate_key(KEY_FILE)
    cipher = initialize_cipher(KEY_FILE)

    # Verificar autenticação
    if not st.session_state.authenticated:
        show_login_page()
        return

    # Obter tipo e setor do usuário
    user_type = get_user_type(st.session_state.username, USERS_FILE)
    user_sector = get_user_sector(st.session_state.username, USERS_FILE)

    # Armazenar o tipo e setor de usuário na sessão
    st.session_state.user_type = user_type
    st.session_state.user_sector = user_sector

    # Aplicar CSS global
    st.markdown("""
    <style>
        /* Estilo geral */
        .main {
            background-color: #f8f9fa;
            padding: 1rem;
        }

           /* Remover o menu de deploy */
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* Remover a borda colorida */
        [data-testid="stAppViewContainer"] {
            border: none !important;
        }

        /* Remover o rodapé do Streamlit */
        footer {
            display: none !important;
        }

        /* Remover o ícone de hambúrguer e menu principal */
        #MainMenu {
            visibility: hidden !important;
        }

        /* Remover o header com informações do Streamlit */
        header {
            display: none !important;
        }

        /* Cards */
        .dashboard-card {
            background-color: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        /* Cabeçalhos */
        h1, h2, h3 {
            color: #1E88E5;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }

        /* Botões da sidebar */
        section[data-testid="stSidebar"] button {
            width: 100%;
            border-radius: 5px;
            text-align: left;
            margin-bottom: 5px;
            height: 40px;
            padding: 0 15px;
            font-size: 14px;
        }

        /* Botão ativo */
        .active-button button {
            background-color: #e3f2fd !important;
            border-left: 3px solid #1E88E5 !important;
            color: #1E88E5 !important;
            font-weight: 500 !important;
        }

        /* Remover padding extra da sidebar */
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 0;
        }

        /* Perfil do usuário */
        .user-profile {
            background-color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border: 1px solid #e0e0e0;
        }

        /* Rodapé da sidebar */
        .sidebar-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            padding: 10px;
            font-size: 12px;
            color: #666;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    # Título principal
    st.title("📊 Portal de Indicadores")

    # Sidebar - Logo
    if os.path.exists("logo.png"):
        st.sidebar.markdown(f"<div style='text-align: center;'>{img_to_html('logo.png')}</div>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<h1 style='text-align: center; font-size: 40px;'>📊</h1>", unsafe_allow_html=True)

    st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)

    # Sidebar - Perfil do usuário
    st.sidebar.markdown(f"""
    <div class="user-profile">
        <p style="margin:0; font-weight:bold;">{st.session_state.username}</p>
        <p style="margin:0; font-size:12px; color:#666;">{user_type}</p>
        {f'<p style="margin:0; font-size:12px; color:#666;">Setor: {user_sector}</p>' if user_type == "Operador" else ''}
    </div>
    """, unsafe_allow_html=True)

    # Botão de logout
    if st.sidebar.button("🚪 Sair", help="Fazer logout"):
        logout()

    st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)

    # Inicializar página atual se não existir
    if 'page' not in st.session_state:
        st.session_state.page = "Dashboard"

    # Definir menus disponíveis com base no tipo de usuário
    if user_type == "Administrador":
        menu_items = ["Dashboard", "Criar Indicador", "Editar Indicador", "Preencher Indicador",
                      "Visão Geral", "Configurações", "Gerenciar Usuários"]
    elif user_type == "Operador":
        menu_items = ["Dashboard", "Preencher Indicador", "Visão Geral"]
        if st.session_state.page not in menu_items:
            st.session_state.page = "Dashboard"
    else:  # Visualizador
        menu_items = ["Dashboard", "Visão Geral"]
        if st.session_state.page not in menu_items:
            st.session_state.page = "Dashboard"

    # Renderizar botões do menu
    for item in menu_items:
        icon = MENU_ICONS.get(item, "📋")

        # Aplicar classe ativa ao botão selecionado
        is_active = st.session_state.page == item
        active_class = "active-button" if is_active else ""

        st.sidebar.markdown(f'<div class="{active_class}">', unsafe_allow_html=True)
        if st.sidebar.button(f"{icon} {item}", key=f"menu_{item}"):
            st.session_state.page = item
            st.rerun()
        st.sidebar.markdown('</div>', unsafe_allow_html=True)

    # Rodapé da sidebar
    st.sidebar.markdown("""
    <div class="sidebar-footer">
        <p style="margin:0;">Portal de Indicadores v1.2</p>
        <p style="margin:3px 0 0 0;">© 2025 Todos os direitos reservados</p>
    </div>
    """, unsafe_allow_html=True)

    # Exibir a página selecionada
    if st.session_state.page == "Dashboard":
        show_dashboard(INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO, SETORES)
    elif st.session_state.page == "Criar Indicador" and user_type == "Administrador":
        create_indicator(SETORES, TIPOS_GRAFICOS, INDICATORS_FILE, INDICATOR_LOG_FILE)
    elif st.session_state.page == "Editar Indicador" and user_type == "Administrador":
        edit_indicator(SETORES, TIPOS_GRAFICOS, INDICATORS_FILE, INDICATOR_LOG_FILE, RESULTS_FILE)
    elif st.session_state.page == "Preencher Indicador" and user_type in ["Administrador", "Operador"]:
        fill_indicator(SETORES, INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO)
    elif st.session_state.page == "Visão Geral":
        show_overview(INDICATORS_FILE, RESULTS_FILE)
    elif st.session_state.page == "Configurações" and user_type == "Administrador":
        show_settings(USERS_FILE, INDICATORS_FILE, RESULTS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE,KEY_FILE, cipher, CONFIG_FILE)
    elif st.session_state.page == "Gerenciar Usuários" and user_type == "Administrador":
        show_user_management(SETORES, USERS_FILE, USER_LOG_FILE)
    else:
        st.warning("Você não tem permissão para acessar esta página.")
        st.session_state.page = "Dashboard"
        st.rerun()

    # Inicia o agendamento de backup usando schedule em um thread separado
    backup_thread = threading.Thread(target=agendar_backup, args=(INDICATORS_FILE, RESULTS_FILE, CONFIG_FILE, USERS_FILE, BACKUP_LOG_FILE, INDICATOR_LOG_FILE, USER_LOG_FILE, KEY_FILE, cipher))
    backup_thread.daemon = True
    backup_thread.start()

# Executar aplicação
if __name__ == "__main__":
    main()
