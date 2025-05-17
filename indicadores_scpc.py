import schedule
import time
import threading
import streamlit as st
import os
import re
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
from sympy import symbols, sympify, SympifyError # Para cálculo seguro e detecção de símbolos

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
    # Adicionar estados para a criação/edição dinâmica
    if 'current_formula_vars' not in st.session_state:
        st.session_state.current_formula_vars = [] # Lista de variáveis detectadas (ex: ['A', 'B', 'C'])
    if 'current_var_descriptions' not in st.session_state:
        st.session_state.current_var_descriptions = {} # Dicionário {variavel: descricao}
    if 'editing_indicator_id' not in st.session_state:
        st.session_state.editing_indicator_id = None # Para saber qual indicador está sendo editado
    # Adicionar estado para armazenar os valores das variáveis ao preencher
    if 'current_variable_values' not in st.session_state:
         st.session_state.current_variable_values = {}

def configure_locale():
    """Configura o locale para português do Brasil."""
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    except locale.Error as e:
        st.warning(f"Não foi possível configurar o locale para pt_BR.UTF-8: {e}. Verifique se o locale está instalado no seu sistema.")

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
            # Garantir que cada indicador tem a estrutura esperada para fórmula e variáveis
            for ind in indicators:
                if "formula" not in ind:
                    ind["formula"] = ""
                if "variaveis" not in ind:
                    ind["variaveis"] = {} # Dicionário {variavel: descricao}
            return indicators
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.error("Erro ao decodificar o arquivo de indicadores. O arquivo pode estar corrompido.")
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


def delete_result(indicator_id, data_referencia, RESULTS_FILE, USER_LOG_FILE):
    """Exclui um resultado específico de um indicador e registra a ação."""
    if not data_referencia or data_referencia == "N/A":
        st.error("Data de referência ausente. Impossível excluir este resultado.")
        return

    results = load_results(RESULTS_FILE)

    # Converter data_referencia para o formato ISO 8601 para comparação
    try:
        data_referencia_iso = datetime.fromisoformat(data_referencia).isoformat()
    except ValueError:
        st.error("Formato de data inválido. Impossível excluir este resultado.")
        return

    # Filtrar os resultados para excluir o resultado específico
    updated_results = [
        r for r in results
        if not (r["indicator_id"] == indicator_id and r["data_referencia"] == data_referencia_iso)
    ]

    save_results(updated_results, RESULTS_FILE)

    # Registrar a ação no log
    log_user_action(f"Resultado excluído do indicador {indicator_id} para {data_referencia}", st.session_state.username,
                    USER_LOG_FILE)

    st.success("Resultado e análise crítica excluídos com sucesso!")
    st.rerun()

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
            results = json.load(f)
            # Garantir que cada resultado tem a estrutura esperada para valores_variaveis
            for res in results:
                if "valores_variaveis" not in res:
                    res["valores_variaveis"] = {} # Dicionário {variavel: valor}
            return results
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.error("Erro ao decodificar o arquivo de resultados. O arquivo pode estar corrompido.")
        return []

