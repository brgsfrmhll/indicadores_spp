import streamlit as st
import json
import hashlib
import os
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Any
import uuid
import pandas as pd


# --- Configuração do Streamlit e CSS Customizado ---
st.set_page_config(
    page_title="NotificaSanta",
    page_icon="favicon/logo.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS customizado
st.markdown(r"""
<style>
    /* Esconde botões e decorações padrão do Streamlit */
    button[data-testid="stDeployButton"],
    .stDeployButton,
    footer,
    #stDecoration,
    .stAppDeployButton {
        display: none !important;
    }

    /* Ajuste de margem superior para o container principal do Streamlit */
    .reportview-container {
        margin-top: -2em;
    }

    /* Permite que a sidebar seja aberta (linha originalmente comentada, mantida para contexto) */
    /* .sidebar-hint {
        /* display: none; */
    /* } */

    /* Garante que a Sidebar fique ACIMA de outros elementos fixos, se houver */
    div[data-testid="stSidebar"] {
        z-index: 9999 !important; /* Prioridade de empilhamento muito alta */
    }

    /* Adjust Streamlit's default margins for sidebar content */
    /* This targets the internal container of the sidebar */
    [data-testid="stSidebarContent"] {
        padding-top: 10px; /* Reduced from default to move content higher */
    }

    /* Logo - Reduced size and moved up */
    div[data-testid="stSidebar"] img {
        transform: scale(0.6); /* Reduce size by 20% */
        transform-origin: top center; /* Scale from the top center */
        margin-top: -80px; /* Pull the image up */
        margin-bottom: -20px; /* Reduce space below image */
    }

    /* Estilo do cabeçalho principal da aplicação */
    .main-header {
        text-align: center;
        color: #2E86AB;
        margin-bottom: 30px;
    }

    /* Novo Estilo para o Título Principal da Sidebar */
    /* Usamos [data-testid="stSidebarContent"] para aumentar a especificidade e garantir a aplicação */
    [data-testid="stSidebarContent"] .sidebar-main-title {
        text-align: center !important; /* Centraliza o texto */
        color: #00008B !important; /* Cor azul escuro para o título principal */
        font-size: 1.76em !important; /* 2.2em * 0.8 = 1.76em */
        font-weight: 700 !important; /* Negrito forte para o título */
        text-transform: uppercase !important; /* Transforma todo o texto em maiúsculas */
        letter-spacing: 2px !important; /* Aumenta o espaçamento entre as letras para um visual "minimalista" e "estiloso" */
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.2) !important; /* Sombra mais suave para profundidade */
        margin-top: -30px !important; /* Move título principal para cima */
    }

    /* Novo Estilo para o Subtítulo da Sidebar */
    /* Usamos [data-testid="stSidebarContent"] para aumentar a especificidade e garantir a aplicação */
    [data-testid="stSidebarContent"] .sidebar-subtitle {
        text-align: center !important; /* Centraliza o texto */
        color: #333 !important; /* Cor mais suave para o subtítulo */
        font-size: 0.72em !important; /* 0.9em * 0.8 = 0.72em */
        font-weight: 400 !important; /* Peso de fonte médio */
        text-transform: uppercase !important; /* Transforma todo o texto em maiúsculas, mantendo a consistência */
        letter-spacing: 1.5px !important; /* Espaçamento entre letras para alinhamento visual */
        margin-top: -30px !important; /* Pull closer to main title */
        margin-bottom: 5px !important; /* Reduce margin below subtitle */
    }

    /* Estilo geral para cartões de notificação */
    .notification-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        background-color: #f9f9f9;
        color: #2E86AB; /* Cor do texto padrão para o cartão */
    }

    /* Cores e destaque para diferentes status de notificação */
    .status-pendente_classificacao { color: #ff9800; font-weight: bold; } /* Laranja */
    .status-classificada { color: #2196f3; font-weight: bold; } /* Azul */
    .status-em_execucao { color: #9c27b0; font-weight: bold; } /* Roxo */
    .status-aguardando_classificador { color: #ff5722; font-weight: bold; } /* Laranja avermelhado (Usado para Revisão Rejeitada) */
    .status-revisao_classificador_execucao { color: #8BC34A; font-weight: bold; } /* Verde Lima - Novo Status */
    .status-aguardando_aprovacao { color: #ffc107; font-weight: bold; } /* Amarelo */
    .status-aprovada { color: #4caf50; font-weight: bold; } /* Verde */
    .status-concluida { color: #4caf50; font-weight: bold; } /* Verde (mesmo que aprovada para simplificar) */
    .status-rejeitada { color: #f44336; font-weight: bold; } /* Vermelho (Usado para Rejeição Inicial) */
    .status-reprovada { color: #f44336; font-weight: bold; } /* Vermelho (Usado para Rejeição de Aprovação)*/
    /* Estilo para o conteúdo da barra lateral */
    .sidebar .sidebar-content {
        background-color: #f0f2f6; /* Cinza claro */
    }

    /* Estilo para a caixa de informações do usuário na sidebar */
    .user-info {
        background-color: #e8f4fd; /* Azul claro */
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 20px;
    }

    /* Estilo para seções de formulário */
    .form-section {
        background-color: #f8f9fa; /* Cinza bem claro */
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #2E86AB; /* Barra lateral azul */
    }

    /* Estilo para campos condicionais em formulários (ex: detalhes de ação imediata) */
    .conditional-field {
        background-color: #fff3cd; /* Amarelo claro */
        padding: 10px;
        border-radius: 5px;
        border-left: 3px solid #ffc107; /* Barra lateral amarela */
        margin: 10px 0;
    }

    /* Estilo para campos obrigatórios */
    .required-field {
        color: #dc3545; /* Vermelho */
        font-weight: bold;
    }

    /* Cores específicas para botões "Sim" e "Não" selecionados */
    div.stButton > button[data-testid='stButton'][data-key*='_sim_step'][data-selected='true'] {
        border-color: #4caf50; /* Verde */
        color: #4caf50;
    }
    div.stButton > button[data-testid='stButton'][data-key*='_nao_step'][data-selected='true'] {
        border-color: #f44336; /* Vermelho */
        color: #f44336;
    }

    /* Negrito geral para labels dentro de blocos horizontais do Streamlit */
    div[data-testid="stHorizontalBlock"] div[data-testid^="st"] label p {
        font-weight: bold;
    }

    /* Estilo para cartões de métricas no dashboard */
    .metric-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }

    .metric-card h4 {
        margin-top: 0;
        color: #333;
    }

    .metric-card p {
        font-size: 1.8em;
        font-weight: bold;
        color: #2E86AB;
        margin-bottom: 0;
    }

    /* Estilo para o rodapé da sidebar */
    .sidebar-footer {
        text-align: center;
        margin-top: 20px; /* Adiciona um espaço acima do rodapé */
        padding: 10px;
        color: #888;
        font-size: 0.75em;
        border-top: 1px solid #eee; /* Linha divisória sutil */
    }

    /* Remove padding do container principal, pois o rodapé fixo foi removido */
    div[data-testid="stAppViewContainer"] {
        padding-bottom: 0px; /* Não é mais necessário padding na parte inferior */
    }

    /* Estilos para o fundo do cartão de notificação com base no status do prazo */
    .notification-card.card-prazo-dentro {
        background-color: #e6ffe6; /* Verde claro para "No Prazo" e "Prazo Próximo" */
        border: 1px solid #4CAF50; /* Borda verde */
    }

    .notification-card.card-prazo-fora {
        background-color: #ffe6e6; /* Vermelho claro para "Atrasada" */
        border: 1px solid #F44336; /* Borda vermelha */
    }

    /* Estilos para status de prazo */
    .deadline-ontrack { color: #4CAF50; font-weight: bold; } /* Verde */
    .deadline-duesoon { color: #FFC107; font-weight: bold; } /* Amarelo */
    .deadline-overdue { color: #F44336; font-weight: bold; } /* Vermelho */
</style>
""", unsafe_allow_html=True)


# --- Constantes Globais e Mapeamentos ---

# Mapeamento de prazos para conclusão da notificação
DEADLINE_DAYS_MAPPING = {
    "Não conformidade": 30,
    "Circunstância de Risco": 30,
    "Near Miss": 30,
    "Evento sem dano": 10,
    "Evento com dano": {
        "Dano leve": 7,
        "Dano moderado": 5,
        "Dano grave": 3,
        "Óbito": 3
    }
}


# --- Classes de Dados Globais ---

class UI_TEXTS:
    selectbox_default_event_shift = "Selecionar Turno"
    selectbox_default_immediate_actions_taken = "Selecione"
    selectbox_default_patient_involved = "Selecione"
    selectbox_default_patient_outcome_obito = "Selecione"
    selectbox_default_initial_event_type = "Selecione"
    selectbox_default_initial_severity = "Selecione"
    selectbox_default_notification_select = "Selecione uma notificação..."
    text_na = "N/A"
    selectbox_default_procede_classification = "Selecione"
    selectbox_default_classificacao_nnc = "Selecione"
    selectbox_default_nivel_dano = "Selecione"
    selectbox_default_prioridade_resolucao = "Selecione"
    selectbox_default_never_event = "Selecione"
    selectbox_default_evento_sentinela = "Selecione"
    selectbox_default_tipo_principal = "Selecione"
    multiselect_instruction_placeholder = "Selecione uma ou mais opções..."
    multiselect_event_spec_label_prefix = "Especificação do Evento "
    multiselect_event_spec_label_suffix = ":"
    multiselect_classification_oms_label = "Classificação OMS:* (selecionar ao menos um)"
    selectbox_default_requires_approval = "Selecione"
    selectbox_default_approver = "Selecione"
    selectbox_default_decisao_revisao = "Selecione"
    selectbox_default_acao_realizar = "Selecione"
    multiselect_assign_executors_label = "Atribuir Executores Responsáveis:*"
    selectbox_default_decisao_aprovacao = "Selecione"
    multiselect_all_option = "Todos"
    selectbox_sort_by_placeholder = "Ordenar por..."
    selectbox_sort_by_label = "Ordenar por:"
    selectbox_items_per_page_placeholder = "Itens por página..."
    selectbox_items_per_page_label = "Itens por página:"
    selectbox_default_admin_debug_notif = "Selecione uma notificação..."
    selectbox_never_event_na_text = "Não Aplicável (N/A)"
    multiselect_user_roles_label = "Funções do Usuário:*"

    # Novos textos para status de prazo
    deadline_status_ontrack = "No Prazo"
    deadline_status_duesoon = "Prazo Próximo"
    deadline_status_overdue = "Atrasada"
    deadline_days_nan = "Nenhum prazo definido"

    # Constantes para filtros do dashboard
    multiselect_filter_status_label = "Filtrar por Status:"
    multiselect_filter_nnc_label = "Filtrar por Classificação NNC:"
    multiselect_filter_priority_label = "Filtrar por Prioridade:"


class FORM_DATA:
    turnos = ["Diurno", "Noturno"]
    classificacao_nnc = ["Não conformidade", "Circunstância de Risco", "Near Miss", "Evento sem dano",
                         "Evento com dano"]
    niveis_dano = ["Dano leve", "Dano moderado", "Dano grave", "Óbito"]
    prioridades = ["Baixa", "Média", "Alta", "Crítica"]

    SETORES = [
        "Superintendência", "Agência Transfusional (AGT)", "Ala A", "Ala B",
        "Ala C", "Ala E", "Almoxarifado", "Assistência Social",
        "Ambulatório Bariátrica/Reparadora", "CCIH", "CDI", "Centro Cirúrgico",
        "Centro Obstétrico", "CME", "Comercial/Tesouraria", "Compras",
        "Comunicação", "Contabilidade", "CPD (TI)", "DPI",
        "Diretoria Assistencial", "Diretoria Clínica", "Diretoria Financeira",
        "Diretoria Técnica", "Departamento Pessoal (RH)", "Ambulatório Egresso (Especialidades)",
        "EMTN", "Farmácia Clínica", "Farmácia Central", "Farmácia Satélite Centro Cirúrgico",
        "Farmácia Oncológica (Manipulação Quimioterapia)", "Farmácia UNACON", "Farmácia Satélite UTI",
        "Faturamento", "Fisioterapia", "Fonoaudiologia", "Gestão de Leitos",
        "Hemodiálise", "Higienização", "Internação/Autorização (Convênio)", "Iodoterapia",
        "Laboratório de Análises Clínicas", "Lavanderia", "Manutenção Equipamentos", "Manutenção Predial",
        "Maternidade", "Medicina do Trabalho", "NHE", "Odontologia", "Ouvidoria", "Pediatria",
        "Portaria/Gestão de Acessos", "Psicologia", "Qualidade", "Quimioterapia (Salão de Quimio)",
        "Recepção", "Recrutamento e Seleção", "Regulação", "SAME", "SESMT",
        "Serviço de Nutrição e Dietética", "SSB", "Urgência e Emergência/Pronto Socorro",
        "UNACON", "UTI Adulto", "UTI Neo e Pediátrica"
    ]
    never_events = [
        "Cirurgia no local errado do corpo, no paciente errado ou o procedimento errado",
        "Retenção de corpo estranho em paciente após a cirurgia",
        "Morte de paciente ou lesão grave associada ao uso de dispositivo médico",
        "Morte de paciente ou lesão grave associada à incompatibilidade de tipo sanguíneo",
        "Morte de paciente ou lesão grave associada a erro de medicação",
        "Morte de paciente ou lesão grave associada à trombose venosa profunda (TVP) ou embolia pulmonar (EP) após artroplastia total de quadril ou joelho",
        "Morte de paciente ou lesão grave associada a hipoglicemia",
        "Morte de paciente ou lesão grave associada à infecção hospitalar",
        "Morte de paciente ou lesão grave associada a úlcera por pressão (escaras) adquirida no hospital",
        "Morte de paciente ou lesão grave associada à contenção inadequada",
        "Morte ou lesão grave associada à falha ou uso incorreto de equipamentos de proteção individual (EPIs)",
        "Morte de paciente ou lesão grave associada à queda do paciente",
        "Morte de paciente ou lesão grave associada à violência física ou sexual no ambiente hospitalar",
        "Morte de paciente ou lesão grave associada ao desaparecimento de paciente"
    ]
    tipos_evento_principal = {
        "Clínico": [
            "Falha Terapêutica/Assistencial",
            "Falha Diagnóstica",
            "Reação Adversa a Medicamento",
            "Infecção Relacionada à Assistência à Saúde (IRAS)",
            "Queda de Paciente",
            "Lesão por Pressão",
            "Identificação Incorreta",
            "Procedimento Incorreto",
            "Transfusão Incorreta",
            "Problema com Dispositivo/Equipamento Médico",
            "Problema com Exames/Resultados",
            "Outros Eventos Clínicos"
        ],
        "Não-clínico": [
            "Incidente de Segurança Patrimonial",
            "Problema Estrutural/Instalações",
            "Problema de Abastecimento/Logística",
            "Incidente de TI/Dados",
            "Erro Administrativo",
            "Outros Eventos Não-clínicos"
        ],
        "Ocupacional": [
            "Acidente com Material Biológico",
            "Acidente de Trabalho (geral)",
            "Doença Ocupacional",
            "Exposição a Agentes de Risco",
            "Outros Eventos Ocupacionais"
        ],
        "Queixa técnica": [],
        "Outros": []
    }
    classificacao_oms = [
        "Quedas", "Infecções", "Medicação", "Cirurgia", "Identificação do Paciente",
        "Procedimentos", "Dispositivos Médicos", "Urgência/Emergência",
        "Segurança do Ambiente", "Comunicação", "Recursos Humanos", "Outros"
    ]


# --- Diretórios de Dados e Arquivos ---
DATA_DIR = "data"
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "notifications.json")


# --- Funções de Persistência e Banco de Dados ---

def init_database():
    """Garante que os diretórios de dados e arquivos iniciais existam."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(ATTACHMENTS_DIR):
        os.makedirs(ATTACHMENTS_DIR)

    if not os.path.exists(USERS_FILE):
        # Cria um usuário admin padrão se users.json não existir
        admin_user = {
            "id": 1, "username": "admin", "password": hash_password("6105/*"),
            "name": "Administrador", "email": "admin@hospital.com",
            "roles": ["admin", "classificador", "executor", "aprovador"],
            "active": True, "created_at": datetime.now().isoformat()
        }
        save_users([admin_user])
        st.toast("Usuário administrador padrão criado!")

    if not os.path.exists(NOTIFICATIONS_FILE):
        save_notifications([])
        st.toast("Arquivo de notificações criado!")


def load_users() -> List[Dict]:
    """Carrega dados de usuário do arquivo JSON."""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_users(users: List[Dict]):
    """Salva dados de usuário no arquivo JSON."""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def load_notifications() -> List[Dict]:
    """Carrega dados de notificação do arquivo JSON."""
    try:
        with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_notifications(notifications: List[Dict]):
    """Salva dados de notificação no arquivo JSON."""
    with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(notifications, f, indent=2, ensure_ascii=False)


def get_next_id(data_list: List[Dict]) -> int:
    """Gera o próximo ID para uma lista de dicionários."""
    if not data_list:
        return 1
    return max([item.get('id', 0) for item in data_list]) + 1


def save_uploaded_file(uploaded_file: Any, notification_id: int) -> Optional[Dict]:
    """Salva um arquivo enviado para o diretório de anexos e retorna suas informações."""
    if uploaded_file is None:
        return None
    original_name = uploaded_file.name
    safe_original_name = "".join(c for c in original_name if c.isalnum() or c in ('.', '_', '-')).rstrip('.')
    unique_filename = f"{notification_id}_{uuid.uuid4().hex}_{safe_original_name}"
    file_path = os.path.join(ATTACHMENTS_DIR, unique_filename)
    try:
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)  # Garante que o diretório exista
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return {"unique_name": unique_filename, "original_name": original_name}
    except Exception as e:
        st.error(f"Erro ao salvar o anexo {original_name}: {e}")
        return None


def get_attachment_data(unique_filename: str) -> Optional[bytes]:
    """Lê o conteúdo de um arquivo de anexo."""
    file_path = os.path.join(ATTACHMENTS_DIR, unique_filename)
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        st.warning(f"Anexo não encontrado no caminho: {unique_filename}")
        return None
    except Exception as e:
        st.error(f"Erro ao ler o anexo {unique_filename}: {e}")
        return None


# --- Funções de Autenticação e Autorização ---

def hash_password(password: str) -> str:
    """Faz o hash de uma senha usando SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Autentica um usuário com base no nome de usuário e senha."""
    users = load_users()
    hashed_password = hash_password(password)
    for user in users:
        if (user.get('username', '').lower() == username.lower() and
                user.get('password') == hashed_password and
                user.get('active', True)):
            return user
    return None


def logout_user():
    """Desloga o usuário atual."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.page = 'create_notification'
    _reset_form_state()
    if 'initial_classification_state' in st.session_state: st.session_state.pop('initial_classification_state')
    if 'review_classification_state' in st.session_state: st.session_state.pop('review_classification_state')
    if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
        'current_initial_classification_id')
    if 'current_review_classification_id' in st.session_state: st.session_state.pop('current_review_classification_id')


def check_permission(required_role: str) -> bool:
    """Verifica se o usuário logado possui a função necessária ou é um admin."""
    if not st.session_state.authenticated or st.session_state.user is None:
        return False
    user_roles = st.session_state.user.get('roles', [])
    return required_role in user_roles or 'admin' in user_roles


def get_users_by_role(role: str) -> List[Dict]:
    """Retorna usuários ativos com uma função específica."""
    users = load_users()
    return [user for user in users if role in user.get('roles', []) and user.get('active', True)]


def update_user(user_id: int, updates: Dict) -> Optional[Dict]:
    """Atualiza um registro de usuário existente."""
    users = load_users()
    for i, user in enumerate(users):
        if user.get('id') == user_id:
            for key, value in updates.items():
                if key == 'password' and value:
                    users[i][key] = hash_password(value)
                elif key != 'password':
                    users[i][key] = value
            save_users(users)
            return users[i]
    return None


def create_user(data: Dict) -> Optional[Dict]:
    """Cria um novo registro de usuário."""
    users = load_users()
    if any(user.get('username', '').lower() == data.get('username', '').lower() for user in users):
        return None
    user = {
        "id": get_next_id(users),
        "username": data.get('username', '').strip(),
        "password": hash_password(data.get('password', '').strip()),
        "name": data.get('name', '').strip(),
        "email": data.get('email', '').strip(),
        "roles": data.get('roles', []),
        "active": True,
        "created_at": datetime.now().isoformat()
    }
    users.append(user)
    save_users(users)
    return user


# --- Funções de Manipulação de Dados de Notificação ---

def create_notification(data: Dict, uploaded_files: Optional[List[Any]] = None) -> Dict:
    """Cria um novo registro de notificação."""
    notifications = load_notifications()
    notification_id = get_next_id(notifications)
    saved_attachments = []
    if uploaded_files:
        for file in uploaded_files:
            saved_file_info = save_uploaded_file(file, notification_id)
            if saved_file_info:
                saved_attachments.append(saved_file_info)

    # Converte objetos de data e hora para strings no formato ISO para serialização JSON
    occurrence_date_iso = data.get('occurrence_date').isoformat() if isinstance(data.get('occurrence_date'),
                                                                                date) else None
    occurrence_time_str = data.get('occurrence_time').isoformat() if isinstance(data.get('occurrence_time'),
                                                                                time) else str(
        data.get('occurrence_time')) if data.get('occurrence_time') is not None else None

    notification = {
        "id": notification_id,
        "title": data.get('title', '').strip(),
        "description": data.get('description', '').strip(),
        "location": data.get('location', '').strip(),
        "occurrence_date": occurrence_date_iso,
        "occurrence_time": occurrence_time_str,
        "reporting_department": data.get('reporting_department', '').strip(),
        "reporting_department_complement": data.get('reporting_department_complement', '').strip(),
        "notified_department": data.get('notified_department', '').strip(),
        "notified_department_complement": data.get('notified_department_complement', '').strip(),
        "event_shift": data.get('event_shift', UI_TEXTS.selectbox_default_event_shift),
        "immediate_actions_taken": data.get('immediate_actions_taken',
                                            UI_TEXTS.selectbox_default_immediate_actions_taken),
        "immediate_action_description": data.get('immediate_action_description', '').strip() if data.get(
            'immediate_actions_taken') == "Sim" else '',
        "patient_involved": data.get('patient_involved', UI_TEXTS.selectbox_default_patient_involved),
        "patient_id": data.get('patient_id', '').strip() if data.get('patient_involved') == "Sim" else '',
        "patient_outcome_obito": (
            True if data.get('patient_outcome_obito') == "Sim" else
            False if data.get('patient_outcome_obito') == "Não" else
            None
        ) if data.get('patient_involved') == "Sim" else None,
        "additional_notes": data.get('additional_notes', '').strip(),
        "status": "pendente_classificacao",
        "created_at": datetime.now().isoformat(),
        "classification": None,
        "rejection_classification": None,
        "executors": [],
        "approver": None,
        "actions": [],
        "review_execution": None,
        "approval": None,
        "rejection_approval": None,
        "conclusion": None,
        "attachments": saved_attachments,
        "history": [{
            "action": "Notificação criada",
            "user": "Sistema (Formulário Público)",
            "timestamp": datetime.now().isoformat(),
            "details": f"Notificação enviada para classificação. Título: {data.get('title', 'Sem título')[:100]}..." if len(
                data.get('title',
                         '')) > 100 else f"Notificação enviada para classificação. Título: {data.get('title', 'Sem título')}"
        }]
    }
    notifications.append(notification)
    save_notifications(notifications)
    return notification


def update_notification(notification_id: int, updates: Dict):
    """Atualiza um registro de notificação com novos dados."""
    notifications = load_notifications()
    for i, notification in enumerate(notifications):
        if notification.get('id') == notification_id:
            notifications[i].update(updates)
            save_notifications(notifications)
            return notifications[i]
    return None


def add_history_entry(notification_id: int, action: str, user: str, details: str = ""):
    """Adiciona uma entrada ao histórico de uma notificação."""
    notifications = load_notifications()
    for i, notification in enumerate(notifications):
        if notification.get('id') == notification_id:
            if 'history' not in notifications[i] or not isinstance(notifications[i]['history'], list):
                notifications[i]['history'] = []
            notifications[i]['history'].append({
                "action": action,
                "user": user,
                "timestamp": datetime.now().isoformat(),
                "details": details
            })
            save_notifications(notifications)
            return True
    return False


# --- Funções Auxiliares/Utilitárias ---

def get_deadline_status(deadline_date_str: Optional[str], completion_timestamp_str: Optional[str] = None) -> Dict:
    """
    Calcula o status do prazo com base no prazo final e, caso aplicável, também se a notificação foi concluída a tempo.
    Retorna um dicionário com 'text' (status) e 'class' (classe CSS para estilo).
    """
    if not deadline_date_str:
        return {"text": UI_TEXTS.deadline_days_nan, "class": ""}

    try:
        deadline_date = date.fromisoformat(deadline_date_str)

        if completion_timestamp_str:
            # A notificação foi concluída, compare a data de conclusão com o prazo limite
            completion_date = datetime.fromisoformat(completion_timestamp_str).date()
            if completion_date <= deadline_date:
                return {"text": UI_TEXTS.deadline_status_ontrack, "class": "deadline-ontrack"}
            else:
                return {"text": UI_TEXTS.deadline_status_overdue, "class": "deadline-overdue"}
        else:
            # Caso não tenha sido concluída ainda: verificar relação com a data de hoje
            today = date.today()
            days_diff = (deadline_date - today).days

            if days_diff < 0:
                return {"text": UI_TEXTS.deadline_status_overdue, "class": "deadline-overdue"}  # Prazo vencido
            elif days_diff <= 7:
                return {"text": UI_TEXTS.deadline_status_duesoon, "class": "deadline-duesoon"}  # Prazo próximo
            else:
                return {"text": UI_TEXTS.deadline_status_ontrack, "class": "deadline-ontrack"}  # Dentro do prazo
    except ValueError:
        return {"text": UI_TEXTS.text_na, "class": ""}  # Formato inválido de data


