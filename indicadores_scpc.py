import streamlit as st
import os
import json
import hashlib
import pandas as pd
from datetime import datetime
import base64
from io import BytesIO
import plotly.express as px
import time

# Configuração da página
st.set_page_config(
    page_title="Portal de Indicadores",
    page_icon="📊",
    layout="wide"
)

# Diretório de dados
DATA_DIR = "data"
INDICATORS_FILE = os.path.join(DATA_DIR, "indicators.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

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

# Ícones para o menu
MENU_ICONS = {
    "Dashboard": "📈",
    "Criar Indicador": "➕",
    "Editar Indicador": "✏️",
    "Preencher Indicador": "📝",
    "Visão Geral": "📊",
    "Gerenciar Usuários": "👥",
    "Configurações": "⚙️"
}


# Função para carregar usuários
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        default_users = {
            "admin": {
                "password": hashlib.sha256("6105/*".encode()).hexdigest(),
                "tipo": "Administrador",
                "setor": "Todos"
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default_users, f)
        return default_users


# Função para salvar usuários
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)


# Função para verificar credenciais
def verify_credentials(username, password):
    users = load_users()
    if username in users:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if isinstance(users[username], dict):
            return hashed_password == users[username].get("password", "")
        else:
            # Compatibilidade com formato antigo
            return hashed_password == users[username]
    return False


# Função para obter o tipo de usuário
def get_user_type(username):
    users = load_users()
    if username in users:
        if isinstance(users[username], dict):
            return users[username].get("tipo", "Visualizador")
        else:
            # Compatibilidade com formato antigo - assume admin para usuários antigos
            return "Administrador" if username == "admin" else "Visualizador"
    return "Visualizador"  # Padrão para segurança


# Função para obter o setor do usuário
def get_user_sector(username):
    users = load_users()
    if username in users:
        if isinstance(users[username], dict):
            return users[username].get("setor", "Todos")
        else:
            # Compatibilidade com formato antigo
            return "Todos"
    return "Todos"  # Padrão para segurança


# Função para carregar indicadores
def load_indicators():
    try:
        with open(INDICATORS_FILE, "r") as f:
            return json.load(f)
    except:
        return []


# Função para salvar indicadores
def save_indicators(indicators):
    with open(INDICATORS_FILE, "w") as f:
        json.dump(indicators, f, indent=4)


# Função para carregar resultados
def load_results():
    try:
        with open(RESULTS_FILE, "r") as f:
            return json.load(f)
    except:
        return []


# Função para salvar resultados
def save_results(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=4)


# Função para carregar configurações
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        config = {"theme": "padrao"}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        return config


# Função para salvar configurações
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


# Função para gerar ID único para indicadores
def generate_id():
    return datetime.now().strftime("%Y%m%d%H%M%S")


# Função para formatar data como mês/ano
def format_date_as_month_year(date):
    try:
        return date.strftime("%b/%Y")
    except:
        try:
            return date.strftime("%m/%Y")
        except:
            return str(date)


# Função para exportar DataFrame para Excel
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    processed_data = output.getvalue()
    return processed_data


# Função para criar link de download
def get_download_link(df, filename, text):
    val = to_excel(df)
    b64 = base64.b64encode(val).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" style="display: inline-block; padding: 0.5rem 1rem; background-color: #1E88E5; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">{text}</a>'


# Função para converter imagem para base64
def base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        # Retornar uma string vazia se a imagem não for encontrada
        return ""


# Função para criar gráfico
def create_chart(indicator_id, chart_type):
    # Carregar resultados
    results = load_results()

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
    indicators = load_indicators()
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


# Função para mostrar a tela de login
def show_login_page():
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
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if os.path.exists("logo.jpg"):
                st.image("logo.jpg", width=160)
            else:
                st.markdown("<h1 style='text-align: center; font-size: 50px;'>📊</h1>", unsafe_allow_html=True)

        # Títulos centralizados
        st.markdown("<h1 style='text-align: center; font-size: 26px; color: #1E88E5;'>Portal de Indicadores</h1>",
                    unsafe_allow_html=True)
        st.markdown(
            "<h2 style='text-align: center; font-size: 18px; color: #546E7A; margin-bottom: 20px;'>Santa Casa</h2>",
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

                        if verify_credentials(username, password):
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


# Função para criar indicador
def create_indicator():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Criar Novo Indicador")

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

        submitted = st.form_submit_button("Criar Indicador")

        if submitted:
            if nome and objetivo and calculo and meta:
                # Efeito de carregamento
                with st.spinner("Criando indicador..."):
                    time.sleep(0.5)  # Pequeno delay para efeito visual

                    # Carregar indicadores existentes
                    indicators = load_indicators()

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
                        save_indicators(indicators)

                        st.success(f"Indicador '{nome}' criado com sucesso!")
            else:
                st.warning("Todos os campos são obrigatórios.")
    st.markdown('</div>', unsafe_allow_html=True)


# Função para editar indicador
def edit_indicator():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Editar Indicador")

    # Carregar indicadores
    indicators = load_indicators()

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
        with st.form("editar_indicador"):
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

            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Salvar Alterações")
            with col2:
                delete = st.form_submit_button("Excluir Indicador", type="secondary")

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
                    save_indicators(indicators)
                    st.success(f"Indicador '{nome}' atualizado com sucesso!")
            else:
                st.warning("Todos os campos são obrigatórios.")

        if delete:
            # Confirmar exclusão
            confirm_delete = st.checkbox(f"Confirmar exclusão do indicador '{selected_indicator['nome']}'?")

            if confirm_delete:
                # Remover indicador
                indicators = [ind for ind in indicators if ind["id"] != selected_indicator["id"]]
                save_indicators(indicators)

                # Remover resultados associados
                results = load_results()
                results = [r for r in results if r["indicator_id"] != selected_indicator["id"]]
                save_results(results)

                st.success(f"Indicador '{selected_indicator['nome']}' excluído com sucesso!")
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def fill_indicator():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Preencher Indicador")

    # Carregar indicadores
    indicators = load_indicators()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtrar indicadores pelo setor do usuário (se for operador)
    user_type = st.session_state.user_type
    user_sector = st.session_state.user_sector

    if user_type == "Operador":
        indicators = [ind for ind in indicators if ind["responsavel"] == user_sector]

        if not indicators:
            st.info(f"Não há indicadores associados ao seu setor ({user_sector}).")
            st.markdown('</div>', unsafe_allow_html=True)
            return

    # Selecionar indicador para preencher
    indicator_names = [ind["nome"] for ind in indicators]
    selected_indicator_name = st.selectbox("Selecione um indicador para preencher:", indicator_names)

    # Encontrar o indicador selecionado
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        # Exibir informações do indicador
        st.subheader(f"Informações do Indicador: {selected_indicator['nome']}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Objetivo:** {selected_indicator['objetivo']}")
            st.markdown(f"**Fórmula de Cálculo:** {selected_indicator['calculo']}")

        with col2:
            st.markdown(f"**Meta:** {selected_indicator['meta']}")
            st.markdown(f"**Comparação:** {selected_indicator['comparacao']}")
            st.markdown(f"**Setor Responsável:** {selected_indicator['responsavel']}")

        # Separador
        st.markdown("---")

        # Formulário para adicionar resultado
        st.subheader("Adicionar Novo Resultado")

        with st.form("adicionar_resultado"):
            # Definir data de referência (mês/ano)
            col1, col2 = st.columns(2)

            with col1:
                mes = st.selectbox("Mês",
                                   options=range(1, 13),
                                   format_func=lambda x: datetime(2023, x, 1).strftime("%B"))

            with col2:
                ano = st.selectbox("Ano",
                                   options=range(datetime.now().year - 5, datetime.now().year + 1),
                                   index=5)  # Padrão: ano atual

            # Campo para resultado
            resultado = st.number_input("Resultado", step=0.01)

            # Campo para observações
            observacoes = st.text_area("Observações (opcional)",
                                       placeholder="Adicione informações relevantes sobre este resultado")

            # Adicionar seção de análise crítica 5W2H
            st.markdown("### Análise Crítica (5W2H)")
            st.markdown("""
            <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                <p style="margin: 0; font-size: 14px;">
                    A metodologia 5W2H ajuda a estruturar a análise crítica de forma completa, 
                    abordando todos os aspectos relevantes da situação.
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Campos para cada elemento do 5W2H
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

            submitted = st.form_submit_button("Salvar Resultado")

        if submitted:
            # Validar resultado
            if resultado is not None:
                # Criar data de referência
                data_referencia = datetime(ano, mes, 1).isoformat()

                # Criar objeto de análise crítica
                analise_critica = {
                    "what": what,
                    "why": why,
                    "who": who,
                    "when": when,
                    "where": where,
                    "how": how,
                    "howMuch": howMuch
                }

                # Converter para JSON
                analise_critica_json = json.dumps(analise_critica)

                # Carregar resultados existentes
                results = load_results()

                # Verificar se já existe um resultado para este indicador e período
                existing_result = next((r for r in results if r["indicator_id"] == selected_indicator["id"] and r[
                    "data_referencia"] == data_referencia), None)

                if existing_result:
                    # Perguntar se deseja sobrescrever
                    overwrite = st.checkbox("Já existe um resultado para este período. Deseja sobrescrever?")

                    if overwrite:
                        # Atualizar resultado existente
                        for r in results:
                            if r["indicator_id"] == selected_indicator["id"] and r[
                                "data_referencia"] == data_referencia:
                                r["resultado"] = resultado
                                r["observacao"] = observacoes  # Corrigido para "observacao" em vez de "observacoes"
                                r["analise_critica"] = analise_critica_json  # Adicionar análise crítica
                                r["data_atualizacao"] = datetime.now().isoformat()

                        # Salvar alterações
                        save_results(results)
                        st.success(f"Resultado atualizado com sucesso para {datetime(ano, mes, 1).strftime('%B/%Y')}!")
                else:
                    # Adicionar novo resultado
                    new_result = {
                        "indicator_id": selected_indicator["id"],
                        "data_referencia": data_referencia,
                        "resultado": resultado,
                        "observacao": observacoes,  # Corrigido para "observacao" em vez de "observacoes"
                        "analise_critica": analise_critica_json,  # Adicionar análise crítica
                        "data_criacao": datetime.now().isoformat(),
                        "data_atualizacao": datetime.now().isoformat()
                    }

                    # Adicionar à lista e salvar
                    results.append(new_result)
                    save_results(results)

                    st.success(f"Resultado adicionado com sucesso para {datetime(ano, mes, 1).strftime('%B/%Y')}!")
            else:
                st.warning("Por favor, informe o resultado.")

        # Exibir resultados anteriores
        st.subheader("Resultados Anteriores")

        # Carregar resultados
        results = load_results()

        # Filtrar resultados para este indicador
        indicator_results = [r for r in results if r["indicator_id"] == selected_indicator["id"]]

        if indicator_results:
            # Converter para DataFrame
            df_results = pd.DataFrame(indicator_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)

            # Formatar para exibição
            df_display = df_results.copy()
            df_display["Período"] = df_display["data_referencia"].apply(lambda x: x.strftime("%B/%Y"))
            df_display["Resultado"] = df_display["resultado"]

            # Verificar se a coluna 'observacao' existe (corrigido)
            if "observacao" in df_display.columns:
                df_display["Observações"] = df_display["observacao"]
            else:
                df_display["Observações"] = ""

            # Verificar se a coluna 'data_atualizacao' existe
            if "data_atualizacao" in df_display.columns:
                df_display["Data de Atualização"] = pd.to_datetime(df_display["data_atualizacao"]).dt.strftime(
                    "%d/%m/%Y %H:%M")
            else:
                df_display["Data de Atualização"] = "N/A"

            # Verificar se há análise crítica
            if "analise_critica" in df_display.columns:
                df_display["Análise Crítica"] = df_display["analise_critica"].apply(
                    lambda x: "✅ Preenchida" if x and x.strip() != "{}" else "❌ Não preenchida"
                )
            else:
                df_display["Análise Crítica"] = "❌ Não preenchida"

            # Selecionar colunas para exibição
            df_display = df_display[["Período", "Resultado", "Observações", "Análise Crítica", "Data de Atualização"]]

            # Exibir tabela
            st.dataframe(df_display, use_container_width=True)

            # Permitir visualizar/editar análise crítica de resultados anteriores
            st.subheader("Visualizar/Editar Análise Crítica")

            # Selecionar período para visualizar/editar
            periodos = df_results["data_referencia"].dt.strftime("%B/%Y").tolist()
            selected_periodo = st.selectbox("Selecione um período:", periodos)

            # Encontrar o resultado selecionado
            selected_result_index = \
            df_results[df_results["data_referencia"].dt.strftime("%B/%Y") == selected_periodo].index[0]
            selected_result = df_results.loc[selected_result_index]

            # Verificar se tem análise crítica
            has_analise = False
            analise_dict = {
                "what": "", "why": "", "who": "", "when": "", "where": "", "how": "", "howMuch": ""
            }

            if "analise_critica" in selected_result and selected_result["analise_critica"]:
                try:
                    analise_dict = json.loads(selected_result["analise_critica"])
                    has_analise = True
                except:
                    pass

            # Exibir/editar análise crítica
            with st.expander("Análise Crítica 5W2H", expanded=True):
                if has_analise:
                    st.info(f"Visualizando análise crítica para o período {selected_periodo}")
                else:
                    st.warning(f"Não há análise crítica para o período {selected_periodo}. Preencha abaixo.")

                # Formulário para editar análise crítica
                with st.form("editar_analise"):
                    what_edit = st.text_area("O que (What)",
                                             value=analise_dict.get("what", ""),
                                             placeholder="O que está acontecendo? Qual é a situação atual do indicador?")

                    why_edit = st.text_area("Por que (Why)",
                                            value=analise_dict.get("why", ""),
                                            placeholder="Por que isso está acontecendo? Quais são as causas?")

                    who_edit = st.text_area("Quem (Who)",
                                            value=analise_dict.get("who", ""),
                                            placeholder="Quem é responsável? Quem está envolvido?")

                    when_edit = st.text_area("Quando (When)",
                                             value=analise_dict.get("when", ""),
                                             placeholder="Quando isso aconteceu? Qual é o prazo para resolução?")

                    where_edit = st.text_area("Onde (Where)",
                                              value=analise_dict.get("where", ""),
                                              placeholder="Onde ocorre a situação? Em qual processo ou área?")

                    how_edit = st.text_area("Como (How)",
                                            value=analise_dict.get("how", ""),
                                            placeholder="Como resolver a situação? Quais ações devem ser tomadas?")

                    howMuch_edit = st.text_area("Quanto custa (How Much)",
                                                value=analise_dict.get("howMuch", ""),
                                                placeholder="Quanto custará implementar a solução? Quais recursos são necessários?")

                    submit_edit = st.form_submit_button("Atualizar Análise Crítica")

                if submit_edit:
                    # Atualizar análise crítica
                    nova_analise = {
                        "what": what_edit,
                        "why": why_edit,
                        "who": who_edit,
                        "when": when_edit,
                        "where": where_edit,
                        "how": how_edit,
                        "howMuch": howMuch_edit
                    }

                    # Converter para JSON
                    nova_analise_json = json.dumps(nova_analise)

                    # Atualizar no DataFrame
                    df_results.at[selected_result_index, "analise_critica"] = nova_analise_json

                    # Verificar se a coluna 'data_atualizacao' existe no DataFrame
                    if "data_atualizacao" in df_results.columns:
                        df_results.at[selected_result_index, "data_atualizacao"] = datetime.now().isoformat()

                    # Atualizar nos resultados
                    for i, r in enumerate(results):
                        if r["indicator_id"] == selected_indicator["id"] and r["data_referencia"] == selected_result[
                            "data_referencia"]:
                            results[i]["analise_critica"] = nova_analise_json

                            # Verificar se a chave 'data_atualizacao' existe no dicionário
                            if "data_atualizacao" in results[i]:
                                results[i]["data_atualizacao"] = datetime.now().isoformat()
                            else:
                                # Adicionar a chave se não existir
                                results[i]["data_atualizacao"] = datetime.now().isoformat()

                    # Salvar alterações
                    save_results(results)
                    st.success(f"Análise crítica atualizada com sucesso para {selected_periodo}!")
                    st.rerun()

            # Exibir gráfico
            st.subheader("Gráfico de Evolução")

            # Criar gráfico com o tipo padrão do indicador
            fig = create_chart(selected_indicator["id"], selected_indicator["tipo_grafico"])

            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Não foi possível gerar o gráfico.")

            # Botão para exportar dados
            if st.button("📥 Exportar Resultados para Excel"):
                # Preparar dados para exportação
                export_df = df_display.copy()

                # Criar link de download
                download_link = get_download_link(export_df,
                                                  f"resultados_{selected_indicator['nome'].replace(' ', '_')}.xlsx",
                                                  "📥 Clique aqui para baixar os dados em Excel")
                st.markdown(download_link, unsafe_allow_html=True)
        else:
            st.info("Nenhum resultado registrado para este indicador.")

    st.markdown('</div>', unsafe_allow_html=True)

def show_dashboard():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Dashboard de Indicadores")

    # Carregar indicadores e resultados
    indicators = load_indicators()
    results = load_results()

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

    # Filtrar por status se necessário
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
            fig = create_chart(ind["id"], ind["tipo_grafico"])
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
                variacao_color = "#26A69A" if (data["variacao"] >= 0 and ind["comparacao"] == "Maior é melhor") or (
                            data["variacao"] <= 0 and ind["comparacao"] == "Menor é melhor") else "#FF5252"
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
    if st.button("📥 Exportar Todos os Dados para Excel"):
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
        download_link = get_download_link(df_export, "indicadores_dashboard.xlsx",
                                          "📥 Clique aqui para baixar os dados em Excel")
        st.markdown(download_link, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# Função para mostrar visão geral
def show_overview():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Visão Geral dos Indicadores")

    # Carregar indicadores e resultados
    indicators = load_indicators()
    results = load_results()

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
        if st.button("📥 Exportar Visão Geral para Excel"):
            download_link = get_download_link(df_overview, "visao_geral_indicadores.xlsx",
                                              "📥 Clique aqui para baixar os dados em Excel")
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


# Função para mostrar configurações
def show_settings():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Configurações")

    # Informações sobre o sistema
    st.subheader("Informações do Sistema")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Versão do Portal:** 1.2.0

        **Data da Última Atualização:** 18/04/2025

        **Desenvolvido por:** Equipe de Desenvolvimento
        """)

    with col2:
        st.markdown("""
        **Suporte Técnico:**

        Email: suporte@portalindicadores.com

        Telefone: (11) 1234-5678
        """)

    # Botão para limpar dados (apenas para admin)
    if st.session_state.username == "admin":
        st.subheader("Administração do Sistema")

        with st.expander("Opções Avançadas"):
            st.warning("⚠️ Estas opções podem causar perda de dados. Use com cuidado.")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("🗑️ Limpar Todos os Resultados"):
                    confirm = st.checkbox("Confirmar exclusão de todos os resultados?")
                    if confirm:
                        with open(RESULTS_FILE, "w") as f:
                            json.dump([], f)
                        st.success("Todos os resultados foram excluídos com sucesso!")

            with col2:
                if st.button("🗑️ Limpar Todos os Indicadores"):
                    confirm = st.checkbox("Confirmar exclusão de todos os indicadores?")
                    if confirm:
                        with open(INDICATORS_FILE, "w") as f:
                            json.dump([], f)
                        with open(RESULTS_FILE, "w") as f:
                            json.dump([], f)
                        st.success("Todos os indicadores e resultados foram excluídos com sucesso!")

    st.markdown('</div>', unsafe_allow_html=True)


# Função para mostrar a página de gerenciamento de usuários
def show_user_management():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Gerenciamento de Usuários")

    users = load_users()

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
        save_users(users)
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

        submit = st.form_submit_button("Adicionar Usuário")

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
                save_users(users)
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
        else:
            user_type = "Administrador" if user == "admin" else "Visualizador"
            user_sector = "Todos"
            nome_completo = ""
            email = ""

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
                            save_users(users)
                            st.success(f"✅ Usuário '{new_nome}' atualizado com sucesso!")

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
                            del users[login]
                            save_users(users)
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
        if st.button("📥 Exportar Lista de Usuários"):
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
            download_link = get_download_link(df_export, "usuarios_sistema.xlsx",
                                              "📥 Clique aqui para baixar a lista de usuários")
            st.markdown(download_link, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
# Função para fazer logout
def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# Verificar autenticação
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False


# Interface principal
def main():
    try:
        # Verificar autenticação
        if not st.session_state.authenticated:
            show_login_page()
            return

        # Obter tipo e setor do usuário
        user_type = get_user_type(st.session_state.username)
        user_sector = get_user_sector(st.session_state.username)

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
        if os.path.exists("logo.jpg"):
            st.sidebar.image("logo.jpg", width=150, use_container_width=True)
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
            show_dashboard()
        elif st.session_state.page == "Criar Indicador" and user_type == "Administrador":
            create_indicator()
        elif st.session_state.page == "Editar Indicador" and user_type == "Administrador":
            edit_indicator()
        elif st.session_state.page == "Preencher Indicador" and user_type in ["Administrador", "Operador"]:
            fill_indicator()
        elif st.session_state.page == "Visão Geral":
            show_overview()
        elif st.session_state.page == "Configurações" and user_type == "Administrador":
            show_settings()
        elif st.session_state.page == "Gerenciar Usuários" and user_type == "Administrador":
            show_user_management()
        else:
            st.warning("Você não tem permissão para acessar esta página.")
            st.session_state.page = "Dashboard"
            st.rerun()

    except Exception as e:
        st.error(f"Ocorreu um erro: {str(e)}")
        import traceback
        st.sidebar.error(traceback.format_exc())

# Executar aplicação
if __name__ == "__main__":
    main()