def save_results(results, RESULTS_FILE):
    """Salva os resultados no arquivo."""
    try:
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=4, default=str)
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
    """
    Mostra a página de criação de indicador com fórmula dinâmica e teste.
    Permite definir nome, objetivo, fórmula, variáveis, meta, comparação,
    tipo de gráfico e setor responsável.
    """
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Criar Novo Indicador")

    # Limpar estados de sessão relacionados a outras páginas ou edições
    if 'dashboard_data' in st.session_state:
        del st.session_state['dashboard_data']
    st.session_state.editing_indicator_id = None

    # Chave para o formulário principal
    form_key = "create_indicator_form"

    # Inicializar estados de sessão para variáveis dinâmicas e teste
    if 'create_current_formula_vars' not in st.session_state:
        st.session_state.create_current_formula_vars = []
    if 'create_current_var_descriptions' not in st.session_state:
        st.session_state.create_current_var_descriptions = {}
    if 'create_sample_values' not in st.session_state:
        st.session_state.create_sample_values = {}
    if 'create_test_result' not in st.session_state:
        st.session_state.create_test_result = None
    if 'show_variable_section' not in st.session_state:
        st.session_state.show_variable_section = False

    # Detectar variáveis na fórmula atual do input (antes do formulário)
    current_formula_input_value = st.session_state.get(f"{form_key}_formula", "")
    current_detected_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', current_formula_input_value))))

    # Atualizar estados de variáveis se a fórmula mudou
    if st.session_state.create_current_formula_vars != current_detected_vars:
         st.session_state.create_current_formula_vars = current_detected_vars
         new_var_descriptions = {}
         for var in current_detected_vars:
              new_var_descriptions[var] = st.session_state.create_current_var_descriptions.get(var, "")
         st.session_state.create_current_var_descriptions = new_var_descriptions
         new_sample_values = {}
         for var in current_detected_vars:
              new_sample_values[var] = st.session_state.create_sample_values.get(var, 0.0)
         st.session_state.create_sample_values = new_sample_values
         st.session_state.create_test_result = None


    # Formulário principal para criar indicador
    with st.form(key=form_key):
        # Campos básicos do indicador
        nome = st.text_input("Nome do Indicador", key=f"{form_key}_nome")
        objetivo = st.text_area("Objetivo", key=f"{form_key}_objetivo")
        unidade = st.text_input("Unidade do Resultado", placeholder="Ex: %", key=f"{form_key}_unidade")
        formula = st.text_input(
            "Fórmula de Cálculo (Use letras para variáveis, ex: A+B/C)",
            placeholder="Ex: (DEMISSOES / TOTAL_FUNCIONARIOS) * 100",
            key=f"{form_key}_formula"
        )

        # Botão para carregar a fórmula e detectar variáveis (dentro do form, sem key)
        load_formula_button = st.form_submit_button("⚙️ Carregar Fórmula e Variáveis")

        # Seção para Variáveis e Teste da Fórmula (exibida condicionalmente)
        st.markdown("---")
        st.subheader("Variáveis da Fórmula e Teste")

        if st.session_state.show_variable_section and st.session_state.create_current_formula_vars:
            st.info(f"Variáveis detectadas na fórmula: {', '.join(st.session_state.create_current_formula_vars)}")
            st.write("Defina a descrição e insira valores de teste para cada variável:")

            # Inputs para descrição e valores de teste (dentro do form)
            cols_desc = st.columns(min(3, len(st.session_state.create_current_formula_vars)))
            cols_sample = st.columns(min(3, len(st.session_state.create_current_formula_vars)))

            new_var_descriptions = {}
            new_sample_values = {}

            for i, var in enumerate(st.session_state.create_current_formula_vars):
                col_idx = i % len(cols_desc)
                with cols_desc[col_idx]:
                    new_var_descriptions[var] = st.text_input(
                        f"Descrição para '{var}'",
                        value=st.session_state.create_current_var_descriptions.get(var, ""),
                        placeholder=f"Ex: {var} - Número de Atendimentos",
                        key=f"{form_key}_desc_input_{var}"
                    )
                with cols_sample[col_idx]:
                     new_sample_values[var] = st.number_input(
                         f"Valor de Teste para '{var}'",
                         value=float(st.session_state.create_sample_values.get(var, 0.0)),
                         step=0.01,
                         format="%.2f",
                         key=f"{form_key}_sample_input_{var}"
                     )

            # Atualiza estados dinâmicos com valores dos inputs do form
            st.session_state.create_current_var_descriptions = new_var_descriptions
            st.session_state.create_sample_values = new_sample_values

            # Botão para testar a fórmula (dentro do form, sem key)
            test_formula_button = st.form_submit_button("✨ Testar Fórmula")

            # Exibir resultado do teste
            if st.session_state.create_test_result is not None:
                 current_unidade_input_value = st.session_state.get(f"{form_key}_unidade", "")
                 st.markdown(f"**Resultado do Teste:** **{st.session_state.create_test_result:.2f}{current_unidade_input_value}**")

        elif st.session_state.show_variable_section and not st.session_state.create_current_formula_vars:
             st.warning("Nenhuma variável (letras) encontrada na fórmula. O resultado será um valor fixo.")
             st.session_state.create_current_formula_vars = []
             st.session_state.create_current_var_descriptions = {}
             st.session_state.create_sample_values = {}
             st.session_state.create_test_result = None

        else:
            st.info("Insira a fórmula acima e clique em '⚙️ Carregar Fórmula e Variáveis' para definir as variáveis e testar.")
            st.session_state.create_current_formula_vars = []
            st.session_state.create_current_var_descriptions = {}
            st.session_state.create_sample_values = {}
            st.session_state.create_test_result = None
            st.session_state.show_variable_section = False


        # Outros campos do indicador (dentro do form)
        st.markdown("---")
        meta = st.number_input("Meta", step=0.01, format="%.2f", key=f"{form_key}_meta")
        comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"], key=f"{form_key}_comparacao")
        tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS, key=f"{form_key}_tipo_grafico")
        responsavel = st.selectbox("Setor Responsável", SETORES, key=f"{form_key}_responsavel")

        # Botão principal de criação (dentro do form, sem key)
        create_button = st.form_submit_button("➕ Criar")

    # --- Lógica para lidar com os botões de submissão (FORA do formulário) ---
    # Acessa os valores dos inputs e botões submetidos via session_state

    if load_formula_button:
        # Ativa a exibição da seção de variáveis se a fórmula não estiver vazia
        formula_submitted = st.session_state.get(f"{form_key}_formula", "")
        if formula_submitted:
             st.session_state.show_variable_section = True
             st.session_state.create_test_result = None # Limpa resultado do teste anterior
        else:
             st.session_state.show_variable_section = False
             st.session_state.create_current_formula_vars = []
             st.session_state.create_current_var_descriptions = {}
             st.session_state.create_sample_values = {}
             st.session_state.create_test_result = None
             st.warning("⚠️ Por favor, insira uma fórmula para carregar.")


    elif test_formula_button:
         # Lógica para testar a fórmula com valores de teste
         formula_str = st.session_state.get(f"{form_key}_formula", "")
         variable_values = st.session_state.create_sample_values
         unidade_submitted = st.session_state.get(f"{form_key}_unidade", "")

         if not formula_str:
              st.warning("⚠️ Por favor, insira uma fórmula para testar.")
              st.session_state.create_test_result = None
         elif not variable_values and formula_str:
              try:
                  calculated_result = float(sympify(formula_str))
                  st.session_state.create_test_result = calculated_result
              except (SympifyError, ValueError, TypeError) as e:
                  st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe ou se todas as variáveis foram inseridas. Detalhes: {e}")
                  st.session_state.create_test_result = None
         elif variable_values:
              try:
                  var_symbols = symbols(list(variable_values.keys()))
                  expr = sympify(formula_str, locals=dict(zip(variable_values.keys(), var_symbols)))
                  subs_dict = {symbols(var): float(value) for var, value in variable_values.items()}
                  calculated_result = float(expr.subs(subs_dict))
                  st.session_state.create_test_result = calculated_result
              except (SympifyError, ZeroDivisionError, ValueError, TypeError) as e:
                  st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe ou se há divisão por zero. Detalhes: {e}")
                  st.session_state.create_test_result = None
              except Exception as e:
                   st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                   st.session_state.create_test_result = None


    elif create_button:
        # Lógica para criar o indicador
        nome_submitted = st.session_state.get(f"{form_key}_nome", "")
        objetivo_submitted = st.session_state.get(f"{form_key}_objetivo", "")
        formula_submitted = st.session_state.get(f"{form_key}_formula", "")
        unidade_submitted = st.session_state.get(f"{form_key}_unidade", "")
        meta_submitted = st.session_state.get(f"{form_key}_meta", 0.0)
        comparacao_submitted = st.session_state.get(f"{form_key}_comparacao", "Maior é melhor")
        tipo_grafico_submitted = st.session_state.get(f"{form_key}_tipo_grafico", TIPOS_GRAFICOS[0])
        responsavel_submitted = st.session_state.get(f"{form_key}_responsavel", SETORES[0])
        variaveis_desc_submitted = st.session_state.create_current_var_descriptions

        # Validar campos obrigatórios
        if not nome_submitted or not objetivo_submitted or not formula_submitted:
             st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (Nome, Objetivo, Fórmula).")
        else:
            # Validar a fórmula antes de salvar
            if formula_submitted:
                try:
                    var_symbols = symbols(st.session_state.create_current_formula_vars)
                    sympify(formula_submitted, locals=dict(zip(st.session_state.create_current_formula_vars, var_symbols)))
                except (SympifyError, ValueError, TypeError) as e:
                    st.error(f"❌ Erro na sintaxe da fórmula: {e}")
                    return
                except Exception as e:
                     st.error(f"❌ Erro inesperado ao validar a fórmula: {e}")
                     return

            with st.spinner("Criando indicador..."):
                time.sleep(0.5)
                indicators = load_indicators(INDICATORS_FILE)

                if any(ind["nome"] == nome_submitted for ind in indicators):
                    st.error(f"❌ Já existe um indicador com o nome '{nome_submitted}'.")
                else:
                    new_indicator = {
                        "id": generate_id(),
                        "nome": nome_submitted,
                        "objetivo": objetivo_submitted,
                        "formula": formula_submitted,
                        "variaveis": variaveis_desc_submitted,
                        "unidade": unidade_submitted,
                        "meta": meta_submitted,
                        "comparacao": comparacao_submitted,
                        "tipo_grafico": tipo_grafico_submitted,
                        "responsavel": responsavel_submitted,
                        "data_criacao": datetime.now().isoformat(),
                        "data_atualizacao": datetime.now().isoformat()
                    }

                    indicators.append(new_indicator)
                    save_indicators(indicators, INDICATORS_FILE)
                    log_indicator_action("Indicador criado", new_indicator["id"], INDICATOR_LOG_FILE)

                    st.success(f"✅ Indicador '{nome_submitted}' criado com sucesso!")

                    # Limpar estado do formulário e estados dinâmicos após sucesso
                    if form_key in st.session_state:
                        del st.session_state[form_key]
                    st.session_state.create_current_formula_vars = []
                    st.session_state.create_current_var_descriptions = {}
                    st.session_state.create_sample_values = {}
                    st.session_state.create_test_result = None
                    st.session_state.show_variable_section = False

                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