def format_date_time_summary(date_val: Any, time_val: Any) -> str:
    """Formata data e hora opcional para exibição."""
    date_part_formatted = UI_TEXTS.text_na
    time_part_formatted = ''

    if isinstance(date_val, date):
        date_part_formatted = date_val.strftime('%d/%m/%Y')
    elif isinstance(date_val, str) and date_val:
        try:
            date_part_formatted = datetime.fromisoformat(date_val).date().strftime('%d/%m/%Y')
        except ValueError:
            date_part_formatted = 'Data inválida'
    elif date_val is None:
        date_part_formatted = 'Não informada'

    if isinstance(time_val, time):
        time_part_formatted = f" às {time_val.strftime('%H:%M')}"
    elif isinstance(time_val, str) and time_val and time_val.lower() != 'none':
        try:
            time_str_part = time_val.split('.')[0]
            try:
                time_obj = datetime.strptime(time_str_part, '%H:%M:%S').time()
            except ValueError:
                try:
                    time_obj = datetime.strptime(time_str_part, '%H:%M').time()
                except ValueError:
                    time_part_formatted = f" às {time_val}"
                    time_obj = None

            if time_obj:
                time_part_formatted = f" às {time_obj.strftime('%H:%M')}"

        except ValueError:
            time_part_formatted = f" às {time_val}"
    elif time_val is None:
        time_part_formatted = ''

    return f"{date_part_formatted}{time_part_formatted}"


def _clear_execution_form_state(notification_id: int):
    """Limpa as chaves do session_state para o formulário de execução após o envio."""
    key_desc = f"exec_action_desc_{notification_id}_refactored"
    key_choice = f"exec_action_choice_{notification_id}_refactored"
    key_evidence_desc = f"exec_evidence_desc_{notification_id}_refactored"
    key_evidence_attachments = f"exec_evidence_attachments_{notification_id}_refactored"

    if key_desc in st.session_state:
        del st.session_state[key_desc]
    if key_choice in st.session_state:
        del st.session_state[key_choice]
    if key_evidence_desc in st.session_state:
        del st.session_state[key_evidence_desc]
    if key_evidence_attachments in st.session_state:
        del st.session_state[key_evidence_attachments]


def _clear_approval_form_state(notification_id: int):
    """Limpa as chaves do session_state para o formulário de aprovação."""
    key_notes = f"approval_notes_{notification_id}_refactored"
    key_decision = f"approval_decision_{notification_id}_refactored"

    if key_notes in st.session_state:
        del st.session_state[key_notes]
    if key_decision in st.session_state:
        del st.session_state[key_decision]


def _reset_form_state():
    """Reinicia as variáveis de estado para o formulário de criação de notificação e outros estados específicos da página."""
    keys_to_clear = [
        'form_step', 'create_form_data',
        'create_title_state_refactored', 'create_location_state_refactored',
        'create_occurrence_date_state_refactored', 'create_event_time_state_refactored',
        'create_reporting_dept_state_refactored', 'create_reporting_dept_comp_state_refactored',
        'create_event_shift_state_refactored', 'create_description_state_refactored',
        'immediate_actions_taken_state_refactored', 'create_immediate_action_desc_state_refactored',
        'patient_involved_state_refactored', 'create_patient_id_state_refactored',
        'create_patient_outcome_obito_state_refactored', 'create_notified_dept_state_refactored',
        'create_notified_dept_comp_state_refactored', 'additional_notes_state_refactored',
        'create_attachments_state_refactored',
        # Dashboard states
        'dashboard_filter_status', 'dashboard_filter_nnc', 'dashboard_filter_priority',
        'dashboard_filter_date_start', 'dashboard_filter_date_end', 'dashboard_search_query',
        'dashboard_sort_column', 'dashboard_sort_ascending', 'dashboard_current_page', 'dashboard_items_per_page'
    ]
    current_keys = set(st.session_state.keys())
    for key in current_keys:
        if key in keys_to_clear:
            st.session_state.pop(key, None)

    st.session_state.form_step = 1
    st.session_state.create_form_data = {
        'title': '', 'location': '', 'occurrence_date': datetime.now().date(),
        'occurrence_time': datetime.now().time(), 'reporting_department': '',
        'reporting_department_complement': '', 'event_shift': UI_TEXTS.selectbox_default_event_shift,
        'description': '',
        'immediate_actions_taken': UI_TEXTS.selectbox_default_immediate_actions_taken,
        'immediate_action_description': '',
        'patient_involved': UI_TEXTS.selectbox_default_patient_involved,
        'patient_id': '',
        'patient_outcome_obito': UI_TEXTS.selectbox_default_patient_outcome_obito,
        'notified_department': '',
        'notified_department_complement': '', 'additional_notes': '', 'attachments': []
    }


# --- Funções de Renderização da Interface (UI) ---