def edit_indicator(SETORES, TIPOS_GRAFICOS, INDICATORS_FILE, INDICATOR_LOG_FILE, RESULTS_FILE):
    """Mostra a página de edição de indicador com fórmula dinâmica."""
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
    # Usar o ID do indicador no estado da sessão se estiver editando um
    selected_indicator_id_from_state = st.session_state.editing_indicator_id

    # Encontrar o índice do indicador selecionado (se houver um no estado)
    initial_index = 0
    if selected_indicator_id_from_state:
         try:
             # Encontra o índice do indicador com o ID salvo no estado
             initial_index = next(i for i, ind in enumerate(indicators) if ind["id"] == selected_indicator_id_from_state)
         except StopIteration:
             # Indicador do estado não encontrado (talvez foi excluído), resetar estado
             st.session_state.editing_indicator_id = None
             st.session_state.current_formula_vars = []
             st.session_state.current_var_descriptions = {}
             st.session_state.current_variable_values = {} # Limpa também os valores de variáveis


    selected_indicator_name = st.selectbox(
        "Selecione um indicador para editar:",
        indicator_names,
        index=initial_index if initial_index < len(indicator_names) else 0,
        key="edit_indicator_select" # Chave única para este selectbox
    )

    # Encontrar o indicador selecionado
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        # Carregar a fórmula e variáveis existentes para o estado da sessão ao selecionar um novo indicador
        # Verifica se o indicador selecionado mudou ou se os estados de fórmula/variáveis estão vazios
        if st.session_state.editing_indicator_id != selected_indicator["id"] or not st.session_state.current_formula_vars:
             st.session_state.editing_indicator_id = selected_indicator["id"]
             # Carrega a fórmula existente do indicador
             existing_formula = selected_indicator.get("formula", "")
             st.session_state.current_formula_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', existing_formula))))
             # Carrega as descrições de variáveis existentes do indicador
             st.session_state.current_var_descriptions = selected_indicator.get("variaveis", {})
             # Garantir que todas as variáveis detectadas tenham uma entrada no dicionário de descrições
             for var in st.session_state.current_formula_vars:
                  if var not in st.session_state.current_var_descriptions:
                       st.session_state.current_var_descriptions[var] = ""
             # Remover descrições de variáveis que não estão mais na fórmula (limpeza)
             vars_to_remove = [v for v in st.session_state.current_var_descriptions if v not in st.session_state.current_formula_vars]
             for var in vars_to_remove:
                  del st.session_state.current_var_descriptions[var]

             # Limpa os valores de variáveis ao mudar de indicador
             st.session_state.current_variable_values = {}

        # Estado para gerenciar a confirmação de exclusão
        delete_state_key = f"delete_state_{selected_indicator['id']}"
        if delete_state_key not in st.session_state:
            st.session_state[delete_state_key] = None # Pode ser None, 'confirming', 'deleting'


        # Formulário para editar indicador
        # Usamos uma chave única para o formulário para que ele seja re-renderizado corretamente
        with st.form(key=f"edit_form_{selected_indicator['id']}"):
            nome = st.text_input("Nome do Indicador", value=selected_indicator["nome"])
            objetivo = st.text_area("Objetivo", value=selected_indicator["objetivo"])

            # NOVO: Campo para a unidade do resultado
            unidade = st.text_input("Unidade do Resultado", value=selected_indicator.get("unidade", ""), placeholder="Ex: %", key=f"edit_unidade_input_{selected_indicator['id']}")

            # Campo para a fórmula (pré-preenchido com o valor existente)
            formula = st.text_input(
                "Fórmula de Cálculo (Use letras para variáveis, ex: A+B/C)",
                value=selected_indicator.get("formula", ""), # Carrega a fórmula existente
                placeholder="Ex: (DEMISSOES / TOTAL_FUNCIONARIOS) * 100",
                key=f"edit_formula_input_{selected_indicator['id']}" # Chave única
            )

            # Detectar variáveis na fórmula ATUAL do input para exibição dos campos de descrição
            current_detected_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', formula))))

            # Atualizar estado da sessão se a fórmula mudou no input
            if st.session_state.current_formula_vars != current_detected_vars:
                 st.session_state.current_formula_vars = current_detected_vars
                 # Tentar manter descrições existentes para variáveis que ainda existem
                 new_var_descriptions = {}
                 for var in current_detected_vars:
                      new_var_descriptions[var] = st.session_state.current_var_descriptions.get(var, "")
                 st.session_state.current_var_descriptions = new_var_descriptions
                 # st.experimental_rerun() # Pode ser necessário um rerun aqui para atualizar os inputs de descrição


            # Campos para definir a descrição das variáveis (aparecem após a fórmula ser inserida e variáveis detectadas)
            st.markdown("---")
            st.subheader("Definição das Variáveis na Fórmula")

            if st.session_state.current_formula_vars:
                st.info(f"Variáveis detectadas na fórmula: {', '.join(st.session_state.current_formula_vars)}")
                st.write("Defina a descrição para cada variável:")

                # Usar colunas para organizar os inputs de descrição
                cols = st.columns(min(3, len(st.session_state.current_formula_vars)))
                new_var_descriptions = {}
                for i, var in enumerate(st.session_state.current_formula_vars):
                    col_idx = i % len(cols)
                    with cols[col_idx]:
                        # Usar a descrição existente do estado da sessão
                        new_var_descriptions[var] = st.text_input(
                            f"Descrição para '{var}'",
                            value=st.session_state.current_var_descriptions.get(var, ""),
                            placeholder=f"Ex: {var} - Número de Atendimentos",
                            key=f"desc_input_{var}_edit_{selected_indicator['id']}" # Chave única
                        )
                # Atualiza o estado da sessão com as descrições preenchidas
                st.session_state.current_var_descriptions = new_var_descriptions

            else:
                st.warning("Nenhuma variável (letras) encontrada na fórmula. O resultado será um valor fixo.")
                st.session_state.current_var_descriptions = {}


            # Outros campos do indicador
            st.markdown("---")
            # NOVO: Limitar input de meta a 2 casas decimais
            meta = st.number_input("Meta", value=float(selected_indicator.get("meta", 0.0)), step=0.01, format="%.2f")

            comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"],
                                      index=0 if selected_indicator.get("comparacao", "Maior é melhor") == "Maior é melhor" else 1)
            tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS,
                                        index=TIPOS_GRAFICOS.index(selected_indicator.get("tipo_grafico", "Linha")) if selected_indicator.get("tipo_grafico", "Linha") in TIPOS_GRAFICOS else 0)
            responsavel = st.selectbox("Setor Responsável", SETORES,
                                       index=SETORES.index(selected_indicator.get("responsavel", SETORES[0])) if selected_indicator.get("responsavel", SETORES[0]) in SETORES else 0)

            # Criar colunas para os botões
            col1, col2, col3 = st.columns([1, 3, 1])

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
                submit = st.form_submit_button("💾 Salvar")
            with col3:
                # Botão Excluir - Sem 'key' dentro do form
                delete_button_clicked = st.form_submit_button("️ Excluir", type="secondary") # REMOVIDO O ARGUMENTO 'key'


            # --- Lógica após a submissão do formulário ---
            if submit:
                # Validar a fórmula antes de salvar
                if formula:
                    try:
                        # Tenta parsear a fórmula para verificar a sintaxe básica
                        var_symbols = symbols(st.session_state.current_formula_vars)
                        sympify(formula, locals=dict(zip(st.session_state.current_formula_vars, var_symbols)))
                    except SympifyError as e:
                        st.error(f"❌ Erro na sintaxe da fórmula: {e}")
                        return
                    except Exception as e:
                        st.error(f"❌ Erro inesperado ao validar a fórmula: {e}")
                        return

                # Validar se todas as variáveis detectadas têm descrição (opcional)
                # if st.session_state.current_formula_vars and any(desc.strip() == "" for desc in st.session_state.current_var_descriptions.values()):
                #      st.error("❌ Por favor, defina a descrição para todas as variáveis detectadas.")
                #      return

                # Validar campos obrigatórios (Nome, Objetivo, Fórmula)
                if nome and objetivo and formula:
                    # Verificar se o nome foi alterado e se já existe outro indicador com esse nome
                    if nome != selected_indicator["nome"] and any(
                            ind["nome"] == nome for ind in indicators if ind["id"] != selected_indicator["id"]):
                        st.error(f"❌ Já existe um indicador com o nome '{nome}'.")
                    else:
                        # Atualizar indicador
                        for ind in indicators:
                            if ind["id"] == selected_indicator["id"]:
                                ind["nome"] = nome
                                ind["objetivo"] = objetivo
                                ind["formula"] = formula # Salva a fórmula editada
                                ind["variaveis"] = st.session_state.current_var_descriptions # Salva as descrições editadas
                                ind["unidade"] = unidade # NOVO: Salva a unidade
                                ind["meta"] = meta
                                ind["comparacao"] = comparacao
                                ind["tipo_grafico"] = tipo_grafico
                                ind["responsavel"] = responsavel
                                ind["data_atualizacao"] = datetime.now().isoformat()

                        # Salvar alterações
                        save_indicators(indicators, INDICATORS_FILE)
                        st.session_state["indicators"] = load_indicators(INDICATORS_FILE)  # Recarrega os indicadores
                        st.success(f"✅ Indicador '{nome}' atualizado com sucesso!")

                        # Limpar estado da sessão relacionado à edição após salvar
                        st.session_state.editing_indicator_id = None
                        st.session_state.current_formula_vars = []
                        st.session_state.current_var_descriptions = {}
                        st.session_state.current_variable_values = {} # Limpa também os valores de variáveis

                        st.rerun() # Recarrega a página para atualizar a lista ou mostrar o indicador editado
                else:
                    st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (Nome, Objetivo, Fórmula).")

            # Lógica para iniciar a confirmação de exclusão (fora do form)
            # Se o botão de exclusão dentro do formulário foi clicado, definimos o estado para 'confirming'
            if delete_button_clicked:
                 st.session_state[delete_state_key] = 'confirming'
                 st.rerun() # Rerun para exibir a mensagem de confirmação fora do formulário


        # Bloco de confirmação de exclusão (fora do form)
        # Este bloco só é exibido se o estado for 'confirming'
        if st.session_state.get(delete_state_key) == 'confirming':
            st.warning(f"Tem certeza que deseja excluir o indicador '{selected_indicator['nome']}'?")
            col1, col2 = st.columns(2)
            with col1:
                # Botão Sim, Excluir - FORA do form, PRECISA de 'key'
                if st.button("✅ Sim, Excluir", key=f"confirm_delete_{selected_indicator['id']}"):
                    # Define o estado para 'deleting' e reruns para executar a exclusão
                    st.session_state[delete_state_key] = 'deleting'
                    st.rerun()
            with col2:
                # Botão Cancelar - FORA do form, PRECISA de 'key'
                if st.button("❌ Cancelar", key=f"cancel_delete_{selected_indicator['id']}"):
                    st.info("Exclusão cancelada.")
                    # Reseta o estado e reruns
                    st.session_state[delete_state_key] = None
                    st.rerun()

        # Bloco de execução da exclusão (fora do form)
        # Este bloco só é executado se o estado for 'deleting'
        if st.session_state.get(delete_state_key) == 'deleting':
            # Executa a exclusão
            delete_indicator(selected_indicator["id"], INDICATORS_FILE, RESULTS_FILE, INDICATOR_LOG_FILE)
            st.success(f"Indicador '{selected_indicator['nome']}' excluído com sucesso!")

            # Reseta o estado e reruns para atualizar a lista de indicadores
            st.session_state[delete_state_key] = None
            st.session_state.editing_indicator_id = None # Limpa também o estado de edição
            st.session_state.current_formula_vars = []
            st.session_state.current_var_descriptions = {}
            st.session_state.current_variable_values = {} # Limpa também os valores de variáveis


            st.rerun()


    st.markdown('</div>', unsafe_allow_html=True)
     