def show_sidebar():
    """Renderiza a barra lateral com navegação e informações do usuário/login."""
    with st.sidebar:
        st.image("logo.png", use_container_width=True)
        st.markdown("<h2 class='sidebar-main-title'>Portal de Notificações</h2>", unsafe_allow_html=True)
        st.markdown("<h3 class='sidebar-subtitle'>Santa Casa de Poços de Caldas</h3>", unsafe_allow_html=True)
        st.markdown("---")

        if st.session_state.authenticated and st.session_state.user:
            st.markdown(f"""
            <div class="user-info">
                <strong>👤 {st.session_state.user.get('name', 'Usuário')}</strong><br>
                <small>{st.session_state.user.get('username', UI_TEXTS.text_na)}</small><br>
                <small>Funções: {', '.join(st.session_state.user.get('roles', [])) or 'Nenhuma'}</small>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("### 📋 Menu Principal")

            if st.button("📝 Nova Notificação", key="nav_create_notif", use_container_width=True):
                st.session_state.page = 'create_notification'
                _reset_form_state()
                if 'initial_classification_state' in st.session_state: st.session_state.pop(
                    'initial_classification_state')
                if 'review_classification_state' in st.session_state: st.session_state.pop(
                    'review_classification_state')
                if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
                    'current_initial_classification_id')
                if 'current_review_classification_id' in st.session_state: st.session_state.pop(
                    'current_review_classification_id')
                st.rerun()

            if st.button("📊 Dashboard de Notificações", key="nav_dashboard", use_container_width=True):
                st.session_state.page = 'dashboard'
                _reset_form_state()
                st.rerun()

            user_roles = st.session_state.user.get('roles', [])

            if 'classificador' in user_roles or 'admin' in user_roles:
                if st.button("🔍 Classificação/Revisão", key="nav_classification",
                             use_container_width=True):
                    st.session_state.page = 'classification'
                    _reset_form_state()
                    if 'initial_classification_state' in st.session_state: st.session_state.pop(
                        'initial_classification_state')
                    if 'review_classification_state' in st.session_state: st.session_state.pop(
                        'review_classification_state')
                    if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
                        'current_initial_classification_id')
                    if 'current_review_classification_id' in st.session_state: st.session_state.pop(
                        'current_review_classification_id')
                    st.rerun()

            if 'executor' in user_roles or 'admin' in user_roles:
                if st.button("⚡ Execução", key="nav_execution", use_container_width=True):
                    st.session_state.page = 'execution'
                    _reset_form_state()
                    if 'initial_classification_state' in st.session_state: st.session_state.pop(
                        'initial_classification_state')
                    if 'review_classification_state' in st.session_state: st.session_state.pop(
                        'review_classification_state')
                    if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
                        'current_initial_classification_id')
                    if 'current_review_classification_id' in st.session_state: st.session_state.pop(
                        'current_review_classification_id')
                    st.rerun()

            if 'aprovador' in user_roles or 'admin' in user_roles:
                if st.button("✅ Aprovação", key="nav_approval", use_container_width=True):
                    st.session_state.page = 'approval'
                    _reset_form_state()
                    if 'initial_classification_state' in st.session_state: st.session_state.pop(
                        'initial_classification_state')
                    if 'review_classification_state' in st.session_state: st.session_state.pop(
                        'review_classification_state')
                    if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
                        'current_initial_classification_id')
                    if 'current_review_classification_id' in st.session_state: st.session_state.pop(
                        'current_review_classification_id')
                    st.rerun()

            if 'admin' in user_roles:
                if st.button("⚙️ Administração", key="nav_admin", use_container_width=True):
                    st.session_state.page = 'admin'
                    _reset_form_state()
                    if 'initial_classification_state' in st.session_state: st.session_state.pop(
                        'initial_classification_state')
                    if 'review_classification_state' in st.session_state: st.session_state.pop(
                        'review_classification_state')
                    if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
                        'current_initial_classification_id')
                    if 'current_review_classification_id' in st.session_state: st.session_state.pop(
                        'current_review_classification_id')
                    st.rerun()

            st.markdown("---")
            if st.button("🚪 Sair", key="nav_logout", use_container_width=True):
                logout_user()
                st.rerun()
        else:
            st.markdown("### 🔐 Login do Operador")
            with st.form("sidebar_login_form"):
                username = st.text_input("Usuário", key="sidebar_username_form")
                password = st.text_input("Senha", type="password", key="sidebar_password_form")
                if st.form_submit_button("🔑 Entrar", use_container_width=True):
                    user = authenticate_user(st.session_state.sidebar_username_form,
                                             st.session_state.sidebar_password_form)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.success(f"Login realizado com sucesso! Bem-vindo, {user.get('name', 'Usuário')}.")
                        st.session_state.pop('sidebar_username_form', None)
                        st.session_state.pop('sidebar_password_form', None)
                        if 'classificador' in user.get('roles', []) or 'admin' in user.get('roles', []):
                            st.session_state.page = 'classification'
                        else:
                            st.session_state.page = 'create_notification'
                        st.rerun()
                    else:
                        st.error("Usuário ou senha inválidos!")
            st.markdown("---")

        st.markdown("""
        <div class="sidebar-footer">
            NotificaSanta v1.0.5<br>
            &copy; 2025 Todos os direitos reservados
        </div>
        """, unsafe_allow_html=True)


def display_notification_full_details(notification: Dict, user_id_logged_in: Optional[int] = None,
                                      user_username_logged_in: Optional[str] = None):
    st.markdown("### 📝 Detalhes da Notificação")
    col_det1, col_det2 = st.columns(2)
    with col_det1:
        st.markdown("**📝 Evento Reportado Original**")
        st.write(f"**Título:** {notification.get('title', UI_TEXTS.text_na)}")
        st.write(f"**Local:** {notification.get('location', UI_TEXTS.text_na)}")
        occurrence_datetime_summary = format_date_time_summary(notification.get('occurrence_date'),
                                                               notification.get('occurrence_time'))
        st.write(f"**Data/Hora Ocorrência:** {occurrence_datetime_summary}")
        st.write(f"**Setor Notificante:** {notification.get('reporting_department', UI_TEXTS.text_na)}")
        if notification.get('immediate_actions_taken') == 'Sim' and notification.get('immediate_action_description'):
            st.write(
                f"**Ações Imediatas Reportadas:** {notification.get('immediate_action_description', UI_TEXTS.text_na)[:100]}...")

    with col_det2:
        st.markdown("**⏱️ Informações de Gestão e Classificação**")
        classif = notification.get('classification', {})
        st.write(f"**Classificação NNC:** {classif.get('nnc', UI_TEXTS.text_na)}")
        if classif.get('nivel_dano'): st.write(f"**Nível de Dano:** {classif.get('nivel_dano', UI_TEXTS.text_na)}")
        st.write(f"**Prioridade:** {classif.get('prioridade', UI_TEXTS.text_na)}")
        st.write(f"**Never Event:** {classif.get('never_event', UI_TEXTS.text_na)}")
        st.write(f"**Evento Sentinela:** {'Sim' if classif.get('is_sentinel_event') else 'Não'}")
        st.write(f"**Tipo Principal:** {classif.get('event_type_main', UI_TEXTS.text_na)}")
        sub_type_display_closed = ''
        if classif.get('event_type_sub'):
            if isinstance(classif['event_type_sub'], list):
                sub_type_display_closed = ', '.join(classif['event_type_sub'])
            else:
                sub_type_display_closed = str(classif['event_type_sub'])
        if sub_type_display_closed: st.write(f"**Especificação:** {sub_type_display_closed}")
        st.write(f"**Classificação OMS:** {', '.join(classif.get('oms', [UI_TEXTS.text_na]))}")
        st.write(f"**Classificado por:** {classif.get('classificador', UI_TEXTS.text_na)}")

        # Exibição do Prazo e Status
        deadline_date_str = classif.get('deadline_date')
        if deadline_date_str:
            deadline_date_formatted = datetime.fromisoformat(deadline_date_str).strftime('%d/%m/%Y')
            deadline_status = get_deadline_status(deadline_date_str)
            st.markdown(
                f"**Prazo de Conclusão:** {deadline_date_formatted} (<span class='{deadline_status['class']}'>{deadline_status['text']}</span>)",
                unsafe_allow_html=True)
        else:
            st.write(f"**Prazo de Conclusão:** {UI_TEXTS.deadline_days_nan}")

    st.markdown("**📝 Descrição Completa do Evento**")
    st.info(notification.get('description', UI_TEXTS.text_na))
    if classif.get('notes'):
        st.markdown("**📋 Orientações / Observações do Classificador**")
        st.success(classif.get('notes', UI_TEXTS.text_na))

    if notification.get('actions'):
        st.markdown("#### ⚡ Histórico de Ações")
        for action in sorted(notification['actions'], key=lambda x: x.get('timestamp', '')):
            action_type = "🏁 CONCLUSÃO (Executor)" if action.get('final_action_by_executor') else "📝 AÇÃO Registrada"
            action_timestamp = action.get('timestamp', UI_TEXTS.text_na)
            if action_timestamp != UI_TEXTS.text_na:
                try:
                    action_timestamp = datetime.fromisoformat(action_timestamp).strftime('%d/%m/%Y %H:%M:%S')
                except ValueError:
                    pass

            if user_id_logged_in and action.get('executor_id') == user_id_logged_in:
                st.markdown(f"""
                <div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px; border-left: 3px solid #4CAF50;'>
                    <strong>{action_type}</strong> - por <strong>VOCÊ ({action.get('executor_name', UI_TEXTS.text_na)})</strong> em {action_timestamp}
                    <br>
                    <em>{action.get('description', UI_TEXTS.text_na)}</em>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='notification-card'>
                    <strong>{action_type}</strong> - por <strong>{action.get('executor_name', UI_TEXTS.text_na)}</strong> em {action_timestamp}
                    <br>
                    <em>{action.get('description', UI_TEXTS.text_na)}</em>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("---")

    if notification.get('review_execution'):
        st.markdown("#### 🛠️ Revisão de Execução")
        review_exec = notification['review_execution']
        st.write(f"**Decisão:** {review_exec.get('decision', UI_TEXTS.text_na)}")
        st.write(f"**Revisado por:** {review_exec.get('reviewed_by', UI_TEXTS.text_na)}")
        st.write(f"**Observações:** {review_exec.get('notes', UI_TEXTS.text_na)}")
        if review_exec.get('rejection_reason'):
            st.write(f"**Motivo Rejeição:** {review_exec.get('rejection_reason', UI_TEXTS.text_na)}")
    if notification.get('approval'):
        st.markdown("#### ✅ Aprovação Final")
        approval_info = notification['approval']
        if user_username_logged_in and (
                approval_info.get('approved_by') or {}) == user_username_logged_in:
            st.markdown(f"""
            <div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px; border-left: 3px solid #4CAF50;'>
                <strong>Decisão:</strong> {approval_info.get('decision', UI_TEXTS.text_na)}
                <br>
                <strong>Aprovado por:</strong> VOCÊ ({approval_info.get('approved_by', UI_TEXTS.text_na)})
                <br>
                <strong>Observações:</strong> {approval_info.get('notes', UI_TEXTS.text_na)}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.write(f"**Decisão:** {approval_info.get('decision', UI_TEXTS.text_na)}")
            st.write(f"**Aprovado por:** {approval_info.get('approved_by', UI_TEXTS.text_na)}")
            st.write(f"**Observações:** {approval_info.get('notes', UI_TEXTS.text_na)}")

    if notification.get('rejection_classification'):
        st.markdown("#### ❌ Rejeição na Classificação Inicial")
        rej_classif = notification['rejection_classification']
        st.write(f"**Motivo:** {rej_classif.get('reason', UI_TEXTS.text_na)}")
        st.write(f"**Rejeitado por:** {rej_classif.get('classified_by', UI_TEXTS.text_na)}")

    if notification.get('rejection_approval'):
        st.markdown("#### ⛔ Reprovação na Aprovação")
        rej_appr = notification['rejection_approval']
        if user_username_logged_in and (rej_appr.get('rejected_by') or {}) == user_username_logged_in:
            st.markdown(f"""
            <div style='background-color: #ffe6e6; padding: 10px; border-radius: 5px; border-left: 3px solid #f44336;'>
                <strong>Motivo:</strong> {rej_appr.get('reason', UI_TEXTS.text_na)}
                <br>
                <strong>Reprovado por:</strong> VOCÊ ({rej_appr.get('rejected_by', UI_TEXTS.text_na)})
            </div>
            """, unsafe_allow_html=True)
        else:
            st.write(f"**Motivo:** {rej_appr.get('reason', UI_TEXTS.text_na)}")
            st.write(f"**Reprovado por:** {rej_appr.get('rejected_by', UI_TEXTS.text_na)}")

    if notification.get('rejection_execution_review'):
        st.markdown("#### 🔄 Execução Rejeitada (Revisão do Classificador)")
        rej_exec_review = notification['rejection_execution_review']
        if user_username_logged_in and (
                rej_exec_review.get('reviewed_by') or {}) == user_username_logged_in:
            st.markdown(f"""
            <div style='background-color: #ffe6e6; padding: 10px; border-radius: 5px; border-left: 3px solid #f44336;'>
                <strong>Motivo:</strong> {rej_exec_review.get('reason', UI_TEXTS.text_na)}
                <br>
                <strong>Rejeitado por:</strong> VOCÊ ({rej_exec_review.get('reviewed_by', UI_TEXTS.text_na)})
            </div>
            """, unsafe_allow_html=True)
        else:
            st.write(f"**Motivo:** {rej_exec_review.get('reason', UI_TEXTS.text_na)}")
            st.write(f"**Rejeitado por:** {rej_exec_review.get('reviewed_by', UI_TEXTS.text_na)}")

    if notification.get('attachments'):
        st.markdown("#### 📎 Anexos")
        for attach_info in notification['attachments']:
            unique_name_to_use = None
            original_name_to_use = None
            if isinstance(attach_info, dict) and 'unique_name' in attach_info and 'original_name' in attach_info:
                unique_name_to_use = attach_info['unique_name']
                original_name_to_use = attach_info['original_name']
            elif isinstance(attach_info, str):
                unique_name_to_use = attach_info
                original_name_to_use = attach_info
            if unique_name_to_use:
                file_content = get_attachment_data(unique_name_to_use)
                if file_content:
                    st.download_button(
                        label=f"Baixar {original_name_to_use}",
                        data=file_content,
                        file_name=original_name_to_use,
                        mime="application/octet-stream",
                        key=f"download_closed_{notification['id']}_{unique_name_to_use}"
                    )
                else:
                    st.write(f"Anexo: {original_name_to_use} (arquivo não encontrado ou corrompido)")

    st.markdown("---")


def show_create_notification():
    """
    Renderiza a página para criar novas notificações como um formulário multi-etapa.
    Controla as etapas usando st.session_state e gerencia a persistência explícita de dados e a validação.
    """
    st.markdown("<h1 class='main-header'>📝 Nova Notificação (Formulário NNC)</h1>", unsafe_allow_html=True)
    if not st.session_state.authenticated:
        st.info("Para acompanhar o fluxo completo de uma notificação (classificação, execução, aprovação), faça login.")

    if 'form_step' not in st.session_state:
        _reset_form_state()

    current_data = st.session_state.create_form_data
    current_step = st.session_state.form_step

    st.markdown(f"### Etapa {current_step}")

    if current_step == 1:
        with st.container():
            st.markdown("""
            <div class="form-section">
                <h3>📋 Etapa 1: Detalhes da Ocorrência</h3>
                <p>Preencha as informações básicas sobre o evento ocorrido.</p>
            </div>
            """, unsafe_allow_html=True)

            current_data['title'] = st.text_input(
                "Título da Notificação*", value=current_data['title'], placeholder="Breve resumo da notificação",
                help="Descreva brevemente o evento ocorrido", key="create_title_state_refactored")
            current_data['location'] = st.text_input(
                "Local do Evento*", value=current_data['location'],
                placeholder="Ex: UTI - Leito 05, Centro Cirúrgico - Sala 3",
                help="Especifique o local exato onde ocorreu o evento", key="create_location_state_refactored")

            col1, col2 = st.columns(2)
            with col1:
                current_data['occurrence_date'] = st.date_input(
                    "Data da Ocorrência do Evento*", value=current_data['occurrence_date'],
                    help="Selecione a data em que o evento ocorreu", key="create_occurrence_date_state_refactored")
            with col2:
                current_data['occurrence_time'] = st.time_input(
                    "Hora Aproximada do Evento", value=current_data['occurrence_time'],
                    help="Hora aproximada em que o evento ocorreu.", key="create_event_time_state_refactored")
            current_data['reporting_department'] = st.selectbox(
                "Setor Notificante*",
                options=FORM_DATA.SETORES,
                index=FORM_DATA.SETORES.index(current_data['reporting_department'])
                if current_data['reporting_department'] in FORM_DATA.SETORES
                else 0,
                help="Selecione o setor responsável por notificar o evento",
                key="create_reporting_dept_state_refactored"
            )
            current_data['reporting_department_complement'] = st.text_input(
                "Complemento do Setor Notificante", value=current_data['reporting_department_complement'],
                placeholder="Informações adicionais do setor (opcional)",
                help="Detalhes adicionais sobre o setor notificante (Ex: Equipe A, Sala 101)",
                key="create_reporting_dept_comp_state_refactored")

            event_shift_options = [UI_TEXTS.selectbox_default_event_shift] + FORM_DATA.turnos
            current_data['event_shift'] = st.selectbox(
                "Turno do Evento*", options=event_shift_options,
                index=event_shift_options.index(current_data['event_shift']) if current_data[
                                                                                    'event_shift'] in event_shift_options else 0,
                help="Turno em que o evento ocorreu", key="create_event_shift_state_refactored")

            current_data['description'] = st.text_area(
                "Descrição Detalhada do Evento*", value=current_data['description'],
                placeholder="Descreva:\n• O que aconteceu?\n• Quando aconteceu?\n• Onde aconteceu?\n• Quem esteve envolvido?\n• Como aconteceu?\n• Consequências observadas",
                height=150,
                help="Forneça uma descrição completa, objetiva e cronológica do evento",
                key="create_description_state_refactored")

            st.markdown("<span class='required-field'>* Campos obrigatórios</span>", unsafe_allow_html=True)
            st.markdown("---")


    elif current_step == 2:
        with st.container():
            st.markdown("""
            <div class="form-section">
                <h3>⚡ Etapa 2: Ações Imediatas</h3>
                <p>Indique se alguma ação foi tomada imediatamente após o evento.</p>
            </div>
            """, unsafe_allow_html=True)

            immediate_actions_taken_options = [UI_TEXTS.selectbox_default_immediate_actions_taken, "Sim", "Não"]
            current_data['immediate_actions_taken'] = st.selectbox(
                "Foram tomadas ações imediatas?*", options=immediate_actions_taken_options,
                index=immediate_actions_taken_options.index(current_data['immediate_actions_taken']) if current_data[
                                                                                                            'immediate_actions_taken'] in immediate_actions_taken_options else 0,
                key="immediate_actions_taken_state_refactored", help="Indique se alguma ação foi tomada...")
            st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)

            if current_data['immediate_actions_taken'] == 'Sim':
                st.markdown("""
                   <div class="conditional-field">
                       <h4>📝 Detalhes das Ações Imediatas</h4>
                       <p>Descreva detalhadamente as ações que foram tomadas.</p>
                   </div>
                   """, unsafe_allow_html=True)
                current_data['immediate_action_description'] = st.text_area(
                    "Descrição detalhada da ação realizada*", value=current_data['immediate_action_description'],
                    placeholder="Descreva:\n• Quais ações foram tomadas?\n• Por quem foram executadas?\n• Quando foram realizadas?\n• Resultados obtidos",
                    height=150,
                    key="create_immediate_action_desc_state_refactored",
                    help="Forneça um relato completo...")
                st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
            else:
                current_data['immediate_action_description'] = ""

            st.markdown("---")

    elif current_step == 3:
        with st.container():
            st.markdown("""
              <div class="form-section">
                  <h3>🏥 Etapa 3: Impacto no Paciente</h3>
                  <p>Indique se o evento teve qualquer tipo de envolvimento ou impacto em um paciente.</p>
              </div>
              """, unsafe_allow_html=True)

            patient_involved_options = [UI_TEXTS.selectbox_default_patient_involved, "Sim", "Não"]
            current_data['patient_involved'] = st.selectbox(
                "O evento atingiu algum paciente?*", options=patient_involved_options,
                index=patient_involved_options.index(current_data[
                                                         'patient_involved']) if current_data[
                                                                                     'patient_involved'] in patient_involved_options else 0,
                key="patient_involved_state_refactored",
                help="Indique se o evento teve qualquer tipo de envolvimento...")
            st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)

            if current_data['patient_involved'] == 'Sim':
                st.markdown("""
                   <div class="conditional-field">
                       <h4>🏥 Informações do Paciente Afetado</h4>
                       <p>Preencha as informações do paciente envolvido no evento.</p>
                   </div>
                   """, unsafe_allow_html=True)
                col5, col6 = st.columns(2)
                with col5:
                    current_data['patient_id'] = st.text_input(
                        "Número do Atendimento/Prontuário*", value=current_data['patient_id'],
                        placeholder="Ex: 123456789", key="create_patient_id_refactored",
                        help="Número de identificação do paciente...")
                with col6:
                    patient_outcome_obito_options = [UI_TEXTS.selectbox_default_patient_outcome_obito, "Sim",
                                                     "Não"]
                    current_data['patient_outcome_obito'] = st.selectbox(
                        "O paciente evoluiu com óbito?*", options=patient_outcome_obito_options,
                        index=patient_outcome_obito_options.index(current_data['patient_outcome_obito']) if
                        current_data['patient_outcome_obito'] in patient_outcome_obito_options else 0,
                        key="create_patient_outcome_obito_refactored",
                        help="Indique se o evento resultou diretamente no óbito do paciente.")
                st.markdown("<span class='required-field'>* Campos obrigatórios</span>", unsafe_allow_html=True)
            else:
                current_data['patient_id'] = ""
                current_data['patient_outcome_obito'] = UI_TEXTS.selectbox_default_patient_outcome_obito

            st.markdown("---")

    elif current_step == 4:
        with st.container():
            st.markdown("""
              <div class="form-section">
                  <h3>📄 Etapa 4: Informações Adicionais e Evidências</h3>
                  <p>Complete as informações adicionais e anexe documentos, se aplicável.</p>
              </div>
              """, unsafe_allow_html=True)

            col7, col8 = st.columns(2)
            with col7:
                current_data['notified_department'] = st.selectbox(
                    "Setor Notificado*",
                    options=FORM_DATA.SETORES,
                    index=FORM_DATA.SETORES.index(current_data['notified_department'])
                    if current_data['notified_department'] in FORM_DATA.SETORES
                    else 0,
                    help="Selecione o setor que será notificado sobre o evento",
                    key="create_notified_dept_refactored"
                )
            with col8:
                current_data['notified_department_complement'] = st.text_input(
                    "Complemento do Setor Notificado", value=current_data['notified_department_complement'],
                    placeholder="Informações adicionais (opcional)",
                    help="Detalhes adicionais sobre o setor notificante (Ex: Equipe A, Sala 101)",
                    key="create_notified_dept_comp_refactored"
                )
            st.markdown("<span class='required-field'>* Campo obrigatório (Setor Notificado)</span>",
                        unsafe_allow_html=True)

            current_data['additional_notes'] = st.text_area(
                "Observações Adicionais", value=current_data['additional_notes'],
                placeholder="Qualquer outra informação que considere relevante.",
                height=100, key="additional_notes_refactored",
                help="Adicione qualquer outra informação relevante...")
            st.markdown("---")

            st.markdown("### 📎 Documentos e Evidências")
            uploaded_files_list_widget = st.file_uploader(
                "Anexar arquivos relacionados ao evento (Opcional)", type=None, accept_multiple_files=True,
                help="Anexe fotos, documentos...", key="create_attachments_refactored"
            )

            current_data['attachments'] = st.session_state.get('create_attachments_refactored', [])

            if current_data.get('attachments'):
                st.info(
                    f"📁 {len(current_data['attachments'])} arquivo(s) selecionado(s): {', '.join([f.name for f in current_data['attachments']])}")

            st.markdown("---")


    elif current_step == 5:
        with st.container():
            st.markdown("""
            <div class="form-section" style="border-left: 4px solid #4caf50;">
                <h3>🎉 Notificação Enviada com Sucesso!</h3>
                <p>Obrigado por registrar o evento. Sua notificação foi encaminhada para a equipe responsável para análise e processamento.</p>
            </div>
            """, unsafe_allow_html=True)
            st.balloons()
            st.markdown("---")

    col_prev, col_cancel_btn, col_next_submit = st.columns(3)

    with col_prev:
        if current_step > 1 and current_step < 5:
            if st.button("◀️ Voltar", key=f"step_back_btn_refactored_{current_step}",
                         use_container_width=True):
                st.session_state.form_step -= 1
                st.rerun()

    with col_cancel_btn:
        if current_step < 5:
            if st.button("🚫 Cancelar Notificação", key="step_cancel_btn_refactored",
                         use_container_width=True):
                _reset_form_state()
                st.rerun()

    with col_next_submit:
        if current_step < 4:
            if st.button(f"➡️ Próximo",
                         key=f"step_next_btn_refactored_{current_step}", use_container_width=True):
                validation_errors = []

                if current_step == 1:
                    if not current_data['title'].strip(): validation_errors.append(
                        'Etapa 1: Título da Notificação é obrigatório.')
                    if not current_data['description'].strip(): validation_errors.append(
                        'Etapa 1: Descrição Detalhada é obrigatória.')
                    if not current_data['location'].strip(): validation_errors.append(
                        'Etapa 1: Local do Evento é obrigatório.')
                    if current_data['occurrence_date'] is None or not isinstance(current_data['occurrence_date'],
                                                                                 date): validation_errors.append(
                        'Etapa 1: Data da Ocorrência é obrigatória.')
                    if not current_data['reporting_department'].strip(): validation_errors.append(
                        'Etapa 1: Setor Notificante é obrigatório.')
                    if current_data['event_shift'] == UI_TEXTS.selectbox_default_event_shift: validation_errors.append(
                        'Etapa 1: Turno do Evento é obrigatório.')

                elif current_step == 2:
                    if current_data[
                        'immediate_actions_taken'] == UI_TEXTS.selectbox_default_immediate_actions_taken: validation_errors.append(
                        'Etapa 2: É obrigatório indicar se foram tomadas Ações Imediatas (Sim/Não).')
                    if current_data['immediate_actions_taken'] == "Sim" and not current_data[
                        'immediate_action_description'].strip(): validation_errors.append(
                        "Etapa 2: Descrição das ações imediatas é obrigatória quando há ações imediatas.")
                elif current_step == 3:
                    if current_data[
                        'patient_involved'] == UI_TEXTS.selectbox_default_patient_involved: validation_errors.append(
                        'Etapa 3: É obrigatório indicar se o Paciente foi Afetado (Sim/Não).')
                    if current_data['patient_involved'] == "Sim":
                        if not current_data['patient_id'].strip(): validation_errors.append(
                            "Etapa 3: Número do Atendimento/Prontuário é obrigatório quando paciente é afetado.")
                        if current_data[
                            'patient_outcome_obito'] == UI_TEXTS.selectbox_default_patient_outcome_obito: validation_errors.append(
                            "Etapa 3: Evolução para óbito é obrigatório quando paciente é afetado.")

                if validation_errors:
                    st.error("⚠️ **Por favor, corrija os seguintes erros:**")
                    for error in validation_errors:
                        st.warning(error)
                else:
                    st.session_state.form_step += 1
                    st.rerun()

        elif current_step == 4:
            with st.form("submit_form_refactored_step4", clear_on_submit=False):
                submit_button = st.form_submit_button("📤 Enviar Notificação", use_container_width=True)

                if submit_button:
                    st.subheader("Validando e Enviando Notificação...")
                    validation_errors = []

                    # Re-valida TODOS os campos obrigatórios de TODAS as etapas (1-4) antes do envio final
                    if not current_data['title'].strip(): validation_errors.append(
                        'Etapa 1: Título da Notificação é obrigatório.')
                    if not current_data['description'].strip(): validation_errors.append(
                        'Etapa 1: Descrição Detalhada é obrigatória.')
                    if not current_data['location'].strip(): validation_errors.append(
                        'Etapa 1: Local do Evento é obrigatório.')
                    if current_data['occurrence_date'] is None or not isinstance(current_data['occurrence_date'],
                                                                                 date): validation_errors.append(
                        'Etapa 1: Data da Ocorrência é obrigatória.')
                    if not current_data['reporting_department']:
                        validation_errors.append("Etapa 1: Setor Notificante é obrigatório.")
                    if current_data['event_shift'] == UI_TEXTS.selectbox_default_event_shift: validation_errors.append(
                        'Etapa 1: Turno do Evento é obrigatório.')
                    if current_data[
                        'immediate_actions_taken'] == UI_TEXTS.selectbox_default_immediate_actions_taken: validation_errors.append(
                        'Etapa 2: É obrigatório indicar se foram tomadas Ações Imediatas (Sim/Não).')
                    if current_data['immediate_actions_taken'] == "Sim" and not current_data[
                        'immediate_action_description'].strip(): validation_errors.append(
                        "Etapa 2: Descrição das ações imediatas é obrigatória quando há ações imediatas.")

                    if current_data[
                        'patient_involved'] == UI_TEXTS.selectbox_default_patient_involved: validation_errors.append(
                        'Etapa 3: É obrigatório indicar se o Paciente foi Afetado (Sim/Não).')
                    if current_data['patient_involved'] == "Sim":
                        if not current_data['patient_id'].strip(): validation_errors.append(
                            "Etapa 3: Número do Atendimento/Prontuário é obrigatório quando paciente é afetado.")
                        if current_data[
                            'patient_outcome_obito'] == UI_TEXTS.selectbox_default_patient_outcome_obito: validation_errors.append(
                            "Etapa 3: Evolução para óbito é obrigatório quando paciente é afetado.")
                    if not current_data['notified_department']:
                        validation_errors.append("Etapa 4: Setor Notificado é obrigatório.")

                    if validation_errors:
                        st.error("⚠️ **Por favor, corrija os seguintes erros antes de enviar:**")
                        for error in validation_errors:
                            st.warning(error)
                    else:
                        notification_data_to_save = current_data.copy()
                        uploaded_files_list = notification_data_to_save.pop('attachments', [])
                        try:
                            notification = create_notification(notification_data_to_save, uploaded_files_list)
                            st.success(f"✅ **Notificação #{notification['id']} criada com sucesso!**")
                            st.info(
                                "📋 Sua notificação foi enviada para classificação e será processada pela equipe responsável.")

                            with st.expander("📄 Resumo da Notificação Enviada", expanded=False):
                                occurrence_datetime_summary = format_date_time_summary(
                                    notification_data_to_save.get('occurrence_date'),
                                    notification_data_to_save.get('occurrence_time')
                                )

                                st.write(f"**ID:** #{notification['id']}")
                                st.write(f"**Título:** {notification_data_to_save.get('title', UI_TEXTS.text_na)}")
                                st.write(f"**Local:** {notification_data_to_save.get('location', UI_TEXTS.text_na)}")
                                st.write(f"**Data/Hora do Evento:** {occurrence_datetime_summary}")
                                st.write(
                                    f"**Turno:** {notification_data_to_save.get('event_shift', UI_TEXTS.text_na)}")
                                reporting_department = notification_data_to_save.get('reporting_department',
                                                                                     UI_TEXTS.text_na)
                                reporting_complement = notification_data_to_save.get('reporting_department_complement')
                                reporting_dept_display = f"{reporting_department}{f' ({reporting_complement})' if reporting_complement else ''}"
                                st.write(f"**Setor Notificante:** {reporting_dept_display}")

                                notified_department = notification_data_to_save.get('notified_department',
                                                                                    UI_TEXTS.text_na)
                                notified_complement = notification_data_to_save.get('notified_department_complement')
                                notified_dept_display = f"{notified_department}{f' ({notified_complement})' if notified_complement else ''}"
                                st.write(f"**Setor Notificado:** {notified_dept_display}")

                                st.write(
                                    f"**Descrição:** {notification_data_to_save.get('description', UI_TEXTS.text_na)[:200]}..." if len(
                                        notification_data_to_save.get('description',
                                                                      '')) > 200 else notification_data_to_save.get(
                                        'description', UI_TEXTS.text_na))
                                st.write(
                                    f"**Ações Imediatas Tomadas:** {notification_data_to_save.get('immediate_actions_taken', UI_TEXTS.text_na)}")
                                if notification_data_to_save.get('immediate_actions_taken') == 'Sim':
                                    st.write(
                                        f"**Descrição Ações Imediatas:** {notification_data_to_save.get('immediate_action_description', UI_TEXTS.text_na)[:200]}..." if len(
                                            notification_data_to_save.get('immediate_action_description',
                                                                          '')) > 200 else notification_data_to_save.get(
                                            'immediate_action_description', UI_TEXTS.text_na))
                                st.write(
                                    f"**Paciente Envolvido:** {notification_data_to_save.get('patient_involved', UI_TEXTS.text_na)}")
                                if notification_data_to_save.get('patient_involved') == 'Sim':
                                    st.write(
                                        f"**N° Atendimento:** {notification_data_to_save.get('patient_id', UI_TEXTS.text_na)}")
                                    outcome_text = 'Sim' if notification_data_to_save.get(
                                        'patient_outcome_obito') is True else 'Não' if notification_data_to_save.get(
                                        'patient_outcome_obito') is False else 'Não informado'
                                    st.write(f"**Evoluiu para óbito:** {outcome_text}")
                                if notification_data_to_save.get('additional_notes'):
                                    st.write(
                                        f"**Observações Adicionais:** {notification_data_to_save.get('additional_notes', UI_TEXTS.text_na)[:200]}..." if len(
                                            notification_data_to_save.get('additional_notes',
                                                                          '')) > 200 else notification_data_to_save.get(
                                            'additional_notes', UI_TEXTS.text_na))
                                if uploaded_files_list:
                                    st.write(
                                        f"**Anexos:** {len(uploaded_files_list)} arquivo(s) - {', '.join([f.name for f in uploaded_files_list])}")
                                else:
                                    st.write("**Anexos:** Nenhum arquivo anexado.")

                            st.session_state.form_step = 5
                            _reset_form_state()
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Ocorreu um erro ao finalizar a notificação: {e}")
                            st.warning("Por favor, revise as informações e tente enviar novamente.")

    if current_step == 5:
        if st.button("➕ Preencher Nova Notificação", key="new_notif_after_submit_btn_refactored",
                     use_container_width=True):
            _reset_form_state()
            st.rerun()


def show_classification():
    """
    Renderiza a página para classificadores realizarem a classificação inicial de novas notificações
    e revisarem a execução das ações concluídas pelas partes responsáveis.
    """
    if not check_permission('classificador'):
        st.error("❌ Acesso negado! Você não tem permissão para classificar notificações.")
        return

    st.markdown("<h1 class='main-header'>🔍 Classificação e Revisão de Notificações</h1>", unsafe_allow_html=True)
    st.info(
        "📋 Nesta área, você pode realizar a classificação inicial de novas notificações e revisar a execução das ações concluídas pelos responsáveis.")

    all_notifications = load_notifications()
    pending_initial_classification = [n for n in all_notifications if n.get('status') == "pendente_classificacao"]
    pending_execution_review = [n for n in all_notifications if n.get('status') == "revisao_classificador_execucao"]
    closed_statuses = ['aprovada', 'rejeitada', 'reprovada', 'concluida']
    closed_notifications = [n for n in all_notifications if n.get('status') in closed_statuses]

    if not pending_initial_classification and not pending_execution_review and not closed_notifications:
        st.info(
            "✅ Não há notificações pendentes de classificação inicial, revisão de execução ou encerradas no momento.")
        return

    tab_initial_classif, tab_review_exec, tab_closed_notifs = st.tabs(
        [f"⏳ Pendentes Classificação Inicial ({len(pending_initial_classification)})",
         f"🛠️ Revisão de Execução Concluída ({len(pending_execution_review)})",
         f"✅ Notificações Encerradas ({len(closed_notifications)})"]
    )

    with tab_initial_classif:
        st.markdown("### Notificações Aguardando Classificação Inicial")

        if not pending_initial_classification:
            st.info("✅ Não há notificações aguardando classificação inicial no momento.")
        else:
            st.markdown("#### 📋 Selecionar Notificação para Classificação Inicial")
            notification_options_initial = [UI_TEXTS.selectbox_default_notification_select] + [
                f"#{n['id']} | Criada em: {n.get('created_at', UI_TEXTS.text_na)[:10]} | {n.get('title', 'Sem título')[:60]}..."
                for n in pending_initial_classification
            ]

            pending_initial_ids_str = ",".join(str(n['id']) for n in pending_initial_classification)
            selectbox_key_initial = f"classify_selectbox_initial_{pending_initial_ids_str}"

            if selectbox_key_initial not in st.session_state or st.session_state[
                selectbox_key_initial] not in notification_options_initial:
                previous_selection = st.session_state.get(selectbox_key_initial, notification_options_initial[0])
                if previous_selection in notification_options_initial:
                    st.session_state[selectbox_key_initial] = previous_selection
                else:
                    st.session_state[selectbox_key_initial] = notification_options_initial[0]

            selected_option_initial = st.selectbox(
                "Escolha uma notificação para analisar e classificar inicial:",
                options=notification_options_initial,
                index=notification_options_initial.index(st.session_state[selectbox_key_initial]),
                key=selectbox_key_initial,
                help="Selecione na lista a notificação pendente que você deseja classificar.")

            notification_id_initial = None
            notification_initial = None

            if selected_option_initial != UI_TEXTS.selectbox_default_notification_select:
                try:
                    parts = selected_option_initial.split('#')
                    if len(parts) > 1:
                        id_part = parts[1].split(' |')[0]
                        notification_id_initial = int(id_part)
                        notification_initial = next(
                            (n for n in all_notifications if n.get('id') == notification_id_initial), None)
                except (IndexError, ValueError):
                    st.error("Erro ao processar a seleção da notificação para classificação inicial.")
                    notification_initial = None

            if notification_id_initial and (
                    st.session_state.get('current_initial_classification_id') != notification_id_initial):
                if 'initial_classification_state' not in st.session_state:
                    st.session_state.initial_classification_state = {}
                st.session_state.initial_classification_state[notification_id_initial] = {
                    'step': 1,
                    'data': {
                        'procede': UI_TEXTS.selectbox_default_procede_classification,
                        'motivo_rejeicao': '',
                        'classificacao_nnc': UI_TEXTS.selectbox_default_classificacao_nnc,
                        'nivel_dano': UI_TEXTS.selectbox_default_nivel_dano,
                        'prioridade_selecionada': UI_TEXTS.selectbox_default_prioridade_resolucao,
                        'never_event_selecionado': UI_TEXTS.text_na,
                        'evento_sentinela_sim_nao': UI_TEXTS.selectbox_default_evento_sentinela,
                        'tipo_evento_principal_selecionado': UI_TEXTS.selectbox_default_tipo_principal,
                        'tipo_evento_sub_selecionado': [],
                        'tipo_evento_sub_texto_livre': '',
                        'classificacao_oms_selecionada': [],
                        'observacoes_classificacao': '',
                        'requires_approval': UI_TEXTS.selectbox_default_requires_approval,
                        'approver_selecionado': UI_TEXTS.selectbox_default_approver,
                        'executores_selecionados': [],
                    }
                }
                st.session_state.current_initial_classification_id = notification_id_initial
                if 'current_review_classification_id' in st.session_state: st.session_state.pop(
                    'current_review_classification_id')

                st.rerun()

            current_classification_state = st.session_state.initial_classification_state.get(notification_id_initial,
                                                                                             {})
            current_step = current_classification_state.get('step', 1)
            current_data = current_classification_state.get('data', {})

            if notification_initial:
                st.markdown(
                    f"### Notificação Selecionada para Classificação Inicial: #{notification_initial.get('id', UI_TEXTS.text_na)}")

                with st.expander(
                        f"📄 Detalhes Reportados Originalmente (Notificação #{notification_initial.get('id', UI_TEXTS.text_na)})",
                        expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📝 Informações Básicas**")
                        st.write(f"**Título:** {notification_initial.get('title', UI_TEXTS.text_na)}")
                        st.write(f"**Local:** {notification_initial.get('location', UI_TEXTS.text_na)}")
                        occurrence_datetime_summary = format_date_time_summary(
                            notification_initial.get('occurrence_date'), notification_initial.get('occurrence_time'))
                        st.write(f"**Data/Hora:** {occurrence_datetime_summary}")
                        st.write(f"**Turno:** {notification_initial.get('event_shift', UI_TEXTS.text_na)}")
                        reporting_department = notification_initial.get('reporting_department', UI_TEXTS.text_na)
                        reporting_complement = notification_initial.get('reporting_department_complement')
                        reporting_dept_display = f"{reporting_department}{f' ({reporting_complement})' if reporting_complement else ''}"
                        st.write(f"**Setor Notificante:** {reporting_dept_display}")
                        if notification_initial.get('immediate_actions_taken') == 'Sim' and notification_initial.get(
                                'immediate_action_description'):
                            st.write(
                                f"**Ações Imediatas Reportadas:** {notification_initial.get('immediate_action_description', UI_TEXTS.text_na)[:100]}...")
                    with col2:
                        st.markdown("**📊 Detalhes de Paciente e Observações Iniciais**")
                        st.write(
                            f"**Paciente Envolvido:** {notification_initial.get('patient_involved', UI_TEXTS.text_na)}")
                        if notification_initial.get('patient_involved') == 'Sim':
                            st.write(f"**Prontuário:** {notification_initial.get('patient_id', UI_TEXTS.text_na)}")
                            outcome = notification_initial.get('patient_outcome_obito')
                            if outcome is True:
                                st.write("**Evoluiu para Óbito:** Sim")
                            elif outcome is False:
                                st.write("**Evoluiu para Óbito:** Não")
                            else:
                                st.write("**Evoluiu para Óbito:** Não informado")
                    st.markdown("**📝 Descrição Detalhada do Evento**")
                    st.info(notification_initial.get('description', UI_TEXTS.text_na))
                    if notification_initial.get('additional_notes'):
                        st.markdown("**ℹ️ Observações Adicionais do Notificante**")
                        st.info(notification_initial.get('additional_notes', UI_TEXTS.text_na))
                    if notification_initial.get('attachments'):
                        st.markdown("**📎 Anexos**")
                        for attach_info in notification_initial['attachments']:
                            unique_name_to_use = None
                            original_name_to_use = None
                            if isinstance(attach_info,
                                          dict) and 'unique_name' in attach_info and 'original_name' in attach_info:
                                unique_name_to_use = attach_info['unique_name']
                                original_name_to_use = attach_info['original_name']
                            elif isinstance(attach_info, str):
                                unique_name_to_use = attach_info
                                original_name_to_use = attach_info

                            if unique_name_to_use:
                                file_content = get_attachment_data(unique_name_to_use)
                                if file_content:
                                    st.download_button(
                                        label=f"Baixar {original_name_to_use}",
                                        data=file_content,
                                        file_name=original_name_to_use,
                                        mime="application/octet-stream",
                                        key=f"download_init_{notification_initial['id']}_{unique_name_to_use}"
                                    )
                                else:
                                    st.write(f"Anexo: {original_name_to_use} (arquivo não encontrado ou corrompido)")
                st.markdown("---")

                # --- Renderiza a etapa atual do formulário de classificação inicial ---
                if current_step == 1:
                    with st.container():
                        st.markdown("""
                             <div class="form-section">
                                 <h3>📋 Etapa 1: Aceite da Notificação</h3>
                                 <p>Analise os detalhes da notificação e decida se ela procede para classificação.</p>
                             </div>
                             """, unsafe_allow_html=True)
                        procede_options = [UI_TEXTS.selectbox_default_procede_classification, "Sim",
                                           "Não"]
                        current_data['procede'] = st.selectbox(
                            "Após análise, a notificação procede e deve ser classificada?*",
                            options=procede_options,
                            index=procede_options.index(
                                current_data.get('procede', UI_TEXTS.selectbox_default_procede_classification)),
                            key=f"procede_select_{notification_id_initial}_step1_initial_refactored",
                            help="Selecione 'Sim' para classificar a notificação ou 'Não' para rejeitá-la.")
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                        if current_data['procede'] == "Não":
                            current_data['motivo_rejeicao'] = st.text_area(
                                "Justificativa para Rejeição*", value=current_data.get('motivo_rejeicao', ''),
                                key=f"motivo_rejeicao_{notification_id_initial}_step1_initial_refactored",
                                help="Explique detalhadamente por que esta notificação será rejeitada.").strip()
                        else:
                            current_data['motivo_rejeicao'] = ""

                elif current_step == 2:
                    with st.container():
                        st.markdown("""
                             <div class="form-section">
                                 <h3>📘 Etapa 2: Classificação NNC, Dano e Prioridade</h3>
                                 <p>Forneça a classificação de Não Conformidade, o nível de dano (se aplicável) e defina a prioridade.</p>
                             </div>
                             """, unsafe_allow_html=True)
                        classificacao_nnc_options = [
                                                        UI_TEXTS.selectbox_default_classificacao_nnc] + FORM_DATA.classificacao_nnc
                        current_data['classificacao_nnc'] = st.selectbox(
                            "Classificação:*", options=classificacao_nnc_options,
                            index=classificacao_nnc_options.index(
                                current_data.get('classificacao_nnc', UI_TEXTS.selectbox_default_classificacao_nnc)),
                            key=f"class_nnc_{notification_id_initial}_step2_initial_refactored",
                            help="Selecione o tipo de classificação principal do evento.")
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                        if current_data['classificacao_nnc'] == "Evento com dano":
                            nivel_dano_options = [UI_TEXTS.selectbox_default_nivel_dano] + FORM_DATA.niveis_dano
                            current_data['nivel_dano'] = st.selectbox(
                                "Nível de Dano ao Paciente:*", options=nivel_dano_options,
                                index=nivel_dano_options.index(
                                    current_data.get('nivel_dano', UI_TEXTS.selectbox_default_nivel_dano)),
                                key=f"dano_nivel_{notification_id_initial}_step2_initial_refactored",
                                help="Selecione o nível de dano ao paciente.")
                            st.markdown(
                                "<span class='required-field'>* Campo obrigatório quando Evento com Dano</span>",
                                unsafe_allow_html=True)
                        else:
                            current_data['nivel_dano'] = UI_TEXTS.selectbox_default_nivel_dano

                        prioridades_options = [UI_TEXTS.selectbox_default_prioridade_resolucao] + FORM_DATA.prioridades
                        current_data['prioridade_selecionada'] = st.selectbox(
                            "Prioridade de Resolução:*", options=prioridades_options,
                            index=prioridades_options.index(
                                current_data.get('prioridade_selecionada',
                                                 UI_TEXTS.selectbox_default_prioridade_resolucao)),
                            key=f"prioridade_select_{notification_id_initial}_step2_initial_refactored",
                            help="Defina a prioridade para investigação e resolução do evento.")
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                elif current_step == 3:
                    with st.container():
                        st.markdown("""
                             <div class="form-section">
                                 <h3>⚠️ Etapa 3: Eventos Especiais (Never Event / Sentinela)</h3>
                                 <p>Identifique se o evento se enquadra em categorias de alta relevância para a segurança do paciente.</p>
                             </div>
                             """, unsafe_allow_html=True)

                        never_event_options = [UI_TEXTS.selectbox_default_never_event] + FORM_DATA.never_events + [
                            UI_TEXTS.text_na]

                        selected_never_event_for_index = current_data.get('never_event_selecionado', UI_TEXTS.text_na)

                        try:
                            default_index = never_event_options.index(selected_never_event_for_index)
                        except ValueError:
                            default_index = 0

                        current_data['never_event_selecionado'] = st.selectbox(
                            "Never Event:*",
                            options=never_event_options,
                            index=default_index,
                            format_func=lambda
                                x: UI_TEXTS.selectbox_never_event_na_text if x == UI_TEXTS.text_na else x,
                            key=f"never_event_select_{notification_id_initial}_step3_initial_refactored",
                            help="Selecione se o evento se enquadra como um Never Event. Utilize 'Selecione uma opção...' caso não se aplique ou não haja um Never Event identificado."
                        )
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                        evento_sentinela_options = [UI_TEXTS.selectbox_default_evento_sentinela, "Sim", "Não"]
                        current_data['evento_sentinela_sim_nao'] = st.selectbox(
                            "Evento Sentinela?*", options=evento_sentinela_options,
                            index=evento_sentinela_options.index(
                                current_data.get('evento_sentinela_sim_nao',
                                                 UI_TEXTS.selectbox_default_evento_sentinela)),
                            key=f"is_sentinel_event_select_{notification_id_initial}_step3_initial_refactored",
                            help="Indique se o evento é considerado um Evento Sentinela.")
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                elif current_step == 4:
                    with st.container():
                        st.markdown("""
                             <div class="form-section">
                                 <h3> categorização do evento (Tipo Principal e Especificação)</h3>
                                 <p>Classifique o evento pelo tipo principal e especifique, se necessário.</p>
                             </div>
                             """, unsafe_allow_html=True)
                        tipo_evento_principal_options = [UI_TEXTS.selectbox_default_tipo_principal] + list(
                            FORM_DATA.tipos_evento_principal.keys())
                        current_data['tipo_evento_principal_selecionado'] = st.selectbox(
                            "Tipo Principal:*", options=tipo_evento_principal_options,
                            index=tipo_evento_principal_options.index(
                                current_data.get('tipo_evento_principal_selecionado',
                                                 UI_TEXTS.selectbox_default_tipo_principal)),
                            key="event_type_main_refactored", help="Classificação do tipo principal de evento.")
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                        sub_options = FORM_DATA.tipos_evento_principal.get(
                            current_data.get('tipo_evento_principal_selecionado'), [])

                        if current_data.get('tipo_evento_principal_selecionado') in ["Clínico", "Não-clínico",
                                                                                     "Ocupacional"] and sub_options:
                            multiselect_display_options = [UI_TEXTS.multiselect_instruction_placeholder] + sub_options
                            default_sub_selection = current_data.get('tipo_evento_sub_selecionado', [])

                            if not default_sub_selection or not any(
                                    item in sub_options for item in default_sub_selection):
                                default_sub_selection = [UI_TEXTS.multiselect_instruction_placeholder]

                            selected_sub_raw = st.multiselect(
                                f"{UI_TEXTS.multiselect_event_spec_label_prefix}{current_data['tipo_evento_principal_selecionado']}{UI_TEXTS.multiselect_event_spec_label_suffix}",
                                options=multiselect_display_options,
                                default=default_sub_selection,
                                key=f"event_type_sub_select_{notification_id_initial}_step4_initial_refactored",
                                help="Selecione as sub-categorias aplicáveis.")

                            current_data['tipo_evento_sub_selecionado'] = [
                                opt for opt in selected_sub_raw if
                                opt != UI_TEXTS.multiselect_instruction_placeholder
                            ]
                            current_data['tipo_evento_sub_texto_livre'] = ""
                        elif current_data.get('tipo_evento_principal_selecionado') in ["Queixa técnica", "Outros"]:
                            label_text = f"Especifique o tipo '{current_data['tipo_evento_principal_selecionado']}'*" if \
                                current_data[
                                    'tipo_evento_principal_selecionado'] == "Outros" else f"Especifique o tipo '{current_data['tipo_evento_principal_selecionado']}':"
                            current_data['tipo_evento_sub_texto_livre'] = st.text_input(
                                label_text, value=current_data.get('tipo_evento_sub_texto_livre', ''),
                                key=f"event_type_sub_text_{notification_id_initial}_step4_initial_refactored",
                                help="Descreva o tipo de evento 'Queixa Técnica' ou 'Outro'.")
                            current_data['tipo_evento_sub_selecionado'] = []
                            if current_data.get('tipo_evento_principal_selecionado') == "Outros":
                                st.markdown(
                                    "<span class='required-field'>* Campo obrigatório quando Tipo Principal é 'Outros'</span>",
                                    unsafe_allow_html=True)
                        else:
                            current_data['tipo_evento_sub_selecionado'] = []
                            current_data['tipo_evento_sub_texto_livre'] = ""

                elif current_step == 5:
                    with st.container():
                        st.markdown("""
                            <div class="form-section">
                                <h3>🌐 Etapa 5: Classificação OMS</h3>
                                <p>Classifique o evento de acordo com a Classificação Internacional de Segurança do Paciente da OMS.</p>
                            </div>
                            """, unsafe_allow_html=True)
                        oms_options = FORM_DATA.classificacao_oms
                        multiselect_display_options = [UI_TEXTS.multiselect_instruction_placeholder] + oms_options
                        default_oms_selection = current_data.get('classificacao_oms_selecionada', [])
                        if not default_oms_selection or not any(item in oms_options for item in default_oms_selection):
                            default_oms_selection = [UI_TEXTS.multiselect_instruction_placeholder]

                        selected_oms_raw = st.multiselect(
                            UI_TEXTS.multiselect_classification_oms_label,
                            options=multiselect_display_options,
                            default=default_oms_selection,
                            key=f"oms_classif_{notification_id_initial}_step5_initial_refactored",
                            help="Selecione um ou mais tipos de incidente da Classificação da OMS.")

                        current_data['classificacao_oms_selecionada'] = [
                            opt for opt in selected_oms_raw if opt != UI_TEXTS.multiselect_instruction_placeholder
                        ]
                        st.markdown("<span class='required-field'>* Campo obrigatório (selecionar ao menos um)</span>",
                                    unsafe_allow_html=True)

                elif current_step == 6:
                    with st.container():
                        st.markdown("""
                             <div class="form-section">
                                 <h3>📄 Etapa 6: Observações da Classificação</h3>
                                 <p>Adicione quaisquer observações relevantes sobre a classificação do evento.</p>
                             </div>
                             """, unsafe_allow_html=True)
                        current_data['observacoes_classificacao'] = st.text_area(
                            "Observações da Classificação (opcional)",
                            value=current_data.get('observacoes_classificacao', ''),
                            key=f"obs_classif_{notification_id_initial}_step6_initial_refactored",
                            help="Adicione observações relevantes sobre a classificação do evento.").strip()

                elif current_step == 7:
                    with st.container():
                        st.markdown("""
                             <div class="form-section">
                                 <h3>👥 Etapa 7: Atribuição e Fluxo Pós-Classificação</h3>
                                 <p>Defina quem será responsável pela execução das ações e se aprovação superior é necessária.</p>
                             </div>
                             """, unsafe_allow_html=True)

                        executors = get_users_by_role('executor')
                        executor_options = {
                            f"{e.get('name', UI_TEXTS.text_na)} ({e.get('username', UI_TEXTS.text_na)})": e['id']
                            for e in
                            executors}

                        executor_display_options = [UI_TEXTS.multiselect_instruction_placeholder] + list(
                            executor_options.keys())
                        default_executor_selection = [
                            name for name, uid in executor_options.items() if
                            uid in current_data.get('executores_selecionados', [])
                        ]

                        if not default_executor_selection or not any(
                                item in list(executor_options.keys()) for item in default_executor_selection):
                            default_executor_selection = [UI_TEXTS.multiselect_instruction_placeholder]
                        selected_executor_names_raw = st.multiselect(
                            UI_TEXTS.multiselect_assign_executors_label,
                            options=executor_display_options,
                            default=default_executor_selection,
                            key=f"executors_multiselect_{notification_id_initial}_step7_initial_refactored",
                            help="Selecione os usuários que serão responsáveis pela execução das ações corretivas/preventivas.")

                        current_data['executores_selecionados'] = [
                            opt for opt in selected_executor_names_raw if
                            opt != UI_TEXTS.multiselect_instruction_placeholder
                        ]

                        st.markdown(
                            "<span class='required-field'>* Campo obrigatório (selecionar ao menos um executor)</span>",
                            unsafe_allow_html=True)
                        st.markdown("---")

                        requires_approval_options = [UI_TEXTS.selectbox_default_requires_approval, "Sim", "Não"]
                        current_data['requires_approval'] = st.selectbox(
                            "Requer Aprovação Superior após Execução?*",
                            options=requires_approval_options,
                            index=requires_approval_options.index(
                                current_data.get('requires_approval', UI_TEXTS.selectbox_default_requires_approval)),
                            key=f"requires_approval_select_{notification_id_initial}_step7_initial_refactored",
                            help="Indique se esta notificação, após o execução das ações, precisa ser aprovada por um usuário com a função 'aprovador'.")
                        st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)

                        approvers = get_users_by_role('aprovador')
                        approver_options = {
                            f"{a.get('name', UI_TEXTS.text_na)} ({a.get('username', UI_TEXTS.text_na)})": a['id']
                            for a in
                            approvers}
                        approver_select_options = [UI_TEXTS.selectbox_default_approver] + list(
                            approver_options.keys())
                        if current_data['requires_approval'] == 'Sim':
                            selected_approver_name = st.selectbox(
                                "Selecionar Aprovador Responsável:*",
                                options=approver_select_options,
                                index=approver_select_options.index(next(
                                    (name for name, uid in approver_options.items() if
                                     uid == current_data.get('approver_selecionado')),
                                    UI_TEXTS.selectbox_default_approver)),
                                key=f"approver_select_{notification_id_initial}_step7_initial_refactored",
                                help="Selecione o usuário 'aprovador' que será responsável pela aprovação final.")
                            current_data['approver_selecionado'] = approver_options.get(selected_approver_name)
                            st.markdown(
                                "<span class='required-field'>* Campo obrigatório quando requer aprovação</span>",
                                unsafe_allow_html=True)
                        else:
                            current_data['approver_selecionado'] = UI_TEXTS.selectbox_default_approver

                        st.markdown("---")
                        st.markdown("#### ✅ Resumo da Classificação Final")
                        st.write(f"**Classificação NNC:** {current_data.get('classificacao_nnc', UI_TEXTS.text_na)}")
                        if current_data.get('classificacao_nnc') == "Evento com dano" and current_data.get(
                                'nivel_dano') != UI_TEXTS.selectbox_default_nivel_dano:
                            st.write(f"**Nível de Dano:** {current_data.get('nivel_dano', UI_TEXTS.text_na)}")
                        st.write(f"**Prioridade:** {current_data.get('prioridade_selecionada', UI_TEXTS.text_na)}")
                        st.write(f"**Never Event:** {current_data.get('never_event_selecionado', UI_TEXTS.text_na)}")
                        st.write(
                            f"**Evento Sentinela:** {'Sim' if current_data.get('evento_sentinela_sim_nao') == 'Sim' else 'Não'}")
                        st.write(
                            f"**Tipo Principal:** {current_data.get('tipo_evento_principal_selecionado', UI_TEXTS.text_na)}")
                        sub_type_display = ''
                        if current_data.get('tipo_evento_sub_selecionado'):
                            sub_type_display = ', '.join(current_data.get('tipo_evento_sub_selecionado'))
                        elif current_data.get('tipo_evento_sub_texto_livre'):
                            sub_type_display = current_data.get('tipo_evento_sub_texto_livre')
                        if sub_type_display:
                            st.write(f"**Especificação:** {sub_type_display}")
                        st.write(
                            f"**Classificação OMS:** {', '.join(current_data.get('classificacao_oms_selecionada', [UI_TEXTS.text_na]))}")
                        st.write(
                            f"**Observações:** {current_data.get('observacoes_classificacao') or UI_TEXTS.text_na}")

                        displayed_executors = [name for name, uid in executor_options.items() if
                                               uid in current_data.get('executores_selecionados', [])]
                        st.write(f"**Executores Atribuídos:** {', '.join(displayed_executors) or 'Nenhum'}")

                        requires_approval_display = current_data.get('requires_approval', UI_TEXTS.text_na)
                        st.write(f"**Requer Aprovação:** {requires_approval_display}")
                        if requires_approval_display == 'Sim':
                            approver_name_display = next((name for name, uid in approver_options.items() if
                                                          uid == current_data.get('approver_selecionado')),
                                                         UI_TEXTS.selectbox_default_approver)
                            st.write(f"**Aprovador Atribuído:** {approver_name_display}")

                col_prev_initial, col_cancel_initial, col_next_submit_initial = st.columns(3)

                with col_prev_initial:
                    if current_step > 1 and current_step <= 7 and current_data.get('procede') != 'Não':
                        if st.button("◀️ Voltar", use_container_width=True,
                                     key=f"back_btn_{notification_id_initial}_step{current_step}_initial_refactored"):
                            current_classification_state['step'] -= 1
                            st.session_state.initial_classification_state[
                                notification_id_initial] = current_classification_state
                            st.rerun()

                with col_cancel_initial:
                    if current_step <= 7:
                        if st.button("🚫 Cancelar Classificação", use_container_width=True,
                                     key=f"cancel_btn_{notification_id_initial}_step{current_step}_initial_refactored"):
                            st.session_state.initial_classification_state.pop(notification_id_initial,
                                                                              None)
                            st.session_state.pop('current_initial_classification_id', None)
                            st.info(f"A classificação inicial da notificação #{notification_id_initial} foi cancelada.")
                            st.rerun()

                with col_next_submit_initial:
                    if current_step < 7 and current_data.get('procede') != 'Não':
                        if st.button(f"➡️ Próximo",
                                     key=f"next_btn_{notification_id_initial}_step{current_step}_initial_refactored",
                                     use_container_width=True):
                            validation_errors = []
                            if current_step == 1:
                                if current_data.get('procede') != 'Sim': validation_errors.append(
                                    'Etapa 1: Para avançar, a notificação deve proceder (selecione \'Sim\').')
                                if current_data.get('procede') == 'Não' and not current_data.get('motivo_rejeicao'):
                                    validation_errors.append("Etapa 1: Justificativa para Rejeição é obrigatória.")
                            elif current_step == 2:
                                if current_data.get(
                                        'classificacao_nnc') == UI_TEXTS.selectbox_default_classificacao_nnc: validation_errors.append(
                                    "Etapa 2: Classificação NNC é obrigatória.")
                                if current_data.get('classificacao_nnc') == "Evento com dano" and current_data.get(
                                        'nivel_dano') == UI_TEXTS.selectbox_default_nivel_dano: validation_errors.append(
                                    "Etapa 2: Nível de dano é obrigatório para evento com dano.")
                                if current_data.get(
                                        'prioridade_selecionada') == UI_TEXTS.selectbox_default_prioridade_resolucao: validation_errors.append(
                                    "Etapa 2: Prioridade de Resolução é obrigatória.")
                            elif current_step == 3:
                                if current_data.get(
                                        'never_event_selecionado') == UI_TEXTS.selectbox_default_never_event: validation_errors.append(
                                    "Etapa 3: Never Event é obrigatório (selecione 'N/A' se não se aplica).")
                                if current_data.get(
                                        'evento_sentinela_sim_nao') == UI_TEXTS.selectbox_default_evento_sentinela: validation_errors.append(
                                    "Etapa 3: Evento Sentinela é obrigatório (Sim/Não).")
                            elif current_step == 4:
                                if current_data.get(
                                        'tipo_evento_principal_selecionado') == UI_TEXTS.selectbox_default_tipo_principal:
                                    validation_errors.append("Etapa 4: Tipo Principal de Evento é obrigatório.")
                                elif current_data.get('tipo_evento_principal_selecionado') in ["Clínico", "Não-clínico",
                                                                                               "Ocupacional"] and not current_data.get(
                                    'tipo_evento_sub_selecionado'):
                                    validation_errors.append(
                                        "Etapa 4: É obrigatório selecionar ao menos uma Especificação do Evento.")
                                elif current_data.get(
                                        'tipo_evento_principal_selecionado') == 'Outros' and not current_data.get(
                                    'tipo_evento_sub_texto_livre'):
                                    validation_errors.append(
                                        "Etapa 4: A especificação do tipo 'Outros' é obrigatória.")
                                elif current_data.get(
                                        'tipo_evento_principal_selecionado') == 'Queixa técnica' and not current_data.get(
                                    'tipo_evento_sub_texto_livre'):
                                    validation_errors.append(
                                        "Etapa 4: A especificação do tipo 'Queixa técnica' é obrigatória.")
                            elif current_step == 5:
                                if not current_data.get('classificacao_oms_selecionada'): validation_errors.append(
                                    "Etapa 5: Classificação OMS é obrigatória (selecione ao menos um item).")

                            if validation_errors:
                                st.error("⚠️ **Por favor, corrija os seguintes erros para avançar:**")
                                for error in validation_errors: st.warning(error)
                            else:
                                current_classification_state['step'] += 1
                                st.session_state.initial_classification_state[
                                    notification_id_initial] = current_classification_state
                                st.rerun()

                    is_final_classification_submit_step_initial = current_step == 7 and current_data.get(
                        'procede') == 'Sim'
                    is_rejection_submit_step_initial = current_step == 1 and current_data.get('procede') == 'Não'
                    if is_final_classification_submit_step_initial or is_rejection_submit_step_initial:
                        with st.form(
                                key=f"final_classification_submit_form_{notification_id_initial}_step{current_step}_initial_refactored",
                                clear_on_submit=False):
                            submit_button_label = "❌ Rejeitar Notificação" if is_rejection_submit_step_initial else "📤 Enviar Classificação Final"
                            submit_final_action = st.form_submit_button(
                                submit_button_label, use_container_width=True
                            )

                            if submit_final_action:
                                st.subheader("Processando sua decisão final...")
                                validation_errors = []

                                if is_rejection_submit_step_initial:
                                    if not current_data.get('motivo_rejeicao'): validation_errors.append(
                                        "Justificativa de rejeição é obrigatória.")
                                elif is_final_classification_submit_step_initial:
                                    if current_data.get('procede') != 'Sim': validation_errors.append(
                                        'Erro interno: Status "procede" inválido para finalização.')
                                    if current_data.get(
                                            'classificacao_nnc') == UI_TEXTS.selectbox_default_classificacao_nnc: validation_errors.append(
                                        "Etapa 2: Classificação NNC é obrigatória.")
                                    if current_data.get('classificacao_nnc') == "Evento com dano" and current_data.get(
                                            'nivel_dano') == UI_TEXTS.selectbox_default_nivel_dano: validation_errors.append(
                                    "Etapa 2: Nível de dano é obrigatório para evento com dano.")
                                    if current_data.get(
                                            'prioridade_selecionada') == UI_TEXTS.selectbox_default_prioridade_resolucao: validation_errors.append(
                                        "Etapa 2: Prioridade de Resolução é obrigatória.")
                                    if current_data.get(
                                            'never_event_selecionado') == UI_TEXTS.selectbox_default_never_event: validation_errors.append(
                                        "Etapa 3: Never Event é obrigatório (selecione 'N/A' se não se aplica).")
                                    if current_data.get(
                                            'evento_sentinela_sim_nao') == UI_TEXTS.selectbox_default_evento_sentinela: validation_errors.append(
                                        "Etapa 3: Evento Sentinela é obrigatório (Sim/Não).")
                                    if current_data.get(
                                            'tipo_evento_principal_selecionado') == UI_TEXTS.selectbox_default_tipo_principal: validation_errors.append(
                                        "Etapa 4: Tipo Principal de Evento é obrigatório.")
                                    if current_data.get('tipo_evento_principal_selecionado') in ["Clínico",
                                                                                                 "Não-clínico",
                                                                                                 "Ocupacional"] and not current_data.get(
                                        'tipo_evento_sub_selecionado'):
                                        validation_errors.append(
                                            "Etapa 4: É obrigatório selecionar ao menos uma Especificação do Evento.")
                                    elif current_data.get(
                                            'tipo_evento_principal_selecionado') == 'Outros' and not current_data.get(
                                        'tipo_evento_sub_texto_livre'):
                                        validation_errors.append(
                                            "Etapa 4: A especificação do tipo 'Outros' é obrigatória.")
                                    elif current_data.get(
                                            'tipo_evento_principal_selecionado') == 'Queixa técnica' and not current_data.get(
                                        'tipo_evento_sub_texto_livre'):
                                        validation_errors.append(
                                            "Etapa 4: A especificação do tipo 'Queixa técnica' é obrigatória.")

                                    if not current_data.get('classificacao_oms_selecionada'): validation_errors.append(
                                        "Etapa 5: Classificação OMS é obrigatória (selecione ao menos um item).")
                                    if not current_data.get('executores_selecionados'): validation_errors.append(
                                        "Etapa 7: É obrigatório atribuir ao menos um Executor Responsável.")
                                    if current_data.get(
                                            'requires_approval') == UI_TEXTS.selectbox_default_requires_approval: validation_errors.append(
                                        "Etapa 7: É obrigatório indicar se requer Aprovação Superior (Sim/Não).")
                                    if current_data.get('requires_approval') == "Sim" and (
                                            current_data.get('approver_selecionado') is None or current_data.get(
                                        'approver_selecionado') == UI_TEXTS.selectbox_default_approver): validation_errors.append(
                                        "Etapa 7: É obrigatório selecionar o Aprovador Responsável quando requer aprovação.")

                                if validation_errors:
                                    st.error("⚠️ **Por favor, corrija os seguintes erros antes de enviar:**")
                                    for error in validation_errors: st.warning(error)
                                else:
                                    user_name = st.session_state.user.get('name', 'Usuário')
                                    user_username = st.session_state.user.get('username', UI_TEXTS.text_na)

                                    if is_rejection_submit_step_initial:
                                        updates = {
                                            "status": "rejeitada",
                                            "classification": None,
                                            "executors": [],
                                            "approver": None,
                                            "rejection_classification": {
                                                "reason": current_data.get('motivo_rejeicao'),
                                                "classified_by": user_username,
                                                "timestamp": datetime.now().isoformat()
                                            }
                                        }
                                        update_notification(notification_id_initial, updates)
                                        add_history_entry(
                                            notification_id_initial, "Notificação rejeitada na Classificação Inicial",
                                            user_name,
                                            f"Motivo da rejeição: {current_data.get('motivo_rejeicao', '')[:200]}..." if len(
                                                current_data.get('motivo_rejeicao',
                                                                 '')) > 200 else f"Motivo da rejeição: {current_data.get('motivo_rejeicao', '')}"
                                        )
                                        st.success(f"✅ Notificação #{notification_id_initial} rejeitada com sucesso!")
                                        st.info(
                                            "Você será redirecionado para a lista atualizada de notificações pendentes.")
                                    elif is_final_classification_submit_step_initial:
                                        # Recalcula executor_options aqui para garantir que esteja atualizado
                                        all_executors_list_for_map = get_users_by_role('executor')
                                        executor_name_to_id_map = {
                                            f"{e.get('name', UI_TEXTS.text_na)} ({e.get('username', UI_TEXTS.text_na)})":
                                                e['id']
                                            for e in all_executors_list_for_map
                                        }

                                        # Converte os nomes dos executores selecionados (strings) de volta para seus IDs (inteiros)
                                        selected_executor_ids_for_db = [
                                            executor_name_to_id_map[name]
                                            for name in current_data.get('executores_selecionados', [])
                                            if name in executor_name_to_id_map  # Garante que o nome exista no mapeamento
                                        ]

                                        # Calcula o prazo
                                        deadline_days = 0
                                        nnc_type = current_data.get('classificacao_nnc')
                                        if nnc_type == "Evento com dano":
                                            dano_level = current_data.get('nivel_dano')
                                            deadline_days = DEADLINE_DAYS_MAPPING[nnc_type].get(dano_level, 0)
                                        else:
                                            deadline_days = DEADLINE_DAYS_MAPPING.get(nnc_type, 0)

                                        # Garante que deadline_days seja um inteiro, padrão para 0 se não encontrado/inválido
                                        if not isinstance(deadline_days, int):
                                            deadline_days = 0  # Padrão para 0 dias se o mapeamento falhar
                                        deadline_date_calculated = (
                                                date.today() + timedelta(days=deadline_days)).isoformat()

                                        classification_data_to_save = {
                                            "nnc": nnc_type,
                                            "nivel_dano": current_data.get(
                                                'nivel_dano') if nnc_type == "Evento com dano" else None,
                                            "prioridade": current_data.get('prioridade_selecionada'),
                                            "never_event": current_data.get('never_event_selecionado'),
                                            "is_sentinel_event": True if current_data.get(
                                                'evento_sentinela_sim_nao') == "Sim" else False if current_data.get(
                                                'evento_sentinela_sim_nao') == "Não" else None,
                                            "oms": current_data.get('classificacao_oms_selecionada'),
                                            "event_type_main": current_data.get('tipo_evento_principal_selecionado'),
                                            "event_type_sub": current_data.get(
                                                'tipo_evento_sub_selecionado') if current_data.get(
                                                'tipo_evento_principal_selecionado') in ["Clínico", "Não-clínico",
                                                                                         "Ocupacional"] else (
                                                [current_data.get('tipo_evento_sub_texto_livre')] if current_data.get(
                                                    'tipo_evento_sub_texto_livre') else []),
                                            "notes": current_data.get('observacoes_classificacao'),
                                            "classificador": user_username,
                                            "classification_timestamp": datetime.now().isoformat(),
                                            "requires_approval": True if current_data.get(
                                                'requires_approval') == "Sim" else False if current_data.get(
                                                'requires_approval') == "Não" else None,
                                            "deadline_date": deadline_date_calculated
                                        }

                                        updates = {
                                            "status": "classificada",
                                            "classification": classification_data_to_save,
                                            "rejection_classification": None,
                                            "executors": selected_executor_ids_for_db,
                                            "approver": current_data.get('approver_selecionado') if current_data.get(
                                                'requires_approval') == 'Sim' else None
                                        }
                                        update_notification(notification_id_initial, updates)

                                        details_hist = f"Classificação NNC: {classification_data_to_save['nnc']}, Prioridade: {classification_data_to_save.get('prioridade', UI_TEXTS.text_na)}"
                                        if classification_data_to_save["nnc"] == "Evento com dano" and \
                                                classification_data_to_save["nivel_dano"]:
                                            details_hist += f", Nível Dano: {classification_data_to_save['nivel_dano']}"
                                        details_hist += f", Never Event: {classification_data_to_save.get('never_event', UI_TEXTS.text_na)}"
                                        details_hist += f", Evento Sentinela: {'Sim' if classification_data_to_save.get('is_sentinel_event') else 'Não'}"
                                        details_hist += f", Tipo Principal: {classification_data_to_save.get('event_type_main', UI_TEXTS.text_na)}"
                                        sub_detail = classification_data_to_save.get('event_type_sub')
                                        if sub_detail:
                                            if isinstance(sub_detail, list):
                                                details_hist += f" ({', '.join(sub_detail)[:100]}...)" if len(
                                                    ', '.join(sub_detail)) > 100 else f" ({', '.join(sub_detail)})"
                                            else:
                                                details_hist += f" ({str(sub_detail)[:100]}...)" if len(
                                                    str(sub_detail)) > 100 else f" ({str(sub_detail)})"
                                        details_hist += f", Requer Aprovação: {'Sim' if classification_data_to_save.get('requires_approval') else 'Não'}"

                                        # Melhoria para exibir nomes de executores no histórico
                                        all_users = load_users()  # Recarrega todos os usuários para ter os nomes
                                        exec_ids_in_updates = updates.get('executors', [])
                                        exec_names_for_history = [
                                            u.get('name', UI_TEXTS.text_na) for u in all_users
                                            if u.get('id') in exec_ids_in_updates
                                        ]
                                        details_hist += f", Executores: {', '.join(exec_names_for_history) or 'Nenhum'}"

                                        if updates.get('approver'):
                                            approvers_list_hist = all_users  # Reutiliza all_users
                                            approver_name_hist = next(
                                                (a.get('name', UI_TEXTS.text_na) for a in approvers_list_hist if
                                                 a.get('id') == updates.get('approver')), UI_TEXTS.text_na)
                                            details_hist += f", Aprovador: {approver_name_hist}"

                                        add_history_entry(
                                            notification_id_initial, "Notificação classificada e atribuída",
                                            user_name, details_hist
                                        )
                                        st.success(
                                            f"✅ Notificação #{notification_id_initial} classificada e atribuída com sucesso!")
                                        st.info(
                                            "A notificação foi movida para a fase de execução e atribuída aos responsáveis.")

                                    st.session_state.initial_classification_state.pop(notification_id_initial,
                                                                                      None)
                                    st.session_state.pop('current_initial_classification_id', None)
                                    st.rerun()

            else:
                if pending_initial_classification:
                    st.info(f"👆 Selecione uma notificação da lista acima para visualizar e iniciar a classificação.")

    with tab_review_exec:
        st.markdown("### Notificações Aguardando Revisão da Execução")

        if not pending_execution_review:
            st.info("✅ Não há notificações aguardando revisão da execução no momento.")
        else:
            st.markdown("#### 📋 Selecionar Notificação para Revisão")
            notification_options_review = [UI_TEXTS.selectbox_default_notification_select] + [
                f"#{n['id']} | Classificada em: {n.get('classification', {}).get('classification_timestamp', UI_TEXTS.text_na)[:10]} | {n.get('title', 'Sem título')[:60]}..."
                for n in pending_execution_review
            ]

            pending_review_ids_str = ",".join(str(n['id']) for n in pending_execution_review)
            selectbox_key_review = f"classify_selectbox_review_{pending_review_ids_str}"

            if selectbox_key_review not in st.session_state or st.session_state[
                selectbox_key_review] not in notification_options_review:
                previous_selection = st.session_state.get(selectbox_key_review, notification_options_review[0])
                if previous_selection in notification_options_review:
                    st.session_state[selectbox_key_review] = previous_selection
                else:
                    st.session_state[selectbox_key_review] = notification_options_review[0]

            selected_option_review = st.selectbox(
                "Escolha uma notificação para revisar a execução:",
                options=notification_options_review,
                index=notification_options_review.index(st.session_state[selectbox_key_review]),
                key=selectbox_key_review,
                help="Selecione na lista a notificação cuja execução você deseja revisar.")

            notification_id_review = None
            notification_review = None

            if selected_option_review != UI_TEXTS.selectbox_default_notification_select:
                try:
                    parts = selected_option_review.split('#')
                    if len(parts) > 1:
                        id_part = parts[1].split(' |')[0]
                        notification_id_review = int(id_part)
                        notification_review = next(
                            (n for n in all_notifications if n.get('id') == notification_id_review), None)
                except (IndexError, ValueError):
                    st.error("Erro ao processar a seleção da notificação para revisão.")
                    notification_review = None

            if notification_id_review and (
                    st.session_state.get('current_review_classification_id') != notification_id_review):
                if 'review_classification_state' not in st.session_state:
                    st.session_state.review_classification_state = {}
                st.session_state.review_classification_state[notification_id_review] = {
                    'decision': UI_TEXTS.selectbox_default_decisao_revisao,
                    'rejection_reason_review': '',
                    'notes': '',
                }
                st.session_state.current_review_classification_id = notification_id_review
                if 'current_initial_classification_id' in st.session_state: st.session_state.pop(
                    'current_initial_classification_id')

                st.rerun()

            current_review_data = st.session_state.review_classification_state.get(notification_id_review or 0, {})

            # Verifica se notification_review existe antes de usá-lo
            if notification_review is not None:
                st.markdown(
                    f"### Notificação Selecionada para Revisão de Execução: #{notification_review.get('id', UI_TEXTS.text_na)}")

                # Obter informações de prazo para o card
                classif_info = notification_review.get('classification', {})
                deadline_date_str = classif_info.get('deadline_date')

                # Acessa 'timestamp' de 'conclusion' de forma segura
                concluded_timestamp_str = (notification_review.get('conclusion') or {}).get('timestamp')

                # Determinar o status do prazo (cor do texto)
                deadline_status = get_deadline_status(deadline_date_str, concluded_timestamp_str)

                # Determinar a classe do cartão (fundo) com APENAS DOIS STATUS
                card_class = ""
                if deadline_status['class'] == "deadline-ontrack" or deadline_status['class'] == "deadline-duesoon":
                    card_class = "card-prazo-dentro"  # Será verde para "No Prazo" e "Prazo Próximo"
                elif deadline_status['class'] == "deadline-overdue":
                    card_class = "card-prazo-fora"  # Será vermelho para "Atrasada"

                # Renderizar o card com o estilo apropriado
                st.markdown(f"""
                <div class="notification-card {card_class}">
                    <h4>#{notification_review.get('id', UI_TEXTS.text_na)} - {notification_review.get('title', UI_TEXTS.text_na)}</h4>
                    <p><strong>Status:</strong> {notification_review.get('status', UI_TEXTS.text_na).replace('_', ' ').title()}</p>
                    <p><strong>Prazo:</strong> {deadline_status['text']}</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("#### 📋 Detalhes para Revisão")
                col_rev1, col_rev2 = st.columns(2)

                with col_rev1:
                    st.markdown("**📝 Evento Reportado Original**")
                    st.write(f"**Título:** {notification_review.get('title', UI_TEXTS.text_na)}")
                    st.write(f"**Local:** {notification_review.get('location', UI_TEXTS.text_na)}")
                    occurrence_datetime_summary = format_date_time_summary(notification_review.get('occurrence_date'),
                                                                           notification_review.get('occurrence_time'))
                    st.write(f"**Data/Hora Ocorrência:** {occurrence_datetime_summary}")
                    st.write(
                        f"**Setor Notificante:** {notification_review.get('reporting_department', UI_TEXTS.text_na)}")
                    if notification_review.get('immediate_actions_taken') == 'Sim' and notification_review.get(
                            'immediate_action_description'):
                        st.write(
                            f"**Ações Imediatas Reportadas:** {notification_review.get('immediate_action_description', UI_TEXTS.text_na)[:100]}...")

                with col_rev2:
                    st.markdown("**⏱️ Informações de Gestão e Classificação**")
                    classif_review = notification_review.get('classification', {})
                    st.write(f"**Classificação NNC:** {classif_review.get('nnc', UI_TEXTS.text_na)}")
                    if classif_review.get('nivel_dano'): st.write(
                        f"**Nível de Dano:** {classif_review.get('nivel_dano', UI_TEXTS.text_na)}")
                    st.write(f"**Prioridade:** {classif_review.get('prioridade', UI_TEXTS.text_na)}")
                    st.write(f"**Never Event:** {classif_review.get('never_event', UI_TEXTS.text_na)}")
                    st.write(f"**Evento Sentinela:** {'Sim' if classif_review.get('is_sentinel_event') else 'Não'}")
                    st.write(f"**Tipo Principal:** {classif_review.get('event_type_main', UI_TEXTS.text_na)}")
                    sub_type_display_review = ''
                    if classif_review.get('event_type_sub'):
                        if isinstance(classif_review['event_type_sub'], list):
                            sub_type_display_review = ', '.join(classif_review['event_type_sub'])
                        else:
                            sub_type_display_review = str(classif_review['event_type_sub'])
                    if sub_type_display_review: st.write(f"**Especificação:** {sub_type_display_review}")
                    st.write(f"**Classificação OMS:** {', '.join(classif_review.get('oms', [UI_TEXTS.text_na]))}")
                    st.write(
                        f"**Requer Aprovação Superior (Classif. Inicial):** {'Sim' if classif_review.get('requires_approval') else 'Não'}")
                    st.write(f"**Classificado por:** {classif_review.get('classificador', UI_TEXTS.text_na)}")

                    # Exibição do Prazo e Status na Revisão
                    if deadline_date_str:
                        deadline_date_formatted = datetime.fromisoformat(deadline_date_str).strftime('%d/%m/%Y')
                        st.markdown(
                            f"**Prazo de Conclusão:** {deadline_date_formatted} (<span class='{deadline_status['class']}'>{deadline_status['text']}</span>)",
                            unsafe_allow_html=True)
                    else:
                        st.write(f"**Prazo de Conclusão:** {UI_TEXTS.deadline_days_nan}")

                st.markdown("---")
                st.markdown("#### ⚡ Ações Executadas pelos Responsáveis")
                if notification_review.get('actions'):
                    for action in sorted(notification_review['actions'], key=lambda x: x.get('timestamp', '')):
                        action_type = "🏁 CONCLUSÃO (Executor)" if action.get(
                            'final_action_by_executor') else "📝 AÇÃO Registrada"
                        action_timestamp = action.get('timestamp', UI_TEXTS.text_na)
                        if action_timestamp != UI_TEXTS.text_na:
                            try:
                                action_timestamp = datetime.fromisoformat(action_timestamp).strftime(
                                    '%d/%m/%Y %H:%M:%S')
                            except ValueError:
                                pass
                        st.markdown(f"""
                                   <strong>{action_type}</strong> - por <strong>{action.get('executor_name', UI_TEXTS.text_na)}</strong> em {action_timestamp}
                                   <br>
                                   <em>{action.get('description', UI_TEXTS.text_na)}</em>
                                   """, unsafe_allow_html=True)
                        st.markdown("---")
                else:
                    st.warning("⚠️ Nenhuma ação foi registrada pelos executores para esta notificação ainda.")

                users_review = get_users_by_role('executor')  # Pega usuários com a role de executor
                # Mapeia nomes de exibição para IDs de usuário para executores
                executor_name_to_id_map_review = {
                    f"{u.get('name', UI_TEXTS.text_na)} ({u.get('username', UI_TEXTS.text_na)})": u['id']
                    for u in users_review
                }
                # Pega os nomes de exibição dos executores atribuídos
                executor_names_review = [
                    name for name, uid in executor_name_to_id_map_review.items()
                    if uid in notification_review.get('executors', [])
                ]
                st.markdown(
                    f"**👥 Executores Atribuídos Originalmente:** {', '.join(executor_names_review) or 'Nenhum'}")
                if notification_review.get('attachments'):
                    st.markdown("---")
                    st.markdown("#### 📎 Anexos")
                    for attach_info in notification_review['attachments']:
                        unique_name_to_use = None
                        original_name_to_use = None
                        if isinstance(attach_info,
                                      dict) and 'unique_name' in attach_info and 'original_name' in attach_info:
                            unique_name_to_use = attach_info['unique_name']
                            original_name_to_use = attach_info['original_name']
                        elif isinstance(attach_info, str):
                            unique_name_to_use = attach_info
                            original_name_to_use = attach_info

                        if unique_name_to_use:
                            file_content = get_attachment_data(unique_name_to_use)
                            if file_content:
                                st.download_button(
                                    label=f"Baixar {original_name_to_use}",
                                    data=file_content,
                                    file_name=original_name_to_use,
                                    mime="application/octet-stream",
                                    key=f"download_review_{notification_review['id']}_{unique_name_to_use}"
                                )
                            else:
                                st.write(f"Anexo: {original_name_to_use} (arquivo não encontrado ou corrompido)")
                st.markdown("---")

                with st.form(key=f"review_decision_form_{notification_id_review}_refactored", clear_on_submit=False):
                    st.markdown("### 🎯 Decisão de Revisão da Execução")

                    decision_options = [UI_TEXTS.selectbox_default_decisao_revisao, "Aceitar Conclusão",
                                        "Rejeitar Conclusão"]
                    current_review_data['decision'] = st.selectbox(
                        "Decisão:*", options=decision_options,
                        index=decision_options.index(
                            current_review_data.get('decision', UI_TEXTS.selectbox_default_decisao_revisao)),
                        key=f"review_decision_{notification_id_review}_refactored",
                        help="Selecione 'Aceitar Conclusão' se a execução foi satisfatória ou 'Rejeitar Conclusão' para devolvê-la para correção/revisão.")
                    st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)
                    if current_review_data['decision'] == "Rejeitar Conclusão":
                        st.markdown("""
                           <div class="conditional-field">
                               <h4>📝 Detalhes da Rejeição</h4>
                               <p>Explique por que a execução foi rejeitada e o que precisa ser feito.</p>
                           </div>
                           """, unsafe_allow_html=True)
                        current_review_data['rejection_reason_review'] = st.text_area(
                            "Justificativa para Rejeição da Conclusão*",
                            value=current_review_data.get('rejection_reason_review', ''),
                            key=f"rejection_reason_review_{notification_id_review}_refactored",
                            help="Descreva os motivos da rejeição e as ações corretivas necessárias.").strip()
                        st.markdown("<span class='required-field'>* Campo obrigatório ao rejeitar</span>",
                                    unsafe_allow_html=True)
                    else:
                        current_review_data['rejection_reason_review'] = ""

                    current_review_data['notes'] = st.text_area(
                        "Observações da Revisão (opcional)",
                        value=current_review_data.get('notes', ''),
                        key=f"review_notes_{notification_id_review}_refactored",
                        help="Adicione quaisquer observações relevantes sobre a revisão da execução.").strip()

                    submit_button_review = st.form_submit_button("✔️ Confirmar Decisão",
                                                                 use_container_width=True)

                    if submit_button_review:
                        validation_errors = []
                        if current_review_data[
                            'decision'] == UI_TEXTS.selectbox_default_decisao_revisao: validation_errors.append(
                            "É obrigatório selecionar a decisão da revisão (Aceitar/Rejeitar).")
                        if current_review_data['decision'] == "Rejeitar Conclusão" and not current_review_data.get(
                                'rejection_reason_review'): validation_errors.append(
                            "Justificativa para Rejeição da Conclusão é obrigatória.")
                        if validation_errors:
                            st.error("⚠️ **Por favor, corrija os seguintes erros antes de enviar:**")
                            for error in validation_errors: st.warning(error)
                        else:
                            user_name = st.session_state.user.get('name', 'Usuário')
                            user_username = st.session_state.user.get('username', UI_TEXTS.text_na)
                            review_notes = current_review_data.get('notes')

                            review_details_to_save = {
                                'decision': review_decision_state.replace(' Conclusão', ''),
                                'reviewed_by': user_username,
                                'timestamp': datetime.now().isoformat(),
                                'notes': review_notes or None
                            }
                            if review_decision_state == "Rejeitar Conclusão":
                                review_details_to_save['rejection_reason'] = current_review_data.get(
                                    'rejection_reason_review')

                            updates = {'review_execution': review_details_to_save}

                            if review_decision_state == "Aceitar Conclusão":
                                original_classification = notification_review.get('classification', {})
                                requires_approval_after_execution = original_classification.get('requires_approval')
                                if requires_approval_after_execution is True:
                                    new_status = 'aguardando_aprovacao'
                                    updates['status'] = new_status

                                    add_history_entry(
                                        notification_id_review, "Revisão de Execução: Conclusão Aceita",
                                        user_name,
                                        f"Execução aceita pelo classificador. Encaminhada para aprovação superior." + (
                                            f" Obs: {review_notes}" if review_notes else ""))
                                    st.success(
                                        f"✅ Execução da Notificação #{notification_id_review} aceita! Encaminhada para aprovação superior.")
                                else:
                                    new_status = 'aprovada'
                                    updates['status'] = new_status
                                    updates['conclusion'] = {
                                        'concluded_by': user_username,
                                        'notes': review_notes or "Execução revisada e aceita pelo classificador.",
                                        'timestamp': datetime.now().isoformat(),
                                        'status_final': 'aprovada'
                                    },
                                    'approver': None
                                }
                                update_notification(notification_id_review, updates)

                                add_history_entry(
                                    notification_id_review, "Revisão de Execução: Conclusão Aceita e Finalizada",
                                    user_name,
                                    f"Execução revisada e aceita pelo classificador. Ciclo de gestão do evento concluído (não requeria aprovação superior)." + (
                                        f" Obs: {review_notes}" if review_notes else ""))
                                st.success(
                                    f"✅ Execução da Notificação #{notification_id_review} revisada e aceita. Notificação concluída!")
                            elif review_decision_state == "Rejeitar Conclusão":
                                new_status = 'pendente_classificacao'

                                updates = {
                                    'status': new_status,
                                    'approver': None,
                                    'executors': [],
                                    'classification': None,
                                    'review_execution': None,
                                    'approval': None,
                                    'conclusion': None,
                                    'rejection_execution_review': {
                                        'reason': current_review_data.get('rejection_reason_review'),
                                        'reviewed_by': user_username,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                }
                                update_notification(notification_id_review, updates)

                                add_history_entry(
                                    notification_id_review,
                                    "Revisão de Execução: Conclusão Rejeitada e Reclassificação Necessária",
                                    user_name,
                                    f"Execução rejeitada. Notificação movida para classificação inicial para reanálise e reatribuição. Motivo: {current_review_data.get('rejection_reason_review', '')[:150]}..." if len(
                                        current_review_data.get('rejection_reason_review',
                                                                '')) > 150 else f"Execução rejeitada. Notificação movida para classificação inicial para reanálise e reatribuição. Motivo: {current_review_data.get('rejection_reason_review', '')}" + (
                                        f" Obs: {review_notes}" if review_notes else ""))
                                st.warning(
                                    f"⚠️ Execução da Notificação #{notification_id_review} rejeitada! Devolvida para classificação inicial para reanálise e reatribuição.")
                                st.info(
                                    "A notificação foi movida para o status 'pendente_classificacao' e aparecerá na aba 'Pendentes Classificação Inicial' para que a equipe de classificação possa reclassificá-la e redefinir o fluxo.")
                            update_notification(notification_id_review, updates)
                            st.session_state.review_classification_state.pop(notification_id_review, None)
                            st.session_state.pop('current_review_classification_id', None)
                            st.rerun()
            else:
                if pending_execution_review:
                    st.info(f"👆 Selecione uma notificação da lista acima para revisar a execução concluída.")

    with tab_closed_notifs:
        st.markdown("### Notificações Encerradas")

        if not closed_notifications:
            st.info("✅ Não há notificações encerradas no momento.")
        else:
            st.info(f"Total de notificações encerradas: {len(closed_notifications)}.")

            search_query = st.text_input(
                "🔎 Buscar Notificação Encerrada (Título, Descrição, ID):",
                key="closed_notif_search_input",
                placeholder="Ex: 'queda paciente', '12345', 'medicamento errado'"
            ).lower()

            filtered_closed_notifications = []
            if search_query:
                for notif in closed_notifications:
                    if search_query.isdigit() and int(search_query) == notif.get('id'):
                        filtered_closed_notifications.append(notif)
                    elif (search_query in notif.get('title', '').lower() or
                          search_query in notif.get('description', '').lower()):
                        filtered_closed_notifications.append(notif)
            else:
                filtered_closed_notifications = closed_notifications

            if not filtered_closed_notifications:
                st.warning(
                    "⚠️ Nenhuma notificação encontrada com os critérios de busca especificados.")
            else:
                filtered_closed_notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)

                st.markdown(f"**Notificações Encontradas ({len(filtered_closed_notifications)})**:")
                for notification in filtered_closed_notifications:
                    status_class = f"status-{notification.get('status', UI_TEXTS.text_na).replace('_', '-')}"
                    created_at_str = notification.get('created_at', UI_TEXTS.text_na)
                    if created_at_str != UI_TEXTS.text_na:
                        try:
                            created_at_str = datetime.fromisoformat(created_at_str).strftime('%d/%m/%Y %H:%M:%S')
                        except ValueError:
                            pass

                    concluded_by = UI_TEXTS.text_na
                    if notification.get('conclusion') and notification['conclusion'].get('concluded_by'):
                        concluded_by = notification['conclusion']['concluded_by']
                    elif notification.get('approval') and (notification.get('approval') or {}).get('approved_by'):
                        concluded_by = (notification.get('approval') or {}).get('approved_by')
                    elif notification.get('rejection_classification') and (
                            notification.get('rejection_classification') or {}).get('classified_by'):
                        concluded_by = (notification.get('rejection_classification') or {}).get('classified_by')
                    elif notification.get('rejection_approval') and (notification.get('rejection_approval') or {}).get(
                            'rejected_by'):
                        concluded_by = (notification.get('rejection_approval') or {}).get('rejected_by')

                    # Determinar o status do prazo para notificações encerradas
                    classif_info = notification.get('classification', {})
                    deadline_date_str = classif_info.get('deadline_date')

                    # Acessa 'timestamp' de 'conclusion' de forma segura
                    concluded_timestamp_str = (notification.get('conclusion') or {}).get('timestamp')

                    # Verificar se a conclusão foi dentro ou fora do prazo
                    deadline_status = get_deadline_status(deadline_date_str, concluded_timestamp_str)
                    card_class = ""
                    if deadline_status['class'] == "deadline-ontrack" or deadline_status['class'] == "deadline-duesoon":
                        card_class = "card-prazo-dentro"
                    elif deadline_status['class'] == "deadline-overdue":
                        card_class = "card-prazo-fora"

                    st.markdown(f"""
                            <div class="notification-card {card_class}">
                                <h4>#{notification.get('id', UI_TEXTS.text_na)} - {notification.get('title', UI_TEXTS.text_na)}</h4>
                                <p><strong>Status Final:</strong> <span class="{status_class}">{notification.get('status', UI_TEXTS.text_na).replace('_', ' ').title()}</span></p>
                                <p><strong>Encerrada por:</strong> {concluded_by} | <strong>Data de Criação:</strong> {created_at_str}</p>
                                <p><strong>Prazo:</strong> {deadline_status['text']}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    with st.expander(
                            f"👁️ Visualizar Detalhes - Notificação #{notification.get('id', UI_TEXTS.text_na)}"):
                        display_notification_full_details(notification, st.session_state.user.get('id'),
                                                          st.session_state.user.get('username'))


def show_execution():
    """Renderiza a página para executores visualizarem notificações atribuídas e registrarem ações."""
    if not check_permission('executor'):
        st.error("❌ Acesso negado! Você não tem permissão para executar notificações.")
        return

    st.markdown("<h1 class='main-header'>⚡ Execução de Notificações</h1>", unsafe_allow_html=True)
    st.info(
        "Nesta página, você pode visualizar as notificações atribuídas a você, registrar as ações executadas e marcar sua parte como concluída.")

    # Carrega todas as notificações uma única vez no início da função
    all_notifications = load_notifications()
    user_id_logged_in = st.session_state.user.get('id')
    user_username_logged_in = st.session_state.user.get('username')

    all_users = load_users()
    display_name_to_id_map = {
        f"{user.get('name', UI_TEXTS.text_na)} ({user.get('username', UI_TEXTS.text_na)})": user['id']
        for user in all_users
    }

    user_active_notifications = []
    active_execution_statuses = ['classificada', 'em_execucao']
    for notification in all_notifications:
        is_assigned_to_current_user = False
        assigned_executors_raw = notification.get('executors', [])

        for executor_entry in assigned_executors_raw:
            if isinstance(executor_entry, int) and executor_entry == user_id_logged_in:
                is_assigned_to_current_user = True
                break
            elif isinstance(executor_entry, str):
                resolved_id = display_name_to_id_map.get(executor_entry)
                if resolved_id == user_id_logged_in:
                    is_assigned_to_current_user = True
                    break

        if is_assigned_to_current_user and notification.get('status') in active_execution_statuses:
            user_active_notifications.append(notification)

    closed_statuses = ['aprovada', 'rejeitada', 'reprovada', 'concluida']
    closed_my_exec_notifications = [
        n for n in all_notifications
        if n.get('status') in closed_statuses and user_id_logged_in in n.get('executors', [])
    ]

    if not user_active_notifications and not closed_my_exec_notifications:
        st.info("✅ Não há notificações ativas atribuídas a você no momento. Verifique com seu gestor ou classificador.")
        return

    st.success(f"Você tem {len(user_active_notifications)} notificação(es) atribuída(s) aguardando ou em execução.")

    tab_active_notifications, tab_closed_my_exec_notifs = st.tabs(
        ["🔄 Notificações Atribuídas (Ativas)", f"✅ Minhas Ações Encerradas ({len(closed_my_exec_notifications)})"]
    )

    with tab_active_notifications:
        st.markdown("### Notificações Aguardando ou Em Execução")
        priority_order = {p: i for i, p in enumerate(FORM_DATA.prioridades)}
        user_active_notifications.sort(key=lambda x: (
            priority_order.get(x.get('classification', {}).get('prioridade', 'Baixa'), len(FORM_DATA.prioridades)),
            datetime.fromisoformat(x.get('created_at', '1900-01-01T00:00:00')).timestamp()
        ))

        for notification in user_active_notifications:
            status_class = f"status-{notification.get('status', UI_TEXTS.text_na).replace('_', '-')}"
            classif_info = notification.get('classification', {})
            prioridade_display = classif_info.get('prioridade', UI_TEXTS.text_na)
            prioridade_display = prioridade_display if prioridade_display != 'Selecionar' else f"{UI_TEXTS.text_na} (Não Classificado)"

            deadline_date_str = classif_info.get('deadline_date')
            # Pega o timestamp de conclusão para calcular o status do prazo com base na conclusão, se houver
            concluded_timestamp_str = (notification.get('conclusion') or {}).get('timestamp')

            deadline_status = get_deadline_status(deadline_date_str, concluded_timestamp_str)

            # Determinar a classe do cartão (fundo) com APENAS DOIS STATUS: Dentro do Prazo ou Fora do Prazo
            card_class = ""
            if deadline_status['class'] == "deadline-ontrack" or deadline_status['class'] == "deadline-duesoon":
                card_class = "card-prazo-dentro"  # Será verde para "No Prazo" e "Prazo Próximo"
            elif deadline_status['class'] == "deadline-overdue":
                card_class = "card-prazo-fora"  # Será vermelho para "Atrasada"

            st.markdown(f"""
                    <div class="notification-card {card_class}">
                        <h4>#{notification.get('id', UI_TEXTS.text_na)} - {notification.get('title', UI_TEXTS.text_na)}</h4>
                        <p><strong>Status Atual:</strong> <span class="{status_class}">{notification.get('status', UI_TEXTS.text_na).replace('_', ' ').title()}</span></p>
                        <p><strong>Local do Evento:</strong> {notification.get('location', UI_TEXTS.text_na)} | <strong>Prioridade:</strong> {prioridade_display} <strong class='{deadline_status['class']}'>Prazo: {deadline_status['text']}</strong></p>
                    </div>
                    """, unsafe_allow_html=True)

            executor_has_already_concluded_their_part = False
            if user_id_logged_in:
                for action_entry in notification.get('actions', []):
                    if action_entry.get('executor_id') == user_id_logged_in and action_entry.get(
                            'final_action_by_executor') == True:
                        executor_has_already_concluded_their_part = True
                        break

            if executor_has_already_concluded_their_part:
                st.info(
                    f"✅ Sua parte na execução da Notificação #{notification.get('id')} já foi concluída. Você não pode adicionar mais ações para esta notificação.")
            else:
                with st.form(f"action_form_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                             clear_on_submit=False):
                    st.markdown("### 📝 Registrar Ação Executada ou Concluir Sua Parte")
                    action_type_choice_options = [UI_TEXTS.selectbox_default_acao_realizar, "Registrar Ação",
                                                  "Concluir Minha Parte"]
                    action_type_choice_state = st.selectbox(
                        "Qual ação deseja realizar?*", options=action_type_choice_options,
                        key=f"exec_action_choice_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                        index=action_type_choice_options.index(
                            st.session_state.get(
                                f"exec_action_choice_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                                UI_TEXTS.selectbox_default_acao_realizar)),
                        help="Selecione 'Registrar Ação' para adicionar um passo ao histórico ou 'Concluir Minha Parte' para finalizar sua execução."
                    )
                    st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)

                    action_description_state = st.text_area(
                        "Descrição detalhada da ação realizada*",
                        value=st.session_state.get(
                            f"exec_action_desc_{notification.get('id', UI_TEXTS.text_na)}_refactored", ""),
                        placeholder="Descreva:\n• O QUÊ foi feito?\n• POR QUÊ foi feito (qual o objetivo)?\n• ONDE foi realizado?\n• QUANDO foi realizado (data/hora)?\n• QUEM executou (se aplicável)?\n• COMO foi executado (passos, métodos)?\n• QUANTO CUSTOU (recursos, tempo)?\n• QUÃO FREQUENTE (se for uma ação contínua)?",
                        height=180,
                        key=f"exec_action_desc_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                        help="Forneça um relato completo e estruturado da ação executada ou da conclusão da sua parte, utilizando os pontos do 5W3H como guia."
                    ).strip()

                    # Novos campos para "Concluir Minha Parte" - inicialmente vazios
                    evidence_description_state = ""
                    uploaded_evidence_files = []

                    if action_type_choice_state == "Concluir Minha Parte":
                        st.markdown("""
                           <div class="conditional-field">
                               <h4>✅ Evidências da Tratativa</h4>
                               <p>Descreva e anexe as evidências da tratativa realizada para esta notificação.</p>
                           </div>
                           """, unsafe_allow_html=True)
                        evidence_description_state = st.text_area(
                            "Descrição da Evidência (Opcional)",
                            value=st.session_state.get(
                                f"exec_evidence_desc_{notification.get('id', UI_TEXTS.text_na)}_refactored", ""),
                            placeholder="Descreva o resultado da tratativa, evidências de conclusão, etc.",
                            height=100,
                            key=f"exec_evidence_desc_{notification.get('id', UI_TEXTS.text_na)}_refactored"
                        ).strip()

                        uploaded_evidence_files = st.file_uploader(
                            "Anexar arquivos de Evidência (Opcional)", type=None, accept_multiple_files=True,
                            key=f"exec_evidence_attachments_{notification.get('id', UI_TEXTS.text_na)}_refactored"
                        )

                    submit_button = st.form_submit_button("✔️ Confirmar Ação",
                                                          use_container_width=True)
                    st.markdown("---")

                    if submit_button:
                        validation_errors = []
                        if action_type_choice_state == UI_TEXTS.selectbox_default_acao_realizar:
                            validation_errors.append("É obrigatório selecionar o tipo de ação (Registrar ou Concluir).")
                        if not action_description_state:
                            validation_errors.append("A descrição detalhada da ação é obrigatória.")

                        if validation_errors:
                            st.error("⚠️ **Por favor, corrija os seguintes erros:**")
                            for error in validation_errors: st.warning(error)
                        else:
                            # Encontra a notificação na lista principal de notificações
                            current_notification_in_list = next(
                                (n for n in all_notifications if n.get('id') == notification.get('id')), None)

                            # Se por algum motivo a notificação não for encontrada (deveria sempre ser),
                            # evita um erro e aborta.
                            if not current_notification_in_list:
                                st.error(
                                    "Erro interno: Notificação não encontrada na lista principal para atualização.")
                            else:
                                # Re-verifica se o executor já concluiu sua parte antes de processar
                                recheck_executor_already_concluded = False
                                for existing_action_recheck in current_notification_in_list.get('actions', []):
                                    if existing_action_recheck.get(
                                            'executor_id') == user_id_logged_in and existing_action_recheck.get(
                                        'final_action_by_executor') == True:
                                        recheck_executor_already_concluded = True
                                        break

                                if recheck_executor_already_concluded:
                                    st.error(
                                        "❌ Sua parte nesta notificação já foi marcada como concluída anteriormente. Operação abortada.")
                                    _clear_execution_form_state(notification['id'])
                                    st.rerun()
                                else:
                                    # Prepara a ação a ser registrada
                                    saved_evidence_attachments = []
                                    if action_type_choice_state == "Concluir Minha Parte" and uploaded_evidence_files:
                                        for file in uploaded_evidence_files:
                                            saved_file_info = save_uploaded_file(file, notification.get('id'))
                                            if saved_file_info:
                                                saved_evidence_attachments.append(saved_file_info)

                                    action = {
                                        'executor_id': user_id_logged_in,
                                        'executor_name': user_username_logged_in,  # Usar o username logado
                                        'description': action_description_state,
                                        'timestamp': datetime.now().isoformat(),
                                        'final_action_by_executor': action_type_choice_state == "Concluir Minha Parte",
                                        'evidence_description': evidence_description_state if action_type_choice_state == "Concluir Minha Parte" else None,
                                        'evidence_attachments': saved_evidence_attachments if action_type_choice_state == "Concluir Minha Parte" else None
                                    }

                                    # Garante que a lista de ações exista e seja uma lista
                                    if 'actions' not in current_notification_in_list or not isinstance(
                                            current_notification_in_list['actions'], list):
                                        current_notification_in_list['actions'] = []

                                    current_notification_in_list['actions'].append(action)

                                    # Lógica para Registrar Ação
                                    if action_type_choice_state == "Registrar Ação":
                                        if current_notification_in_list.get('status') == 'classificada':
                                            current_notification_in_list['status'] = 'em_execucao'

                                        add_history_entry(current_notification_in_list['id'], "Ação registrada (Execução)",
                                                          user_username_logged_in,  # Usar o username logado
                                                          f"Registrou ação: {action_description_state[:100]}..." if len(
                                                              action_description_state) > 100 else f"Registrou ação: {action_description_state}")
                                        st.success(
                                            "✅ Ação registrada com sucesso! O status da notificação foi atualizado para 'em execução' se ainda não estava.")

                                    # Lógica para Concluir Minha Parte
                                    elif action_type_choice_state == "Concluir Minha Parte":
                                        all_assigned_executors_ids = set(current_notification_in_list.get('executors', []))
                                        executors_who_concluded_ids = set(
                                            a.get('executor_id') for a in current_notification_in_list['actions'] if
                                            a.get('final_action_by_executor'))

                                        all_executors_concluded = all_assigned_executors_ids.issubset(
                                            executors_who_concluded_ids) and len(all_assigned_executors_ids) > 0

                                        if all_executors_concluded:
                                            current_notification_in_list['status'] = 'revisao_classificador_execucao'
                                        history_details = f"Executor {user_username_logged_in} concluiu sua parte das ações."
                                        if 'history' not in current_notification_in_list or not isinstance(
                                                current_notification_in_list['history'], list):
                                            current_notification_in_list['history'] = []
                                        current_notification_in_list['history'].append({
                                            "action": "Execução concluída (por executor)",
                                            "user": user_username_logged_in,
                                            "timestamp": datetime.now().isoformat(),
                                            "details": history_details
                                        })

                                        st.success(
                                            f"✅ Sua execução foi concluída nesta notificação! Status atual: '{current_notification_in_list['status'].replace('_', ' ').title()}'.")
                                        if not all_executors_concluded:
                                            users_list_exec = load_users()
                                            remaining_executors_ids = list(
                                                all_assigned_executors_ids - executors_who_concluded_ids)
                                            remaining_executors_names = [u.get('name', UI_TEXTS.text_na) for u in
                                                                         users_list_exec if
                                                                         u.get('id') in remaining_executors_ids]
                                            st.info(
                                                f"Aguardando conclusão dos seguintes executores: {', '.join(remaining_executors_names) or 'Nenhum'}.")
                                        elif all_executors_concluded:
                                            st.info(
                                                f"Todos os executores concluíram suas partes. A notificação foi enviada para revisão final pelo classificador.\n\nEvidência da tratativa:\n{evidence_description_state}\n\nAnexos: {len(saved_evidence_attachments) if saved_evidence_attachments else 0}")

                                    # SALVA A LISTA COMPLETA DE NOTIFICAÇÕES APENAS UMA VEZ AQUI
                                    save_notifications(all_notifications)
                                    _clear_execution_form_state(
                                        notification['id'])  # Limpa o estado do formulário para a próxima iteração
                                    st.rerun()

                with st.expander("👥 Adicionar Executor Adicional"):
                    with st.form(f"add_executor_form_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                                 clear_on_submit=True):
                        executors = get_users_by_role('executor')
                        current_executors_ids = notification.get('executors', [])
                        available_executors = [e for e in executors if e.get('id') not in current_executors_ids]

                        if available_executors:
                            executor_options = {
                                f"{e.get('name', UI_TEXTS.text_na)} ({e.get('username', UI_TEXTS.text_na)})": e['id']
                                for e in
                                available_executors}

                            add_executor_display_options = [UI_TEXTS.multiselect_instruction_placeholder] + list(
                                executor_options.keys())
                            default_add_executor_selection = [UI_TEXTS.multiselect_instruction_placeholder]

                            new_executor_name_to_add_raw = st.selectbox(
                                "Selecionar executor para adicionar:*",
                                options=add_executor_display_options,
                                index=add_executor_display_options.index(default_add_executor_selection[0]),
                                key=f"add_executor_select_exec_{notification.get('id', UI_TEXTS.text_na)}_form_refactored",
                                help="Selecione o usuário executor que será adicionado a esta notificação."
                            )
                            new_executor_name_to_add = (
                                new_executor_name_to_add_raw
                                if new_executor_name_to_add_raw != UI_TEXTS.multiselect_instruction_placeholder
                                else None
                            )

                            st.markdown("<span class='required-field'>* Campo obrigatório</span>",
                                        unsafe_allow_html=True)

                            submit_button = st.form_submit_button("➕ Adicionar Executor",
                                                                  use_container_width=True)
                            if submit_button:
                                if new_executor_name_to_add:
                                    new_executor_id = executor_options[new_executor_name_to_add]
                                    # Modifica o objeto notification diretamente na lista all_notifications
                                    current_notification_in_list = next(
                                        (n for n in all_notifications if n.get('id') == notification.get('id')), None)
                                    if current_notification_in_list:
                                        if 'executors' not in current_notification_in_list or not isinstance(
                                                current_notification_in_list['executors'], list):
                                            current_notification_in_list['executors'] = []
                                        current_notification_in_list['executors'].append(new_executor_id)

                                        # Adiciona ao histórico
                                        if 'history' not in current_notification_in_list or not isinstance(
                                                current_notification_in_list['history'], list):
                                            current_notification_in_list['history'] = []
                                        current_notification_in_list['history'].append({
                                            "action": "Executor adicionado (durante execução)",
                                            "user": user_username_logged_in,
                                            "timestamp": datetime.now().isoformat(),
                                            "details": f"Adicionado o executor: {new_executor_name_to_add}"
                                        })

                                        save_notifications(all_notifications)  # Salva a lista completa
                                        st.success(
                                            f"✅ {new_executor_name_to_add} adicionado como executor para esta notificação.")
                                        st.rerun()
                                    else:
                                        st.error("Erro: Notificação não encontrada para adicionar executor.")
                                else:
                                    st.error("⚠️ Por favor, selecione um executor para adicionar.")
                        else:
                            st.info("Não há executores adicionais disponíveis para atribuição no momento.")

    with tab_closed_my_exec_notifs:
        st.markdown("### Minhas Ações Encerradas")

        if not closed_my_exec_notifications:
            st.info("✅ Não há notificações encerradas em que você estava envolvido como executor no momento.")
        else:
            st.info(
                f"Total de notificações encerradas em que você estava envolvido: {len(closed_my_exec_notifications)}.")

            search_query_exec_closed = st.text_input(
                "🔎 Buscar em Minhas Ações Encerradas (Título, Descrição, ID):",
                key="closed_exec_notif_search_input",
                placeholder="Ex: 'reparo', '987', 'instalação'"
            ).lower()

            filtered_closed_my_exec_notifications = []
            if search_query_exec_closed:
                for notif in closed_my_exec_notifications:
                    if search_query_exec_closed.isdigit() and int(search_query_exec_closed) == notif.get('id'):
                        filtered_closed_my_exec_notifications.append(notif)
                    elif (search_query_exec_closed in notif.get('title', '').lower() or
                          search_query_exec_closed in notif.get('description', '').lower()):
                        filtered_closed_my_exec_notifications.append(notif)
            else:
                filtered_closed_my_exec_notifications = closed_my_exec_notifications

            if not filtered_closed_my_exec_notifications:
                st.warning(
                    "⚠️ Nenhuma notificação encontrada com os critérios de busca especificados em suas ações encerradas.")
            else:
                filtered_closed_my_exec_notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)

                st.markdown(f"**Notificações Encontradas ({len(filtered_closed_my_exec_notifications)})**:")
                for notification in filtered_closed_my_exec_notifications:
                    status_class = f"status-{notification.get('status', UI_TEXTS.text_na).replace('_', '-')}"
                    created_at_str = notification.get('created_at', UI_TEXTS.text_na)
                    if created_at_str != UI_TEXTS.text_na:
                        try:
                            created_at_str = datetime.fromisoformat(created_at_str).strftime('%d/%m/%Y %H:%M:%S')
                        except ValueError:
                            pass

                    concluded_by = UI_TEXTS.text_na
                    if notification.get('conclusion') and notification['conclusion'].get('concluded_by'):
                        concluded_by = notification['conclusion']['concluded_by']
                    elif notification.get('approval') and (notification.get('approval') or {}).get('approved_by'):
                        concluded_by = (notification.get('approval') or {}).get('approved_by')
                    elif notification.get('rejection_classification') and (
                            notification.get('rejection_classification') or {}).get('classified_by'):
                        concluded_by = (notification.get('rejection_classification') or {}).get('classified_by')
                    elif notification.get('rejection_approval') and (notification.get('rejection_approval') or {}).get(
                            'rejected_by'):
                        concluded_by = (notification.get('rejection_approval') or {}).get('rejected_by')

                    # Determinar o status do prazo para notificações encerradas
                    classif_info = notification.get('classification', {})
                    deadline_date_str = classif_info.get('deadline_date')
                    concluded_timestamp_str = (notification.get('conclusion') or {}).get('timestamp')

                    # Verificar se a conclusão foi dentro ou fora do prazo
                    deadline_status = get_deadline_status(deadline_date_str, concluded_timestamp_str)
                    card_class = ""
                    if deadline_status['class'] == "deadline-ontrack" or deadline_status['class'] == "deadline-duesoon":
                        card_class = "card-prazo-dentro"
                    elif deadline_status['class'] == "deadline-overdue":
                        card_class = "card-prazo-fora"

                    st.markdown(f"""
                            <div class="notification-card {card_class}">
                                <h4>#{notification.get('id', UI_TEXTS.text_na)} - {notification.get('title', UI_TEXTS.text_na)}</h4>
                                <p><strong>Status Final:</strong> <span class="{status_class}">{notification.get('status', UI_TEXTS.text_na).replace('_', ' ').title()}</span></p>
                                <p><strong>Encerrada por:</strong> {concluded_by} | <strong>Data de Criação:</strong> {created_at_str}</p>
                                <p><strong>Prazo:</strong> {deadline_status['text']}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    with st.expander(
                            f"👁️ Visualizar Detalhes - Notificação #{notification.get('id', UI_TEXTS.text_na)}"):
                        display_notification_full_details(notification, user_id_logged_in, user_username_logged_in)


def show_approval():
    """Renderiza a página para aprovadores revisarem e aprovarem/rejeitarem notificações."""
    if not check_permission('aprovador'):
        st.error("❌ Acesso negado! Você não tem permissão para aprovar notificações.")
        return

    st.markdown("<h1 class='main-header'>✅ Aprovação de Notificações</h1>", unsafe_allow_html=True)
    st.info(
        "📋 Analise as notificações que foram concluídas pelos executores e revisadas/aceitas pelo classificador, e que requerem sua aprovação final.")
    all_notifications = load_notifications()
    user_id_logged_in = st.session_state.user.get('id')
    user_username_logged_in = st.session_state.user.get('username')

    pending_approval = [n for n in all_notifications if
                        n.get('status') == 'aguardando_aprovacao' and n.get('approver') == user_id_logged_in]

    closed_statuses = ['aprovada', 'rejeitada', 'reprovada', 'concluida']
    closed_my_approval_notifications = [
        n for n in all_notifications
        if n.get('status') in closed_statuses and (
                (n.get('status') == 'aprovada' and (n.get('approval') or {}).get(
                    'approved_by') == user_username_logged_in) or
                (n.get('status') == 'reprovada' and (n.get('rejection_approval') or {}).get(
                    'rejected_by') == user_username_logged_in)
        )
    ]

    if not pending_approval and not closed_my_approval_notifications:
        st.info("✅ Não há notificações aguardando sua aprovação ou que foram encerradas por você no momento.")
        return

    st.success(f"⏳ Você tem {len(pending_approval)} notificação(es) aguardando sua aprovação.")

    tab_pending_approval, tab_closed_my_approval_notifs = st.tabs(
        ["⏳ Aguardando Minha Aprovação", f"✅ Minhas Aprovações Encerradas ({len(closed_my_approval_notifications)})"]
    )

    with tab_pending_approval:
        priority_order = {p: i for i, p in enumerate(FORM_DATA.prioridades)}
        pending_approval.sort(key=lambda x: (
            priority_order.get(x.get('classification', {}).get('prioridade', 'Baixa'), len(FORM_DATA.prioridades)),
            datetime.fromisoformat(
                x.get('classification', {}).get('classification_timestamp',
                                                '1900-01-01T00:00:00')).timestamp() if x.get(
                'classification', {}).get('classification_timestamp') else 0
        ))

        for notification in pending_approval:
            status_class = f"status-{notification.get('status', UI_TEXTS.text_na).replace('_', '-')}"
            classif_info = notification.get('classification', {})
            prioridade_display = classif_info.get('prioridade', UI_TEXTS.text_na)
            prioridade_display = prioridade_display if prioridade_display != 'Selecionar' else f"{UI_TEXTS.text_na} (Não Classificado)"

            # Obter informações de prazo para o card
            deadline_date_str = classif_info.get('deadline_date')

            # CORREÇÃO APLICADA AQUI: Acessa 'timestamp' de 'conclusion' de forma segura
            concluded_timestamp_str = (notification.get('conclusion') or {}).get('timestamp')

            # Determinar o status do prazo (cor do texto)
            # A função get_deadline_status precisa ser capaz de receber concluded_timestamp_str
            deadline_status = get_deadline_status(deadline_date_str, concluded_timestamp_str)

            # Determinar a classe do cartão (fundo) com APENAS DOIS STATUS
            card_class = ""
            if deadline_status['class'] == "deadline-ontrack" or deadline_status['class'] == "deadline-duesoon":
                card_class = "card-prazo-dentro"  # Será verde para "No Prazo" e "Prazo Próximo"
            elif deadline_status['class'] == "deadline-overdue":
                card_class = "card-prazo-fora"  # Será vermelho para "Atrasada"

            # Renderizar o card com o estilo apropriado
            st.markdown(f"""
                    <div class="notification-card {card_class}">
                        <h4>#{notification.get('id', UI_TEXTS.text_na)} - {notification.get('title', UI_TEXTS.text_na)}</h4>
                        <p><strong>Status Atual:</strong> <span class="{status_class}">{notification.get('status', UI_TEXTS.text_na).replace('_', ' ').title()}</span></p>
                        <p><strong>Local do Evento:</strong> {notification.get('location', UI_TEXTS.text_na)} | <strong>Prioridade:</strong> {prioridade_display} <strong class='{deadline_status['class']}'>Prazo: {deadline_status['text']}</strong></p>
                    </div>
                    """, unsafe_allow_html=True)

            with st.expander(
                    f"📋 Análise Completa e Decisão - Notificação #{notification.get('id', UI_TEXTS.text_na)}",
                    expanded=True):
                st.markdown("### 🧐 Detalhes para Análise de Aprovação")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**📝 Evento Original Reportado**")
                    st.write(f"**Título:** {notification.get('title', UI_TEXTS.text_na)}")
                    st.write(f"**Local:** {notification.get('location', UI_TEXTS.text_na)}")
                    occurrence_datetime_summary = format_date_time_summary(notification.get('occurrence_date'),
                                                                           notification.get('occurrence_time'))
                    st.write(f"**Data/Hora Ocorrência:** {occurrence_datetime_summary}")
                    st.write(f"**Setor Notificante:** {notification.get('reporting_department', UI_TEXTS.text_na)}")
                    if notification.get('immediate_actions_taken') == 'Sim' and notification.get(
                            'immediate_action_description'):
                        st.write(
                            f"**Ações Imediatas Reportadas:** {notification.get('immediate_action_description', UI_TEXTS.text_na)[:100]}...")
                with col2:
                    st.markdown("**⏱️ Informações de Gestão e Classificação**")
                    classif = notification.get('classification', {})
                    never_event_display = classif.get('never_event', UI_TEXTS.text_na)
                    st.write(f"**Never Event:** {never_event_display}")
                    sentinel_display = 'Sim' if classif.get('is_sentinel_event') else (
                        'Não' if classif.get('is_sentinel_event') is False else UI_TEXTS.text_na)
                    st.write(f"**Evento Sentinela:** {sentinel_display}")
                    st.write(f"**Classificação NNC:** {classif.get('nnc', UI_TEXTS.text_na)}")
                    if classif.get('nivel_dano'): st.write(
                        f"**Nível de Dano:** {classif.get('nivel_dano', UI_TEXTS.text_na)}")
                    event_type_main_display = classif.get('event_type_main', UI_TEXTS.text_na)
                    st.write(f"**Tipo Principal:** {event_type_main_display}")
                    event_type_sub_display = classif.get('event_type_sub')
                    if event_type_sub_display:
                        if isinstance(event_type_sub_display, list):
                            st.write(
                                f"**Especificação:** {', '.join(event_type_sub_display)[:100]}..." if len(', '.join(
                                    event_type_sub_display)) > 100 else f"**Especificação:** {', '.join(event_type_sub_display)}")
                        else:
                            st.write(f"**Especificação:** {str(event_type_sub_display)[:100]}..." if len(
                                str(event_type_sub_display)) > 100 else f"**Especificação:** {str(event_type_sub_display)}")
                    st.write(f"**Classificação OMS:** {', '.join(classif.get('oms', [UI_TEXTS.text_na]))}")
                    st.write(
                        f"**Requer Aprovação Superior (Classif. Inicial):** {'Sim' if classif.get('requires_approval') else 'Não'}")
                    st.write(f"**Classificado por:** {classif.get('classificador', UI_TEXTS.text_na)}")
                    classification_timestamp_str = classif.get('classification_timestamp', UI_TEXTS.text_na)
                    if classification_timestamp_str != UI_TEXTS.text_na:
                        try:
                            classification_timestamp_str = datetime.fromisoformat(
                                classification_timestamp_str).strftime(
                                '%d/%m/%Y %H:%M:%S')
                        except ValueError:
                            pass
                        st.write(f"**Classificado em:** {classification_timestamp_str}")

                    # Exibição do Prazo e Status na Aprovação
                    if deadline_date_str:
                        deadline_date_formatted = datetime.fromisoformat(deadline_date_str).strftime('%d/%m/%Y')
                        st.markdown(
                            f"**Prazo de Conclusão:** {deadline_date_formatted} (<span class='{deadline_status['class']}'>{deadline_status['text']}</span>)",
                            unsafe_allow_html=True)
                    else:
                        st.write(f"**Prazo de Conclusão:** {UI_TEXTS.deadline_days_nan}")

                st.markdown("**📝 Descrição Completa do Evento**")
                st.info(notification.get('description', UI_TEXTS.text_na))
                if classif.get('notes'):
                    st.markdown("**📋 Orientações / Observações do Classificador (Classificação Inicial)**")
                    st.info(classif.get('notes', UI_TEXTS.text_na))
                if notification.get('patient_involved') == 'Sim':
                    st.markdown("**🏥 Informações do Paciente Afetado**")
                    st.write(f"**N° Atendimento/Prontuário:** {notification.get('patient_id', UI_TEXTS.text_na)}")
                    outcome = notification.get('patient_outcome_obito')
                    if outcome is not None:
                        st.write(f"**Evoluiu com óbito?** {'Sim' if outcome is True else 'Não'}")
                    else:
                        st.write("**Evoluiu com óbito?** Não informado")
                if notification.get('additional_notes'):
                    st.markdown("**ℹ️ Observações Adicionais do Notificante**")
                    st.info(notification.get('additional_notes', UI_TEXTS.text_na))

                st.markdown("---")
                st.markdown("#### ⚡ Ações Executadas pelos Responsáveis")
                if notification.get('actions'):
                    for action in sorted(notification['actions'], key=lambda x: x.get('timestamp', '')):
                        action_type = "🏁 CONCLUSÃO (Executor)" if action.get(
                            'final_action_by_executor') else "📝 AÇÃO Registrada"
                        action_timestamp = action.get('timestamp', UI_TEXTS.text_na)
                        if action_timestamp != UI_TEXTS.text_na:
                            try:
                                action_timestamp = datetime.fromisoformat(action_timestamp).strftime(
                                    '%d/%m/%Y %H:%M:%S')
                            except ValueError:
                                pass
                        st.markdown(f"""
                            <strong>{action_type}</strong> - por <strong>{action.get('executor_name', UI_TEXTS.text_na)}</strong> em {action_timestamp}
                            <br>
                            <em>{action.get('description', UI_TEXTS.text_na)}</em>
                            """, unsafe_allow_html=True)
                        st.markdown("---")
                else:
                    st.warning("⚠️ Nenhuma ação foi registrada pelos executores para esta notificação ainda.")

                users_exec = get_users_by_role('executor')  # Pega usuários com a role de executor
                # Mapeia nomes de exibição para IDs de usuário para executores
                executor_name_to_id_map_approval = {
                    f"{u.get('name', UI_TEXTS.text_na)} ({u.get('username', UI_TEXTS.text_na)})": u['id']
                    for u in users_exec
                }
                # Pega os nomes de exibição dos executores atribuídos
                executor_names_approval = [
                    name for name, uid in executor_name_to_id_map_approval.items()
                    if uid in notification.get('executors', [])
                ]
                st.markdown(f"**👥 Executores Atribuídos:** {', '.join(executor_names_approval) or 'Nenhum'}")
                review_exec_info = notification.get('review_execution', {})
                if review_exec_info:
                    st.markdown("---")
                    st.markdown("#### 🛠️ Resultado da Revisão do Classificador")
                    review_decision_display = review_exec_info.get('decision', UI_TEXTS.text_na)
                    reviewed_by_display = review_exec_info.get('reviewed_by', UI_TEXTS.text_na)
                    review_timestamp_str = review_exec_info.get('timestamp', UI_TEXTS.text_na)
                    if review_timestamp_str != UI_TEXTS.text_na:
                        try:
                            review_timestamp_str = datetime.fromisoformat(review_timestamp_str).strftime(
                                '%d/%m/%Y %H:%M:%S')
                        except ValueError:
                            pass

                    st.write(f"**Decisão da Revisão:** {review_decision_display}")
                    st.write(f"**Revisado por (Classificador):** {reviewed_by_display} em {review_timestamp_str}")
                    if review_decision_display == 'Rejeitada' and review_exec_info.get('rejection_reason'):
                        st.write(
                            f"**Motivo da Rejeição:** {review_exec_info.get('rejection_reason', UI_TEXTS.text_na)}")
                    if review_exec_info.get('notes'):
                        st.write(
                            f"**Observações do Classificador:** {review_exec_info.get('notes', UI_TEXTS.text_na)}")

                if notification.get('attachments'):
                    st.markdown("---")
                    st.markdown("#### 📎 Anexos")
                    for attach_info in notification['attachments']:
                        unique_name_to_use = None
                        original_name_to_use = None
                        if isinstance(attach_info,
                                      dict) and 'unique_name' in attach_info and 'original_name' in attach_info:
                            unique_name_to_use = attach_info['unique_name']
                            original_name_to_use = attach_info['original_name']
                        elif isinstance(attach_info, str):
                            unique_name_to_use = attach_info
                            original_name_to_use = attach_info
                        if unique_name_to_use:
                            file_content = get_attachment_data(unique_name_to_use)
                            if file_content:
                                st.download_button(
                                    label=f"Baixar {original_name_to_use}",
                                    data=file_content,
                                    file_name=original_name_to_use,
                                    mime="application/octet-stream",
                                    key=f"download_approval_{notification['id']}_{unique_name_to_use}"
                                )
                            else:
                                st.write(f"Anexo: {original_name_to_use} (arquivo não encontrado ou corrompido)")

                st.markdown("---")

                # NOVO: Inicializa ou recupera o estado do formulário de aprovação para esta notificação específica
                if 'approval_form_state' not in st.session_state:
                    st.session_state.approval_form_state = {}
                if notification.get('id') not in st.session_state.approval_form_state:
                    st.session_state.approval_form_state[notification.get('id')] = {
                        'decision': UI_TEXTS.selectbox_default_decisao_aprovacao,
                        'notes': '',
                    }
                current_approval_data = st.session_state.approval_form_state[notification.get('id')]

                with st.form(f"approval_form_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                             clear_on_submit=False):
                    st.markdown("### 🎯 Decisão de Aprovação Final")
                    approval_decision_options = [UI_TEXTS.selectbox_default_decisao_aprovacao, "Aprovar",
                                                 "Reprovar"]
                    current_approval_data['decision'] = st.selectbox(
                        "Decisão:*", options=approval_decision_options,
                        key=f"approval_decision_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                        index=approval_decision_options.index(
                            current_approval_data.get('decision', UI_TEXTS.selectbox_default_decisao_aprovacao)),
                        help="Selecione 'Aprovar' para finalizar a notificação ou 'Reprovar' para devolvê-la para revisão pelo classificador."
                    )
                    st.markdown("<span class='required-field'>* Campo obrigatório</span>", unsafe_allow_html=True)

                    # Capture o valor do text_area e atribua-o ao `current_approval_data['notes']`
                    approval_notes_input = st.text_area(
                        "Observações da Aprovação/Reprovação:*",
                        value=current_approval_data.get('notes', ''),
                        placeholder="• Avalie a completude e eficácia das ações executadas e a revisão do classificador...\n• Indique se as ações foram satisfatórias para mitigar o risco ou resolver o evento.\n• Forneça recomendações adicionais, se necessário.\n• Em caso de reprovação, explique claramente o motivo e o que precisa ser revisado ou corrigido pelo classificador.",
                        height=120, key=f"approval_notes_{notification.get('id', UI_TEXTS.text_na)}_refactored",
                        help="Forneça sua avaliação sobre as ações executadas, a revisão do classificador, e a decisão final.").strip()

                    current_approval_data['notes'] = approval_notes_input  # Atualiza o estado com o valor do text_area

                    submit_button = st.form_submit_button("✔️ Confirmar Decisão",
                                                          use_container_width=True)
                    st.markdown("---")

                    if submit_button:
                        validation_errors = []
                        if current_approval_data[
                            'decision'] == UI_TEXTS.selectbox_default_decisao_aprovacao: validation_errors.append(
                            "É obrigatório selecionar a decisão (Aprovar/Reprovar).")
                        if current_approval_data['decision'] == "Reprovar" and not current_approval_data[
                            'notes']: validation_errors.append(
                            "É obrigatório informar as observações para reprovar a notificação.")

                        if validation_errors:
                            st.error("⚠️ **Por favor, corrija os seguintes erros:**")
                            for error in validation_errors: st.warning(error)
                        else:
                            user_name = st.session_state.user.get('name', 'Usuário')
                            user_username = st.session_state.user.get('username', UI_TEXTS.text_na)
                            approval_notes = current_approval_data['notes']

                            if current_approval_data['decision'] == "Aprovar":
                                new_status = 'aprovada'
                                updates = {
                                    'status': new_status,
                                    'approval': {
                                        'decision': 'Aprovada',
                                        'approved_by': user_username,
                                        'notes': approval_notes or None,
                                        'approved_at': datetime.now().isoformat()
                                    },
                                    'conclusion': {
                                        'concluded_by': user_username,
                                        'notes': approval_notes or "Notificação aprovada superiormente.",
                                        'timestamp': datetime.now().isoformat(),
                                        'status_final': 'aprovada'
                                    },
                                    'approver': None
                                }
                                update_notification(notification['id'], updates)

                                add_history_entry(notification['id'], "Notificação aprovada e finalizada",
                                                  user_name,
                                                  f"Aprovada superiormente." + (
                                                      f" Obs: {approval_notes[:150]}..." if approval_notes and len(
                                                          approval_notes) > 150 else (
                                                          f" Obs: {approval_notes}" if approval_notes else "")))
                                st.success(
                                    f"✅ Notificação #{notification['id']} aprovada e finalizada com sucesso! O ciclo de gestão do evento foi concluído.")
                            elif current_approval_data['decision'] == "Reprovar":
                                new_status = 'aguardando_classificador'
                                updates = {
                                    'status': new_status,
                                    'rejection_approval': {
                                        'decision': 'Reprovada',
                                        'rejected_by': user_username,
                                        'reason': approval_notes,
                                        'rejected_at': datetime.now().isoformat()
                                    },
                                    'approver': None
                                }
                                update_notification(notification['id'], updates)

                                add_history_entry(notification['id'], "Notificação reprovada (Aprovação)",
                                                  user_name,
                                                  f"Reprovada superiormente. Motivo: {approval_notes[:150]}..." if len(
                                                      approval_notes) > 150 else f"Reprovada superiormente. Motivo: {approval_notes}")
                                st.warning(
                                    f"⚠️ Notificação #{notification['id']} reprovada! Devolvida para revisão pelo classificador.")
                                st.info(
                                    "A notificação foi movida para o status 'aguardando classificador' para que a equipe de classificação possa revisar e redefinir o fluxo.")

                            update_notification(notification['id'], updates)
                            # NOVO: Limpa o estado do formulário de aprovação para esta notificação específica
                            st.session_state.approval_form_state.pop(notification['id'], None)
                            _clear_approval_form_state(notification['id'])
                            st.rerun()

    with tab_closed_my_approval_notifs:
        st.markdown("### Minhas Aprovações Encerradas")

        if not closed_my_approval_notifications:
            st.info("✅ Não há notificações encerradas que você aprovou ou reprovou no momento.")
        else:
            st.info(f"Total de notificações encerradas por você: {len(closed_my_approval_notifications)}.")
            search_query_app_closed = st.text_input(
                "🔎 Buscar em Minhas Aprovações Encerradas (Título, Descrição, ID):",
                key="closed_app_notif_search_input",
                placeholder="Ex: 'aprovação', 'reprovado', '456'"
            ).lower()

            filtered_closed_my_approval_notifications = []
            if search_query_app_closed:
                for notif in closed_my_approval_notifications:
                    if search_query_app_closed.isdigit() and int(search_query_app_closed) == notif.get('id'):
                        filtered_closed_my_approval_notifications.append(notif)
                    elif (search_query_app_closed in notif.get('title', '').lower() or
                          search_query_app_closed in notif.get('description', '').lower()):
                        filtered_closed_my_approval_notifications.append(notif)
            else:
                filtered_closed_my_approval_notifications = closed_my_approval_notifications

            if not filtered_closed_my_approval_notifications:
                st.warning(
                    "⚠️ Nenhuma notificação encontrada com os critérios de busca especificados em suas aprovações encerradas.")
            else:
                filtered_closed_my_approval_notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)

                st.markdown(f"**Notificações Encontradas ({len(filtered_closed_my_approval_notifications)})**:")
                for notification in filtered_closed_my_approval_notifications:
                    status_class = f"status-{notification.get('status', UI_TEXTS.text_na).replace('_', '-')}"
                    created_at_str = notification.get('created_at', UI_TEXTS.text_na)
                    if created_at_str != UI_TEXTS.text_na:
                        try:
                            created_at_str = datetime.fromisoformat(created_at_str).strftime('%d/%m/%Y %H:%M:%S')
                        except ValueError:
                            pass

                    concluded_by = UI_TEXTS.text_na
                    if notification.get('conclusion') and notification['conclusion'].get('concluded_by'):
                        concluded_by = notification['conclusion']['concluded_by']
                    elif notification.get('approval') and (notification.get('approval') or {}).get('approved_by'):
                        concluded_by = (notification.get('approval') or {}).get('approved_by')
                    elif notification.get('rejection_classification') and (
                            notification.get('rejection_classification') or {}).get('classified_by'):
                        concluded_by = (notification.get('rejection_classification') or {}).get('classified_by')
                    elif notification.get('rejection_approval') and (notification.get('rejection_approval') or {}).get(
                            'rejected_by'):
                        concluded_by = (notification.get('rejection_approval') or {}).get('rejected_by')

                    # Determinar o status do prazo para notificações encerradas
                    classif_info = notification.get('classification', {})
                    deadline_date_str = classif_info.get('deadline_date')

                    # CORREÇÃO APLICADA AQUI: Acessa 'timestamp' de 'conclusion' de forma segura
                    concluded_timestamp_str = (notification.get('conclusion') or {}).get('timestamp')

                    # Verificar se a conclusão foi dentro ou fora do prazo
                    deadline_status = get_deadline_status(deadline_date_str, concluded_timestamp_str)
                    card_class = ""
                    if deadline_status['class'] == "deadline-ontrack" or deadline_status['class'] == "deadline-duesoon":
                        card_class = "card-prazo-dentro"
                    elif deadline_status['class'] == "deadline-overdue":
                        card_class = "card-prazo-fora"

                    st.markdown(f"""
                            <div class="notification-card {card_class}">
                                <h4>#{notification.get('id', UI_TEXTS.text_na)} - {notification.get('title', UI_TEXTS.text_na)}</h4>
                                <p><strong>Status Final:</strong> <span class="{status_class}">{notification.get('status', UI_TEXTS.text_na).replace('_', ' ').title()}</span></p>
                                <p><strong>Encerrada por:</strong> {concluded_by} | <strong>Data de Criação:</strong> {created_at_str}</p>
                                <p><strong>Prazo:</strong> {deadline_status['text']}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    with st.expander(
                            f"👁️ Visualizar Detalhes - Notificação #{notification.get('id', UI_TEXTS.text_na)}"):
                        display_notification_full_details(notification, st.session_state.user.get('id'),
                                                          st.session_state.user.get('username'))


def show_admin():
    """Renderiza a página de administração."""
    if not check_permission('admin'):
        st.error("❌ Acesso negado! Você não tem permissão de administrador.")
        return

    st.markdown("<h1 class='main-header'>⚙️ Administração do Sistema</h1>", unsafe_allow_html=True)
    st.info(
        "Esta área permite gerenciar usuários, configurar o sistema e acessar ferramentas de desenvolvimento.")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["👥 Usuários", "💾 Configurações e Dados", "🛠️ Visualização de Desenvolvimento", "ℹ️ Sobre o Sistema"])

    with tab1:
        st.markdown("### 👥 Gerenciamento de Usuários")

        with st.expander("➕ Criar Novo Usuário", expanded=False):
            with st.form("create_user_form_refactored", clear_on_submit=True):
                st.markdown("**📝 Dados do Novo Usuário**")
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Nome de Usuário*", placeholder="usuario.exemplo",
                                                 key="admin_new_username_form_refactored").strip()
                    new_password = st.text_input("Senha*", type="password", key="admin_new_password_form_refactored",
                                                 placeholder="Senha segura").strip()
                    new_password_confirm = st.text_input("Repetir Senha*", type="password",
                                                         key="admin_new_password_confirm_form_refactored",
                                                         placeholder="Repita a senha").strip()
                with col2:
                    new_name = st.text_input("Nome Completo*", placeholder="Nome Sobrenome",
                                             key="admin_new_name_form_refactored").strip()
                    new_email = st.text_input("Email*", placeholder="usuario@hospital.com",
                                              key="admin_new_email_form_refactored").strip()

                    available_roles_options = ["classificador", "executor", "aprovador", "admin"]
                    instructional_roles_text = UI_TEXTS.multiselect_instruction_placeholder
                    display_roles_options = [instructional_roles_text] + available_roles_options

                    current_selected_roles_from_state = st.session_state.get("admin_new_roles_form_refactored", [])
                    default_selection_for_display = [
                        role for role in current_selected_roles_from_state if role != instructional_roles_text
                    ]
                    if not default_selection_for_display and (
                            not current_selected_roles_from_state or instructional_roles_text in current_selected_roles_from_state):
                        default_selection_for_display = [instructional_roles_text]

                    new_roles_raw = st.multiselect(
                        UI_TEXTS.multiselect_user_roles_label,
                        options=display_roles_options,
                        default=default_selection_for_display,
                        help="Selecione uma ou mais funções para o novo usuário.",
                        key="admin_new_roles_form_refactored"
                    )

                st.markdown("<span class='required-field'>* Campos obrigatórios</span>", unsafe_allow_html=True)
                submit_button = st.form_submit_button("➕ Criar Usuário", use_container_width=True)

            if submit_button:
                username_state = st.session_state.get("admin_new_username_form_refactored", "").strip()
                password_state = st.session_state.get("admin_new_password_form_refactored", "").strip()
                password_confirm_state = st.session_state.get("admin_new_password_confirm_form_refactored", "").strip()
                name_state = st.session_state.get("admin_new_name_form_refactored", "").strip()
                email_state = st.session_state.get("admin_new_email_form_refactored", "").strip()
                roles_to_save = [role for role in new_roles_raw if role != instructional_roles_text]

                validation_errors = []
                if not username_state: validation_errors.append("Nome de Usuário é obrigatório.")
                if not password_state: validation_errors.append("Senha é obrigatória.")
                if password_state != password_confirm_state: validation_errors.append("As senhas não coincidem.")
                if not name_state: validation_errors.append("Nome Completo é obrigatório.")
                if not email_state: validation_errors.append("Email é obrigatório.")
                if not roles_to_save: validation_errors.append(
                    "Pelo menos uma Função é obrigatória.")

                if validation_errors:
                    st.error("⚠️ **Por favor, corrija os seguintes erros:**")
                    for error in validation_errors: st.warning(error)
                else:
                    user_data = {'username': username_state, 'password': password_state, 'name': name_state,
                                 'email': email_state, 'roles': roles_to_save}
                    if create_user(user_data):
                        st.success(f"✅ Usuário '{name_state}' criado com sucesso!\n\n")
                        st.rerun()
                    else:
                        st.error("❌ Nome de usuário já existe. Por favor, escolha outro.")

        st.markdown("### 📋 Usuários Cadastrados no Sistema")
        users = load_users()
        if users:
            if 'editing_user_id' not in st.session_state:
                st.session_state.editing_user_id = None

            users_to_display = [u for u in users if u['id'] != st.session_state.editing_user_id]

            users_to_display.sort(key=lambda x: x.get('name', ''))

            for user in users_to_display:
                status_icon = "🟢" if user.get('active', True) else "🔴"

                expander_key = f"user_expander_{user.get('id', UI_TEXTS.text_na)}"
                with st.expander(
                        f"**{user.get('name', UI_TEXTS.text_na)}** ({user.get('username', UI_TEXTS.text_na)}) {status_icon}",
                        expanded=(st.session_state.editing_user_id == user['id'])):
                    col_display, col_actions = st.columns([0.7, 0.3])

                    with col_display:
                        st.write(f"**ID:** {user.get('id', UI_TEXTS.text_na)}")
                        st.write(f"**Email:** {user.get('email', UI_TEXTS.text_na)}")
                        st.write(f"**Funções:** {', '.join(user.get('roles', [UI_TEXTS.text_na]))}")
                        st.write(f"**Status:** {'✅ Ativo' if user.get('active', True) else '❌ Inativo'}")
                        created_at_str = user.get('created_at', UI_TEXTS.text_na)
                        if created_at_str != UI_TEXTS.text_na:
                            try:
                                created_at_str = datetime.fromisoformat(created_at_str).strftime('%d/%m/%Y %H:%M:%S')
                            except ValueError:
                                pass
                        st.write(f"**Criado em:** {created_at_str}")

                    with col_actions:
                        if user.get('id') != 1 and user.get('id') != st.session_state.user.get('id'):
                            if st.button("✏️ Editar", key=f"edit_user_{user.get('id', UI_TEXTS.text_na)}",
                                         use_container_width=True):
                                st.session_state.editing_user_id = user['id']
                                st.session_state[f"edit_name_{user['id']}"] = user.get('name', '')
                                st.session_state[f"edit_email_{user['id']}"] = user.get('email', '')
                                st.session_state[f"edit_roles_{user['id']}"] = user.get('roles', [])
                                st.session_state[f"edit_active_{user['id']}"] = user.get('active', True)
                                st.rerun()

                            action_text = "🔒 Desativar" if user.get('active', True) else "🔓 Ativar"
                            if st.button(action_text, key=f"toggle_user_{user.get('id', UI_TEXTS.text_na)}",
                                         use_container_width=True):
                                current_user_status = user.get('active', True)
                                updates = {'active': not current_user_status}
                                updated_user = update_user(user['id'], updates)
                                if updated_user:
                                    status_msg = "desativado" if not updated_user['active'] else "ativado"
                                    st.success(
                                        f"✅ Usuário '{user.get('name', UI_TEXTS.text_na)}' {status_msg} com sucesso.")
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao atualizar status do usuário.")
                        elif user.get('id') == 1:
                            st.info("👑 Admin inicial não editável.")
                        elif user.get('id') == st.session_state.user.get('id'):
                            st.info("👤 Você não pode editar sua própria conta.")
                            st.info(
                                "Para alterar sua senha ou dados, faça logout e use a opção de recuperação de senha ou peça a outro admin para editar.")

            if st.session_state.editing_user_id:
                edited_user = next((u for u in users if u['id'] == st.session_state.editing_user_id), None)
                if edited_user:
                    st.markdown(
                        f"### ✏️ Editando Usuário: {edited_user.get('name', UI_TEXTS.text_na)} ({edited_user.get('username', UI_TEXTS.text_na)})")
                    with st.form(key=f"edit_user_form_{edited_user['id']}", clear_on_submit=False):
                        st.text_input("Nome de Usuário", value=edited_user.get('username', ''), disabled=True)

                        edited_name = st.text_input("Nome Completo*",
                                                    value=st.session_state.get(f"edit_name_{edited_user['id']}",
                                                                               edited_user.get('name', '')),
                                                    key=f"edit_name_{edited_user['id']}_input").strip()
                        edited_email = st.text_input("Email*",
                                                     value=st.session_state.get(f"edit_email_{edited_user['id']}",
                                                                                edited_user.get('email', '')),
                                                     key=f"edit_email_{edited_user['id']}_input").strip()
                        available_roles = ["classificador", "executor", "aprovador", "admin"]
                        instructional_roles_text = UI_TEXTS.multiselect_instruction_placeholder
                        display_roles_options = [instructional_roles_text] + available_roles

                        current_edited_roles = st.session_state.get(f"edit_roles_{edited_user['id']}_input",
                                                                    edited_user.get('roles', []))

                        default_edit_selection_for_display = [
                            role for role in current_edited_roles if role != instructional_roles_text
                        ]
                        if not default_edit_selection_for_display and (
                                not current_edited_roles or instructional_roles_text in current_edited_roles):
                            default_edit_selection_for_display = [instructional_roles_text]

                        edited_roles_raw = st.multiselect(
                            UI_TEXTS.multiselect_user_roles_label,
                            options=display_roles_options,
                            default=default_edit_selection_for_display,
                            key=f"edit_roles_{edited_user['id']}_input"
                        )
                        edited_roles = [role for role in edited_roles_raw if role != instructional_roles_text]
                        edited_active = st.checkbox("Ativo",
                                                    value=st.session_state.get(f"edit_active_{edited_user['id']}",
                                                                               edited_user.get('active', True)),
                                                    key=f"edit_active_{edited_user['id']}_input")
                        st.markdown("---")
                        st.markdown("#### Alterar Senha (Opcional)")
                        new_password = st.text_input("Nova Senha", type="password",
                                                     key=f"new_password_{edited_user['id']}_input").strip()
                        new_password_confirm = st.text_input("Repetir Nova Senha", type="password",
                                                             key=f"new_password_confirm_{edited_user['id']}_input").strip()

                        st.markdown(
                            "<span class='required-field'>* Campos obrigatórios (para nome, email e funções)</span>",
                            unsafe_allow_html=True)

                        col_edit_submit, col_edit_cancel = st.columns(2)
                        with col_edit_submit:
                            submit_edit_button = st.form_submit_button("💾 Salvar Alterações",
                                                                       use_container_width=True)
                        with col_edit_cancel:
                            cancel_edit_button = st.form_submit_button("❌ Cancelar Edição",
                                                                       use_container_width=True)

                        if submit_edit_button:
                            edit_validation_errors = []
                            if not edited_name: edit_validation_errors.append("Nome Completo é obrigatório.")
                            if not edited_email: edit_validation_errors.append("Email é obrigatório.")
                            if not edited_roles: edit_validation_errors.append(
                                "Pelo menos uma Função é obrigatória.")
                            if new_password:
                                if new_password != new_password_confirm:
                                    edit_validation_errors.append("As novas senhas não coincidem.")
                                if len(new_password) < 6:
                                    edit_validation_errors.append("A nova senha deve ter no mínimo 6 caracteres.")

                            if edit_validation_errors:
                                st.error("⚠️ **Por favor, corrija os seguintes erros:**")
                                for error in edit_validation_errors: st.warning(error)
                            else:
                                updates_to_apply = {
                                    'name': edited_name,
                                    'email': edited_email,
                                    'roles': edited_roles,
                                    'active': edited_active
                                }
                                if new_password:
                                    updates_to_apply['password'] = new_password

                                updated_user_final = update_user(edited_user['id'], updates_to_apply)
                                if updated_user_final:
                                    st.success(
                                        f"✅ Usuário '{updated_user_final.get('name', UI_TEXTS.text_na)}' atualizado com sucesso!")
                                    st.session_state.editing_user_id = None
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao salvar alterações do usuário.")

                        if cancel_edit_button:
                            st.session_state.editing_user_id = None
                            st.rerun()

        else:
            st.info("📋 Nenhum usuário cadastrado no sistema.")

    with tab2:
        st.markdown("### 💾 Configurações e Gerenciamento de Dados")
        st.warning(
            "⚠️ Esta seção é destinada a desenvolvedores para visualizar a estrutura completa dos dados. Não é para uso operacional normal.")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 💾 Backup dos Dados")
            st.info("Gera um arquivo JSON contendo todos os dados de usuários e notificações cadastrados no sistema.")
            if st.button("📥 Gerar Backup (JSON)", use_container_width=True,
                         key="generate_backup_btn"):
                backup_data = {
                    'users': load_users(),
                    'notifications': load_notifications(),
                    'backup_date': datetime.now().isoformat(),
                    'version': '1.1'
                }
                backup_json = json.dumps(backup_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="⬇️ Baixar Backup Agora", data=backup_json,
                    file_name=f"hospital_notif_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json", use_container_width=True, key="download_backup_btn"
                )
        with col2:
            st.markdown("#### 📤 Restaurar Dados")
            st.info(
                "Carrega um arquivo JSON de backup para restaurar dados de usuários e notificações. **Isso sobrescreverá os dados existentes!**")
            uploaded_file = st.file_uploader("Selecione um arquivo de backup (formato JSON):", type=['json'],
                                             key="admin_restore_file_uploader")
            if uploaded_file:
                with st.form("restore_form", clear_on_submit=False):
                    submit_button = st.form_submit_button("🔄 Restaurar Dados", use_container_width=True,
                                                          key="restore_data_btn")
                    if submit_button:
                        try:
                            uploaded_file_content = st.session_state.admin_restore_file_uploader.getvalue().decode(
                                'utf8')
                            backup_data = json.loads(uploaded_file_content)
                            if isinstance(backup_data,
                                          dict) and 'users' in backup_data and 'notifications' in backup_data:
                                save_users(backup_data['users'])
                                save_notifications(backup_data['notifications'])
                                st.success("✅ Dados restaurados com sucesso a partir do arquivo!\n\n")
                                st.info("A página será recarregada para refletir os dados restaurados.")
                                st.session_state.pop('admin_restore_file_uploader', None)
                                _reset_form_state()
                                st.session_state.initial_classification_state = {}
                                st.session_state.review_classification_state = {}
                                st.session_state.current_initial_classification_id = None
                                st.session_state.current_review_classification_id = None

                                st.rerun()
                            else:
                                st.error(
                                    "❌ Arquivo de backup inválido. O arquivo JSON não contém a estrutura esperada (chaves 'users' e 'notifications').")
                        except json.JSONDecodeError:
                            st.error("❌ Erro ao ler o arquivo JSON. Certifique-se de que é um arquivo JSON válido.")
                        except Exception as e:
                            st.error(f"❌ Ocorreu um erro inesperado ao restaurar os dados: {str(e)}")

    with tab3:
        st.markdown("### 🛠️ Visualização de Desenvolvimento e Debug")
        st.warning(
            "⚠️ Esta seção é destinada a desenvolvedores para visualizar a estrutura completa dos dados. Não é para uso operacional normal.")
        notifications = load_notifications()
        if notifications:
            selected_notif_display_options = [UI_TEXTS.selectbox_default_admin_debug_notif] + [
                f"#{n.get('id', UI_TEXTS.text_na)} - {n.get('title', UI_TEXTS.text_na)} (Status: {n.get('status', UI_TEXTS.text_na).replace('_', ' ')})"
                for n in notifications
            ]
            selectbox_key_debug = "admin_debug_notif_select_refactored"
            if selectbox_key_debug not in st.session_state or st.session_state[
                selectbox_key_debug] not in selected_notif_display_options:
                st.session_state[selectbox_key_debug] = selected_notif_display_options[0]

            selected_notif_display = st.selectbox(
                "Selecionar notificação para análise detalhada (JSON):",
                options=selected_notif_display_options,
                index=selected_notif_display_options.index(st.session_state[selectbox_key_debug]) if st.session_state[
                                                                                                         selectbox_key_debug] in selected_notif_display_options else 0,
                key=selectbox_key_debug
            )
            if selected_notif_display != UI_TEXTS.selectbox_default_admin_debug_notif:
                try:
                    parts = selected_notif_display.split('#')
                    if len(parts) > 1:
                        id_part = parts[1].split(' -')[0]
                        notif_id = int(id_part)
                        notification = next((n for n in notifications if n.get('id') == notif_id), None)
                        if notification:
                            st.markdown("#### Dados Completos da Notificação (JSON)")
                            st.json(notification)
                        else:
                            st.error("❌ Notificação não encontrada.")
                    else:
                        st.error("❌ Formato de seleção inválido.")
                except (IndexError, ValueError) as e:
                    st.error(f"❌ Erro ao processar seleção ou encontrar notificação: {e}")
        else:
            st.info("📋 Nenhuma notificação encontrada para análise de desenvolvimento.")

    with tab4:
        st.markdown("### ℹ️ Informações do Sistema")
        st.markdown("#### Detalhes do Portal")
        st.write(f"**Versão do Portal:** 1.0.5")
        st.write(f"**Data da Última Atualização:** 21/06/2025")
        st.write(f"**Desenvolvido por:** FIA Softworks")
        st.markdown("#### Contato")
        st.markdown("##### Suporte Técnico:")
        st.write(f"**Email:** beborges@outlook.com.br")
        st.write(f"**Telefone:** (35) 93300-1414")


def show_dashboard():
    """
    Renders a comprehensive dashboard for notification visualization.
    Includes key metrics, charts, and a detailed, filterable, searchable, and paginated list of notifications.
    """
    st.markdown("<h1 class='main-header'>📊 Dashboard de Notificações</h1>", unsafe_allow_html=True)
    st.info("Visão geral e detalhada de todas as notificações registradas no sistema.")

    all_notifications = load_notifications()
    if not all_notifications:
        st.warning(
            "⚠️ Nenhuma notificação encontrada para exibir no dashboard. Comece registrando uma nova notificação.")
        return

    st.markdown("### Visão Geral e Métricas Chave")
    total = len(all_notifications)
    pending_classif = len([n for n in all_notifications if n.get('status') == "pendente_classificacao"])
    in_progress_statuses = ['classificada', 'em_execucao', 'aguardando_classificador',
                            'aguardando_aprovacao', 'revisao_classificador_execucao']
    in_progress = len([n for n in all_notifications if n.get('status') in in_progress_statuses])
    completed = len([n for n in all_notifications if n.get('status') == 'aprovada'])
    rejected = len([n for n in all_notifications if n.get('status') in ['rejeitada', 'reprovada']])

    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    with col_m1:
        st.markdown(f"<div class='metric-card'><h4>Total</h4><p>{total}</p></div>", unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"<div class='metric-card'><h4>Pendente Classif.</h4><p>{pending_classif}</p></div>",
                    unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"<div class='metric-card'><h4>Em Andamento</h4><p>{in_progress}</p></div>", unsafe_allow_html=True)
    with col_m4:
        st.markdown(f"<div class='metric-card'><h4>Concluídas</h4><p>{completed}</p></div>", unsafe_allow_html=True)
    with col_m5:
        st.markdown(f"<div class='metric-card'><h4>Rejeitadas</h4><p>{rejected}</p></div>", unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### Gráficos de Tendência e Distribuição")
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### Distribuição de Notificações por Status")
        status_mapping = {
            'pendente_classificacao': 'Pendente Classif. Inicial',
            'classificada': 'Classificada (Aguardando Exec.)',
            'em_execucao': 'Em Execução',
            'revisao_classificador_execucao': 'Aguardando Revisão Exec.',
            'aguardando_classificador': 'Aguardando Classif. (Revisão)',
            'aguardando_aprovacao': 'Aguardando Aprovação',
            'aprovada': 'Concluída (Aprovada)',
            'rejeitada': 'Rejeitada (Classif. Inicial)',
            'reprovada': 'Reprovada (Aprovação)'
        }
        status_count = {}
        for notification in all_notifications:
            status = notification.get('status', UI_TEXTS.text_na)
            mapped_status = status_mapping.get(status, status)
            status_count[mapped_status] = status_count.get(mapped_status, 0) + 1

        if status_count:
            status_df = pd.DataFrame(list(status_count.items()), columns=['Status', 'Quantidade'])
            status_order = [status_mapping.get(s) for s in ['pendente_classificacao', 'classificada', 'em_execucao',
                                                            'revisao_classificador_execucao',
                                                            'aguardando_classificador',
                                                            'aguardando_aprovacao', 'aprovada', 'rejeitada',
                                                            'reprovada']]
            status_order = [s for s in status_order if s and s in status_df['Status'].tolist()]
            if status_order:
                status_df['Status'] = pd.Categorical(status_df['Status'], categories=status_order, ordered=True)
                status_df = status_df.sort_values('Status')
            st.bar_chart(status_df.set_index('Status'))
        else:
            st.info("Nenhum dado de status para gerar o gráfico.")

    with col_chart2:
        st.markdown("#### Notificações Criadas ao Longo do Tempo")
        if all_notifications:
            df_notifications = pd.DataFrame(all_notifications)
            df_notifications['created_at_dt'] = pd.to_datetime(df_notifications['created_at'])
            df_notifications['month_year'] = df_notifications['created_at_dt'].dt.to_period('M').astype(str)
            monthly_counts = df_notifications.groupby('month_year').size().reset_index(name='count')
            monthly_counts['month_year'] = pd.to_datetime(monthly_counts['month_year'])
            monthly_counts = monthly_counts.sort_values('month_year')
            monthly_counts['month_year'] = monthly_counts['month_year'].dt.strftime(
                '%Y-%m')

            st.line_chart(monthly_counts.set_index('month_year'))
        else:
            st.info("Nenhum dado para gerar o gráfico de tendência.")

    st.markdown("---")

    st.markdown("### Lista Detalhada de Notificações")

    col_filters1, col_filters2, col_filters3 = st.columns(3)

    all_option_text = UI_TEXTS.multiselect_all_option

    if 'dashboard_filter_status' not in st.session_state: st.session_state.dashboard_filter_status = [all_option_text]
    if 'dashboard_filter_nnc' not in st.session_state: st.session_state.dashboard_filter_nnc = [all_option_text]
    if 'dashboard_filter_priority' not in st.session_state: st.session_state.dashboard_filter_priority = [
        all_option_text]
    if 'dashboard_filter_date_start' not in st.session_state: st.session_state.dashboard_filter_date_start = None
    if 'dashboard_filter_date_end' not in st.session_state: st.session_state.dashboard_filter_date_end = None
    if 'dashboard_search_query' not in st.session_state: st.session_state.dashboard_search_query = ""
    if 'dashboard_sort_column' not in st.session_state: st.session_state.dashboard_sort_column = 'created_at'
    if 'dashboard_sort_ascending' not in st.session_state: st.session_state.dashboard_sort_ascending = False

    with col_filters1:
        all_status_options_keys = list(status_mapping.keys())
        display_status_options_with_all = [all_option_text] + all_status_options_keys

        current_status_selection_raw = st.session_state.get("dashboard_filter_status_select", [all_option_text])
        if all_option_text in current_status_selection_raw and len(current_status_selection_raw) > 1:
            default_status_selection_for_display = [all_option_text]
        elif not current_status_selection_raw:
            default_status_selection_for_display = [all_option_text]
        else:
            default_status_selection_for_display = current_status_selection_raw

        st.session_state.dashboard_filter_status = st.multiselect(
            UI_TEXTS.multiselect_filter_status_label,
            options=display_status_options_with_all,
            format_func=lambda x: status_mapping.get(x, x.replace('_', ' ').title()),
            default=default_status_selection_for_display,
            key="dashboard_filter_status_select"
        )
        if all_option_text in st.session_state.dashboard_filter_status and len(
                st.session_state.dashboard_filter_status) > 1:
            st.session_state.dashboard_filter_status = [all_option_text]
        elif not st.session_state.dashboard_filter_status:
            st.session_state.dashboard_filter_status = [all_option_text]

        applied_status_filters = [s for s in st.session_state.dashboard_filter_status if s != all_option_text]

        all_nnc_options = FORM_DATA.classificacao_nnc
        display_nnc_options_with_all = [all_option_text] + all_nnc_options
        current_nnc_selection_raw = st.session_state.get("dashboard_filter_nnc_select", [all_option_text])

        if all_option_text in current_nnc_selection_raw and len(current_nnc_selection_raw) > 1:
            default_nnc_selection_for_display = [all_option_text]
        elif not current_nnc_selection_raw:
            default_nnc_selection_for_display = [all_option_text]
        else:
            default_nnc_selection_for_display = current_nnc_selection_raw

        st.session_state.dashboard_filter_nnc = st.multiselect(
            UI_TEXTS.multiselect_filter_nnc_label,
            options=display_nnc_options_with_all,
            default=default_nnc_selection_for_display,
            key="dashboard_filter_nnc_select"
        )
        if all_option_text in st.session_state.dashboard_filter_nnc and len(st.session_state.dashboard_filter_nnc) > 1:
            st.session_state.dashboard_filter_nnc = [all_option_text]
        elif not st.session_state.dashboard_filter_nnc:
            st.session_state.dashboard_filter_nnc = [all_option_text]
        applied_nnc_filters = [n for n in st.session_state.dashboard_filter_nnc if n != all_option_text]

    with col_filters2:
        all_priority_options = FORM_DATA.prioridades
        display_priority_options_with_all = [all_option_text] + all_priority_options
        current_priority_selection_raw = st.session_state.get("dashboard_filter_priority_select", [all_option_text])
        if all_option_text in current_priority_selection_raw and len(current_priority_selection_raw) > 1:
            default_priority_selection_for_display = [all_option_text]
        elif not current_priority_selection_raw:
            default_priority_selection_for_display = [all_option_text]
        else:
            default_priority_selection_for_display = current_priority_selection_raw

        st.session_state.dashboard_filter_priority = st.multiselect(
            UI_TEXTS.multiselect_filter_priority_label,
            options=display_priority_options_with_all,
            default=default_priority_selection_for_display,
            key="dashboard_filter_priority_select"
        )
        if all_option_text in st.session_state.dashboard_filter_priority and len(
                st.session_state.dashboard_filter_priority) > 1:
            st.session_state.dashboard_filter_priority = [all_option_text]
        elif not st.session_state.dashboard_filter_priority:
            st.session_state.dashboard_filter_priority = [all_option_text]
        applied_priority_filters = [p for p in st.session_state.dashboard_filter_priority if p != all_option_text]
        date_start_default = st.session_state.dashboard_filter_date_start or (
            min(pd.to_datetime([n['created_at'] for n in all_notifications if
                                'created_at' in n])).date() if all_notifications else None
        )
        date_end_default = st.session_state.dashboard_filter_date_end or (
            max(pd.to_datetime([n['created_at'] for n in all_notifications if
                                'created_at' in n])).date() if all_notifications else None
        )

        st.session_state.dashboard_filter_date_start = st.date_input(
            "Data Inicial (Criação):", value=date_start_default, key="dashboard_filter_date_start_input"
        )
        st.session_state.dashboard_filter_date_end = st.date_input(
            "Data Final (Criação):", value=date_end_default, key="dashboard_filter_date_date_end_input"
        )

    with col_filters3:
        st.session_state.dashboard_search_query = st.text_input(
            "Buscar (Título, Descrição, ID):",
            value=st.session_state.dashboard_search_query,
            key="dashboard_search_query_input"
        ).lower()

        sort_options_map = {
            'ID': 'id',
            'Data de Criação': 'created_at',
            'Título': 'title',
            'Local': 'location',
            'Prioridade': 'classification.prioridade',
        }
        sort_options_display = [UI_TEXTS.selectbox_sort_by_placeholder] + list(sort_options_map.keys())
        selected_sort_option_display = st.selectbox(
            UI_TEXTS.selectbox_sort_by_label,
            options=sort_options_display,
            index=0,
            key="dashboard_sort_column_select"
        )
        if selected_sort_option_display != UI_TEXTS.selectbox_sort_by_placeholder:
            st.session_state.dashboard_sort_column = sort_options_map[selected_sort_option_display]
        else:
            st.session_state.dashboard_sort_column = 'created_at'

        st.session_state.dashboard_sort_ascending = st.checkbox(
            "Ordem Crescente", value=st.session_state.dashboard_sort_ascending, key="dashboard_sort_ascending_checkbox"
        )

    filtered_notifications = []
    for notification in all_notifications:
        match = True

        if applied_status_filters:
            if notification.get('status') not in applied_status_filters:
                match = False
        if match and applied_nnc_filters:
            classif_nnc = notification.get('classification', {}).get('nnc')
            if classif_nnc not in applied_nnc_filters:
                match = False
        if match and applied_priority_filters:
            priority = notification.get('classification', {}).get('prioridade')
            if priority not in applied_priority_filters:
                match = False

        if match and st.session_state.dashboard_filter_date_start and st.session_state.dashboard_filter_date_end:
            created_at_date = datetime.fromisoformat(notification['created_at']).date()
            if not (
                    st.session_state.dashboard_filter_date_start <= created_at_date <= st.session_state.dashboard_filter_date_end):
                match = False

        if match and st.session_state.dashboard_search_query:
            query = st.session_state.dashboard_search_query
            search_fields = [
                str(notification.get('id', '')).lower(),
                notification.get('title', '').lower(),
                notification.get('description', '').lower(),
                notification.get('location', '').lower()
            ]
            if not any(query in field for field in search_fields):
                match = False

        if match:
            filtered_notifications.append(notification)

    def get_sort_value(notif, sort_key):
        if sort_key == 'id':
            return notif.get('id', 0)
        elif sort_key == 'created_at':
            return datetime.fromisoformat(notif.get('created_at', '1900-01-01T00:00:00'))
        elif sort_key == 'title':
            return notif.get('title', '')
        elif sort_key == 'location':
            return notif.get('location', '')
        elif sort_key == 'classification.prioridade':
            priority_value = notif.get('classification', {}).get('prioridade', 'Baixa')
            priority_order_val = {'Crítica': 4, 'Alta': 3, 'Média': 2, 'Baixa': 1, UI_TEXTS.text_na: 0,
                                  UI_TEXTS.selectbox_default_prioridade_resolucao: 0}
            return priority_order_val.get(priority_value, 0)
        return None

    actual_sort_column = st.session_state.dashboard_sort_column
    if actual_sort_column in sort_options_map.values():
        filtered_notifications.sort(
            key=lambda n: get_sort_value(n, actual_sort_column),
            reverse=not st.session_state.dashboard_sort_ascending
        )

    st.write(f"**Notificações Encontradas: {len(filtered_notifications)}**")

    items_per_page_options = [5, 10, 20, 50]
    items_per_page_display_options = [UI_TEXTS.selectbox_items_per_page_placeholder] + [str(x) for x in
                                                                                        items_per_page_options]

    if 'dashboard_items_per_page' not in st.session_state: st.session_state.dashboard_items_per_page = 10

    selected_items_per_page_display = st.selectbox(
        UI_TEXTS.selectbox_items_per_page_label,
        options=items_per_page_display_options,
        index=items_per_page_display_options.index(str(st.session_state.dashboard_items_per_page)) if str(
            st.session_state.dashboard_items_per_page) in items_per_page_display_options else 0,
        key="dashboard_items_per_page_select"
    )
    if selected_items_per_page_display != UI_TEXTS.selectbox_items_per_page_placeholder:
        st.session_state.dashboard_items_per_page = int(selected_items_per_page_display)
    else:
        st.session_state.dashboard_items_per_page = 10

    total_pages = (
                          len(filtered_notifications) + st.session_state.dashboard_items_per_page - 1) // st.session_state.dashboard_items_per_page
    if total_pages == 0: total_pages = 1

    if 'dashboard_current_page' not in st.session_state: st.session_state.dashboard_current_page = 1
    st.session_state.dashboard_current_page = st.number_input(
        "Página:", min_value=1, max_value=total_pages, value=st.session_state.dashboard_current_page,
        key="dashboard_current_page_input"
    )

    start_idx = (st.session_state.dashboard_current_page - 1) * st.session_state.dashboard_items_per_page
    end_idx = start_idx + st.session_state.dashboard_items_per_page
    paginated_notifications = filtered_notifications[start_idx:end_idx]

    if not paginated_notifications:
        st.info("Nenhuma notificação encontrada com os filtros e busca aplicados.")
    else:
        for notification in paginated_notifications:
            status_class = f"status-{notification.get('status', UI_TEXTS.text_na).replace('_', '-')}"
            created_at_str = datetime.fromisoformat(notification['created_at']).strftime('%d/%m/%Y %H:%M:%S')
            current_status_display = status_mapping.get(notification.get('status', UI_TEXTS.text_na),
                                                        notification.get('status', UI_TEXTS.text_na).replace('_',
                                                                                                             ' ').title())

            # Get deadline details for display in dashboard list
            classif_info = notification.get('classification', {})
            deadline_date_str = classif_info.get('deadline_date')
            deadline_html = ""
            if deadline_date_str:
                deadline_date_formatted = datetime.fromisoformat(deadline_date_str).strftime('%d/%m/%Y')
                deadline_status = get_deadline_status(deadline_date_str)
                deadline_html = f" | <strong class='{deadline_status['class']}'>Prazo: {deadline_date_formatted} ({deadline_status['text']})</strong>"

            st.markdown(f"""
                <div class="notification-card">
                    <h4>#{notification.get('id', UI_TEXTS.text_na)} - {notification.get('title', UI_TEXTS.text_na)}</h4>
                    <p><strong>Status:</strong> <span class="{status_class}">{current_status_display}</span> {deadline_html}</p>
                    <p><strong>Local:</strong> {notification.get('location', UI_TEXTS.text_na)} | <strong>Criada em:</strong> {created_at_str}</p>
                </div>
                """, unsafe_allow_html=True)

            with st.expander(f"👁️ Visualizar Detalhes - Notificação #{notification.get('id', UI_TEXTS.text_na)}"):
                display_notification_full_details(notification,
                                                  st.session_state.user.get(
                                                      'id') if st.session_state.authenticated else None,
                                                  st.session_state.user.get(
                                                      'username') if st.session_state.authenticated else None)


def main():
    """Main function to run the Streamlit application."""
    init_database()

    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'user' not in st.session_state: st.session_state.user = None
    if 'page' not in st.session_state: st.session_state.page = 'create_notification'

    if 'initial_classification_state' not in st.session_state: st.session_state.initial_classification_state = {}
    if 'review_classification_state' not in st.session_state: st.session_state.review_classification_state = {}
    if 'current_initial_classification_id' not in st.session_state: st.session_state.current_initial_classification_id = None
    if 'current_review_classification_id' not in st.session_state: st.session_state.current_review_classification_id = None
    # NOVO: Adiciona o estado para o formulário de aprovação
    if 'approval_form_state' not in st.session_state: st.session_state.approval_form_state = {}

    show_sidebar()

    restricted_pages = ['dashboard', 'classification', 'execution', 'approval', 'admin']
    if st.session_state.page in restricted_pages and not st.session_state.authenticated:
        st.warning("⚠️ Você precisa estar logado para acessar esta página.")
        st.session_state.page = 'create_notification'
        st.rerun()

    if st.session_state.page == 'create_notification':
        show_create_notification()
    elif st.session_state.page == 'dashboard':
        show_dashboard()
    elif st.session_state.page == 'classification':
        show_classification()
    elif st.session_state.page == 'execution':
        show_execution()
    elif st.session_state.page == 'approval':
        show_approval()
    elif st.session_state.page == 'admin':
        show_admin()
    else:
        st.error("Página solicitada inválida. Redirecionando para a página inicial.")
        st.session_state.page = 'create_notification'
        st.rerun()


if __name__ == "__main__":
    main()