def display_result_with_delete(result, selected_indicator, RESULTS_FILE, USER_LOG_FILE):
    """Exibe um resultado com a opção de excluir."""
    data_referencia = result.get('data_referencia')
    if data_referencia:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 2, 2, 2, 1])  # Ajuste as proporções das colunas
        with col1:
            st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
        with col2:
            st.write(result.get('resultado', 'N/A'))
        with col3:
            st.write(result.get('observacao', 'N/A'))
        with col4:
            st.write(result.get('status_analise', 'N/A'))
        with col5:
            st.write(pd.to_datetime(result.get('data_atualizacao')).strftime("%d/%m/%Y %H:%M") if result.get('data_atualizacao') else 'N/A')
        with col6:
            if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}"):
                delete_result(selected_indicator['id'], data_referencia, RESULTS_FILE, USER_LOG_FILE)
    else:
        st.warning("Data de referência ausente. Impossível excluir este resultado.")

def fill_indicator(SETORES, INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO, USER_LOG_FILE, USERS_FILE):
    """Mostra a página de preenchimento de indicador com calculadora dinâmica."""
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
    user_name = st.session_state.get("username", "Usuário não identificado") # Usar username da sessão

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
            # Mostrar a fórmula se existir
            if selected_indicator.get("formula"):
                 st.markdown(f"**Fórmula de Cálculo:** `{selected_indicator['formula']}`")
            else:
                 st.markdown(f"**Fórmula de Cálculo:** Não definida (preenchimento direto)")
            # NOVO: Mostrar a unidade
            st.markdown(f"**Unidade do Resultado:** {selected_indicator.get('unidade', 'Não definida')}")


        with col2:
            # NOVO: Formatar exibição da meta para 2 casas decimais e adicionar unidade
            meta_display = f"{float(selected_indicator.get('meta', 0.0)):.2f}{selected_indicator.get('unidade', '')}"
            st.markdown(f"**Meta:** {meta_display}")
            st.markdown(f"**Comparação:** {selected_indicator['comparacao']}")
            st.markdown(f"**Setor Responsável:** {selected_indicator['responsavel']}")

        # Mostrar descrições das variáveis se existirem
        if selected_indicator.get("variaveis"):
             st.markdown("---")
             st.subheader("Variáveis do Indicador")
             # Exibir variáveis e suas descrições em colunas
             vars_list = list(selected_indicator["variaveis"].items())
             if vars_list:
                 cols = st.columns(min(3, len(vars_list)))
                 for i, (var, desc) in enumerate(vars_list):
                     col_idx = i % len(cols)
                     with cols[col_idx]:
                         st.markdown(f"**{var}:** {desc or 'Sem descrição'}")


        st.markdown("---")

        # Carregar resultados existentes para verificar meses já preenchidos
        results = load_results(RESULTS_FILE)
        indicator_results = [r for r in results if r["indicator_id"] == selected_indicator["id"]]

        # Criar um conjunto de meses/anos já preenchidos
        filled_periods = set()
        for result in indicator_results:
            if "data_referencia" in result:
                try:
                    # Normaliza a data de referência para comparação (apenas ano e mês)
                    date_ref = pd.to_datetime(result["data_referencia"]).to_period('M')
                    filled_periods.add(date_ref)
                except:
                    pass # Ignora resultados com data inválida

        # Verificar se há períodos disponíveis para preenchimento
        current_date = datetime.now()
        available_periods = []

        # Considerar os últimos 5 anos para possíveis preenchimentos
        for year in range(current_date.year - 5, current_date.year + 1):
            for month in range(1, 13):
                period = pd.Period(year=year, month=month, freq='M')
                # Não permitir preenchimento de meses futuros
                if period > pd.Period(current_date, freq='M'):
                    continue
                if period not in filled_periods:
                    available_periods.append(period)

        if not available_periods:
            st.info("Todos os períodos relevantes já foram preenchidos para este indicador.")
        else:
            st.subheader("Adicionar Novo Resultado")
            with st.form("adicionar_resultado"):
                # Ordenar períodos disponíveis (mais recentes primeiro)
                available_periods.sort(reverse=True)

                # Criar opções para o selectbox
                period_options = [f"{p.strftime('%B/%Y')}" for p in available_periods]
                selected_period_str = st.selectbox("Selecione o período para preenchimento:", period_options)

                # Encontrar o objeto Period selecionado
                selected_period = next((p for p in available_periods if p.strftime('%B/%Y') == selected_period_str), None)

                # Extrair mês e ano do período selecionado
                selected_month, selected_year = selected_period.month, selected_period.year if selected_period else (None, None)

                # --- Lógica da Calculadora Dinâmica ---
                calculated_result = None # Variável para armazenar o resultado calculado

                # Verificar se o indicador tem fórmula e variáveis
                if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                    st.markdown("#### Valores das Variáveis")
                    st.info(f"Insira os valores para calcular o resultado usando a fórmula: `{selected_indicator['formula']}`")

                    # Usar colunas para organizar os inputs das variáveis
                    vars_to_fill = list(selected_indicator["variaveis"].items())
                    if vars_to_fill:
                        # Usar uma chave única para os inputs de variável dentro do formulário
                        variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                        if variable_values_key not in st.session_state:
                             st.session_state[variable_values_key] = {}

                        cols = st.columns(min(3, len(vars_to_fill)))

                        # Criar inputs para cada variável
                        for i, (var, desc) in enumerate(vars_to_fill):
                            col_idx = i % len(cols)
                            with cols[col_idx]:
                                # Usar o valor do estado da sessão se existir, caso contrário, 0.0
                                default_value = st.session_state[variable_values_key].get(var, 0.0)
                                # NOVO: Limitar input de variável a 2 casas decimais
                                st.session_state[variable_values_key][var] = st.number_input(
                                    f"{var} ({desc or 'Sem descrição'})",
                                    value=float(default_value), # Garantir que o valor inicial é float
                                    step=0.01, # Ajuste o passo conforme a necessidade
                                    format="%.2f", # NOVO: Limitar a 2 casas decimais
                                    key=f"var_input_{var}_{selected_indicator['id']}_{selected_period_str}" # Chave única para o input
                                )

                        # Botão para calcular o resultado
                        test_button_clicked = st.form_submit_button("✨ Calcular Resultado")

                        # Exibir o resultado calculado se estiver no estado da sessão
                        calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"
                        if st.session_state.get(calculated_result_state_key) is not None:
                             calculated_result = st.session_state[calculated_result_state_key]
                             # NOVO: Formatar resultado calculado para 2 casas decimais e adicionar unidade
                             result_display = f"{calculated_result:.2f}{selected_indicator.get('unidade', '')}"
                             st.markdown(f"**Resultado Calculado:** **{result_display}**") # Exibe novamente se já calculado


                    else:
                         st.warning("O indicador tem uma fórmula, mas nenhuma variável definida. O resultado será um valor fixo.")
                         # Se não tem variáveis, volta para o input direto de resultado
                         # NOVO: Limitar input de resultado direto a 2 casas decimais
                         resultado_input_value = st.number_input("Resultado", step=0.01, format="%.2f", key=f"direct_result_input_{selected_indicator['id']}_{selected_period_str}")
                         st.session_state[variable_values_key] = {} # Garante que valores_variaveis está vazio
                         st.session_state[calculated_result_state_key] = None # Garante que resultado calculado está vazio


                else:
                    # Indicador sem fórmula, usa preenchimento direto do resultado
                    # NOVO: Limitar input de resultado direto a 2 casas decimais
                    resultado_input_value = st.number_input("Resultado", step=0.01, format="%.2f", key=f"direct_result_input_{selected_indicator['id']}_{selected_period_str}")
                    variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}" # Definir a chave mesmo sem variáveis
                    st.session_state[variable_values_key] = {} # Garante que valores_variaveis está vazio
                    calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}" # Definir a chave mesmo sem cálculo
                    st.session_state[calculated_result_state_key] = None # Garante que resultado calculado está vazio


                # Campos de Observações e Análise Crítica (mantidos)
                observacoes = st.text_area("Observações (opcional)",
                                           placeholder="Adicione informações relevantes sobre este resultado",
                                           key=f"obs_input_{selected_indicator['id']}_{selected_period_str}")
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
                                    placeholder="O que está acontecendo? Qual é a situação atual do indicador?",
                                    key=f"what_input_{selected_indicator['id']}_{selected_period_str}")
                why = st.text_area("Por que (Why)",
                                   placeholder="Por que isso está acontecendo? Quais são as causas?",
                                   key=f"why_input_{selected_indicator['id']}_{selected_period_str}")
                who = st.text_area("Quem (Who)",
                                    placeholder="Quem é responsável? Quem está envolvido?",
                                    key=f"who_input_{selected_indicator['id']}_{selected_period_str}")
                when = st.text_area("Quando (When)",
                                    placeholder="Quando isso aconteceu? Qual é o prazo para resolução?",
                                    key=f"when_input_{selected_indicator['id']}_{selected_period_str}")
                where = st.text_area("Onde (Where)",
                                     placeholder="Onde ocorre a situação? Em qual processo ou área?",
                                     key=f"where_input_{selected_indicator['id']}_{selected_period_str}")
                how = st.text_area("Como (How)",
                                   placeholder="Como resolver a situação? Quais ações devem ser tomadas?",
                                   key=f"how_input_{selected_indicator['id']}_{selected_period_str}")
                howMuch = st.text_area("Quanto custa (How Much)",
                                       placeholder="Quanto custará implementar a solução? Quais recursos são necessários?",
                                       key=f"howmuch_input_{selected_indicator['id']}_{selected_period_str}")

                # Botão Salvar
                submitted = st.form_submit_button("✔️ Salvar")

            # --- Lógica após a submissão do formulário ---
            # NOVO: Lógica para lidar com os botões de submissão (Calcular e Salvar)
            if test_button_clicked:
                 # Lógica para calcular o resultado (copiada e adaptada do create_indicator)
                 formula_str = selected_indicator.get("formula", "")
                 variable_values = st.session_state.get(variable_values_key, {})

                 if not formula_str:
                      st.warning("⚠️ Este indicador não possui fórmula definida para calcular.")
                      st.session_state[calculated_result_state_key] = None
                 elif not variable_values and formula_str: # Testar fórmula sem variáveis (valor fixo)
                      try:
                          # Tenta avaliar a fórmula como um valor fixo
                          calculated_result = float(sympify(formula_str))
                          st.session_state[calculated_result_state_key] = calculated_result
                          # st.success(f"Resultado calculado: **{calculated_result:.2f}{selected_indicator.get('unidade', '')}**") # Exibir após rerun
                      except (SympifyError, ValueError) as e:
                          st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe ou se todas as variáveis foram inseridas. Detalhes: {e}")
                          st.session_state[calculated_result_state_key] = None
                      except Exception as e:
                           st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                           st.session_state[calculated_result_state_key] = None
                 elif variable_values: # Testar fórmula com variáveis
                      try:
                          # Criar objetos simbólicos para as variáveis
                          var_symbols = symbols(list(variable_values.keys()))
                          # Parsear a fórmula
                          expr = sympify(formula_str, locals=dict(zip(variable_values.keys(), var_symbols)))

                          # Substituir os símbolos pelos valores numéricos
                          # Garantir que os valores são numéricos antes de substituir
                          subs_dict = {symbols(var): float(value) for var, value in variable_values.items()}
                          calculated_result = float(expr.subs(subs_dict))

                          st.session_state[calculated_result_state_key] = calculated_result
                          # st.success(f"Resultado calculado: **{calculated_result:.2f}{selected_indicator.get('unidade', '')}**") # Exibir após rerun

                      except SympifyError as e:
                          st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe. Detalhes: {e}")
                          st.session_state[calculated_result_state_key] = None # Limpa resultado calculado
                      except ZeroDivisionError:
                          st.error("❌ Erro ao calcular a fórmula: Divisão por zero com os valores de teste fornecidos.")
                          st.session_state[calculated_result_state_key] = None # Limpa resultado calculado
                      except Exception as e:
                           # Captura o erro específico e exibe uma mensagem mais amigável,
                           # ou a mensagem original para outros erros inesperados
                           if "cannot create 'dict_keys' instances" in str(e):
                                st.error("❌ Erro interno ao processar as variáveis da fórmula. Verifique se as variáveis na fórmula correspondem às variáveis definidas para o indicador.")
                           else:
                                st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                           st.session_state[calculated_result_state_key] = None # Limpa resultado calculado

                 # Rerun para atualizar a exibição com o resultado calculado
                 st.rerun()


            elif submitted:
                # Lógica de salvamento
                final_result_to_save = None
                values_to_save = {}

                # Determinar qual resultado salvar (calculado ou direto)
                if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                    # Se tem fórmula, tenta usar o resultado calculado do estado da sessão
                    final_result_to_save = st.session_state.get(calculated_result_state_key)
                    values_to_save = st.session_state.get(variable_values_key, {}) # Salva os valores das variáveis

                    if final_result_to_save is None:
                         st.warning("⚠️ Por favor, calcule o resultado antes de salvar.")
                         return # Impede o salvamento se o resultado calculado não existir
                else:
                    # Se não tem fórmula, usa o valor do input direto
                    final_result_to_save = resultado_input_value
                    values_to_save = {} # Não há valores de variáveis para salvar

                # Validar se há um resultado para salvar
                if final_result_to_save is not None:
                    # Formatar a data de referência para ISO 8601
                    data_referencia_iso = datetime(selected_year, selected_month, 1).isoformat()

                    analise_critica = {
                        "what": what, "why": why, "who": who, "when": when,
                        "where": where, "how": how, "howMuch": howMuch
                    }

                    # Verificar o status de preenchimento da análise crítica
                    campos_preenchidos = sum(1 for campo in analise_critica.values() if campo and campo.strip()) # Verifica se o campo não é None e não está vazio/só espaços
                    total_campos = 7 # 5W2H

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
                         if r["indicator_id"] == selected_indicator["id"] and r["data_referencia"] == data_referencia_iso),
                        None)

                    if existing_result:
                        st.warning(
                            f"⚠️ Já existe um resultado para {datetime(selected_year, selected_month, 1).strftime('%B/%Y')}. Este período não deveria estar disponível para preenchimento.")
                    else:
                        new_result = {
                            "indicator_id": selected_indicator["id"],
                            "data_referencia": data_referencia_iso,
                            "resultado": final_result_to_save, # Salva o resultado (calculado ou direto)
                            "valores_variaveis": values_to_save, # Salva os valores das variáveis (vazio se preenchimento direto)
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
                            f"✅ Resultado adicionado com sucesso para {datetime(selected_year, selected_month, 1).strftime('%B/%Y')}!")

                        # Limpar estados da sessão relacionados ao preenchimento após salvar
                        # st.session_state.current_variable_values = {} # Limpa os valores das variáveis
                        if variable_values_key in st.session_state:
                             del st.session_state[variable_values_key] # Limpa a chave específica do formulário
                        if calculated_result_state_key in st.session_state:
                             del st.session_state[calculated_result_state_key] # Limpa o resultado calculado

                        st.rerun() # Recarrega a página para atualizar a lista de períodos disponíveis
                else:
                    st.warning("⚠️ Por favor, informe o resultado ou calcule-o antes de salvar.")

        # Exibir resultados anteriores
        st.subheader("Resultados Anteriores")
        if indicator_results:
            # Ordenar resultados por data (mais recente primeiro)
            indicator_results_sorted = sorted(indicator_results, key=lambda x: x.get("data_referencia", ""), reverse=True)

            # Obter a unidade do indicador para exibição
            unidade_display = selected_indicator.get('unidade', '')

            # Exibir cabeçalho da tabela
            # Ajustar colunas para incluir valores das variáveis ou não
            if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                 # Se tem fórmula, mostra colunas para variáveis e resultado
                 cols_header = st.columns([1.5] + [1] * len(selected_indicator["variaveis"]) + [1, 2, 2, 1]) # Data + Variáveis + Resultado + Obs + Análise + Ações
                 with cols_header[0]: st.markdown("**Período**")
                 for i, var in enumerate(selected_indicator["variaveis"].keys()):
                      with cols_header[i+1]: st.markdown(f"**{var}**")
                 with cols_header[len(selected_indicator["variaveis"])+1]: st.markdown(f"**Resultado ({unidade_display})**") # NOVO: Adiciona unidade ao cabeçalho
                 with cols_header[len(selected_indicator["variaveis"])+2]: st.markdown("**Observações**")
                 with cols_header[len(selected_indicator["variaveis"])+3]: st.markdown("**Análise Crítica**")
                 with cols_header[len(selected_indicator["variaveis"])+4]: st.markdown("**Ações**")

                 # Iterar sobre os resultados e exibir cada uno
                 for result in indicator_results_sorted:
                      cols_data = st.columns([1.5] + [1] * len(selected_indicator["variaveis"]) + [1, 2, 2, 1])
                      data_referencia = result.get('data_referencia')
                      if data_referencia:
                           with cols_data[0]: st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
                           # Exibir valores das variáveis
                           valores_vars = result.get("valores_variaveis", {})
                           for i, var in enumerate(selected_indicator["variaveis"].keys()):
                                with cols_data[i+1]:
                                     # NOVO: Formatar exibição dos valores das variáveis a 2 casas decimais
                                     var_value = valores_vars.get(var)
                                     if isinstance(var_value, (int, float)):
                                          st.write(f"{var_value:.2f}")
                                     else:
                                          st.write('N/A') # Exibe o valor da variável ou N/A

                           with cols_data[len(selected_indicator["variaveis"])+1]:
                                # NOVO: Formatar exibição do resultado a 2 casas decimais e adicionar unidade
                                result_value = result.get('resultado')
                                if isinstance(result_value, (int, float)):
                                     st.write(f"{result_value:.2f}{unidade_display}")
                                else:
                                     st.write('N/A')

                           with cols_data[len(selected_indicator["variaveis"])+2]: st.write(result.get('observacao', 'N/A'))
                           with cols_data[len(selected_indicator["variaveis"])+3]:
                                # Exibir status da análise crítica e expandir para ver detalhes
                                analise_critica_json = result.get('analise_critica', '{}')
                                status_analise = get_analise_status(analise_critica_json)
                                st.write(status_analise)
                                try:
                                     analise_dict = json.loads(analise_critica_json)
                                     if any(analise_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                                          with st.expander("Ver Análise"):
                                               st.markdown("**O que:** " + analise_dict.get("what", ""))
                                               st.markdown("**Por que:** " + analise_dict.get("why", ""))
                                               st.markdown("**Quem:** " + analise_dict.get("who", ""))
                                               st.markdown("**Quando:** " + analise_dict.get("when", ""))
                                               st.markdown("**Onde:** " + analise_dict.get("where", ""))
                                               st.markdown("**Como:** " + analise_dict.get("how", ""))
                                               st.markdown("**Quanto custa:** " + analise_dict.get("howMuch", ""))
                                except:
                                      st.write("Erro ao carregar análise.")

                           with cols_data[len(selected_indicator["variaveis"])+4]:
                                if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}"):
                                    delete_result(selected_indicator['id'], data_referencia, RESULTS_FILE, USER_LOG_FILE)
                      else:
                           st.warning("Resultado com data de referência ausente. Impossível exibir/excluir.")

            else:
                 # Se não tem fórmula, mostra colunas padrão
                 col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 2, 2, 2, 1])
                 with col1: st.markdown("**Período**")
                 with col2: st.markdown(f"**Resultado ({unidade_display})**") # NOVO: Adiciona unidade ao cabeçalho
                 with col3: st.markdown("**Observações**")
                 with col4: st.markdown("**Análise Crítica**")
                 with col5: st.markdown("**Data de Atualização**")
                 with col6: st.markdown("**Ações**")

                 # Iterar sobre os resultados e exibir cada um
                 for result in indicator_results_sorted:
                      data_referencia = result.get('data_referencia')
                      if data_referencia:
                           col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 2, 2, 2, 1])
                           with col1: st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
                           with col2:
                                # NOVO: Formatar exibição do resultado a 2 casas decimais e adicionar unidade
                                result_value = result.get('resultado')
                                if isinstance(result_value, (int, float)):
                                     st.write(f"{result_value:.2f}{unidade_display}")
                                else:
                                     st.write('N/A')
                           with col3: st.write(result.get('observacao', 'N/A'))
                           with col4:
                                # Exibir status da análise crítica e expandir para ver detalhes
                                analise_critica_json = result.get('analise_critica', '{}')
                                status_analise = get_analise_status(analise_critica_json)
                                st.write(status_analise)
                                try:
                                     analise_dict = json.loads(analise_critica_json)
                                     if any(analise_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                                          with st.expander("Ver Análise"):
                                               st.markdown("**O que:** " + analise_dict.get("what", ""))
                                               st.markdown("**Por que:** " + analise_dict.get("why", ""))
                                               st.markdown("**Quem:** " + analise_dict.get("who", ""))
                                               st.markdown("**Quando:** " + analise_dict.get("when", ""))
                                               st.markdown("**Onde:** " + analise_dict.get("where", ""))
                                               st.markdown("**Como:** " + analise_dict.get("how", ""))
                                               st.markdown("**Quanto custa:** " + analise_dict.get("howMuch", ""))
                                except:
                                     st.write("Erro ao carregar análise.")

                           with col5: st.write(pd.to_datetime(result.get('data_atualizacao')).strftime("%d/%m/%Y %H:%M") if result.get('data_atualizacao') else 'N/A')
                           with col6:
                                if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}"):
                                    delete_result(selected_indicator['id'], data_referencia, RESULTS_FILE, USER_LOG_FILE)
                      else:
                           st.warning("Resultado com data de referência ausente. Impossível exibir/excluir.")


        else:
            st.info("Nenhum resultado registrado para este indicador.")

        # --------------- LOG DE PREENCHIMENTO (NOVO BLOCO) ---------------
        st.markdown("---")
        # Carregar todos os resultados após possíveis atualizações
        all_results = load_results(RESULTS_FILE)
        log_results = [r for r in all_results if r["indicator_id"] == selected_indicator["id"]]
        log_results = sorted(log_results, key=lambda x: x.get("data_atualizacao", ""), reverse=True)

        with st.expander("📜 Log de Preenchimentos (clique para visualizar)", expanded=False):
            if log_results:
                log_data_list = []
                unidade_log = selected_indicator.get('unidade', '') # Obter unidade para o log
                for r in log_results:
                     # NOVO: Formatar resultado salvo para 2 casas decimais e adicionar unidade
                     result_saved_display = r.get("resultado")
                     if isinstance(result_saved_display, (int, float)):
                          result_saved_display = f"{result_saved_display:.2f}{unidade_log}"
                     else:
                          result_saved_display = "N/A"

                     # NOVO: Formatar valores das variáveis para 2 casas decimais
                     valores_vars = r.get("valores_variaveis", {})
                     if valores_vars:
                          valores_vars_display = ", ".join([f"{v}={float(val):.2f}" if isinstance(val, (int, float)) else f"{v}={val}" for v, val in valores_vars.items()])
                     else:
                          valores_vars_display = "N/A"


                     log_entry = {
                          "Período": pd.to_datetime(r.get("data_referencia")).strftime("%B/%Y") if r.get("data_referencia") else "N/A",
                          "Resultado Salvo": result_saved_display, # NOVO: Usar resultado formatado
                          "Valores Variáveis": valores_vars_display, # NOVO: Usar valores formatados
                          "Usuário": r.get("usuario", "System"),
                          "Status Análise Crítica": r.get("status_analise", get_analise_status(r.get("analise_critica", "{}"))),
                          "Data/Hora Preenchimento": pd.to_datetime(r.get("data_atualizacao", r.get("data_criacao", datetime.now().isoformat()))).strftime("%d/%m/%Y %H:%M")
                     }

                     log_data_list.append(log_entry)

                log_df = pd.DataFrame(log_data_list)
                # Reordenar colunas para melhor visualização
                cols_order = ["Período", "Resultado Salvo", "Valores Variáveis", "Usuário", "Status Análise Crítica", "Data/Hora Preenchimento"]
                log_df = log_df[cols_order]

                st.dataframe(log_df, use_container_width=True)
            else:
                st.info("Nenhum registro de preenchimento encontrado para este indicador.")


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
            setores_disponiveis = ["Todos"] + sorted(list(set(ind["responsavel"] for ind in indicators))) # NOVO: Ordenar setores
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

    # Resumo em cards horizontais (mantido, não exibe valores formatados aqui)
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
            meta = float(ind.get("meta", 0.0)) # Usar .get com valor padrão

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

    # Gráfico de status dos indicadores (mantido)
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
                meta = float(ind.get("meta", 0.0)) # Usar .get com valor padrão
                resultado = float(last_result)

                if ind["comparacao"] == "Maior é melhor":
                    status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else:  # Menor é melhor
                    status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"

                # Calcular variação percentual
                # NOVO: Tratar divisão por zero na variação
                if meta != 0:
                    variacao = ((resultado / meta) - 1) * 100
                    if ind["comparacao"] == "Menor é melhor":
                        variacao = -variacao  # Inverter para exibição correta
                else:
                    variacao = float('inf') if resultado > 0 else (float('-inf') if resultado < 0 else 0) # Representar variação infinita ou zero

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
        unidade_display = ind.get('unidade', '') # NOVO: Obter a unidade do indicador

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
                # NOVO: Formatar exibição da meta para 2 casas decimais e adicionar unidade
                meta_display = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
                st.markdown(f"""
                <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;">
                    <p style="margin:0; font-size:12px; color:#666;">Meta</p>
                    <p style="margin:0; font-weight:bold; font-size:18px;">{meta_display}</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                status_color = "#26A69A" if data["status"] == "Acima da Meta" else "#FF5252"
                # NOVO: Formatar exibição do último resultado para 2 casas decimais e adicionar unidade
                last_result_display = f"{float(data['last_result']):.2f}{unidade_display}" if isinstance(data['last_result'], (int, float)) else "N/A"
                st.markdown(f"""
                <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;">
                    <p style="margin:0; font-size:12px; color:#666;">Último Resultado</p>
                    <p style="margin:0; font-weight:bold; font-size:18px; color:{status_color};">{last_result_display}</p>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                # NOVO: Formatar exibição da variação para 2 casas decimais
                variacao_color = "#26A69A" if (data["variacao"] >= 0 and ind["comparacao"] == "Maior é melhor") or \
                                            (data["variacao"] <= 0 and ind["comparacao"] == "Menor é melhor") else "#FF5252"
                # NOVO: Tratar exibição de variação infinita
                if data['variacao'] == float('inf'):
                    variacao_text = "+∞%"
                    variacao_color = "#26A69A" if ind["comparacao"] == "Maior é melhor" else "#FF5252"
                elif data['variacao'] == float('-inf'):
                     variacao_text = "-∞%"
                     variacao_color = "#26A69A" if ind["comparacao"] == "Menor é melhor" else "#FF5252"
                elif isinstance(data['variacao'], (int, float)):
                    variacao_text = f"{data['variacao']:.2f}%"
                else:
                    variacao_text = "N/A"

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
                                                          ind.get("meta", 0.0)) and ind["comparacao"] == "Maior é melhor") or
                                                                         (float(row["resultado"]) <= float(
                                                                             ind.get("meta", 0.0)) and ind[
                                                                              "comparacao"] == "Menor é melhor")
                                                      else "Abaixo da Meta", axis=1)

                    # Formatar para exibição - Corrigindo o erro da coluna 'observacoes'
                    # NOVO: Formatar coluna de resultado na tabela histórica
                    df_display = df_hist[["data_referencia", "resultado", "status"]].copy()
                    df_display["resultado"] = df_display["resultado"].apply(lambda x: f"{float(x):.2f}{unidade_display}" if isinstance(x, (int, float)) else "N/A")


                    # Verificar se a coluna 'observacao' existe no DataFrame
                    if "observacao" in df_hist.columns:
                        df_display["observacao"] = df_hist["observacao"]
                    else:
                        df_display["observacao"] = ""  # Adicionar coluna vazia se não existir

                    df_display["data_referencia"] = df_display["data_referencia"].apply(
                        lambda x: x.strftime("%d/%m/%Y"))
                    df_display.columns = ["Data de Referência", f"Resultado ({unidade_display})", "Status", "Observações"] # NOVO: Adiciona unidade ao cabeçalho da tabela

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
                                                           (tendencia == "decrescente" and ind[ # CORREÇÃO: Menor é melhor, decrescente é bom
                                                               "comparacao"] == "Menor é melhor") else \
                                "#FF5252" if (tendencia == "decrescente" and ind["comparacao"] == "Maior é melhor") or \
                                             (tendencia == "crescente" and ind["comparacao"] == "Menor é melhor") else \
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
                            meta_float = float(ind.get("meta", 0.0)) # Usar .get com valor padrão
                            last_result_float = float(data["last_result"]) if isinstance(data["last_result"], (int, float)) else None

                            if last_result_float is not None:
                                if tendencia == "crescente" and ind["comparacao"] == "Maior é melhor":
                                    st.success(
                                        "O indicador apresenta evolução positiva, com resultados crescentes nos últimos períodos.")
                                    if last_result_float >= meta_float:
                                        st.success(
                                            "O resultado atual está acima da meta estabelecida, demonstrando bom desempenho.")
                                    else:
                                        st.warning(
                                            "Apesar da evolução positiva, o resultado ainda está abaixo da meta estabelecida.")
                                elif tendencia == "decrescente" and ind["comparacao"] == "Maior é melhor":
                                    st.error(
                                        "O indicador apresenta tendência de queda, o que é preocupante para este tipo de métrica.")
                                    if last_result_float >= meta_float:
                                        st.warning(
                                            "Embora o resultado atual ainda esteja acima da meta, a tendência de queda requer atenção.")
                                    else:
                                        st.error(
                                            "O resultado está abaixo da meta e com tendência de queda, exigindo ações corretivas urgentes.")
                                elif tendencia == "crescente" and ind["comparacao"] == "Menor é melhor":
                                    st.error(
                                        "O indicador apresenta tendência de aumento, o que é negativo para este tipo de métrica.")
                                    if last_result_float <= meta_float:
                                        st.warning(
                                            "Embora o resultado atual ainda esteja dentro da meta, a tendência de aumento requer atenção.")
                                    else:
                                        st.error(
                                            "O resultado está acima da meta e com tendência de aumento, exigindo ações corretivas urgentes.")
                                elif tendencia == "decrescente" and ind["comparacao"] == "Menor é melhor":
                                    st.success(
                                        "O indicador apresenta evolução positiva, com resultados decrescentes nos últimos períodos.")
                                    if last_result_float <= meta_float:
                                        st.success(
                                            "O resultado atual está dentro da meta estabelecida, demonstrando bom desempenho.")
                                    else:
                                        st.warning(
                                            "Apesar da evolução positiva, o resultado ainda está acima da meta estabelecida.")
                                else:  # Estável
                                    if (last_result_float >= meta_float and ind[
                                        "comparacao"] == "Maior é melhor") or \
                                            (last_result_float <= meta_float and ind[
                                                "comparacao"] == "Menor é melhor"):
                                        st.info("O indicador apresenta estabilidade e está dentro da meta estabelecida.")
                                    else:
                                        st.warning(
                                            "O indicador apresenta estabilidade, porém está fora da meta estabelecida.")
                            else:
                                st.info("Não foi possível realizar a análise automática devido a dados de resultado inválidos.")

                        else:
                            st.info(
                                "Não há dados suficientes para análise de tendência (mínimo de 3 períodos necessários)."
                            )
                    else:
                        st.info("Não há dados históricos suficientes para análise de tendência.")

                    # Adicionar análise crítica no formato 5W2H
                    st.markdown("<h4>Análise Crítica 5W2H</h4>", unsafe_allow_html=True)

                    # Verificar se existe análise crítica para o último resultado
                    ultimo_resultado = df_hist.iloc[0]

                    # Verificar se a análise crítica existe nos dados
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
            # NOVO: Formatar exibição da meta para 2 casas decimais e adicionar unidade
            meta_display = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
            st.markdown(f"""
            <div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0; width: 200px; margin: 10px auto;">
                <p style="margin:0; font-size:12px; color:#666;">Meta</p>
                <p style="margin:0; font-weight:bold; font-size:18px;">{meta_display}</p>
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
            unidade_export = ind.get('unidade', '') # NOVO: Obter unidade para exportação

            # NOVO: Formatar resultados e meta para exportação
            last_result_export = f"{float(data['last_result']):.2f}{unidade_export}" if isinstance(data['last_result'], (int, float)) else "N/A"
            meta_export = f"{float(ind.get('meta', 0.0)):.2f}{unidade_export}"

            # NOVO: Formatar variação para exportação
            if data['variacao'] == float('inf'):
                variacao_export = "+Inf"
            elif data['variacao'] == float('-inf'):
                 variacao_export = "-Inf"
            elif isinstance(data['variacao'], (int, float)):
                variacao_export = f"{data['variacao']:.2f}%"
            else:
                variacao_export = "N/A"


            # Adicionar à lista de dados
            export_data.append({
                "Nome": ind["nome"],
                "Setor": ind["responsavel"],
                "Meta": meta_export, # NOVO: Meta formatada
                "Último Resultado": last_result_export, # NOVO: Último resultado formatado
                "Período": data["data_formatada"],
                "Status": data["status"],
                "Variação": variacao_export # NOVO: Variação formatada
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

    # Adicionar campo de busca (mantido)
    search_query = st.text_input("�� Buscar indicador por nome ou setor", placeholder="Digite para buscar...")


    # Aplicar filtros
    filtered_indicators = indicators

    if setor_filtro and "Todos" not in setor_filtro:
        filtered_indicators = [ind for ind in filtered_indicators if ind["responsavel"] in setor_filtro]

    # Criar DataFrame para visão geral
    overview_data = []

    for ind in filtered_indicators:
        # Obter resultados para este indicador
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]

        # NOVO: Obter a unidade do indicador
        unidade_display = ind.get('unidade', '')

        if ind_results:
            # Ordenar por data e pegar o mais recente
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)

            last_result = df_results.iloc[0]["resultado"]
            last_date = df_results.iloc[0]["data_referencia"]

            # Calcular status
            try:
                meta = float(ind.get("meta", 0.0)) # Usar .get com valor padrão
                resultado = float(last_result)

                if ind["comparacao"] == "Maior é melhor":
                    status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else:  # Menor é melhor
                    status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"

                # Calcular variação percentual
                # NOVO: Tratar divisão por zero na variação
                if meta != 0.0:
                    variacao = ((resultado / meta) - 1) * 100
                    if ind["comparacao"] == "Menor é melhor":
                        variacao = -variacao  # Inverter para exibição correta
                else:
                    variacao = float('inf') if resultado > 0 else (float('-inf') if resultado < 0 else 0) # Representar variação infinita ou zero


            except:
                status = "N/A"
                variacao = 0

            # Formatar data
            data_formatada = format_date_as_month_year(last_date)

            # NOVO: Formatar resultado e meta para exibição com unidade e 2 casas decimais
            last_result_formatted = f"{float(last_result):.2f}{unidade_display}" if isinstance(last_result, (int, float)) else "N/A"
            meta_formatted = f"{float(meta):.2f}{unidade_display}"

            # NOVO: Formatar variação para exibição
            if variacao == float('inf'):
                variacao_formatted = "+Inf"
            elif variacao == float('-inf'):
                 variacao_formatted = "-Inf"
            elif isinstance(variacao, (int, float)):
                variacao_formatted = f"{variacao:.2f}%"
            else:
                variacao_formatted = "N/A"


        else:
            last_result_formatted = "N/A"
            data_formatada = "N/A"
            status = "Sem Resultados"
            variacao_formatted = "N/A"
            # NOVO: Formatar meta mesmo sem resultados
            meta_formatted = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"


        # Adicionar à lista de dados
        overview_data.append({
            "Nome": ind["nome"],
            "Setor": ind["responsavel"],
            "Meta": meta_formatted, # NOVO: Usar meta formatada
            "Último Resultado": last_result_formatted, # NOVO: Usar último resultado formatado
            "Período": data_formatada,
            "Status": status,
            "Variação": variacao_formatted # NOVO: Usar variação formatada (removido o '%')
        })

    # Aplicar filtro de status
    if status_filtro and "Todos" not in status_filtro:
        overview_data = [d for d in overview_data if d["Status"] in status_filtro]

    # Aplicar busca por nome ou setor
    if search_query:
        search_query_lower = search_query.lower()
        overview_data = [d for d in overview_data if search_query_lower in d["Nome"].lower() or search_query_lower in d["Setor"].lower()]


    # Criar DataFrame
    df_overview = pd.DataFrame(overview_data)

    if not df_overview.empty:
        # Exibir visão geral
        # NOVO: Renomear coluna de Variação para incluir (%)
        df_overview.rename(columns={'Variação': 'Variação (%)'}, inplace=True)
        st.dataframe(df_overview, use_container_width=True)

        # Botão para exportar dados
        if st.button("📤 Exportar para Excel"):
            # Os dados em overview_data já estão formatados, então podemos usá-los diretamente
            df_export = pd.DataFrame(overview_data)
            # NOVO: Renomear coluna de Variação para incluir (%) na exportação também
            df_export.rename(columns={'Variação': 'Variação (%)'}, inplace=True)

            download_link = get_download_link(df_export, "visao_geral_indicadores.xlsx")
            st.markdown(download_link, unsafe_allow_html=True)

        # Gráfico de resumo por setor (mantido)
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

        # Gráfico de status (mantido)
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

    # Define local pt-br
    configure_locale()

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
    with st.sidebar.container():
        col1, col2 = st.columns([3, 1])  # Ajuste as proporções das colunas conforme necessário

        with col1:
            st.markdown(f"""
            <div style="background-color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #e0e0e0;">
                <p style="margin:0; font-weight:bold;">{st.session_state.username}</p>
                <p style="margin:0; font-size:12px; color:#666;">{st.session_state.user_type}</p>
                {'<p style="margin:0; font-size:12px; color:#666;">Setor: ' + st.session_state.user_sector + '</p>' if st.session_state.user_type == "Operador" else ''}
            </div>
            """, unsafe_allow_html=True)

        with col2:
            if st.button("🚪", help="Fazer logout"):
                logout()

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
        # Correção: incluir USER_LOG_FILE e USERS_FILE na chamada
        fill_indicator(SETORES, INDICATORS_FILE, RESULTS_FILE, TEMA_PADRAO, USER_LOG_FILE, USERS_FILE)
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
