import schedule
import time
import threading
import streamlit as st
import xlsxwriter
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
from pathlib import Path
from sympy import symbols, sympify, SympifyError
from streamlit_scroll_to_top import scroll_to_here

# --- Importações e configurações do PostgreSQL ---
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json # Para lidar com JSONB

KEY_FILE = "secret.key"

# --- Funções de Conexão e Criação de Tabelas do PostgreSQL ---

def get_db_connection():
    """
    Estabelece e retorna uma conexão com o banco de dados PostgreSQL.
    """
    try:
        # --- ATENÇÃO: Credenciais hardcoded. Considerar usar variáveis de ambiente ou arquivo de config seguro ---
        conn = psycopg2.connect(
            host="localhost",
            database="scpc_indicadores",
            user="streamlit",
            password="6105/*"
        )
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        # Em uma aplicação Streamlit, você pode querer usar st.error aqui
        # st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def create_tables_if_not_exists():
    """
    Cria as tabelas necessárias no banco de dados PostgreSQL se elas não existirem.
    Também cria um usuário administrador padrão para o primeiro acesso.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # 1. Tabela: usuarios (Removendo a coluna 'setor')
            # Nota: Em uma migração real de DB, você precisaria dropar a coluna 'setor'
            # e talvez migrar dados existentes para a nova tabela usuario_setores.
            # Aqui, apenas garantimos que a tabela exista e adicionamos a nova.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    tipo TEXT NOT NULL, -- 'Administrador', 'Operador', 'Visualizador'
                    nome_completo TEXT,
                    email TEXT,
                    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Tabela: usuario_setores (Nova tabela de ligação para múltiplos setores)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuario_setores (
                    username TEXT REFERENCES usuarios(username) ON DELETE CASCADE,
                    setor TEXT NOT NULL,
                    PRIMARY KEY (username, setor)
                );
            """)

            # Verificar se o usuário admin já existe
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'admin';")
            admin_exists = cur.fetchone()[0] > 0

            # Se o admin não existir, criar um usuário admin padrão e associá-lo ao setor "Todos" (logicamente)
            if not admin_exists:
                # Defina aqui o usuário e senha padrão para o primeiro acesso
                admin_username = "admin"
                admin_password = "admin123"  # Você pode alterar para a senha que preferir

                # Gerar hash da senha
                admin_password_hash = hashlib.sha256(admin_password.encode()).hexdigest()

                # Inserir o usuário admin
                cur.execute("""
                    INSERT INTO usuarios (username, password_hash, tipo, nome_completo, email)
                    VALUES (%s, %s, %s, %s, %s);
                """, (admin_username, admin_password_hash, "Administrador", "Administrador do Sistema", "admin@example.com"))

                # Associar o admin ao setor "Todos" na nova tabela (para consistência, embora admin ignore setores)
                cur.execute("""
                    INSERT INTO usuario_setores (username, setor)
                    VALUES (%s, %s)
                    ON CONFLICT (username, setor) DO NOTHING;
                """, (admin_username, "Todos"))

                print(f"Usuário administrador padrão criado. Username: {admin_username}, Senha: {admin_password}")

            # Resto do código para criar outras tabelas...
            # 3. Tabela: indicadores (Mantida)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS indicadores (
                    id TEXT PRIMARY KEY,
                    nome TEXT NOT NULL UNIQUE,
                    objetivo TEXT,
                    formula TEXT,
                    variaveis JSONB,
                    unidade TEXT,
                    meta NUMERIC(10, 2),
                    comparacao TEXT,
                    tipo_grafico TEXT,
                    responsavel TEXT, -- Responsável ainda é um único setor para o indicador
                    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. Tabela: resultados (Mantida)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resultados (
                    indicator_id TEXT NOT NULL,
                    data_referencia TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    resultado NUMERIC(10, 2),
                    valores_variaveis JSONB,
                    observacao TEXT,
                    analise_critica JSONB,
                    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    usuario TEXT,
                    status_analise TEXT,
                    PRIMARY KEY (indicator_id, data_referencia),
                    FOREIGN KEY (indicator_id) REFERENCES indicadores(id) ON DELETE CASCADE
                );
            """)

            # 5. Tabela: configuracoes (Mantida)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            # Inserir configurações padrão se a tabela estiver vazia
            cur.execute("SELECT COUNT(*) FROM configuracoes;")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO configuracoes (key, value) VALUES (%s, %s);", ("theme", "padrao"))
                cur.execute("INSERT INTO configuracoes (key, value) VALUES (%s, %s);", ("backup_hour", "00:00"))
                cur.execute("INSERT INTO configuracoes (key, value) VALUES (%s, %s);", ("last_backup_date", ""))
                print("Configurações padrão inseridas.")

            # 6. Tabela: log_backup (Mantida)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_backup (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    file_name TEXT,
                    user_performed TEXT
                );
            """)

            # 7. Tabela: log_indicadores (Mantida)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_indicadores (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    indicator_id TEXT,
                    user_performed TEXT
                );
            """)

            # 8. Tabela: log_usuarios (Mantida)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_usuarios (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    username_affected TEXT,
                    user_performed TEXT
                );
            """)

            conn.commit()
            print("Tabelas verificadas/criadas com sucesso no PostgreSQL.")
            return True
        except psycopg2.Error as e:
            print(f"Erro ao criar tabelas: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def load_users():
    """
    Carrega todos os usuários do banco de dados PostgreSQL, incluindo seus setores associados.
    Retorna um dicionário com username como chave e os dados como valor.
    """
    conn = get_db_connection()
    users = {}
    if conn:
        try:
            cur = conn.cursor()
            # Carregar dados básicos dos usuários
            cur.execute("""
                SELECT username, password_hash, tipo, nome_completo, email
                FROM usuarios;
            """)
            rows = cur.fetchall()
            for row in rows:
                username, password_hash, tipo, nome_completo, email = row
                users[username] = {
                    "password": password_hash,
                    "tipo": tipo,
                    "nome_completo": nome_completo,
                    "email": email,
                    "setores": [] # Inicializa com lista vazia
                }

            # Carregar setores associados a cada usuário
            cur.execute("""
                SELECT username, setor
                FROM usuario_setores;
            """)
            sector_rows = cur.fetchall()
            for username, setor in sector_rows:
                if username in users:
                    users[username]["setores"].append(setor)

            return users
        except psycopg2.Error as e:
            print(f"Erro ao carregar usuários e setores: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    return {}

def save_users(users_data):
    """
    Salva os usuários no banco de dados PostgreSQL.
    Esta função sincroniza o dicionário 'users_data' com as tabelas 'usuarios' e 'usuario_setores'.
    Ela insere novos usuários, atualiza os existentes e remove os que não estão mais na lista,
    gerenciando as associações de setores na tabela usuario_setores.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # Obter usuários existentes no DB
            cur.execute("SELECT username FROM usuarios;")
            existing_users_in_db = {row[0] for row in cur.fetchall()}

            current_users_to_save = set(users_data.keys())

            for username, data in users_data.items():
                password_hash = data.get("password", "")
                tipo = data.get("tipo", "Visualizador")
                nome_completo = data.get("nome_completo", "")
                email = data.get("email", "")
                setores = data.get("setores", []) # Lista de setores

                # Inserir ou atualizar usuário na tabela usuarios
                if username in existing_users_in_db:
                    cur.execute("""
                        UPDATE usuarios
                        SET password_hash = %s, tipo = %s, nome_completo = %s, email = %s
                        WHERE username = %s;
                    """, (password_hash, tipo, nome_completo, email, username))
                else:
                    cur.execute("""
                        INSERT INTO usuarios (username, password_hash, tipo, nome_completo, email)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (username, password_hash, tipo, nome_completo, email))

                # Gerenciar setores na tabela usuario_setores
                # 1. Deletar setores existentes para este usuário
                cur.execute("DELETE FROM usuario_setores WHERE username = %s;", (username,))
                # 2. Inserir os novos setores
                if setores: # Somente insere se a lista de setores não for vazia
                    sector_records = [(username, setor) for setor in setores]
                    sql_insert_sectors = "INSERT INTO usuario_setores (username, setor) VALUES (%s, %s);"
                    cur.executemany(sql_insert_sectors, sector_records)

            # Deletar usuários que existem no DB mas não na lista de salvamento
            users_to_delete = existing_users_in_db - current_users_to_save
            for username_to_delete in users_to_delete:
                 # O ON DELETE CASCADE na chave estrangeira de usuario_setores garantirá que as entradas de setor sejam deletadas primeiro
                cur.execute("DELETE FROM usuarios WHERE username = %s;", (username_to_delete,))
                print(f"Usuário '{username_to_delete}' removido do banco de dados.")

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar usuários no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Indicadores (Mantidas, pois a associação de setor do indicador não muda)
def load_indicators():
    """
    Carrega os indicadores do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de indicadores no formato esperado pela aplicação.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                       tipo_grafico, responsavel, data_criacao, data_atualizacao
                FROM indicadores;
            """)
            indicators_data = cur.fetchall()

            indicators = []
            for row in indicators_data:
                (id, nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                 tipo_grafico, responsavel, data_criacao, data_atualizacao) = row

                indicators.append({
                    "id": id,
                    "nome": nome,
                    "objetivo": objetivo,
                    "formula": formula if formula is not None else "",
                    "variaveis": variaveis if variaveis is not None else {},
                    "unidade": unidade if unidade is not None else "",
                    "meta": float(meta) if meta is not None else 0.0,
                    "comparacao": comparacao if comparacao is not None else "Maior é melhor",
                    "tipo_grafico": tipo_grafico if tipo_grafico is not None else "Linha",
                    "responsavel": responsavel if responsavel is not None else "Todos",
                    "data_criacao": data_criacao.isoformat() if data_criacao else "",
                    "data_atualizacao": data_atualizacao.isoformat() if data_atualizacao else ""
                })
            return indicators
        except psycopg2.Error as e:
            print(f"Erro ao carregar indicadores do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_indicators(indicators_data):
    """
    Salva os indicadores no banco de dados PostgreSQL.
    Esta função sincroniza a lista 'indicators_data' com a tabela 'indicadores'.
    Ela insere novos indicadores, atualiza os existentes e remove os que não estão mais na lista.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            cur.execute("SELECT id FROM indicadores;")
            existing_indicator_ids_in_db = {row[0] for row in cur.fetchall()}

            current_indicator_ids_to_save = {ind["id"] for ind in indicators_data}

            for ind in indicators_data:
                indicator_id = ind.get("id")
                nome = ind.get("nome")
                objetivo = ind.get("objetivo")
                formula = ind.get("formula")
                variaveis = Json(ind.get("variaveis", {}))
                unidade = ind.get("unidade")
                meta = ind.get("meta")
                comparacao = ind.get("comparacao")
                tipo_grafico = ind.get("tipo_grafico")
                responsavel = ind.get("responsavel")

                if indicator_id in existing_indicator_ids_in_db:
                    cur.execute("""
                        UPDATE indicadores
                        SET nome = %s, objetivo = %s, formula = %s, variaveis = %s,
                            unidade = %s, meta = %s, comparacao = %s, tipo_grafico = %s,
                            responsavel = %s, data_atualizacao = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                          tipo_grafico, responsavel, indicator_id))
                else:
                    if not indicator_id:
                        indicator_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
                        ind["id"] = indicator_id

                    cur.execute("""
                        INSERT INTO indicadores (id, nome, objetivo, formula, variaveis,
                                                 unidade, meta, comparacao, tipo_grafico,
                                                 responsavel, data_criacao, data_atualizacao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """, (indicator_id, nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                          tipo_grafico, responsavel))

            indicators_to_delete = existing_indicator_ids_in_db - current_indicator_ids_to_save
            for id_to_delete in indicators_to_delete:
                cur.execute("DELETE FROM indicadores WHERE id = %s;", (id_to_delete,))
                print(f"Indicador com ID '{id_to_delete}' removido do banco de dados.")

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar indicadores no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Resultados (Mantidas)
def load_results():
    """
    Carrega os resultados dos indicadores do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de resultados no formato esperado pela aplicação.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT indicator_id, data_referencia, resultado, valores_variaveis,
                       observacao, analise_critica, data_criacao, data_atualizacao,
                       usuario, status_analise
                FROM resultados;
            """)
            results_data = cur.fetchall()

            results = []
            for row in results_data:
                (indicator_id, data_referencia, resultado, valores_variaveis,
                 observacao, analise_critica, data_criacao, data_atualizacao,
                 usuario, status_analise) = row

                results.append({
                    "indicator_id": indicator_id,
                    "data_referencia": data_referencia.isoformat() if data_referencia else "",
                    "resultado": float(resultado) if resultado is not None else 0.0,
                    "valores_variaveis": valores_variaveis if valores_variaveis is not None else {},
                    "observacao": observacao if observacao is not None else "",
                    "analise_critica": analise_critica if analise_critica is not None else {}, # JSONB é carregado como dict
                    "data_criacao": data_criacao.isoformat() if data_criacao else "",
                    "data_atualizacao": data_atualizacao.isoformat() if data_atualizacao else "",
                    "usuario": usuario if usuario is not None else "System",
                    "status_analise": status_analise if status_analise is not None else "N/A"
                })
            return results
        except psycopg2.Error as e:
            print(f"Erro ao carregar resultados do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_results(results_data):
    """
    Salva os resultados dos indicadores no banco de dados PostgreSQL.
    Esta função sincroniza a lista 'results_data' com a tabela 'resultados'.
    Ela insere novos resultados e atualiza os existentes.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            cur.execute("SELECT indicator_id, data_referencia FROM resultados;")
            existing_results_keys_in_db = {(row[0], row[1].isoformat()) for row in cur.fetchall()}

            for res in results_data:
                indicator_id = res.get("indicator_id")
                data_referencia_str = res.get("data_referencia")

                try:
                    data_referencia_dt = datetime.fromisoformat(data_referencia_str)
                except (ValueError, TypeError):
                    print(f"Erro: data_referencia inválida para o resultado: {data_referencia_str}")
                    continue

                resultado = res.get("resultado")
                valores_variaveis = Json(res.get("valores_variaveis", {}))
                observacao = res.get("observacao")

                analise_critica_data = res.get("analise_critica", {})
                # Garante que analise_critica_data é um dicionário, mesmo se vier como string JSON
                if isinstance(analise_critica_data, str):
                    try:
                        analise_critica_data = json.loads(analise_critica_data)
                    except json.JSONDecodeError:
                        analise_critica_data = {}
                analise_critica = Json(analise_critica_data)

                usuario = res.get("usuario")
                status_analise = res.get("status_analise")

                current_key = (indicator_id, data_referencia_dt.isoformat())

                if current_key in existing_results_keys_in_db:
                    cur.execute("""
                        UPDATE resultados
                        SET resultado = %s, valores_variaveis = %s, observacao = %s,
                            analise_critica = %s, data_atualizacao = CURRENT_TIMESTAMP,
                            usuario = %s, status_analise = %s
                        WHERE indicator_id = %s AND data_referencia = %s;
                    """, (resultado, valores_variaveis, observacao, analise_critica,
                          usuario, status_analise, indicator_id, data_referencia_dt))
                else:
                    cur.execute("""
                        INSERT INTO resultados (indicator_id, data_referencia, resultado,
                                                valores_variaveis, observacao, analise_critica,
                                                data_criacao, data_atualizacao, usuario, status_analise)
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s);
                    """, (indicator_id, data_referencia_dt, resultado, valores_variaveis,
                          observacao, analise_critica, usuario, status_analise))

            current_results_keys_to_save = {(res.get("indicator_id"), datetime.fromisoformat(res.get("data_referencia")).isoformat()) for res in results_data if res.get("data_referencia")}
            results_to_delete = existing_results_keys_in_db - current_results_keys_to_save
            for ind_id, data_ref_str in results_to_delete:
                data_ref_dt = datetime.fromisoformat(data_ref_str)
                cur.execute("DELETE FROM resultados WHERE indicator_id = %s AND data_referencia = %s;", (ind_id, data_ref_dt))
                print(f"Resultado para indicador '{ind_id}' e data '{data_ref_str}' removido do banco de dados.")

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar resultados no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Configurações (Mantidas)
def load_config():
    """
    Carrega as configurações do banco de dados PostgreSQL.
    Retorna um dicionário de configurações.
    """
    conn = get_db_connection()
    config = {}
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM configuracoes;")
            config_data = cur.fetchall()

            for row in config_data:
                key, value = row
                config[key] = value

            if "theme" not in config:
                config["theme"] = "padrao"
            if "backup_hour" not in config:
                config["backup_hour"] = "00:00"
            if "last_backup_date" not in config:
                config["last_backup_date"] = ""

            return config
        except psycopg2.Error as e:
            print(f"Erro ao carregar configurações do banco de dados: {e}")
            return {"theme": "padrao", "backup_hour": "00:00", "last_backup_date": ""}
        finally:
            cur.close()
            conn.close()
    return {"theme": "padrao", "backup_hour": "00:00", "last_backup_date": ""}

def save_config(config_data):
    """
    Salva as configurações no banco de dados PostgreSQL.
    Esta função atualiza as configurações existentes e insere novas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            for key, value in config_data.items():
                cur.execute("""
                    INSERT INTO configuracoes (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """, (key, value))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar configurações no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Logs de Backup (Mantidas)
def load_backup_log():
    """
    Carrega o log de backup do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de entradas de log.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, action, file_name, user_performed FROM log_backup ORDER BY timestamp DESC;")
            log_data = cur.fetchall()

            log_entries = []
            for row in log_data:
                timestamp, action, file_name, user_performed = row
                log_entries.append({
                    "timestamp": timestamp.isoformat() if timestamp else "",
                    "action": action if action is not None else "",
                    "file_name": file_name if file_name is not None else "",
                    "user": user_performed if user_performed is not None else "System"
                })
            return log_entries
        except psycopg2.Error as e:
            print(f"Erro ao carregar log de backup do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_backup_log(log_data):
    """
    Salva o log de backup no banco de dados PostgreSQL.
    Esta função limpa o log existente e reinseri as entradas fornecidas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM log_backup;")

            for entry in log_data:
                timestamp_dt = datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else datetime.now()
                action = entry.get("action")
                file_name = entry.get("file_name")
                user_performed = entry.get("user", "System")

                cur.execute("""
                    INSERT INTO log_backup (timestamp, action, file_name, user_performed)
                    VALUES (%s, %s, %s, %s);
                """, (timestamp_dt, action, file_name, user_performed))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar o log de backup no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def log_backup_action(action, file_name, user_performed):
    """
    Registra uma ação de backup no log do banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            log_entry_user = user_performed

            cur.execute("""
                INSERT INTO log_backup (action, file_name, user_performed)
                VALUES (%s, %s, %s);
            """, (action, file_name, log_entry_user))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao registrar ação de backup no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Logs de Indicadores (Mantidas)
def load_indicator_log():
    """
    Carrega o log de indicadores do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de entradas de log.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, action, indicator_id, user_performed FROM log_indicadores ORDER BY timestamp DESC;")
            log_data = cur.fetchall()

            log_entries = []
            for row in log_data:
                timestamp, action, indicator_id, user_performed = row
                log_entries.append({
                    "timestamp": timestamp.isoformat() if timestamp else "",
                    "action": action if action is not None else "",
                    "indicator_id": indicator_id if indicator_id is not None else "",
                    "user": user_performed if user_performed is not None else "System"
                })
            return log_entries
        except psycopg2.Error as e:
            print(f"Erro ao carregar log de indicadores do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_indicator_log(log_data):
    """
    Salva o log de indicadores no banco de dados PostgreSQL.
    Esta função limpa o log existente e reinseri as entradas fornecidas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM log_indicadores;")

            for entry in log_data:
                timestamp_dt = datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else datetime.now()
                action = entry.get("action")
                indicator_id = entry.get("indicator_id")
                user_performed = entry.get("user", "System")

                cur.execute("""
                    INSERT INTO log_indicadores (timestamp, action, indicator_id, user_performed)
                    VALUES (%s, %s, %s, %s);
                """, (timestamp_dt, action, indicator_id, user_performed))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar o log de indicadores no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def log_indicator_action(action, indicator_id, user_performed):
    """
    Registra uma ação de indicador no log do banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            log_entry_user = user_performed

            cur.execute("""
                INSERT INTO log_indicadores (action, indicator_id, user_performed)
                VALUES (%s, %s, %s);
            """, (action, indicator_id, log_entry_user))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao registrar ação de indicador no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Logs de Usuários (Mantidas)
def load_user_log():
    """
    Carrega o log de usuários do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de entradas de log.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, action, username_affected, user_performed FROM log_usuarios ORDER BY timestamp DESC;")
            log_data = cur.fetchall()

            log_entries = []
            for row in log_data:
                timestamp, action, username_affected, user_performed = row
                log_entries.append({
                    "timestamp": timestamp.isoformat() if timestamp else "",
                    "action": action if action is not None else "",
                    "username": username_affected if username_affected is not None else "",
                    "user": user_performed if user_performed is not None else "System"
                })
            return log_entries
        except psycopg2.Error as e:
            print(f"Erro ao carregar log de usuários do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_user_log(log_data):
    """
    Salva o log de usuários no banco de dados PostgreSQL.
    Esta função limpa o log existente e reinseri as entradas fornecidas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM log_usuarios;")

            for entry in log_data:
                timestamp_dt = datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else datetime.now()
                action = entry.get("action")
                username_affected = entry.get("username")
                user_performed = entry.get("user", "System")

                cur.execute("""
                    INSERT INTO log_usuarios (timestamp, action, username_affected, user_performed)
                    VALUES (%s, %s, %s, %s);
                """, (timestamp_dt, action, username_affected, user_performed))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar o log de usuários no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def log_user_action(action, username_affected, user_performed):
    """
    Registra uma ação de usuário no log do banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            log_entry_user = user_performed

            cur.execute("""
                INSERT INTO log_usuarios (action, username_affected, user_performed)
                VALUES (%s, %s, %s);
            """, (action, username_affected, log_entry_user))

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao registrar ação de usuário no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# --- Funções Auxiliares e de UI (Adaptadas para o DB) ---

# Lista de Setores (Mantida)
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

# Tipos de Gráfico (Mantidos)
TIPOS_GRAFICOS = ["Linha", "Barra", "Pizza", "Área", "Dispersão"]

# Tema Padrão (Mantido)
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

def img_to_bytes(img_path):
    try:
        img_bytes = Path(img_path).read_bytes()
        encoded = base64.b64encode(img_bytes).decode()
        return encoded
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {img_path}")
        return None
    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")
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

def initialize_session_state():
    """Inicializa o estado da sessão do Streamlit."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    # Remove a chave antiga 'user_sector' que agora será uma lista 'user_sectors'
    if 'user_sector' in st.session_state:
        del st.session_state.user_sector
    if 'user_type' not in st.session_state:
        st.session_state.user_type = "Visualizador"
    if 'user_sectors' not in st.session_state: # Nova chave para armazenar a lista de setores
         st.session_state.user_sectors = []
    if 'current_formula_vars' not in st.session_state:
        st.session_state.current_formula_vars = []
    if 'current_var_descriptions' not in st.session_state:
        st.session_state.current_var_descriptions = {}
    if 'editing_indicator_id' not in st.session_state:
        st.session_state.editing_indicator_id = None
    if 'current_variable_values' not in st.session_state:
         st.session_state.current_variable_values = {}
    if 'should_scroll_to_top' not in st.session_state:
        st.session_state.should_scroll_to_top = False

def configure_locale():
    """Configura o locale para português do Brasil."""
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    except locale.Error as e:
        st.warning(f"Não foi possível configurar o locale para pt_BR.UTF-8: {e}. Verifique se o locale está instalado no seu sistema.")

def scroll_to_top():
    """Define o estado para que a página role para o topo no próximo rerun."""
    st.session_state.should_scroll_to_top = True

def configure_page():
    """Configura a página do Streamlit."""
    image_path = "logo.png"
    logo_base64 = img_to_bytes(image_path)
    page_icon_value = "📈"

    if logo_base64:
        page_icon_value = f"data:image/png;base64,{logo_base64}"
    st.set_page_config(
        page_title="Portal de Indicadores - Santa Casa Poços de Caldas",
        page_icon=page_icon_value,
        layout="wide"
    )

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

def generate_id():
    """Gera um ID único baseado na data e hora (com microssegundos para maior unicidade)."""
    return datetime.now().strftime("%Y%m%d%H%M%S%f")

def format_date_as_month_year(date):
    """Formata a data como mês/ano."""
    try:
        # Tenta formato abreviado (Jan/2023)
        return date.strftime("%b/%Y")
    except:
        # Fallback para formato numérico (01/2023) se o locale não suportar %b
        try:
            return date.strftime("%m/%Y")
        except:
            # Fallback genérico
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
    # Adiciona estilo para o link parecer um botão Streamlit
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" style="display: inline-block; padding: 0.5rem 1rem; background-color: #1E88E5; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">Baixar Excel</a>'

def create_chart(indicator_id, chart_type, TEMA_PADRAO):
    """Cria um gráfico com base no tipo especificado."""
    results = load_results()
    indicator_results = [r for r in results if r["indicator_id"] == indicator_id]

    if not indicator_results:
        return None

    df = pd.DataFrame(indicator_results)
    df["data_referencia"] = pd.to_datetime(df["data_referencia"])
    df = df.sort_values("data_referencia")
    df["data_formatada"] = df["data_referencia"].apply(format_date_as_month_year)

    indicators = load_indicators()
    indicator = next((ind for ind in indicators if ind["id"] == indicator_id), None)

    if not indicator:
        return None

    chart_colors = TEMA_PADRAO["chart_colors"]
    is_dark = TEMA_PADRAO["is_dark"]
    background_color = TEMA_PADRAO["background_color"]
    text_color = TEMA_PADRAO["text_color"]

    if chart_type == "Linha":
        fig = px.line(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]], markers=True)
        # Garante que a meta seja um float antes de adicionar a linha
        meta_value = float(indicator.get("meta", 0.0)) if indicator.get("meta") is not None else None
        if meta_value is not None:
            fig.add_hline(y=meta_value, line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    elif chart_type == "Barra":
        fig = px.bar(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]])
        # Garante que a meta seja um float antes de adicionar a linha
        meta_value = float(indicator.get("meta", 0.0)) if indicator.get("meta") is not None else None
        if meta_value is not None:
            fig.add_hline(y=meta_value, line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    elif chart_type == "Pizza":
        # Para pizza, pegamos apenas o último resultado
        if not df.empty:
            last_result = float(df.iloc[-1]["resultado"])
            meta_value = float(indicator.get("meta", 0.0)) if indicator.get("meta") is not None else None
            # Ajuste para garantir que haja dados válidos para a pizza.
            values_for_pie = [last_result]
            names_for_pie = ["Resultado Atual"]
            if meta_value is not None and meta_value > 0:
                 values_for_pie.append(meta_value)
                 names_for_pie.append("Meta")
            elif meta_value == 0 and last_result == 0:
                 # Caso especial onde meta e resultado são 0
                 values_for_pie = [1, 1] # Valores fictícios para exibir algo
                 names_for_pie = ["Resultado (0)", "Meta (0)"]

            fig = px.pie(names=names_for_pie, values=values_for_pie, title=f"Último Resultado vs Meta: {indicator['nome']}", color_discrete_sequence=[chart_colors[0], chart_colors[1]], hole=0.4)
        else:
            # Não há dados para o gráfico de pizza
            return None
    elif chart_type == "Área":
        fig = px.area(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]])
        # Garante que a meta seja um float antes de adicionar a linha
        meta_value = float(indicator.get("meta", 0.0)) if indicator.get("meta") is not None else None
        if meta_value is not None:
            fig.add_hline(y=meta_value, line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    elif chart_type == "Dispersão":
        fig = px.scatter(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]], size_max=15)
        # Garante que a meta seja um float antes de adicionar a linha
        meta_value = float(indicator.get("meta", 0.0)) if indicator.get("meta") is not None else None
        if meta_value is not None:
            fig.add_hline(y=meta_value, line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    else:
        # Tipo de gráfico não suportado
        return None

    fig.update_layout(xaxis_title="Data de Referência", yaxis_title="Resultado", template="plotly_white")
    if is_dark:
        fig.update_layout(template="plotly_dark", paper_bgcolor=background_color, plot_bgcolor="#1E1E1E", font=dict(color=text_color))
    return fig

def show_login_page():
    """Mostra a página de login."""
    st.markdown("""
    <style>
    #MainMenu, header, footer {display: none;}
    .main { background-color: #f8f9fa; padding: 0; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stAppViewContainer"] { border: none !important; }
    footer { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    header { display: none !important; }
    .stTextInput > div > div > input { border-radius: 6px; border: 1px solid #E0E0E0; padding: 10px 15px; font-size: 15px; }
div[data-testid="stForm"] button[type="submit"] { background-color: #1E88E5; color: white; border: none; border-radius: 6px; padding: 10px 15px; font-size: 16px; font-weight: 500; width: 100%; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 600px; }
    .stAlert { border-radius: 6px; }
    .stApp { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        image_path = "logo.png"
        if os.path.exists(image_path):
            st.markdown(f"<div style='text-align: center;'>{img_to_html(image_path)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align: center; font-size: 50px;'>📊</h1>", unsafe_allow_html=True)

        st.markdown("<h1 style='text-align: center; font-size: 30px; color: #1E88E5;'>Portal de Indicadores</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; font-size: 26px; color: #546E7A; margin-bottom: 20px;'>Santa Casa - Poços de Caldas</h2>", unsafe_allow_html=True)
        st.markdown("<hr style='height: 2px; background: #E0E0E0; border: none; margin: 20px 0;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='font-size: 18px; color: #455A64; margin-bottom: 15px;'>Acesse sua conta</h3>", unsafe_allow_html=True)

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
                            # Carregar tipo e setores após login bem-sucedido
                            users_data = load_users()
                            user_info = users_data.get(username, {})
                            st.session_state.user_type = user_info.get("tipo", "Visualizador")
                            st.session_state.user_sectors = user_info.get("setores", []) # Carrega a lista de setores
                            st.success("Login realizado com sucesso!")
                            time.sleep(0.8)
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")
                else:
                    st.error("Por favor, preencha todos os campos.")
        st.markdown("<p style='text-align: center; font-size: 12px; color: #78909C; margin-top: 30px;'>© 2025 Portal de Indicadores - Santa Casa</p>", unsafe_allow_html=True)

def verify_credentials(username, password):
    """Verifica as credenciais do usuário diretamente do banco de dados."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # A query agora só precisa da senha_hash e tipo da tabela usuarios
            cur.execute("SELECT password_hash, tipo FROM usuarios WHERE username = %s;", (username,))
            result = cur.fetchone()
            if result:
                stored_hash = result[0]
                # tipo_usuario = result[1] # Não precisamos do tipo aqui, apenas para verificar credenciais
                input_hash = hashlib.sha256(password.encode()).hexdigest() # Considerar usar bcrypt/scrypt
                return stored_hash == input_hash
            return False
        except psycopg2.Error as e:
            print(f"Erro ao verificar credenciais: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    return False

def get_user_type(username):
    """Obtém o tipo de usuário."""
    # Esta função agora carrega todos os usuários para encontrar o tipo
    users = load_users()
    if username in users:
        return users[username].get("tipo", "Visualizador")
    return "Visualizador"

def get_user_sectors(username):
    """Obtém a lista de setores do usuário."""
     # Esta função agora carrega todos os usuários para encontrar os setores
    users = load_users()
    if username in users:
        return users[username].get("setores", [])
    # Se o usuário não for encontrado, retorna uma lista vazia
    return []


def create_indicator(SETORES, TIPOS_GRAFICOS):
    """Mostra a página de criação de indicador."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Criar Novo Indicador")
    if 'dashboard_data' in st.session_state: del st.session_state['dashboard_data']
    st.session_state.editing_indicator_id = None # Garante que não estamos em modo de edição ao criar

    # As chaves do session_state para este formulário precisam ser únicas ou redefinidas
    # Usaremos um prefixo para evitar conflitos com a página de edição
    form_prefix = "create_"
    if f'{form_prefix}current_formula_vars' not in st.session_state: st.session_state[f'{form_prefix}current_formula_vars'] = []
    if f'{form_prefix}current_var_descriptions' not in st.session_state: st.session_state[f'{form_prefix}current_var_descriptions'] = {}
    if f'{form_prefix}sample_values' not in st.session_state: st.session_state[f'{form_prefix}sample_values'] = {}
    if f'{form_prefix}test_result' not in st.session_state: st.session_state[f'{form_prefix}test_result'] = None
    if f'{form_prefix}show_variable_section' not in st.session_state: st.session_state[f'{form_prefix}show_variable_section'] = False
    if f'{form_prefix}formula_loaded' not in st.session_state: st.session_state[f'{form_prefix}formula_loaded'] = False

    # Campos de entrada do formulário de criação
    nome = st.text_input("Nome do Indicador", key=f"{form_prefix}nome_input", value=st.session_state.get(f"{form_prefix}nome_input", ""))
    objetivo = st.text_area("Objetivo", key=f"{form_prefix}objetivo_input", value=st.session_state.get(f"{form_prefix}objetivo_input", ""))
    unidade = st.text_input("Unidade do Resultado", placeholder="Ex: %", key=f"{form_prefix}unidade_input", value=st.session_state.get(f"{form_prefix}unidade_input", ""))
    formula = st.text_input("Fórmula de Cálculo (Use letras para variáveis, ex: A+B/C)", placeholder="Ex: (DEMISSOES / TOTAL_FUNCIONARIOS) * 100", key=f"{form_prefix}formula_input", value=st.session_state.get(f"{form_prefix}formula_input", ""))

    # Botão para carregar a fórmula (fora do form para poder atualizar a seção de variáveis)
    load_formula_button = st.button("⚙️ Carregar Fórmula e Variáveis", key=f"{form_prefix}load_formula_button_outside")

    if load_formula_button:
        formula_value = st.session_state.get(f"{form_prefix}formula_input", "")
        if formula_value:
            # Detecta variáveis (letras) na fórmula
            current_detected_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', formula_value))))
            st.session_state[f'{form_prefix}current_formula_vars'] = current_detected_vars

            # Mantém descrições existentes para variáveis que ainda estão na fórmula
            new_var_descriptions = {}
            for var in current_detected_vars:
                new_var_descriptions[var] = st.session_state[f'{form_prefix}current_var_descriptions'].get(var, "")
            st.session_state[f'{form_prefix}current_var_descriptions'] = new_var_descriptions

            # Mantém valores de teste existentes para variáveis que ainda estão na fórmula
            new_sample_values = {}
            for var in current_detected_vars:
                 new_sample_values[var] = st.session_state[f'{form_prefix}sample_values'].get(var, 0.0)
            st.session_state[f'{form_prefix}sample_values'] = new_sample_values

            st.session_state[f'{form_prefix}test_result'] = None # Reseta resultado do teste
            st.session_state[f'{form_prefix}show_variable_section'] = True
            st.session_state[f'{form_prefix}formula_loaded'] = True
            st.rerun() # Rerun para mostrar a seção de variáveis

        else:
            # Limpa o estado se a fórmula estiver vazia
            st.session_state[f'{form_prefix}show_variable_section'] = False
            st.session_state[f'{form_prefix}formula_loaded'] = False
            st.session_state[f'{form_prefix}current_formula_vars'] = []
            st.session_state[f'{form_prefix}current_var_descriptions'] = {}
            st.session_state[f'{form_prefix}sample_values'] = {}
            st.session_state[f'{form_prefix}test_result'] = None
            st.warning("⚠️ Por favor, insira uma fórmula para carregar.")

    st.markdown("---")
    st.subheader("Variáveis da Fórmula e Teste")

    # Só mostra a seção de variáveis se a fórmula foi carregada
    if st.session_state.get(f'{form_prefix}show_variable_section', False):
        if st.session_state.get(f'{form_prefix}current_formula_vars'):
            st.info(f"Variáveis detectadas na fórmula: {', '.join(st.session_state[f'{form_prefix}current_formula_vars'])}")
            st.write("Defina a descrição e insira valores de teste para cada variável:")

            # Formulário para definir descrições e testar valores
            with st.form(key=f"{form_prefix}test_formula_form"):
                cols_desc = st.columns(min(3, len(st.session_state[f'{form_prefix}current_formula_vars'])))
                cols_sample = st.columns(min(3, len(st.session_state[f'{form_prefix}current_formula_vars'])))
                new_var_descriptions = {}
                new_sample_values = {}

                for i, var in enumerate(st.session_state[f'{form_prefix}current_formula_vars']):
                    # Coluna para descrição
                    col_idx = i % len(cols_desc)
                    with cols_desc[col_idx]:
                        new_var_descriptions[var] = st.text_input(
                            f"Descrição para '{var}'",
                            value=st.session_state[f'{form_prefix}current_var_descriptions'].get(var, ""),
                            placeholder=f"Ex: {var} - Número de Atendimentos",
                            key=f"{form_prefix}test_desc_input_{var}" # Chave única baseada em prefixo e variável
                        )
                    # Coluna para valor de teste
                    col_idx = i % len(cols_sample)
                    with cols_sample[col_idx]:
                        new_sample_values[var] = st.number_input(
                            f"Valor de Teste para '{var}'",
                            value=float(st.session_state[f'{form_prefix}sample_values'].get(var, 0.0)),
                            step=0.01,
                            format="%.2f",
                            key=f"{form_prefix}test_sample_input_{var}" # Chave única
                        )

                # Atualiza o estado da sessão com os valores dos inputs
                st.session_state[f'{form_prefix}current_var_descriptions'] = new_var_descriptions
                st.session_state[f'{form_prefix}sample_values'] = new_sample_values

                test_formula_button = st.form_submit_button("✨ Testar Fórmula")

                if test_formula_button:
                     formula_str = st.session_state.get(f"{form_prefix}formula_input", "")
                     variable_values = st.session_state.get(f'{form_prefix}sample_values', {})
                     unidade_value = st.session_state.get(f"{form_prefix}unidade_input", "")

                     if not formula_str:
                         st.warning("⚠️ Por favor, insira uma fórmula para testar.")
                         st.session_state[f'{form_prefix}test_result'] = None
                     elif not variable_values and formula_str:
                          # Caso da fórmula sem variáveis
                          try:
                              calculated_result = float(sympify(formula_str))
                              st.session_state[f'{form_prefix}test_result'] = calculated_result
                          except (SympifyError, ValueError) as e:
                              st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe. Detalhes: {e}")
                              st.session_state[f'{form_prefix}test_result'] = None
                          except Exception as e:
                              st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                              st.session_state[f'{form_prefix}test_result'] = None
                     elif variable_values:
                          # Caso da fórmula com variáveis
                          try:
                              # Cria símbolos para as variáveis
                              var_symbols = symbols(list(variable_values.keys()))
                              # Analisa a string da fórmula em uma expressão simbólica
                              expr = sympify(formula_str, locals=dict(zip(variable_values.keys(), var_symbols)))
                              # Cria um dicionário de substituição com os valores de teste
                              # Garante que os valores são float
                              subs_dict = {symbols(var): float(value) for var, value in variable_values.items()}
                              # Avalia a expressão com os valores de teste
                              calculated_result = float(expr.subs(subs_dict))
                              st.session_state[f'{form_prefix}test_result'] = calculated_result
                          except SympifyError as e:
                              st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe. Detalhes: {e}")
                              st.session_state[f'{form_prefix}test_result'] = None
                          except ZeroDivisionError:
                              st.error("❌ Erro ao calcular a fórmula: Divisão por zero com os valores de teste fornecidos.")
                              st.session_state[f'{form_prefix}test_result'] = None
                          except Exception as e:
                               # Tratamento específico para erro comum de variáveis não mapeadas
                               if "cannot create 'dict_keys' instances" in str(e):
                                   st.error("❌ Erro interno ao processar as variáveis da fórmula. Verifique se as variáveis na fórmula correspondem às variáveis definidas para o indicador.")
                               else:
                                   st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                               st.session_state[f'{form_prefix}test_result'] = None
                # Exibe o resultado do teste se disponível
                if st.session_state.get(f'{form_prefix}test_result') is not None:
                     unidade_value = st.session_state.get(f"{form_prefix}unidade_input", "")
                     st.markdown(f"**Resultado do Teste:** **{st.session_state[f'{form_prefix}test_result']:.2f}{unidade_value}**")
        else:
             st.warning("Nenhuma variável (letras) encontrada na fórmula. O resultado será um valor fixo.")
             # Limpa variáveis relacionadas ao teste se não há variáveis na fórmula
             st.session_state[f'{form_prefix}current_formula_vars'] = []
             st.session_state[f'{form_prefix}current_var_descriptions'] = {}
             st.session_state[f'{form_prefix}sample_values'] = {}
             st.session_state[f'{form_prefix}test_result'] = None
    else:
        st.info("Insira a fórmula acima e clique em '⚙️ Carregar Fórmula e Variáveis' para definir as variáveis e testar.")
        # Garante que o estado esteja limpo se a seção não for exibida
        st.session_state[f'{form_prefix}current_formula_vars'] = []
        st.session_state[f'{form_prefix}current_var_descriptions'] = {}
        st.session_state[f'{form_prefix}sample_values'] = {}
        st.session_state[f'{form_prefix}test_result'] = None
        st.session_state[f'{form_prefix}show_variable_section'] = False
        st.session_state[f'{form_prefix}formula_loaded'] = False


    st.markdown("---")
    # Formulário principal para criar o indicador (campos que não dependem da fórmula)
    with st.form(key=f"{form_prefix}indicator_form"):
        # Recupera valores do estado da sessão para persistência
        meta = st.number_input("Meta", step=0.01, format="%.2f", key=f"{form_prefix}meta", value=st.session_state.get(f"{form_prefix}meta", 0.0))
        comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"], key=f"{form_prefix}comparacao", index=["Maior é melhor", "Menor é melhor"].index(st.session_state.get(f"{form_prefix}comparacao", "Maior é melhor")))
        tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS, key=f"{form_prefix}tipo_grafico", index=TIPOS_GRAFICOS.index(st.session_state.get(f"{form_prefix}tipo_grafico", TIPOS_GRAFICOS[0])) if TIPOS_GRAFICOS else 0)
        responsavel = st.selectbox("Setor Responsável", SETORES, key=f"{form_prefix}responsavel", index=SETORES.index(st.session_state.get(f"{form_prefix}responsavel", SETORES[0])) if SETORES else 0) # Indicador ainda é responsável por um único setor
        create_button = st.form_submit_button("➕ Criar")

        # Lógica de criação ao submeter o formulário
        if create_button:
            # Recupera todos os valores dos campos, incluindo os da parte de cima (fora deste form)
            nome_submitted = st.session_state.get(f"{form_prefix}nome_input", "")
            objetivo_submitted = st.session_state.get(f"{form_prefix}objetivo_input", "")
            formula_submitted = st.session_state.get(f"{form_prefix}formula_input", "")
            unidade_submitted = st.session_state.get(f"{form_prefix}unidade_input", "")
            meta_submitted = st.session_state.get(f"{form_prefix}meta", 0.0)
            comparacao_submitted = st.session_state.get(f"{form_prefix}comparacao", "Maior é melhor")
            tipo_grafico_submitted = st.session_state.get(f"{form_prefix}tipo_grafico", TIPOS_GRAFICOS[0] if TIPOS_GRAFICOS else "")
            responsavel_submitted = st.session_state.get(f"{form_prefix}responsavel", SETORES[0] if SETORES else "")
            variaveis_desc_submitted = st.session_state.get(f'{form_prefix}current_var_descriptions', {})


            # Validação dos campos obrigatórios
            if not nome_submitted or not objetivo_submitted or not formula_submitted:
                 st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (Nome, Objetivo, Fórmula).")
            else:
                # Validação da fórmula usando sympy
                if formula_submitted:
                    try:
                        # Cria símbolos apenas para as variáveis detectadas na fórmula submetida
                        vars_in_submitted_formula = sorted(list(set(re.findall(r'[a-zA-Z]+', formula_submitted))))
                        var_symbols = symbols(vars_in_submitted_formula)
                        # Tenta analisar a fórmula
                        sympify(formula_submitted, locals=dict(zip(vars_in_submitted_formula, var_symbols)))
                    except (SympifyError, ValueError, TypeError) as e:
                         st.error(f"❌ Erro na sintaxe da fórmula: {e}"); return # Impede a criação se a fórmula for inválida
                    except Exception as e:
                         st.error(f"❌ Erro inesperado ao validar a fórmula: {e}"); return # Impede a criação

                with st.spinner("Criando indicador...\ Academia FIA Softworks"):
                    time.sleep(0.5) # Pequeno delay para simular processamento
                    indicators = load_indicators()
                    # Verifica se já existe um indicador com o mesmo nome
                    if any(ind["nome"].strip().lower() == nome_submitted.strip().lower() for ind in indicators):
                        st.error(f"❌ Já existe um indicador com o nome '{nome_submitted}'.")
                    else:
                        # Cria o novo indicador como um dicionário
                        new_indicator = {
                            "id": generate_id(), # Gera um ID único
                            "nome": nome_submitted,
                            "objetivo": objetivo_submitted,
                            "formula": formula_submitted,
                            "variaveis": variaveis_desc_submitted,
                            "unidade": unidade_submitted,
                            "meta": meta_submitted,
                            "comparacao": comparacao_submitted,
                            "tipo_grafico": tipo_grafico_submitted,
                            "responsavel": responsavel_submitted,
                            "data_criacao": datetime.now().isoformat(), # Data de criação
                            "data_atualizacao": datetime.now().isoformat() # Data da última atualização
                        }
                        indicators.append(new_indicator) # Adiciona à lista em memória
                        save_indicators(indicators) # Salva a lista no banco de dados
                        log_indicator_action("Indicador criado", new_indicator["id"], st.session_state.username) # Registra no log

                        st.success(f"✅ Indicador '{nome_submitted}' criado com sucesso!")
                        time.sleep(2) # Aguarda um pouco antes de limpar e rerodar

                        # Limpa os inputs e o estado da sessão associado ao formulário de criação
                        if f"{form_prefix}nome_input" in st.session_state: del st.session_state[f"{form_prefix}nome_input"]
                        if f"{form_prefix}objetivo_input" in st.session_state: del st.session_state[f"{form_prefix}objetivo_input"]
                        if f"{form_prefix}unidade_input" in st.session_state: del st.session_state[f"{form_prefix}unidade_input"]
                        if f"{form_prefix}formula_input" in st.session_state: del st.session_state[f"{form_prefix}formula_input"]
                        if f"{form_prefix}indicator_form" in st.session_state: del st.session_state[f"{form_prefix}indicator_form"] # Limpa o estado do form principal
                        st.session_state[f'{form_prefix}current_formula_vars'] = []
                        st.session_state[f'{form_prefix}current_var_descriptions'] = {}
                        st.session_state[f'{form_prefix}sample_values'] = {}
                        st.session_state[f'{form_prefix}test_result'] = None
                        st.session_state[f'{form_prefix}show_variable_section'] = False
                        st.session_state[f'{form_prefix}formula_loaded'] = False

                        scroll_to_top() # Rola a página para o topo
                        st.rerun() # Reinicia a aplicação para limpar a tela e mostrar sucesso
    st.markdown('</div>', unsafe_allow_html=True)


def edit_indicator(SETORES, TIPOS_GRAFICOS):
    """Mostra a página de edição de indicador com fórmula dinâmica."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Editar Indicador")

    # Garante que a lista de indicadores no estado da sessão esteja atualizada
    if "indicators" not in st.session_state or not st.session_state["indicators"]:
         st.session_state["indicators"] = load_indicators()
    indicators = st.session_state["indicators"]


    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    indicator_names = [ind["nome"] for ind in indicators]

    # Seleciona o indicador a ser editado
    # Usa editing_indicator_id do session_state para manter o indicador selecionado após reruns
    selected_indicator_id_from_state = st.session_state.get('editing_indicator_id')
    initial_index = 0
    if selected_indicator_id_from_state:
         try:
             # Encontra o índice do indicador salvo no estado da sessão
             initial_index = next(i for i, ind in enumerate(indicators) if ind["id"] == selected_indicator_id_from_state)
         except StopIteration:
             # Se o indicador salvo não for mais encontrado (talvez deletado), reseta o estado
             st.session_state.editing_indicator_id = None
             st.session_state.current_formula_vars = []
             st.session_state.current_var_descriptions = {}
             st.session_state.current_variable_values = {}


    selected_indicator_name = st.selectbox("Selecione um indicador para editar:", indicator_names, index=initial_index if initial_index < len(indicator_names) else 0, key="edit_indicator_select")

    # Encontra o objeto indicador completo a partir do nome selecionado
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        # Se o indicador selecionado mudou ou é a primeira vez carregando, atualiza o estado
        if st.session_state.get('editing_indicator_id') != selected_indicator["id"]:
             st.session_state.editing_indicator_id = selected_indicator["id"]
             # Carrega as variáveis da fórmula e descrições existentes para o estado da sessão
             existing_formula = selected_indicator.get("formula", "")
             st.session_state.current_formula_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', existing_formula))))
             st.session_state.current_var_descriptions = selected_indicator.get("variaveis", {})
             # Garante que todas as variáveis detectadas na fórmula tenham uma entrada na descrição (mesmo que vazia)
             for var in st.session_state.current_formula_vars:
                  if var not in st.session_state.current_var_descriptions:
                       st.session_state.current_var_descriptions[var] = ""
             # Remove descrições de variáveis que não estão mais na fórmula
             vars_to_remove = [v for v in st.session_state.current_var_descriptions if v not in st.session_state.current_formula_vars]
             for var in vars_to_remove:
                 if var in st.session_state.current_var_descriptions:
                     del st.session_state.current_var_descriptions[var]
             # Reseta valores de teste ao mudar de indicador
             st.session_state.current_variable_values = {}
             st.session_state.current_test_result = None # Adiciona estado para o resultado do teste na edição

        # Chave para o estado de confirmação de exclusão (única por indicador)
        delete_state_key = f"delete_state_{selected_indicator['id']}"
        if delete_state_key not in st.session_state:
            st.session_state[delete_state_key] = None # 'None', 'confirming', 'deleting'

        # Formulário principal de edição
        with st.form(key=f"edit_form_{selected_indicator['id']}"): # Chave única para o formulário
            # Campos de entrada, preenchidos com os valores atuais do indicador
            nome = st.text_input("Nome do Indicador", value=selected_indicator["nome"])
            objetivo = st.text_area("Objetivo", value=selected_indicator["objetivo"])
            unidade = st.text_input("Unidade do Resultado", value=selected_indicator.get("unidade", ""), placeholder="Ex: %", key=f"edit_unidade_input_{selected_indicator['id']}")
            formula = st.text_input("Fórmula de Cálculo (Use letras para variáveis, ex: A+B/C)", value=selected_indicator.get("formula", ""), placeholder="Ex: (DEMISSOES / TOTAL_FUNCIONARIOS) * 100", key=f"edit_formula_input_{selected_indicator['id']}")

            # Verifica se as variáveis na fórmula mudaram e atualiza o estado da sessão
            current_detected_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', formula))))
            if st.session_state.current_formula_vars != current_detected_vars:
                 st.session_state.current_formula_vars = current_detected_vars
                 # Mantém descrições existentes para variáveis que ainda estão na nova fórmula
                 new_var_descriptions = {}
                 for var in current_detected_vars:
                      new_var_descriptions[var] = st.session_state.current_var_descriptions.get(var, "")
                 st.session_state.current_var_descriptions = new_var_descriptions
                 # Remove descrições de variáveis que não estão mais na nova fórmula
                 vars_to_remove = [v for v in st.session_state.current_var_descriptions if v not in st.session_state.current_formula_vars]
                 for var in vars_to_remove:
                     if var in st.session_state.current_var_descriptions:
                         del st.session_state.current_var_descriptions[var]


            st.markdown("---")
            st.subheader("Definição das Variáveis na Fórmula")
            # Exibe a seção de definição de variáveis se houver variáveis detectadas
            if st.session_state.current_formula_vars:
                st.info(f"Variáveis detectadas na fórmula: {', '.join(st.session_state.current_formula_vars)}")
                st.write("Defina a descrição para cada variável:")
                cols = st.columns(min(3, len(st.session_state.current_formula_vars)))
                new_var_descriptions = {}
                for i, var in enumerate(st.session_state.current_formula_vars):
                    col_idx = i % len(cols)
                    with cols[col_idx]:
                        # Input para a descrição de cada variável
                        new_var_descriptions[var] = st.text_input(
                            f"Descrição para '{var}'",
                            value=st.session_state.current_var_descriptions.get(var, ""),
                            placeholder=f"Ex: {var} - Número de Atendimentos",
                            key=f"desc_input_{var}_edit_{selected_indicator['id']}" # Chave única
                        )
                # Atualiza o estado da sessão com as descrições modificadas
                st.session_state.current_var_descriptions = new_var_descriptions
            else:
                st.warning("Nenhuma variável (letras) encontrada na fórmula. O resultado será um valor fixo.")
                st.session_state.current_var_descriptions = {} # Limpa descrições se não houver variáveis


            st.markdown("---")
            # Campos restantes do formulário de edição
            meta = st.number_input("Meta", value=float(selected_indicator.get("meta", 0.0)), step=0.01, format="%.2f")
            comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"], index=0 if selected_indicator.get("comparacao", "Maior é melhor") == "Maior é melhor" else 1)
            tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS, index=TIPOS_GRAFICOS.index(selected_indicator.get("tipo_grafico", "Linha")) if selected_indicator.get("tipo_grafico", "Linha") in TIPOS_GRAFICOS else 0)
            responsavel = st.selectbox("Setor Responsável", SETORES, index=SETORES.index(selected_indicator.get("responsavel", SETORES[0])) if selected_indicator.get("responsavel", SETORES[0]) in SETORES else 0) # Indicador ainda é responsável por um único setor

            # Botões Salvar e Excluir
            col1, col2, col3 = st.columns([1, 3, 1])
            # Ajuste o alinhamento do botão Salvar
            st.markdown("""<style>[data-testid="stForm"] div:nth-child(3) > div:first-child { text-align: right; }</style>""", unsafe_allow_html=True)
            with col1: submit = st.form_submit_button("💾 Salvar")
            with col3: delete_button_clicked = st.form_submit_button("️ Excluir", type="secondary")


            # Lógica ao clicar em Salvar
            if submit:
                # Validação da fórmula antes de salvar
                if formula:
                    try:
                        # Cria símbolos para as variáveis detectadas na fórmula submetida
                        vars_in_submitted_formula = sorted(list(set(re.findall(r'[a-zA-Z]+', formula))))
                        var_symbols = symbols(vars_in_submitted_formula)
                        # Tenta analisar a fórmula
                        sympify(formula, locals=dict(zip(vars_in_submitted_formula, var_symbols)))
                    except SympifyError as e:
                         st.error(f"❌ Erro na sintaxe da fórmula: {e}"); return # Impede salvar se a fórmula for inválida
                    except Exception as e:
                         st.error(f"❌ Erro inesperado ao validar a fórmula: {e}"); return # Impede salvar

                # Validação dos campos obrigatórios
                if nome and objetivo and formula: # Fórmula ainda é considerada obrigatória
                    # Verifica se o novo nome já existe em outro indicador
                    if nome != selected_indicator["nome"] and any(ind["nome"].strip().lower() == nome.strip().lower() for ind in indicators if ind["id"] != selected_indicator["id"]):
                        st.error(f"❌ Já existe um indicador com o nome '{nome}'.")
                    else:
                        # Atualiza o indicador na lista em memória
                        for ind in indicators:
                            if ind["id"] == selected_indicator["id"]:
                                ind["nome"] = nome
                                ind["objetivo"] = objetivo
                                ind["formula"] = formula
                                # Salva as descrições das variáveis a partir do estado da sessão
                                ind["variaveis"] = st.session_state.current_var_descriptions
                                ind["unidade"] = unidade
                                ind["meta"] = meta
                                ind["comparacao"] = comparacao
                                ind["tipo_grafico"] = tipo_grafico
                                ind["responsavel"] = responsavel
                                ind["data_atualizacao"] = datetime.now().isoformat()
                                break # Para o loop após encontrar e atualizar

                        save_indicators(indicators) # Salva a lista atualizada no banco de dados
                        st.session_state["indicators"] = load_indicators() # Recarrega do DB para garantir consistência

                        with st.spinner("Atualizando indicador..."):
                            st.success(f"✅ Indicador '{nome}' atualizado com sucesso!")
                            time.sleep(2) # Aguarda um pouco

                        # Limpa o estado da sessão relacionado à edição para voltar à seleção
                        st.session_state.editing_indicator_id = None
                        st.session_state.current_formula_vars = []
                        st.session_state.current_var_descriptions = {}
                        st.session_state.current_variable_values = {}
                        if 'current_test_result' in st.session_state: del st.session_state.current_test_result

                        scroll_to_top() # Rola para o topo
                        st.rerun() # Reinicia a aplicação

                else:
                    st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (Nome, Objetivo, Fórmula).")

            # Lógica ao clicar em Excluir (apenas define o estado para confirmar)
            if delete_button_clicked:
                 st.session_state[delete_state_key] = 'confirming'
                 st.rerun() # Reroda para mostrar a mensagem de confirmação

        # Mostra a mensagem de confirmação de exclusão
        if st.session_state.get(delete_state_key) == 'confirming':
            st.warning(f"Tem certeza que deseja excluir o indicador '{selected_indicator['nome']}'? Esta ação excluirá também todos os resultados associados e não poderá ser desfeita.")
            col1, col2 = st.columns(2)
            with col1:
                # Botão de confirmação da exclusão
                if st.button("✅ Sim, Excluir", key=f"confirm_delete_{selected_indicator['id']}"):
                    st.session_state[delete_state_key] = 'deleting' # Define estado para deletar
                    st.rerun() # Reroda para executar a exclusão
            with col2:
                # Botão de cancelar a exclusão
                if st.button("❌ Cancelar", key=f"cancel_delete_{selected_indicator['id']}"):
                    st.info("Exclusão cancelada.")
                    st.session_state[delete_state_key] = None # Reseta o estado de confirmação
                    st.rerun() # Reroda para remover a mensagem de confirmação

        # Executa a exclusão se o estado for 'deleting'
        if st.session_state.get(delete_state_key) == 'deleting':
            # Função para deletar no DB (implementada abaixo)
            delete_indicator(selected_indicator["id"], st.session_state.username)
            with st.spinner("Excluindo indicador..."):
                st.success(f"Indicador '{selected_indicator['nome']}' excluído com sucesso!")
                time.sleep(2) # Aguarda um pouco

            # Limpa o estado da sessão e reroda
            st.session_state[delete_state_key] = None
            st.session_state.editing_indicator_id = None
            st.session_state.current_formula_vars = []
            st.session_state.current_var_descriptions = {}
            st.session_state.current_variable_values = {}
            if 'current_test_result' in st.session_state: del st.session_state.current_test_result
            scroll_to_top()
            st.rerun() # Reinicia a aplicação

    st.markdown('</div>', unsafe_allow_html=True)

def delete_indicator(indicator_id, user_performed):
    """Exclui um indicador e seus resultados associados do banco de dados."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # A exclusão na tabela indicadores deve ser suficiente,
            # pois a chave estrangeira em 'resultados' tem ON DELETE CASCADE
            cur.execute("DELETE FROM indicadores WHERE id = %s;", (indicator_id,))
            conn.commit()
            log_indicator_action("Indicador excluído", indicator_id, user_performed)
            # Recarrega a lista de indicadores no estado da sessão após exclusão bem-sucedida
            # st.session_state["indicators"] = load_indicators() # Removido, load_indicators é chamado em edit_indicator ao entrar na página
            return True
        except psycopg2.Error as e:
            print(f"Erro ao excluir indicador do banco de dados: {e}")
            st.error(f"Erro ao excluir indicador: {e}") # Exibe erro no Streamlit
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Esta função não é mais usada diretamente para excluir resultados individuais no fill_indicator,
# a exclusão foi integrada diretamente no loop de exibição de resultados. Mantida para referência se necessário.
# def display_result_with_delete(result, selected_indicator):
#     """Exibe um resultado com a opção de excluir e ícone de status da meta."""
#     data_referencia = result.get('data_referencia')
#     if data_referencia:
#         col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
#         with col1: st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
#         with col2:
#             resultado = result.get('resultado', 'N/A'); unidade = selected_indicator.get('unidade', ''); meta = selected_indicator.get('meta', None); comparacao = selected_indicator.get('comparacao', 'Maior é melhor')
#             icone = ":white_circle:"
#             try:
#                 resultado_float = float(resultado); meta_float = float(meta)
#                 if comparacao == "Maior é melhor": icone = ":white_check_mark:" if resultado_float >= meta_float else ":x:"
#                 elif comparacao == "Menor é melhor": icone = ":white_check_mark:" if resultado_float <= meta_float else ":x:"
#             except (TypeError, ValueError): pass
#             st.markdown(f"{icone} **{resultado:.2f}{unidade}**")
#         with col3: st.write(result.get('observacao', 'N/A'))
#         with col4: st.write(result.get('status_analise', 'N/A'))
#         with col5: st.write(pd.to_datetime(result.get('data_atualizacao')).strftime("%d/%m/%Y %H:%M") if result.get('data_atualizacao') else 'N/A')
#         with col6:
#             # Botão de exclusão para este resultado específico
#             if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}_{selected_indicator['id']}_{datetime.now().timestamp()}"): # Chave mais única com timestamp
#                 # Chama a função para deletar o resultado no DB
#                 delete_result(selected_indicator['id'], data_referencia, st.session_state.username)
#                 # Recarrega os resultados após a exclusão para atualizar a exibição
#                 # (A exclusão está no loop de exibição em fill_indicator agora)
#                 # st.rerun() # delete_result já chama rerun
#     else:
#         st.warning("Resultado com data de referência ausente. Impossível exibir/excluir este resultado.")


def delete_result(indicator_id, data_referencia_str, user_performed):
    """Exclui um resultado específico de um indicador no banco de dados."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Converte a string de data de referência para datetime para a query
            data_referencia_dt = datetime.fromisoformat(data_referencia_str)
            cur.execute("""
                DELETE FROM resultados
                WHERE indicator_id = %s AND data_referencia = %s;
            """, (indicator_id, data_referencia_dt))
            conn.commit()
            # Log da ação de exclusão de resultado
            log_indicator_action(f"Resultado excluído para {data_referencia_str}", indicator_id, user_performed)
            st.success("Resultado excluído com sucesso!")
            time.sleep(1) # Pequeno delay antes do rerun
            st.rerun() # Reroda para atualizar a lista de resultados exibida
            return True
        except (ValueError, TypeError):
             st.error(f"Erro ao excluir resultado: Formato de data inválido para '{data_referencia_str}'.")
             return False
        except psycopg2.Error as e:
            print(f"Erro ao excluir resultado do banco de dados: {e}")
            st.error(f"Erro ao excluir resultado do banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False


def fill_indicator(SETORES, TEMA_PADRAO):
    """Mostra a página de preenchimento de indicador com calculadora dinâmica."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Preencher Indicador")
    # Carrega indicadores e resultados
    indicators = load_indicators()
    results = load_results()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Obter informações do usuário logado (agora user_sectors é uma lista)
    user_type = st.session_state.user_type
    user_sectors = st.session_state.user_sectors # Lista de setores
    user_name = st.session_state.get("username", "Usuário não identificado")

    # Filtrar indicadores para Operadores: só mostra indicadores onde o setor responsável está na lista de setores do usuário
    if user_type == "Operador":
        filtered_indicators = [ind for ind in indicators if ind["responsavel"] in user_sectors]
        if not filtered_indicators:
            sectors_display = ", ".join(user_sectors) if user_sectors else "nenhum setor associado"
            st.info(f"Não há indicadores associados a nenhum dos seus setores ({sectors_display}).")
            st.markdown('</div>', unsafe_allow_html=True)
            return
    else:
        # Administradores e Visualizadores veem todos os indicadores
        filtered_indicators = indicators


    indicator_names = [ind["nome"] for ind in filtered_indicators]
    # Use uma chave única para o selectbox de seleção de indicador
    selected_indicator_name = st.selectbox("Selecione um indicador para preencher:", indicator_names, key="select_indicator_fill")
    # Encontra o objeto indicador completo a partir do nome selecionado
    selected_indicator = next((ind for ind in filtered_indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        st.subheader(f"Informações do Indicador: {selected_indicator['nome']}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Objetivo:** {selected_indicator['objetivo']}\ Academia FIA Softworks")
            if selected_indicator.get("formula"):
                st.markdown(f"**Fórmula de Cálculo:** `{selected_indicator['formula']}`")
            else:
                st.markdown(f"**Fórmula de Cálculo:** Não definida (preenchimento direto)") # Mensagem clara
            st.markdown(f"**Unidade do Resultado:** {selected_indicator.get('unidade', 'Não definida')}")
        with col2:
            # Formatação da meta
            meta_display = f"{float(selected_indicator.get('meta', 0.0)):.2f}{selected_indicator.get('unidade', '')}"
            st.markdown(f"**Meta:** {meta_display}")
            st.markdown(f"**Comparação:** {selected_indicator['comparacao']}")
            st.markdown(f"**Setor Responsável:** {selected_indicator['responsavel']}") # Indicador ainda tem um único responsável

        # Seções de variáveis e preenchimento
        if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
            st.markdown("---")
            st.subheader("Variáveis do Indicador")
            vars_list = list(selected_indicator["variaveis"].items())
            if vars_list:
                # Exibe as variáveis e suas descrições
                cols = st.columns(min(3, len(vars_list)))
                for i, (var, desc) in enumerate(vars_list):
                    col_idx = i % len(cols)
                    with cols[col_idx]:
                        st.markdown(f"**{var}:** {desc or 'Sem descrição'}") # Exibe descrição ou um fallback
        st.markdown("---")

        # Obter resultados existentes para este indicador
        indicator_results = [r for r in results if r["indicator_id"] == selected_indicator["id"]]

        # Identificar períodos já preenchidos
        filled_periods = set()
        for result in indicator_results:
            if "data_referencia" in result:
                try:
                    # Converte para Period para comparar apenas Mês/Ano
                    date_ref = pd.to_datetime(result["data_referencia"]).to_period('M')
                    filled_periods.add(date_ref)
                except:
                    # Ignora resultados com data inválida
                    pass

        # Gerar lista de períodos disponíveis (últimos 5 anos + ano atual, até o mês atual)
        current_date = datetime.now()
        available_periods = []
        # Loop pelos anos
        for year in range(current_date.year - 5, current_date.year + 1):
            # Loop pelos meses
            for month in range(1, 13):
                period = pd.Period(year=year, month=month, freq='M')
                # Ignora períodos futuros
                if period > pd.Period(current_date, freq='M'):
                    continue
                # Adiciona o período se ainda não foi preenchido
                if period not in filled_periods:
                    available_periods.append(period)

        # Se não há períodos disponíveis para preencher
        if not available_periods:
            st.info("Todos os períodos relevantes já foram preenchidos para este indicador.")
        else:
            st.subheader("Adicionar Novo Resultado")
            # Formulário para adicionar um novo resultado
            with st.form(key=f"add_result_form_{selected_indicator['id']}"): # Chave única para o formulário

                # Ordena os períodos disponíveis do mais recente para o mais antigo
                available_periods.sort(reverse=True)
                # Cria as opções para o selectbox
                period_options = [f"{p.strftime('%B/%Y')}" for p in available_periods]
                # Seleciona o período
                selected_period_str = st.selectbox("Selecione o período para preenchimento:", period_options)
                # Encontra o objeto Period selecionado
                selected_period = next((p for p in available_periods if p.strftime('%B/%Y') == selected_period_str), None)
                # Extrai mês e ano
                selected_month, selected_year = selected_period.month, selected_period.year if selected_period else (None, None)

                calculated_result = None
                # Verifica se o indicador tem fórmula e variáveis para o cálculo
                if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                    st.markdown("#### Valores das Variáveis")
                    st.info(f"Insira os valores para calcular o resultado usando a fórmula: `{selected_indicator['formula']}`")

                    vars_to_fill = list(selected_indicator["variaveis"].items())
                    if vars_to_fill:
                        # Inputs para os valores das variáveis
                        variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                        # Inicializa o estado da sessão para armazenar os valores dos inputs para este período/indicador
                        if variable_values_key not in st.session_state:
                             st.session_state[variable_values_key] = {}

                        cols = st.columns(min(3, len(vars_to_fill)))
                        for i, (var, desc) in enumerate(vars_to_fill):
                            col_idx = i % len(cols)
                            with cols[col_idx]:
                                # Input para cada variável, recuperando o valor do estado da sessão
                                default_value = st.session_state[variable_values_key].get(var, 0.0)
                                st.session_state[variable_values_key][var] = st.number_input(
                                    f"{var} ({desc or 'Sem descrição'})",
                                    value=float(default_value), # Garante que o valor inicial seja float
                                    step=0.01,
                                    format="%.2f",
                                    key=f"var_input_{var}_{selected_indicator['id']}_{selected_period_str}" # Chave única
                                )

                        # Botão para calcular o resultado usando a fórmula e os valores inseridos
                        test_button_clicked = st.form_submit_button("✨ Calcular Resultado")

                        # Chave para armazenar o resultado calculado no estado da sessão
                        calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"

                        # Exibe o resultado calculado se ele existir no estado da sessão
                        if st.session_state.get(calculated_result_state_key) is not None:
                            calculated_result = st.session_state[calculated_result_state_key]
                            result_display = f"{calculated_result:.2f}{selected_indicator.get('unidade', '')}"
                            st.markdown(f"**Resultado Calculado:** **{result_display}**")

                            # Compara o resultado calculado com a meta
                            meta_valor = float(selected_indicator.get('meta', 0.0))
                            comparacao_tipo = selected_indicator['comparacao']

                            if comparacao_tipo == "Maior é melhor":
                                if calculated_result >= meta_valor:
                                    st.success(f"🎉 Meta Atingida! O resultado ({result_display}) é maior ou igual à meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                                else:
                                    st.warning(f"⚠️ Meta Não Atingida. O resultado ({result_display}) é menor que a meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                            elif comparacao_tipo == "Menor é melhor":
                                if calculated_result <= meta_valor:
                                    st.success(f"🎉 Meta Atingida! O resultado ({result_display}) é menor ou igual à meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                                else:
                                    st.warning(f"⚠️ Meta Não Atingida. O resultado ({result_display}) é maior que a meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")

                    else:
                        # Caso o indicador tenha fórmula mas não tenha variáveis definidas
                        st.warning("O indicador tem uma fórmula, mas nenhuma variável definida. O resultado será um valor fixo.")
                        # Input direto para o resultado neste caso especial
                        resultado_input_value = st.number_input(
                            "Resultado",
                            step=0.01,
                            format="%.2f",
                            key=f"direct_result_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                        )
                        # Garante que o estado de variáveis e resultado calculado esteja limpo
                        variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                        st.session_state[variable_values_key] = {}
                        calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"
                        st.session_state[calculated_result_state_key] = None

                else:
                    # Caso o indicador NÃO tenha fórmula (preenchimento direto do resultado)
                    resultado_input_value = st.number_input(
                        "Resultado",
                        step=0.01,
                        format="%.2f",
                        key=f"direct_result_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                    )
                    # Garante que o estado de variáveis e resultado calculado esteja limpo
                    variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                    st.session_state[variable_values_key] = {}
                    calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"
                    st.session_state[calculated_result_state_key] = None


                # Área para observações e Análise Crítica (5W2H)
                observacoes = st.text_area(
                    "Observações (opcional)",
                    placeholder="Adicione informações relevantes sobre este resultado",
                    key=f"obs_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                st.markdown("### Análise Crítica (5W2H)")
                st.markdown("""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;"><p style="margin: 0; font-size: 14px;">A metodologia 5W2H ajuda a estruturar a análise crítica de forma completa, abordando todos os aspectos relevantes da situação.</p></div>""", unsafe_allow_html=True)
                # Inputs para os campos do 5W2H
                what = st.text_area(
                    "O que (What)",
                    placeholder="O que está acontecendo? Qual é a situação atual do indicador?",
                    key=f"what_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                why = st.text_area(
                    "Por que (Why)",
                    placeholder="Por que isso está acontecendo? Quais são as causas?",
                    key=f"why_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                who = st.text_area(
                    "Quem (Who)",
                    placeholder="Quem é responsável? Quem está envolvido?",
                    key=f"who_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                when = st.text_area(
                    "Quando (When)",
                    placeholder="Quando isso aconteceu? Qual é o prazo para resolução?",
                    key=f"when_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                where = st.text_area(
                    "Onde (Where)",
                    placeholder="Onde ocorre a situação? Em qual processo ou área?",
                    key=f"where_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                how = st.text_area(
                    "Como (How)",
                    placeholder="Como resolver a situação? Quais ações devem ser tomadas?",
                    key=f"how_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )
                howMuch = st.text_area(
                    "Quanto custa (How Much)",
                    placeholder="Quanto custará implementar a solução? Quais recursos são necessários?",
                    key=f"howmuch_input_{selected_indicator['id']}_{selected_period_str}" # Chave única
                )

                # Botão principal para salvar o resultado
                submitted = st.form_submit_button("✔️ Salvar")

            # Lógica ao clicar no botão "Calcular Resultado" (fora do form principal)
            # Este bloco é executado APÓS o form principal ser processado,
            # mas as ações dentro dele (como rerun) afetam o próximo ciclo.
            if test_button_clicked:
                formula_str = selected_indicator.get("formula", "")
                variable_values = st.session_state.get(variable_values_key, {})
                # A lógica de cálculo já está na seção de teste dentro do formulário.
                # Apenas garantimos que o rerun aconteça.
                st.rerun()

            # Lógica ao clicar no botão "Salvar"
            elif submitted:
                final_result_to_save = None
                values_to_save = {}

                # Determina qual resultado salvar: o calculado (se houver fórmula) ou o inserido diretamente
                if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                    final_result_to_save = st.session_state.get(calculated_result_state_key)
                    values_to_save = st.session_state.get(variable_values_key, {})
                    if final_result_to_save is None: # Se clicou em salvar mas não calculou
                        st.warning("⚠️ Por favor, calcule o resultado antes de salvar.")
                        return # Para a execução se o resultado calculado for nulo
                else:
                    # Se não há fórmula, pega o valor do input direto
                    final_result_to_save = resultado_input_value
                    values_to_save = {} # Não há variáveis para salvar

                # Se temos um resultado para salvar
                if final_result_to_save is not None:
                    # Formata a data de referência para salvar no DB
                    data_referencia_iso = datetime(selected_year, selected_month, 1).isoformat()

                    # Coleta os dados da análise crítica
                    analise_critica = {
                        "what": what,
                        "why": why,
                        "who": who,
                        "when": when,
                        "where": where,
                        "how": how,
                        "howMuch": howMuch
                    }
                    # Calcula o status de preenchimento da análise crítica
                    status_analise = get_analise_status(analise_critica)
                    analise_critica["status_preenchimento"] = status_analise # Salva o status na análise

                    # Cria o objeto do novo resultado
                    new_result = {
                        "indicator_id": selected_indicator["id"],
                        "data_referencia": data_referencia_iso,
                        "resultado": final_result_to_save,
                        "valores_variaveis": values_to_save, # Salva os valores das variáveis
                        "observacao": observacoes,
                        "analise_critica": analise_critica, # Salva a análise crítica completa
                        "data_criacao": datetime.now().isoformat(),
                        "data_atualizacao": datetime.now().isoformat(), # Usa data atual para atualização
                        "usuario": user_name, # Salva o nome do usuário que preencheu
                        "status_analise": status_analise # Salva o status da análise
                    }

                    # Carrega todos os resultados, remove o resultado existente para o período (se houver) e adiciona o novo/atualizado
                    all_results = load_results()
                    all_results = [r for r in all_results if not (r["indicator_id"] == new_result["indicator_id"] and r["data_referencia"] == new_result["data_referencia"])]
                    all_results.append(new_result)

                    # Salva a lista atualizada de resultados no DB
                    save_results(all_results)

                    with st.spinner("Salvando resultado..."):
                        st.success(f"✅ Resultado adicionado/atualizado com sucesso para {datetime(selected_year, selected_month, 1).strftime('%B/%Y')}!")
                        time.sleep(2) # Pequeno delay

                    # Limpa o estado da sessão associado ao formulário de preenchimento para este período/indicador
                    if variable_values_key in st.session_state:
                        del st.session_state[variable_values_key]
                    if calculated_result_state_key in st.session_state:
                        del st.session_state[calculated_result_state_key]
                    # Limpar inputs de texto (observacoes e 5w2h) - Streamlit geralmente faz isso sozinho em reruns de formulários, mas podemos limpar explicitamente se necessário
                    # del st.session_state[f"obs_input_{selected_indicator['id']}_{selected_period_str}"] # Exemplo
                    scroll_to_top() # Rola para o topo
                    st.rerun() # Reinicia a aplicação
                else:
                    st.warning("⚠️ Por favor, informe o resultado ou calcule-o antes de salvar.")


        st.subheader("Resultados Anteriores")
        # Exibe a lista de resultados anteriores para o indicador selecionado
        if indicator_results:
            # Ordena os resultados pelo período (data_referencia) do mais recente para o mais antigo
            indicator_results_sorted = sorted(indicator_results, key=lambda x: x.get("data_referencia", ""), reverse=True)

            unidade_display = selected_indicator.get('unidade', '') # Unidade do indicador

            # Define as colunas da tabela de acordo com a existência de variáveis na fórmula
            if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                # Colunas: Período, Valores das Variáveis, Resultado, Observações, Análise Crítica, Ações
                cols_header = st.columns([1.5] + [1] * len(selected_indicator["variaveis"]) + [1.5, 2, 2, 1])
                # Cabeçalhos das colunas
                with cols_header[0]: st.markdown("**Período**")
                for i, var in enumerate(selected_indicator["variaveis"].keys()):
                    with cols_header[i+1]:
                        st.markdown(f"**{var}**") # Nome da variável como cabeçalho
                with cols_header[len(selected_indicator["variaveis"])+1]: st.markdown(f"**Resultado ({unidade_display})**")
                with cols_header[len(selected_indicator["variaveis"])+2]: st.markdown("**Observações**")
                with cols_header[len(selected_indicator["variaveis"])+3]: st.markdown("**Análise Crítica**")
                with cols_header[len(selected_indicator["variaveis"])+4]: st.markdown("**Ações**")

                # Loop pelos resultados e exibe os dados em colunas
                for result in indicator_results_sorted:
                    cols_data = st.columns([1.5] + [1] * len(selected_indicator["variaveis"]) + [1.5, 2, 2, 1])
                    data_referencia = result.get('data_referencia')
                    if data_referencia:
                        # Período
                        with cols_data[0]:
                            try: st.write(pd.to_datetime(data_referencia).strftime("%B/%Y")) # Formato Mês/Ano
                            except: st.write(data_referencia) # Fallback

                        # Valores das variáveis
                        valores_vars = result.get("valores_variaveis", {})
                        for i, var in enumerate(selected_indicator["variaveis"].keys()):
                            with cols_data[i+1]:
                                var_value = valores_vars.get(var)
                                if isinstance(var_value, (int, float)):
                                    st.write(f"{var_value:.2f}") # Formata valores numéricos
                                else:
                                    st.write('N/A')

                        # Resultado e status da meta
                        with cols_data[len(selected_indicator["variaveis"])+1]:
                            result_value = result.get('resultado')
                            unidade = selected_indicator.get('unidade', '')
                            meta = selected_indicator.get('meta', None)
                            comparacao = selected_indicator.get('comparacao', 'Maior é melhor')
                            icone = ":white_circle:" # Ícone padrão
                            try:
                                # Tenta converter para float para comparação
                                resultado_float = float(result_value)
                                meta_float = float(meta)
                                if comparacao == "Maior é melhor":
                                    icone = ":white_check_mark:" if resultado_float >= meta_float else ":x:" # Ícone de check/x
                                elif comparacao == "Menor é melhor":
                                    icone = ":white_check_mark:" if resultado_float <= meta_float else ":x:" # Ícone de check/x
                            except (TypeError, ValueError):
                                # Se a conversão falhar, mantém o ícone padrão
                                pass
                            if isinstance(result_value, (int, float)):
                                st.markdown(f"{icone} **{result_value:.2f}{unidade}**") # Exibe resultado formatado com ícone
                            else:
                                st.write('N/A') # Exibe N/A se o resultado não for numérico

                        # Observações
                        with cols_data[len(selected_indicator["variaveis"])+2]:
                            st.write(result.get('observacao', 'N/A')) # Exibe observação ou N/A

                        # Análise Crítica
                        with cols_data[len(selected_indicator["variaveis"])+3]:
                            analise_critica_dict = result.get('analise_critica', {})
                            status_analise = get_analise_status(analise_critica_dict) # Obtém o status de preenchimento
                            st.write(status_analise) # Exibe o status

                            # Exibe os detalhes da análise crítica em um expander se houver algum campo preenchido
                            if any(analise_critica_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                                with st.expander("Ver Análise"):
                                    st.markdown("**O que:** " + analise_critica_dict.get("what", ""))
                                    st.markdown("**Por que:** " + analise_critica_dict.get("why", ""))
                                    st.markdown("**Quem:** " + analise_critica_dict.get("who", ""))
                                    st.markdown("**Quando:** " + analise_critica_dict.get("when", ""))
                                    st.markdown("**Onde:** " + analise_critica_dict.get("where", ""))
                                    st.markdown("**Como:** " + analise_critica_dict.get("how", ""))
                                    st.markdown("**Quanto custa:** " + analise_critica_dict.get("howMuch", ""))

                        # Botão de exclusão para este resultado
                        with cols_data[len(selected_indicator["variaveis"])+4]:
                             # Adiciona uma chave única para cada botão de exclusão
                            if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}_{selected_indicator['id']}_fill"):
                                # Chama a função para deletar o resultado
                                delete_result(selected_indicator['id'], data_referencia, st.session_state.username)
                                # O delete_result já chama st.rerun() se for bem-sucedido

                    else:
                         # Mensagem de aviso se o resultado não tiver data de referência
                         st.warning("Resultado com data de referência ausente. Impossível exibir/excluir.")
            else:
                # Layout da tabela se o indicador NÃO tem fórmula (preenchimento direto)
                # Colunas: Período, Resultado, Observações, Análise Crítica, Data de Atualização, Ações
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 2, 2, 2, 1])
                # Cabeçalhos
                with col1: st.markdown("**Período**")
                with col2: st.markdown(f"**Resultado ({unidade_display})**")
                with col3: st.markdown("**Observações**")
                with col4: st.markdown("**Análise Crítica**")
                with col5: st.markdown("**Atualizado em**")
                with col6: st.markdown("**Ações**")

                # Loop pelos resultados
                for result in indicator_results_sorted:
                    data_referencia = result.get('data_referencia')
                    if data_referencia:
                        # Dados do resultado nas colunas
                        col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 2, 2, 2, 1])
                        # Período
                        with col1:
                            try: st.write(pd.to_datetime(data_referencia).strftime("%B/%Y")) # Formato Mês/Ano
                            except: st.write(data_referencia) # Fallback

                        # Resultado
                        with col2:
                            result_value = result.get('resultado')
                            if isinstance(result_value, (int, float)):
                                st.write(f"{result_value:.2f}{unidade_display}") # Exibe resultado formatado
                            else:
                                st.write('N/A') # Exibe N/A

                        # Observações
                        with col3:
                            st.write(result.get('observacao', 'N/A')) # Exibe observação ou N/A

                        # Análise Crítica
                        with col4:
                            analise_critica_dict = result.get('analise_critica', {})
                            status_analise = get_analise_status(analise_critica_dict) # Obtém o status
                            st.write(status_analise) # Exibe o status
                            # Exibe detalhes da análise em expander se houver campos preenchidos
                            if any(analise_critica_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                                with st.expander("Ver Análise"):
                                    st.markdown("**O que:** " + analise_critica_dict.get("what", ""))
                                    st.markdown("**Por que:** " + analise_critica_dict.get("why", ""))
                                    st.markdown("**Quem:** " + analise_critica_dict.get("who", ""))
                                    st.markdown("**Quando:** " + analise_critica_dict.get("when", ""))
                                    st.markdown("**Onde:** " + analise_critica_dict.get("where", ""))
                                    st.markdown("**Como:** " + analise_critica_dict.get("how", ""))
                                    st.markdown("**Quanto custa:** " + analise_critica_dict.get("howMuch", ""))

                        # Data de Atualização
                        with col5:
                            st.write(pd.to_datetime(result.get('data_atualizacao')).strftime("%d/%m/%Y %H:%M") if result.get('data_atualizacao') else 'N/A') # Exibe data formatada ou N/A

                        # Botão de exclusão
                        with col6:
                             # Adiciona uma chave única para cada botão de exclusão
                            if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}_{selected_indicator['id']}_fill"):
                                # Chama a função para deletar o resultado
                                delete_result(selected_indicator['id'], data_referencia, st.session_state.username)
                                # O delete_result já chama st.rerun() se for bem-sucedido

                    else:
                         # Mensagem de aviso se o resultado não tiver data de referência
                         st.warning("Resultado com data de referência ausente. Impossível exibir/excluir.")

        else:
            st.info("Nenhum resultado registrado para este indicador.") # Mensagem se não houver resultados anteriores

        st.markdown("---")
        # Expander para o log de preenchimentos
        # Carrega os logs de resultados especificamente para este indicador
        all_results_log = load_results()
        log_results = [r for r in all_results_log if r.get("indicator_id") == selected_indicator["id"]]
        # Ordena os logs pela data de atualização
        log_results = sorted(log_results, key=lambda x: x.get("data_atualizacao", x.get("data_criacao", "")), reverse=True) # Usa data_criacao como fallback

        with st.expander("📜 Log de Preenchimentos (clique para visualizar)", expanded=False):
            if log_results:
                log_data_list = []
                unidade_log = selected_indicator.get('unidade', '') # Unidade para exibir nos resultados salvos

                for r in log_results:
                    # Formata o resultado salvo para exibição
                    result_saved_display = r.get("resultado")
                    if isinstance(result_saved_display, (int, float)):
                        result_saved_display = f"{result_saved_display:.2f}{unidade_log}"
                    else:
                        result_saved_display = "N/A"

                    # Formata os valores das variáveis salvas para exibição
                    valores_vars = r.get("valores_variaveis", {})
                    if valores_vars:
                        # Cria uma string "Variável=Valor" para cada variável
                        valores_vars_display = ", ".join([f"{v}={float(val):.2f}" if isinstance(val, (int, float)) else f"{v}={val}" for v, val in valores_vars.items()])
                    else:
                        valores_vars_display = "N/A"

                    # Cria a entrada do log
                    log_entry = {
                        "Período": pd.to_datetime(r.get("data_referencia")).strftime("%B/%Y") if r.get("data_referencia") else "N/A",
                        "Resultado Salvo": result_saved_display,
                        "Valores Variáveis": valores_vars_display,
                        "Usuário": r.get("usuario", "System"),
                        "Status Análise Crítica": get_analise_status(r.get("analise_critica", {})), # Status da análise
                        "Data/Hora Preenchimento": pd.to_datetime(r.get("data_atualizacao", r.get("data_criacao", datetime.now().isoformat()))).strftime("%d/%m/%Y %H:%M") # Data/Hora da atualização ou criação
                    }
                    log_data_list.append(log_entry) # Adiciona à lista de logs

                # Cria um DataFrame e exibe na tabela
                log_df = pd.DataFrame(log_data_list)
                # Define a ordem das colunas
                cols_order = ["Período", "Resultado Salvo", "Valores Variáveis", "Usuário", "Status Análise Crítica", "Data/Hora Preenchimento"]
                log_df = log_df[cols_order]
                st.dataframe(log_df, use_container_width=True)
            else:
                st.info("Nenhum registro de preenchimento encontrado para este indicador.") # Mensagem se não houver logs
    st.markdown('</div>', unsafe_allow_html=True)

# Função auxiliar para obter o status de preenchimento da análise crítica
def get_analise_status(analise_dict):
    """Função auxiliar para verificar o status de preenchimento da análise crítica."""
    if not analise_dict or analise_dict == {}:
        return "❌ Não preenchida"

    # Verifica se o status já está salvo na própria análise (compatibilidade)
    if "status_preenchimento" in analise_dict:
        return analise_dict["status_preenchimento"]

    # Se não estiver salvo, calcula o status
    campos_relevantes = ["what", "why", "who", "when", "where", "how", "howMuch"]
    # Conta quantos campos têm conteúdo não vazio após remover espaços
    campos_preenchidos = sum(1 for campo in campos_relevantes if campo in analise_dict and analise_dict[campo] and analise_dict[campo].strip())
    total_campos = len(campos_relevantes)

    if campos_preenchidos == 0: return "❌ Não preenchida"
    elif campos_preenchidos == total_campos: return "✅ Preenchida completamente"
    else: return f"⚠️ Preenchida parcialmente ({campos_preenchidos}/{total_campos})"


def show_dashboard(SETORES, TEMA_PADRAO):
    """Mostra o dashboard de indicadores."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Dashboard de Indicadores")
    # Carrega indicadores e resultados
    indicators = load_indicators()
    results = load_results()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Obter informações do usuário logado
    user_type = st.session_state.user_type
    user_sectors = st.session_state.user_sectors # Lista de setores

    col1, col2 = st.columns(2)
    with col1:
        # Filtro de setor agora para dashboard
        setores_disponiveis = sorted(list(set([ind["responsavel"] for ind in indicators])))
        filter_options = ["Todos"] + setores_disponiveis

        # Adapta as opções de filtro para Operadores
        if user_type == "Operador":
             # Operadores só podem filtrar pelos seus próprios setores ou "Todos"
             # Cria a lista de opções permitidas para o operador
             allowed_filter_options = ["Todos"] + [s for s in setores_disponiveis if s in user_sectors]
             # Remove duplicatas e mantém a ordem se "Todos" for a primeira opção
             unique_allowed_filter_options = []
             for item in allowed_filter_options:
                 if item not in unique_allowed_filter_options:
                     unique_allowed_filter_options.append(item)

             # Define o filtro padrão. Se o operador tem setores associados, tenta default para eles.
             default_filter = ["Todos"]
             if user_sectors and any(s in unique_allowed_filter_options for s in user_sectors):
                  default_filter = [s for s in user_sectors if s in unique_allowed_filter_options]
                  if not default_filter: default_filter = ["Todos"] # Fallback se nenhum dos setores do usuário estiver na lista disponível

             setor_filtro = st.multiselect("Filtrar por Setor:", unique_allowed_filter_options, default=default_filter, key="dashboard_setor_filter")


        else:
            # Administradores e Visualizadores podem filtrar por qualquer setor
            setor_filtro = st.multiselect("Filtrar por Setor:", filter_options, default=["Todos"], key="dashboard_setor_filter")

    with col2:
        status_options = ["Todos", "Acima da Meta", "Abaixo da Meta", "Sem Resultados", "N/A"] # Inclui N/A
        status_filtro = st.multiselect("Filtrar por Status:", status_options, default=["Todos"], key="dashboard_status_filter")

    # Aplica o filtro por setor
    filtered_indicators = indicators
    if setor_filtro and "Todos" not in setor_filtro:
        filtered_indicators = [ind for ind in indicators if ind["responsavel"] in setor_filtro]
    # Se user é Operador, aplica filtro adicional baseado nos setores DO USUÁRIO, *depois* do filtro de setor selecionado na UI
    # Isso garante que um Operador só veja indicadores dos SEUS setores, mesmo que selecione "Todos" no filtro da UI
    # E se selecionar setores específicos na UI, veja apenas a intersecção entre seus setores e os selecionados.
    if user_type == "Operador" and user_sectors and "Todos" not in user_sectors:
         filtered_indicators = [ind for ind in filtered_indicators if ind["responsavel"] in user_sectors]


    if not filtered_indicators:
        selected_setor_display = ", ".join(setor_filtro) if setor_filtro else "selecionado(s)"
        st.warning(f"Nenhum indicador encontrado para o(s) setor(es) {selected_setor_display}.\n")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    st.subheader("Resumo dos Indicadores")
    total_indicators = len(filtered_indicators)
    indicators_with_results = 0
    indicators_above_target = 0
    indicators_below_target = 0
    indicators_na_status = 0 # Contador para status N/A

    # Calcula os resumos
    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        if ind_results:
            indicators_with_results += 1
            # Encontra o último resultado
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)
            last_result_obj = df_results.iloc[0]
            last_result = last_result_obj["resultado"]
            meta = float(ind.get("meta", 0.0)) # Garante que a meta é float

            try:
                last_result_float = float(last_result)
                if ind["comparacao"] == "Maior é melhor":
                    if last_result_float >= meta: indicators_above_target += 1
                    else: indicators_below_target += 1
                else: # Menor é melhor
                    if last_result_float <= meta: indicators_above_target += 1
                    else: indicators_below_target += 1
            except (TypeError, ValueError):
                 # Se o resultado não é numérico, conta como N/A para status de meta
                 indicators_na_status += 1


    # Exibe os cartões de resumo
    # Ajusta a largura das colunas se necessário, ou mantém 4 colunas
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#1E88E5;">{total_indicators}</h3><p style="margin:0;">Total de Indicadores</p></div>""", unsafe_allow_html=True)
    with col2: st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#1E88E5;">{indicators_with_results}</h3><p style="margin:0;">Com Resultados</p></div>""", unsafe_allow_html=True)
    with col3: st.markdown(f"""<div style="background-color:#26A69A; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{indicators_above_target}</h3><p style="margin:0; color:white;">Acima/Dentro da Meta</p></div>""", unsafe_allow_html=True) # Texto ajustado
    with col4: st.markdown(f"""<div style="background-color:#FF5252; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{indicators_below_target}</h3><p style="margin:0; color:white;">Abaixo/Fora da Meta</p></div>""" if indicators_below_target > 0 else f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#37474F;">{indicators_below_target}</h3><p style="margin:0;">Abaixo/Fora da Meta</p></div>""", unsafe_allow_html=True) # Texto e cor ajustados


    st.subheader("Status dos Indicadores")
    # Dados para o gráfico de pizza de status
    status_data = {"Status": ["Acima/Dentro da Meta", "Abaixo/Fora da Meta", "Sem Resultados", "Status N/A"], "Quantidade": [indicators_above_target, indicators_below_target, total_indicators - indicators_with_results, indicators_na_status]} # Inclui N/A
    df_status = pd.DataFrame(status_data)
    # Mapeamento de cores para os status
    status_color_map = {"Acima/Dentro da Meta": "#26A69A", "Abaixo/Fora da Meta": "#FF5252", "Sem Resultados": "#9E9E9E", "Status N/A": "#607D8B"} # Adicionado cor para N/A

    # Cria o gráfico de pizza - filtra status com quantidade 0 para não aparecer na legenda
    df_status_filtered = df_status[df_status['Quantidade'] > 0]
    if not df_status_filtered.empty:
         fig_status = px.pie(df_status_filtered, names="Status", values="Quantidade", title="Distribuição de Status dos Indicadores", color="Status", color_discrete_map=status_color_map)
         st.plotly_chart(fig_status, use_container_width=True) # Exibe o gráfico
    else:
         st.info("Não há dados de status para exibir o gráfico.")


    st.subheader("Indicadores")
    indicator_data = [] # Lista para armazenar dados de exibição de cada indicador

    # Prepara os dados para exibição detalhada de cada indicador
    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        unidade_display = ind.get('unidade', '') # Unidade do indicador

        last_result = "N/A"
        data_formatada = "N/A"
        status = "Sem Resultados" # Status padrão
        variacao = 0 # Variação vs Meta (numérico)
        last_result_float = None # Resultado float para análise automática

        if ind_results:
            # Encontra o último resultado para cálculo de status e variação
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)
            last_result_obj = df_results.iloc[0]
            last_result = last_result_obj["resultado"]
            last_date = last_result_obj["data_referencia"]

            try:
                # Calcula status e variação se o último resultado for numérico
                meta = float(ind.get("meta", 0.0)) # Garante que a meta é float
                last_result_float = float(last_result) # Tenta converter resultado para float

                if ind["comparacao"] == "Maior é melhor": status = "Acima da Meta" if last_result_float >= meta else "Abaixo da Meta"
                else: status = "Acima da Meta" if last_result_float <= meta else "Abaixo da Meta"

                if meta != 0:
                    variacao = ((last_result_float / meta) - 1) * 100
                    # Se menor é melhor, a variação positiva é ruim (abaixo da meta) e vice-versa
                    if ind["comparacao"] == "Menor é melhor": variacao = -variacao # Inverte o sinal da variação
                else:
                    # Lida com meta zero para variação
                    if last_result_float > 0: variacao = float('inf') # Infinito positivo
                    elif last_result_float < 0: variacao = float('-inf') # Infinito negativo
                    else: variacao = 0 # Zero se resultado e meta são zero

            except (TypeError, ValueError):
                 # Se o resultado não é numérico, o status de meta é N/A
                 status = "N/A"
                 variacao = 0 # Reseta variação numérica
                 last_result_float = None # Reseta resultado float

            # Formata a data do último resultado
            data_formatada = format_date_as_month_year(last_date)

        # Adiciona os dados preparados à lista
        indicator_data.append({
            "indicator": ind,
            "last_result": last_result,
            "last_result_float": last_result_float, # Armazena o float para análise automática
            "data_formatada": data_formatada,
            "status": status,
            "variacao": variacao, # Mantém o valor numérico (pode ser inf)
            "results": ind_results # Inclui todos os resultados para exibir o histórico
        })

    # Aplica o filtro de status, se selecionado (exceto "Todos")
    if status_filtro and "Todos" not in status_filtro:
        indicator_data = [d for d in indicator_data if d["status"] in status_filtro]

    # Exibe a mensagem se nenhum indicador for encontrado após os filtros
    if not indicator_data:
        st.warning("Nenhum indicador encontrado com os filtros selecionados.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Exibe os detalhes de cada indicador filtrado
    for i, data in enumerate(indicator_data):
        ind = data["indicator"]
        unidade_display = ind.get('unidade', '')

        # Card de exibição para o indicador
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:20px;">
            <h3 style="margin:0; color:#1E88E5;">{ind['nome']}</h3>
            <p style="margin:5px 0; color:#546E7A;">Setor: {ind['responsavel']}</p>
        </div>
        """, unsafe_allow_html=True)

        # Exibe o gráfico se houver resultados
        if data["results"]:
            fig = create_chart(ind["id"], ind["tipo_grafico"], TEMA_PADRAO)
            if fig: # Garante que o gráfico foi criado com sucesso
                 st.plotly_chart(fig, use_container_width=True) # Exibe o gráfico

            # Exibe os cartões de resumo do último resultado
            col1, col2, col3 = st.columns(3)
            with col1:
                meta_display = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
                st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;"><p style="margin:0; font-size:12px; color:#666;">Meta</p><p style="margin:0; font-weight:bold; font-size:18px;">{meta_display}</p></div>""", unsafe_allow_html=True)
            with col2:
                # Define a cor do status
                status_color = "#26A69A" if data["status"] == "Acima da Meta" else "#FF5252" if data["status"] == "Abaixo da Meta" else "#9E9E9E" # Cor para Sem Resultados/N/A
                # Formata o último resultado para exibição
                last_result_display = f"{float(data['last_result']):.2f}{unidade_display}" if isinstance(data['last_result'], (int, float)) else "N/A"
                st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;"><p style="margin:0; font-size:12px; color:#666;">Último Resultado ({data['data_formatada']})</p><p style="margin:0; font-weight:bold; font-size:18px; color:{status_color};">{last_result_display}</p></div>""", unsafe_allow_html=True)
            with col3:
                # Define a cor da variação
                variacao_color = "#26A69A" if (data["variacao"] >= 0 and ind["comparacao"] == "Maior é melhor") or (data["variacao"] <= 0 and ind["comparacao"] == "Menor é melhor") else "#FF5252" if (data["variacao"] < 0 and ind["comparacao"] == "Maior é melhor") or (data["variacao"] > 0 and ind["comparacao"] == "Menor é melhor") else "#9E9E9E" # Cor neutra para N/A ou 0%
                # Formata a variação para exibição (lidando com infinitos e N/A)
                if data['variacao'] == float('inf'): variacao_text = "+∞%"; variacao_color = "#26A69A" if ind["comparacao"] == "Maior é melhor" else "#FF5252"
                elif data['variacao'] == float('-inf'): variacao_text = "-∞%"; variacao_color = "#26A69A" if ind["comparacao"] == "Menor é melhor" else "#FF5252"
                elif isinstance(data['variacao'], (int, float)): variacao_text = f"{data['variacao']:.2f}%"
                else: variacao_text = "N/A" # Variação N/A se o cálculo falhou
                st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;"><p style="margin:0; font-size:12px; color:#666;">Variação vs Meta</p><p style="margin:0; font-weight:bold; font-size:18px; color:{variacao_color};">{variacao_text}</p></div>""", unsafe_allow_html=True)

            # Expander para a série histórica e análise crítica
            with st.expander("Ver Série Histórica e Análise Crítica"):
                if data["results"]:
                    # Prepara DataFrame para a série histórica
                    df_hist = pd.DataFrame(data["results"])
                    df_hist["data_referencia"] = pd.to_datetime(df_hist["data_referencia"])
                    df_hist = df_hist.sort_values("data_referencia", ascending=False)

                    # Calcula o status para cada resultado na série histórica
                    # Tenta converter resultado e meta para float, lida com erros resultando em N/A status
                    df_hist["status"] = df_hist.apply(lambda row:
                         "Acima da Meta" if (isinstance(row["resultado"], (int, float)) and isinstance(ind.get("meta"), (int, float)) and ((float(row["resultado"]) >= float(ind.get("meta", 0.0)) and ind.get("comparacao", "Maior é melhor") == "Maior é melhor") or (float(row["resultado"]) <= float(ind.get("meta", 0.0)) and ind.get("comparacao", "Maior é melhor") == "Menor é melhor"))))
                         else "Abaixo da Meta" if (isinstance(row["resultado"], (int, float)) and isinstance(ind.get("meta"), (int, float))))
                         else "N/A" # Status N/A se resultado ou meta não são numéricos
                    , axis=1)


                    # Seleciona e formata colunas para exibição na tabela
                    cols_to_display = ["data_referencia", "resultado", "status"]
                    if "observacao" in df_hist.columns: cols_to_display.append("observacao")
                    if "analise_critica" in df_hist.columns: cols_to_display.append("analise_critica") # Inclui análise crítica para processar

                    df_display = df_hist[cols_to_display].copy()
                    df_display["resultado"] = df_display["resultado"].apply(lambda x: f"{float(x):.2f}{unidade_display}" if isinstance(x, (int, float)) else "N/A")
                    df_display["data_referencia"] = df_display["data_referencia"].apply(lambda x: x.strftime("%d/%m/%Y"))

                    # Processa a coluna de análise crítica para exibir o status
                    if "analise_critica" in df_display.columns:
                         df_display["analise_status"] = df_display["analise_critica"].apply(get_analise_status)
                         df_display = df_display.drop(columns=["analise_critica"]) # Remove a coluna original complexa
                         cols_display_order = ["data_referencia", "resultado", "status", "observacao", "analise_status"]
                         df_display = df_display.reindex(columns=[col for col in cols_display_order if col in df_display.columns]) # Reordena

                    # Renomeia as colunas para exibição amigável
                    display_column_names = {"data_referencia": "Data de Referência", "resultado": f"Resultado ({unidade_display})", "status": "Status", "observacao": "Observações", "analise_status": "Análise Crítica"}
                    df_display.rename(columns=display_column_names, inplace=True)

                    st.dataframe(df_display, use_container_width=True) # Exibe a tabela da série histórica

                    # Análise de Tendência (requer pelo menos 3 resultados NUMÉRICOS)
                    # Filtra resultados que são numericos para a análise de tendência
                    numeric_results = df_hist[pd.to_numeric(df_hist['resultado'], errors='coerce').notna()].copy()
                    numeric_results['resultado'] = pd.to_numeric(numeric_results['resultado']) # Converte para numérico

                    if len(numeric_results) >= 3:
                        # Pega os últimos 3 resultados numéricos e converte para lista
                        ultimos_resultados = numeric_results.sort_values("data_referencia")["resultado"].tolist()

                        if len(ultimos_resultados) >= 3: # Garante que conseguimos pelo menos 3 valores numéricos
                            # Compara os últimos 3 resultados para determinar a tendência
                            if ind.get("comparacao", "Maior é melhor") == "Maior é melhor":
                                tendencia = "crescente" if ultimos_resultados[-1] > ultimos_resultados[-2] > ultimos_resultados[-3] else ("decrescente" if ultimos_resultados[-1] < ultimos_resultados[-2] < ultimos_resultados[-3] else "estável")
                            else: # Menor é melhor
                                tendencia = "crescente" if ultimos_resultados[-1] < ultimos_resultados[-2] < ultimos_resultados[-3] else ("decrescente" if ultimos_resultados[-1] > ultimos_resultados[-2] > ultimos_resultados[-3] else "estável")

                            # Define a cor para a tendência
                            tendencia_color = "#26A69A" if (tendencia == "crescente" and ind.get("comparacao", "Maior é melhor") == "Maior é melhor") or (tendencia == "decrescente" and ind.get("comparacao", "Maior é melhor") == "Menor é melhor") else "#FF5252" if (tendencia == "decrescente" and ind.get("comparacao", "Maior é melhor") == "Maior é melhor") or (tendencia == "crescente" and ind.get("comparacao", "Maior é melhor") == "Menor é melhor") else "#FFC107"

                            st.markdown(f"""<div style="margin-top:15px;"><h4>Análise de Tendência</h4><p>Este indicador apresenta uma tendência <span style="color:{tendencia_color}; font-weight:bold;">{tendencia}</span> nos últimos 3 períodos com resultados numéricos.</p></div>""", unsafe_allow_html=True)

                            # Análise Automática de Desempenho (baseada em tendência e meta)
                            st.markdown("<h4>Análise Automática</h4>", unsafe_allow_html=True)
                            meta_float = float(ind.get("meta", 0.0)) # Garante meta é float

                            if data['last_result_float'] is not None: # Só faz a análise automática se o último resultado for numérico e válido
                                if tendencia == "crescente":
                                    if ind.get("comparacao", "Maior é melhor") == "Maior é melhor":
                                        st.success("O indicador apresenta evolução positiva, com resultados crescentes nos últimos períodos com resultados numéricos.")
                                        if data['last_result_float'] >= meta_float:
                                            st.success("O resultado atual está acima da meta estabelecida, demonstrando bom desempenho.")
                                        else:
                                            st.warning("Apesar da evolução positiva, o resultado ainda está abaixo da meta estabelecida. Continue acompanhando a tendência.")
                                    else: # Menor é melhor
                                        st.error("O indicador apresenta tendência de aumento, o que é negativo para este tipo de métrica.")
                                        if data['last_result_float'] <= meta_float:
                                            st.warning("Embora o resultado atual ainda esteja dentro da meta, a tendência de aumento requer atenção imediata.")
                                        else:
                                            st.error("O resultado está acima da meta e com tendência de aumento, exigindo ações corretivas urgentes.")
                                elif tendencia == "decrescente":
                                    if ind.get("comparacao", "Maior é melhor") == "Maior é melhor":
                                        st.error("O indicador apresenta tendência de queda, o que é preocupante para este tipo de métrica.")
                                        if data['last_result_float'] >= meta_float:
                                            st.warning("Embora o resultado atual ainda esteja acima da meta, a tendência de queda requer atenção.")
                                        else:
                                            st.error("O resultado está abaixo da meta e com tendência de queda, exigindo ações corretivas urgentes.")
                                    else: # Menor é melhor
                                        st.success("O indicador apresenta evolução positiva, com resultados decrescentes nos últimos períodos com resultados numéricos.")
                                        if data['last_result_float'] <= meta_float:
                                            st.success("O resultado atual está dentro da meta estabelecida, demonstrando bom desempenho.")
                                        else:
                                            st.warning("Apesar da evolução positiva, o resultado ainda está acima da meta estabelecida. A tendência de queda é favorável, mas ainda há trabalho a ser feito para atingir a meta.")
                                else: # Estável
                                    if (data['last_result_float'] >= meta_float and ind.get("comparacao", "Maior é melhor") == "Maior é melhor") or (data['last_result_float'] <= meta_float and ind.get("comparacao", "Maior é melhor") == "Menor é melhor"):
                                        st.info("O indicador apresenta estabilidade e está dentro da meta estabelecida. Monitore para garantir a manutenção do desempenho.")
                                    else:
                                        st.warning("O indicador apresenta estabilidade, porém está fora da meta estabelecida. É necessário investigar as causas dessa estabilidade fora da meta.")
                            else:
                                st.info("Não foi possível realizar a análise automática de desempenho para o último resultado (Não numérico ou inválido).")
                        else:
                            st.info("Não há resultados numéricos suficientes para análise de tendência (mínimo de 3 períodos com resultados numéricos necessários).")
                    else: st.info("Não há dados históricos numéricos suficientes para análise de tendência (mínimo de 3 períodos necessários).")

                    # Análise Crítica 5W2H do último resultado
                    st.markdown("<h4>Análise Crítica 5W2H do Último Período</h4>", unsafe_allow_html=True)
                    # Encontra o último resultado (independente de ser numérico)
                    ultimo_resultado = df_hist.iloc[0]
                    has_analysis = False
                    analise_dict = {}
                    if "analise_critica" in ultimo_resultado and ultimo_resultado["analise_critica"] is not None:
                         analise_dict = ultimo_resultado["analise_critica"]
                         # Verifica se há pelo menos um campo de análise preenchido
                         if any(analise_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                             has_analysis = True


                    if has_analysis:
                        # Exibe os campos da análise 5W2H
                        st.markdown("**O que (What):** " + analise_dict.get("what", ""))
                        st.markdown("**Por que (Why):** " + analise_dict.get("why", ""))
                        st.markdown("**Quem (Who):** " + analise_dict.get("who", ""))
                        st.markdown("**Quando (When):** " + analise_dict.get("when", ""))
                        st.markdown("**Onde (Where):** " + analise_dict.get("where", ""))
                        st.markdown("**Como (How):** " + analise_dict.get("how", ""))
                        st.markdown("**Quanto custa (How Much):** " + analise_dict.get("howMuch", ""))
                    else:
                        st.info("Não há análise crítica registrada para o último resultado. Utilize a opção 'Preencher Indicador' para adicionar uma análise crítica no formato 5W2H.")
                        # Expander explicando o 5W2H
                        with st.expander("O que é a análise 5W2H?"):
                            st.markdown("""**5W2H** é uma metodologia de análise que ajuda a estruturar o pensamento crítico sobre um problema ou situação:
- **What (O quê)**: O que está acontecendo? Qual é o problema ou situação?
- **Why (Por quê)**: Por que isso está acontecendo? Quais são as causas?
- **Who (Quem)**: Quem é responsável? Quem está envolvido?
- **When (Quando)**: Quando isso aconteceu? Qual é o prazo para resolução?
- **Where (Onde)**: Onde ocorre o problema? Em qual setor ou processo?
- **How (Como)**: Como resolver o problema? Quais ações devem ser tomadas?
- **How Much (Quanto custa)**: Quanto custará implementar a solução? Quais recursos são necessários?
Esta metodologia ajuda a garantir que todos os aspectos importantes sejam considerados na análise e no plano de ação.""")
                else: st.info("Não há resultados registrados para este indicador para exibir a série histórica.")
        else:
            # Mensagem se não houver resultados para o indicador
            st.info("Este indicador ainda não possui resultados registrados.")
            meta_display = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
            st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0; width: 200px; margin: 10px auto;"><p style="margin:0; font-size:12px; color:#666;">Meta</p><p style="margin:0; font-weight:bold; font-size:18px;">{meta_display}</p></div>""", unsafe_allow_html=True)

        # Separador entre os indicadores
        st.markdown("<hr style='margin: 30px 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)


    # Botão de exportar todos os indicadores exibidos
    if st.button("📤 Exportar Tudo", key="dashboard_export_button"):
        export_data = []
        for data in indicator_data:
            ind = data["indicator"]
            unidade_export = ind.get('unidade', '')
            # Formata o último resultado para exportação
            last_result_export = f"{float(data['last_result']):.2f}{unidade_export}" if isinstance(data['last_result'], (int, float)) else "N/A"
            # Formata a meta para exportação
            meta_export = f"{float(ind.get('meta', 0.0)):.2f}{unidade_export}"
            # Formata a variação para exportação (lidando com infinitos)
            if data['variacao'] == float('inf'): variacao_export = "+Inf"
            elif data['variacao'] == float('-inf'): variacao_export = "-Inf"
            elif isinstance(data['variacao'], (int, float)): variacao_export = f"{data['variacao']:.2f}%"
            else: variacao_export = "N/A"

            # Adiciona os dados preparados à lista de exportação
            export_data.append({
                "Nome": ind["nome"],
                "Setor": ind["responsavel"],
                "Meta": meta_export,
                "Último Resultado": last_result_export,
                "Período": data["data_formatada"],
                "Status": data["status"],
                "Variação": variacao_export
            })
        # Cria DataFrame e gera link de download
        df_export = pd.DataFrame(export_data)
        df_export.rename(columns={'Variação': 'Variação (%)'}, inplace=True) # Renomeia a coluna de variação
        download_link = get_download_link(df_export, "indicadores_dashboard.xlsx")
        st.markdown(download_link, unsafe_allow_html=True) # Exibe o link de download

    st.markdown('</div>', unsafe_allow_html=True)


def show_overview():
    """Mostra a visão geral dos indicadores."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Visão Geral dos Indicadores")
    # Carrega indicadores e resultados
    indicators = load_indicators()
    results = load_results()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtros na visão geral
    col1, col2 = st.columns(2)
    with col1:
        # Filtro multi-seleção por setor (inclui "Todos")
        setores_disponiveis = sorted(list(set([ind["responsavel"] for ind in indicators])))
        setor_filtro = st.multiselect("Filtrar por Setor", options=["Todos"] + setores_disponiveis, default=["Todos"], key="overview_setor_filter")
    with col2:
        # Filtro multi-seleção por status (inclui "Todos")
        status_options = ["Todos", "Acima da Meta", "Abaixo da Meta", "Sem Resultados", "N/A"] # Inclui N/A
        status_filtro = st.multiselect("Status", options=status_options, default=["Todos"], key="overview_status_filter")
    # Campo de busca por texto
    search_query = st.text_input("Buscar indicador por nome ou setor", placeholder="Digite para buscar...", key="overview_search")

    # Aplica o filtro de setor
    filtered_indicators = indicators
    if setor_filtro and "Todos" not in setor_filtro:
        filtered_indicators = [ind for ind in indicators if ind["responsavel"] in setor_filtro]

    overview_data = [] # Lista para armazenar os dados da tabela de visão geral

    # Prepara os dados para a tabela de visão geral
    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        unidade_display = ind.get('unidade', '')

        last_result = "N/A"
        data_formatada = "N/A"
        status = "Sem Resultados"
        variacao = 0 # Variação vs Meta (numérico)

        if ind_results:
            # Pega o último resultado
            df_results = pd.DataFrame(ind_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)
            last_result_obj = df_results.iloc[0]
            last_result = last_result_obj["resultado"]
            last_date = last_result_obj["data_referencia"]

            try:
                # Calcula status e variação se o último resultado for numérico
                meta = float(ind.get("meta", 0.0))
                resultado = float(last_result)

                if ind["comparacao"] == "Maior é melhor": status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else: status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"

                if meta != 0.0:
                    variacao = ((resultado / meta) - 1) * 100
                    if ind["comparacao"] == "Menor é melhor": variacao = -variacao
                else:
                    if resultado > 0: variacao = float('inf')
                    elif resultado < 0: variacao = float('-inf')
                    else: variacao = 0
            except (TypeError, ValueError):
                 status = "N/A"
                 variacao = 0 # Reseta variação


            # Formata os valores para exibição na tabela
            data_formatada = format_date_as_month_year(last_date)
            last_result_formatted = f"{float(last_result):.2f}{unidade_display}" if isinstance(last_result, (int, float)) else "N/A"
            meta_formatted = f"{float(meta):.2f}{unidade_display}"
            # Formata a variação, tratando infinitos
            if variacao == float('inf'): variacao_formatted = "+Inf"
            elif variacao == float('-inf'): variacao_formatted = "-Inf"
            elif isinstance(variacao, (int, float)): variacao_formatted = f"{variacao:.2f}%"
            else: variacao_formatted = "N/A"

        else:
            # Valores para indicadores sem resultados
            last_result_formatted = "N/A"
            data_formatada = "N/A"
            status = "Sem Resultados"
            variacao_formatted = "N/A" # Variação N/A se não há resultado
            meta_formatted = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"


        # Adiciona a linha à lista de dados
        overview_data.append({
            "Nome": ind["nome"],
            "Setor": ind["responsavel"],
            "Meta": meta_formatted,
            "Último Resultado": last_result_formatted,
            "Período": data_formatada,
            "Status": status,
            "Variação": variacao_formatted
        })

    # Aplica o filtro de status
    if status_filtro and "Todos" not in status_filtro:
        overview_data = [d for d in overview_data if d["Status"] in status_filtro]

    # Aplica o filtro de busca por texto (nome ou setor)
    if search_query:
        search_query_lower = search_query.lower()
        overview_data = [d for d in overview_data if search_query_lower in d["Nome"].lower() or search_query_lower in d["Setor"].lower()]


    df_overview = pd.DataFrame(overview_data) # Cria o DataFrame final para exibição
    if not df_overview.empty:
        # Renomeia a coluna Variação para clareza na tabela
        df_overview.rename(columns={'Variação': 'Variação (%)'}, inplace=True)
        st.dataframe(df_overview, use_container_width=True) # Exibe a tabela

        # Botão para exportar a tabela para Excel
        if st.button("📤 Exportar para Excel", key="overview_export_button"):
            # Cria um DataFrame para exportação com os dados originais (não formatados como string) se necessário,
            # mas aqui usamos os dados formatados como string na lista overview_data
            df_export = pd.DataFrame(overview_data)
            df_export.rename(columns={'Variação': 'Variação (%)'}, inplace=True)
            download_link = get_download_link(df_export, "visao_geral_indicadores.xlsx")
            st.markdown(download_link, unsafe_allow_html=True) # Exibe o link de download

        # Gráficos de resumo por setor e status (baseados no DataFrame filtrado)
        st.subheader("Resumo por Setor")
        if not df_overview.empty: # Verifica se o DataFrame ainda tem dados após filtros
            setor_counts = df_overview["Setor"].value_counts().reset_index()
            setor_counts.columns = ["Setor", "Quantidade de Indicadores"]
            fig_setor = px.bar(setor_counts, x="Setor", y="Quantidade de Indicadores", title="Quantidade de Indicadores por Setor", color="Setor")
            st.plotly_chart(fig_setor, use_container_width=True)

        st.subheader("Status dos Indicadores")
        if not df_overview.empty: # Verifica novamente se o DataFrame tem dados
            status_counts = df_overview["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Quantidade"]
             # Mapeamento de cores para os status
            status_color_map = {"Acima da Meta": "#26A69A", "Abaixo da Meta": "#FF5252", "Sem Resultados": "#9E9E9E", "N/A": "#607D8B"} # Adicionado cor para N/A
            fig_status = px.pie(status_counts, names="Status", values="Quantidade", title="Distribuição de Status dos Indicadores", color="Status", color_discrete_map=status_color_map)
            st.plotly_chart(fig_status, use_container_width=True)

    else:
        st.warning("Nenhum indicador encontrado com os filtros selecionados.") # Mensagem se o DataFrame estiver vazio após filtros

    st.markdown('</div>', unsafe_allow_html=True)

def show_settings():
    """Mostra a página de configurações."""
    global KEY_FILE # Declaração global para acessar a variável

    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Configurações")

    config = load_config() # Carrega configurações do DB

    st.subheader("Informações do Sistema")

    # Criando duas colunas com larguras iguais para layout
    col1, col2 = st.columns(2)

    # Coluna 1: Informações do sistema
    with col1:
        st.markdown("##### Detalhes do Portal")
        st.markdown("**Versão do Portal:** 1.4.0") # Versão hardcoded
        st.markdown("**Data da Última Atualização:** 17/06/2025") # Data hardcoded
        st.markdown("**Desenvolvido por:** FIA Softworks") # Desenvolvedor hardcoded

    # Coluna 2: Informações de contato
    with col2:
        st.markdown("##### Contato")
        st.markdown("**Suporte Técnico:**")
        st.markdown("Email: beborges@outlook.com.br") # Contato hardcoded
        st.markdown("Telefone: (35) 93300-1414") # Contato hardcoded


    st.subheader("Backup Automático")
    # Carrega o horário de backup configurado
    if "backup_hour" not in config: config["backup_hour"] = "00:00"
    try:
        backup_hour = datetime.strptime(config["backup_hour"], "%H:%M").time()
    except ValueError:
        # Se o formato salvo estiver errado, usa 00:00 e corrige no DB
        st.error("Formato de hora de backup inválido na configuração. Resetando para 00:00.")
        config["backup_hour"] = "00:00"
        save_config(config)
        backup_hour = datetime.time(0, 0)

    # Input para alterar o horário de backup
    new_backup_hour = st.time_input("Horário do backup automático", backup_hour)

    # Se o horário foi alterado, salva a nova configuração
    if new_backup_hour != backup_hour:
        config["backup_hour"] = new_backup_hour.strftime("%H:%M")
        save_config(config)
        st.success("Horário de backup automático atualizado com sucesso!")
        # Nota: O agendador em outro thread precisa ser reiniciado ou reconfigurado
        # para refletir a nova hora. A implementação atual não faz isso dinamicamente.
        # Seria necessário parar o thread antigo e iniciar um novo com a nova hora.

    # Exibe a data do último backup automático
    if "last_backup_date" in config and config["last_backup_date"]: # Verifica se a chave existe e não está vazia
        st.markdown(f"**Último backup automático:** {config['last_backup_date']}")
    else:
        st.markdown("**Último backup automático:** Nunca executado")


    # Botão para criar backup manual
    if st.button("⟳ Criar novo backup manual", help="Cria um backup manual de todos os dados do sistema."):
        with st.spinner("Criando backup manual..."):
            # Garante que a chave de criptografia existe e inicializa o cipher
            generate_key(KEY_FILE)
            cipher = initialize_cipher(KEY_FILE)
            # Chama a função de backup com tipo 'user'
            backup_file = backup_data(cipher, tipo_backup="user")
            if backup_file:
                st.success(f"Backup manual criado: {backup_file}")
            else:
                st.error("Falha ao criar o backup manual.")

    # Seção para restaurar backup
    if not os.path.exists("backups"):
        os.makedirs("backups") # Cria o diretório de backups se não existir

    # Lista os arquivos .bkp no diretório de backups
    backup_files = sorted([f for f in os.listdir("backups") if f.startswith("backup_") and f.endswith(".bkp")], reverse=True) # Ordena do mais recente para o mais antigo

    if backup_files:
        # Selectbox para selecionar o arquivo de backup a restaurar
        selected_backup = st.selectbox("Selecione o backup para restaurar", backup_files)

        # Botão para iniciar a restauração
        if st.button("⚙️ Restaurar arquivo de backup ️", help="Restaura os dados do sistema a partir de um arquivo de backup. Criará um backup de segurança antes da restauração."):
            st.warning("⚠️ Restaurar um backup irá sobrescrever todos os dados atuais do sistema! Um backup de segurança será criado antes de prosseguir.")
            # Pergunta de confirmação antes de restaurar
            if st.button("Confirmar Restauração", key="confirm_restore_button"): # Chave única
                with st.spinner("Criando backup de segurança antes da restauração..."):
                     # Garante chave e cipher
                    generate_key(KEY_FILE)
                    cipher = initialize_cipher(KEY_FILE)
                    # Cria um backup de segurança ANTES de restaurar
                    backup_file_antes_restauracao = backup_data(cipher, tipo_backup="seguranca")
                    if backup_file_antes_restauracao:
                        st.success(f"Backup de segurança criado: {backup_file_antes_restauracao}")
                    else:
                        st.error("Falha ao criar o backup de segurança. Restauração cancelada.")
                        return # Aborta a restauração se o backup de segurança falhar

                # Procede com a restauração
                try:
                    with st.spinner(f"Restaurando backup de '{selected_backup}'..."):
                        # Garante chave e cipher novamente (caso tenha mudado no rerun)
                        generate_key(KEY_FILE)
                        cipher = initialize_cipher(KEY_FILE)
                        if restore_data(os.path.join("backups", selected_backup), cipher):
                            st.success("Backup restaurado com sucesso! A aplicação será reiniciada.")
                            # Limpa o estado da sessão para forçar recarregamento dos dados
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            time.sleep(2) # Pequeno delay
                            st.rerun() # Reinicia a aplicação
                        else:
                            st.error("Falha ao restaurar o backup.")
                except Exception as e:
                    st.error(f"Ocorreu um erro durante a restauração: {e}")
    else:
        st.info("Nenhum arquivo de backup encontrado no diretório 'backups'.")


    # Opções de administração (apenas para o usuário 'admin')
    if st.session_state.username == "admin":
        st.subheader("Administração do Sistema")
        with st.expander("Opções Avançadas de Limpeza"):
            st.warning("⚠️ Estas opções podem causar perda de dados permanente. Use com extremo cuidado.")

            # Botão para limpar resultados (requer confirmação)
            if st.button("🗑️ Limpar TODOS os resultados", help="Exclui todos os resultados de todos os indicadores no sistema."):
                # Usa o estado da sessão para gerenciar a confirmação
                if "confirm_limpar_resultados" not in st.session_state: st.session_state.confirm_limpar_resultados = False
                # Se não está no estado de confirmação, mostra a mensagem e muda o estado
                if not st.session_state.confirm_limpar_resultados:
                    st.warning("Tem certeza que deseja limpar TODOS os resultados? Esta ação não pode ser desfeita.")
                    st.session_state.confirm_limpar_resultados = True
                    # Adiciona um botão de confirmação separado para evitar cliques acidentais
                    if st.button("Confirmar Limpeza de Resultados", key="confirm_limpar_resultados_btn"): # Chave única
                         pass # Clicar aqui muda o estado para o bloco abaixo executar no próximo rerun
                    if st.button("Cancelar", key="cancel_limpar_resultados_btn"): # Botão de cancelar
                         st.session_state.confirm_limpar_resultados = False
                         st.info("Limpeza cancelada.")
                         st.rerun()
                elif st.session_state.confirm_limpar_resultados: # Se está no estado de confirmação E clicou no botão de confirmar
                    # Verifica se o botão de confirmação foi clicado
                    if st.session_state.get("confirm_limpar_resultados_btn"):
                         with st.spinner("Limpando resultados...\ Academia FIA Softworks"):
                             conn = get_db_connection()
                             if conn:
                                 try:
                                     cur = conn.cursor()
                                     cur.execute("DELETE FROM resultados;") # Deleta todos os resultados
                                     conn.commit()
                                     st.success("Resultados excluídos com sucesso!")
                                     # Limpa a lista de resultados no estado da sessão
                                     if 'results' in st.session_state: del st.session_state.results
                                 except Exception as e:
                                     st.error(f"Erro ao excluir resultados: {e}")
                                     conn.rollback()
                                 finally:
                                     cur.close()
                                     conn.close()
                          # Reseta o estado de confirmação
                         st.session_state.confirm_limpar_resultados = False
                         if "confirm_limpar_resultados_btn" in st.session_state: del st.session_state.confirm_limpar_resultados_btn
                         if "cancel_limpar_resultados_btn" in st.session_state: del st.session_state.cancel_limpar_resultados_btn
                         st.rerun() # Reroda para atualizar a UI


            # Botão para excluir TUDO (indicadores e resultados, requer confirmação)
            if st.button("🧹 Excluir TUDO (Indicadores e Resultados)!", help="Exclui todos os indicadores e seus resultados associados do sistema."):
                 # Usa o estado da sessão para gerenciar a confirmação
                if "confirm_limpar_tudo" not in st.session_state: st.session_state.confirm_limpar_tudo = False
                # Se não está no estado de confirmação, mostra a mensagem e muda o estado
                if not st.session_state.confirm_limpar_tudo:
                    st.warning("Tem certeza que deseja limpar TODOS os indicadores e resultados? Esta ação não pode ser desfeita.")
                    st.session_state.confirm_limpar_tudo = True
                    # Adiciona um botão de confirmação separado
                    if st.button("Confirmar Exclusão TOTAL", key="confirm_limpar_tudo_btn"): # Chave única
                         pass # Clicar aqui muda o estado
                    if st.button("Cancelar", key="cancel_limpar_tudo_btn"): # Botão de cancelar
                         st.session_state.confirm_limpar_tudo = False
                         st.info("Exclusão total cancelada.")
                         st.rerun()
                elif st.session_state.confirm_limpar_tudo: # Se está no estado de confirmação E clicou no botão de confirmar
                     if st.session_state.get("confirm_limpar_tudo_btn"):
                         with st.spinner("Limpando tudo..."):
                             conn = get_db_connection()
                             if conn:
                                 try:
                                     cur = conn.cursor()
                                     # Deleta todos os indicadores (resultados serão excluídos via ON DELETE CASCADE)
                                     cur.execute("DELETE FROM indicadores;")
                                     conn.commit()
                                     st.success("Indicadores e resultados excluídos com sucesso!")
                                     # Limpa as listas no estado da sessão
                                     if 'indicators' in st.session_state: del st.session_state.indicators
                                     if 'results' in st.session_state: del st.session_state.results
                                 except Exception as e:
                                     st.error(f"Erro ao excluir indicadores e resultados: {e}")
                                     conn.rollback()
                                 finally:
                                     cur.close()
                                     conn.close()
                          # Reseta o estado de confirmação
                         st.session_state.confirm_limpar_tudo = False
                         if "confirm_limpar_tudo_btn" in st.session_state: del st.session_state.confirm_limpar_tudo_btn
                         if "cancel_limpar_tudo_btn" in st.session_state: del st.session_state.cancel_limpar_tudo_btn
                         st.rerun() # Reroda para atualizar a UI

    st.markdown('</div>', unsafe_allow_html=True)


def show_user_management(SETORES):
    """Mostra a página de gerenciamento de usuários."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Gerenciamento de Usuários")
    users = load_users() # Carrega a lista de usuários com setores (lista)

    # --- Contagem de usuários por tipo ---
    total_users = len(users)
    admin_count = sum(1 for user, data in users.items() if data.get("tipo") == "Administrador")
    operator_count = sum(1 for user, data in users.items() if data.get("tipo") == "Operador")
    viewer_count = sum(1 for user, data in users.items() if data.get("tipo") == "Visualizador")

    st.subheader("Visão Geral de Usuários")
    # Cartões de resumo de usuários
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#1E88E5;">{total_users}</h3><p style="margin:0;">Total de Usuários</p></div>""", unsafe_allow_html=True)
    with col2: st.markdown(f"""<div style="background-color:#26A69A; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{admin_count}</h3><p style="margin:0; color:white;">Administradores</p></div>""", unsafe_allow_html=True)
    with col3: st.markdown(f"""<div style="background-color:#FFC107; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{operator_count}</h3><p style="margin:0; color:white;">Operadores</p></div>""", unsafe_allow_html=True)
    with col4: st.markdown(f"""<div style="background-color:#7E57C2; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{viewer_count}</h3><p style="margin:0; color:white;">Visualizadores</p></div>""", unsafe_allow_html=True)


    st.subheader("Adicionar Novo Usuário")
    # Formulário para adicionar novo usuário
    with st.form("add_user_form"):
        st.markdown("#### Informações Pessoais")
        col1, col2 = st.columns(2)
        with col1: nome_completo = st.text_input("Nome Completo", placeholder="Digite o nome completo do usuário")
        with col2: email = st.text_input("Email", placeholder="Digite o email do usuário")

        st.markdown("#### Configurações de Permissão")
        # Input para o tipo de usuário
        user_type_new = st.selectbox("Tipo de Usuário", options=["Administrador", "Operador", "Visualizador"], index=2, help="Administrador: acesso total; Operador: gerencia indicadores de um setor; Visualizador: apenas visualização")

        # Input para selecionar MÚLTIPLOS setores (usando st.multiselect)
        # O setor "Todos" não faz sentido para Operadores. Admins e Visualizadores não precisam de setores específicos para ver tudo, mas o multiselect pode ser usado para representação ou futuros filtros.
        # Vamos oferecer todos os setores no multiselect.
        user_sectors_new = st.multiselect("Setor(es) Associado(s)", options=SETORES, default=[], help="Selecione os setores que este usuário poderá gerenciar ou visualizar (para Operadores) ou apenas para referência (para Administradores/Visualizadores).") # Seleção múltipla de setores

        st.markdown("#### Informações de Acesso")
        col1, col2 = st.columns(2)
        with col1: login = st.text_input("Login", placeholder="Digite o login para acesso ao sistema")
        with col2: new_password = st.text_input("Senha", type="password", placeholder="Digite a senha")
        confirm_password = st.text_input("Confirmar Senha", type="password", placeholder="Confirme a senha")

        # Explicação dos tipos de usuário
        st.markdown("""<div style="background-color:#f8f9fa; padding:10px; border-radius:5px; margin-top:10px;"><p style="margin:0; font-size:14px;"><strong>Tipos de usuário:</strong></p><ul style="margin:5px 0 0 15px; padding:0; font-size:13px;"><li><strong>Administrador:</strong> Acesso total ao sistema. Associações de setor são apenas para referência.</li><li><strong>Operador:</strong> Gerencia e preenche indicadores de **seus setores associados**. Deve ter pelo menos um setor associado.</li><li><strong>Visualizador:</strong> Apenas visualiza indicadores e resultados. Associações de setor são apenas para referência/futuros filtros.</li></ul></div>""", unsafe_allow_html=True)

        # Validação básica para Operador ter pelo menos um setor associado
        if user_type_new == "Operador" and not user_sectors_new:
             st.warning("⚠️ Operadores devem ser associados a pelo menos um setor.")

        submit = st.form_submit_button("➕ Adicionar")

    # Lógica ao submeter o formulário de adição
    if submit:
        # Validações
        if not login or not new_password:
             st.error("❌ Login e senha são obrigatórios.")
        elif login in users:
             st.error(f"❌ O login '{login}' já existe.")
        elif new_password != confirm_password:
             st.error("❌ As senhas não coincidem.")
        # Validação para Operador sem setor associado (ajustada)
        elif user_type_new == "Operador" and not user_sectors_new:
            st.error("❌ Operadores devem ser associados a pelo menos um setor.")
        elif not nome_completo:
             st.error("❌ Nome completo é obrigatório.")
        elif email and "@" not in email: # Validação simples de formato de email
             st.error("❌ Formato de email inválido.")
        else:
            # Adiciona o novo usuário ao dicionário em memória
            users[login] = {
                "password": hashlib.sha256(new_password.encode()).hexdigest(), # Hashing da senha
                "tipo": user_type_new,
                "nome_completo": nome_completo,
                "email": email,
                "setores": user_sectors_new, # Salva a lista de setores
                "data_criacao": datetime.now().isoformat() # Data de criação
            }
            save_users(users) # Salva o dicionário atualizado no DB
            log_user_action("Usuário criado", login, st.session_state.username) # Log

            st.success(f"✅ Usuário '{nome_completo}' (login: {login}) adicionado com sucesso como {user_type_new}!")
            time.sleep(1) # Pequeno delay
            st.rerun() # Reinicia a aplicação para atualizar a lista de usuários exibida

    st.subheader("Usuários Cadastrados")
    # Filtros para a lista de usuários
    col1, col2 = st.columns(2)
    with col1: filter_type = st.multiselect("Filtrar por Tipo", options=["Todos", "Administrador", "Operador", "Visualizador"], default=["Todos"], key="filter_user_type")
    # O filtro de setor agora precisa verificar se o usuário tem *qualquer um* dos setores selecionados na lista de filtro
    with col2: filter_sector = st.multiselect("Filtrar por Setor", options=["Todos"] + SETORES, default=["Todos"], key="filter_user_sector")
    search_query = st.text_input("🔍 Buscar usuário por nome, login ou email", placeholder="Digite para buscar...", key="search_user")

    # Aplica os filtros à lista de usuários
    filtered_users = {}
    for user, data in users.items():
        user_type = data.get("tipo", "Visualizador")
        user_sectors = data.get("setores", []) # Pega a lista de setores
        nome_completo = data.get("nome_completo", "")
        email = data.get("email", "")
        data_criacao = data.get("data_criacao", "N/A")

        # Converte data de criação para formato de exibição
        if data_criacao != "N/A":
            try: data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
            except: pass

        # Filtro por busca de texto (nome, login ou email)
        if search_query and search_query.lower() not in user.lower() and search_query.lower() not in nome_completo.lower() and search_query.lower() not in email.lower():
             continue # Pula para o próximo usuário se não corresponder à busca

        # Filtro por Tipo
        type_match = ("Todos" in filter_type or user_type in filter_type)

        # Filtro por Setor (verifica se há interseção entre os setores do usuário e os setores filtrados)
        sector_match = True # Assume match inicialmente
        if filter_sector and "Todos" not in filter_sector:
             # Se o filtro não é "Todos", verifica se algum setor do usuário está na lista de filtro
             # Ou se o usuário é Administrador (que tem acesso a "Todos" logicamente, mesmo que não associado a todos individualmente)
             if user_type == "Administrador":
                 sector_match = True # Administradores sempre passam no filtro de setor
             elif not any(sector in filter_sector for sector in user_sectors):
                  sector_match = False # Operador/Visualizador sem setores em comum com o filtro

        # Adiciona o usuário à lista filtrada se todos os filtros corresponderem
        if type_match and sector_match:
             filtered_users[user] = data

    # Exibe a lista de usuários filtrados
    if filtered_users:
        user_data_list = []
        for user, data in filtered_users.items():
             user_type = data.get("tipo", "Visualizador")
             user_sectors = data.get("setores", [])
             nome_completo = data.get("nome_completo", "")
             email = data.get("email", "")
             data_criacao = data.get("data_criacao", "N/A")
             if data_criacao != "N/A":
                 try: data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
                 except: pass

             # Define cor para o tipo de usuário
             if user_type == "Administrador": type_color = "#26A69A"
             elif user_type == "Operador": type_color = "#FFC107"
             else: type_color = "#7E57C2"

             # Formata a lista de setores para exibição (se houver setores)
             sectors_display = ", ".join(user_sectors) if user_sectors else "Nenhum setor"

             # Adiciona os dados formatados à lista para exibição
             user_data_list.append({
                 "Login": user,
                 "Nome": nome_completo or "Não informado",
                 "Email": email or "Não informado",
                 "Tipo": user_type,
                 "Setores": sectors_display, # Exibe a string formatada
                 "Criado em": data_criacao,
                 "type_color": type_color,
                 "is_current": user == st.session_state.username, # Marca o usuário logado
                 "is_admin": user == "admin" # Marca o admin
             })

        # Exibe cada usuário em um card com botões de ação
        for i, row in enumerate(user_data_list):
            login = row["Login"]
            nome = row["Nome"]
            email = row["Email"]
            user_type = row["Tipo"]
            sectors_display = row["Setores"]
            type_color = row["type_color"]
            is_current = row["is_current"]
            is_admin = row["is_admin"]

            # Card do usuário
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:10px; border-left: 4px solid {type_color};">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <h3 style="margin:0; color:#37474F;">{nome} {' (você)' if is_current else ''}</h3>
                        <p style="margin:5px 0 0 0; color:#546E7A;">Login: <strong>{login}</strong></p>
                        <p style="margin:3px 0 0 0; color:#546E7A;">Email: {email}</p>
                        <p style="margin:3px 0 0 0; color:#546E7A;">Criado em: {row['Criado em']}</p>
                         <p style="margin:3px 0 0 0; color:#546E7A;">Setores: {sectors_display}</p> {/* Exibe os setores associados */}
                    </div>
                    <div>
                        <span style="background-color:{type_color}; color:white; padding:5px 10px; border-radius:15px; font-size:12px;">{user_type}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Botões de Editar e Excluir (não aparecem para o próprio usuário nem para o admin 'admin')
            if not is_admin and not is_current:
                col1, col2 = st.columns(2)
                with col1:
                    # Botão de editar - define estado para mostrar o formulário de edição
                    if st.button("✏️ Editar", key=f"edit_{login}"):
                        st.session_state[f"editing_{login}"] = True # Estado para edição deste usuário
                        st.session_state[f"edit_user_data_{login}\ Academia FIA Softworks"] = users[login] # Salva os dados atuais no estado
                        st.rerun() # Reroda para mostrar o form
                with col2:
                     # Botão de excluir - define estado para confirmar exclusão
                    if st.button("🗑️ Excluir", key=f"del_{login}"):
                        st.session_state[f"deleting_{login}"] = True # Estado para exclusão deste usuário
                        st.rerun() # Reroda para mostrar a confirmação


                # Formulário de Edição (mostra se o estado de edição for True para este usuário)
                if st.session_state.get(f"editing_{login}", False):
                    # Recupera os dados do usuário a ser editado do estado da sessão
                    user_to_edit = st.session_state.get(f"edit_user_data_{login}", {})
                    current_sectors = user_to_edit.get("setores", []) # Setores atuais do usuário

                    with st.form(key=f"edit_form_{login}"): # Chave única para o formulário
                        st.subheader(f"Editar Usuário: {user_to_edit.get('nome_completo', login)}")
                        st.markdown("#### Informações Pessoais")
                        col1, col2 = st.columns(2)
                        with col1: new_nome = st.text_input("Nome Completo", value=user_to_edit.get('nome_completo', ''), key=f"new_nome_{login}")
                        with col2: new_email = st.text_input("Email", value=user_to_edit.get('email', ''), key=f"new_email_{login}")

                        st.markdown("#### Configurações de Permissão")
                        # Selectbox para o tipo de usuário (preenchido com o tipo atual)
                        current_type_index = [
                             "Administrador", "Operador", "Visualizador"
                        ].index(user_to_edit.get("tipo", "Visualizador"))
                        new_type = st.selectbox("Tipo de Usuário", options=["Administrador", "Operador", "Visualizador"], index=current_type_index, key=f"new_type_{login}")

                        # Multi-select para os setores (preenchido com os setores atuais)
                        new_sectors = st.multiselect(
                             "Setor(es) Associado(s)",
                             options=SETORES, # Oferece todos os setores
                             default=current_sectors, # Marca os setores atuais
                             key=f"new_sectors_{login}" # Chave única
                        )

                        st.markdown("#### Informações de Acesso")
                        # Checkbox para redefinir senha
                        reset_password = st.checkbox("Redefinir senha", key=f"reset_pwd_{login}")
                        if reset_password:
                            new_password = st.text_input("Nova senha", type="password", key=f"new_pwd_{login}")
                            confirm_password = st.text_input("Confirmar nova senha", type="password", key=f"confirm_pwd_{login}")

                        # Validações no formulário de edição
                        is_valid = True
                        # Validação para Operador sem setor associado (ajustada)
                        if new_type == "Operador" and not new_sectors:
                            st.error("❌ Operadores devem ser associados a pelo menos um setor.")
                            is_valid = False
                        if new_email and "@" not in new_email: # Validação simples de formato de email
                             st.error("❌ Formato de email inválido.")
                             is_valid = False

                        # Botões Salvar e Cancelar
                        col1, col2 = st.columns(2)
                        with col1: submit_edit = st.form_submit_button("Salvar Alterações")
                        with col2: cancel_edit = st.form_submit_button("Cancelar")


                        # Lógica ao clicar em Salvar Alterações
                        if submit_edit and is_valid:
                            # Validações adicionais para redefinir senha
                            if reset_password:
                                if not new_password:
                                     st.error("❌ A nova senha é obrigatória."); return
                                if new_password != confirm_password:
                                     st.error("❌ As senhas não coincidem."); return

                            # Atualiza os dados do usuário no dicionário em memória
                            # Copia os dados originais para não perder chaves como 'data_criacao'
                            updated_user_data = users[login].copy()
                            updated_user_data["tipo"] = new_type
                            updated_user_data["setores"] = new_sectors # Atualiza a lista de setores
                            updated_user_data["nome_completo"] = new_nome
                            updated_user_data["email"] = new_email

                            if reset_password:
                                 updated_user_data["password"] = hashlib.sha256(new_password.encode()).hexdigest() # Hashing da nova senha

                            users[login] = updated_user_data # Atualiza no dicionário principal

                            save_users(users) # Salva no DB (irá gerenciar a tabela usuario_setores)
                            st.success(f"✅ Usuário '{new_nome}' atualizado com sucesso!")
                            log_user_action("Usuário atualizado", login, st.session_state.username) # Log

                            # Limpa os estados de edição e reroda
                            del st.session_state[f"editing_{login}"]
                            if f"edit_user_data_{login}" in st.session_state: del st.session_state[f"edit_user_data_{login}"]
                            time.sleep(1)
                            st.rerun()

                        # Lógica ao clicar em Cancelar Edição
                        if cancel_edit:
                             # Limpa os estados de edição e reroda
                            del st.session_state[f"editing_{login}"]
                            if f"edit_user_data_{login}" in st.session_state: del st.session_state[f"edit_user_data_{login}"]
                            st.rerun()


                # Confirmação de Exclusão (mostra se o estado de exclusão for True)
                if st.session_state.get(f"deleting_{login}", False):
                    # Pega o nome do usuário para a mensagem
                    user_to_delete_name = users.get(login, {}).get("nome_completo", login)
                    st.warning(f"⚠️ Tem certeza que deseja excluir o usuário '{user_to_delete_name}' (login: {login})? Esta ação removerá o acesso e não poderá ser desfeita.")
                    col1, col2 = st.columns(2)
                    with col1:
                        # Botão de confirmação da exclusão
                        if st.button("✅ Sim, excluir", key=f"confirm_del_{login}"):
                            # Chama a função para deletar o usuário no DB
                            delete_user(login, st.session_state.username)
                            st.success(f"✅ Usuário '{user_to_delete_name}' excluído com sucesso!")
                            # Limpa o estado de exclusão e reroda
                            del st.session_state[f"deleting_{login}"]
                            time.sleep(1)
                            st.rerun()
                    with col2:
                         # Botão de cancelar a exclusão
                        if st.button("❌ Cancelar", key=f"cancel_del_{login}"):
                            # Limpa o estado de exclusão e reroda
                            del st.session_state[f"deleting_{login}"]
                            st.rerun()

            # Separador entre os usuários na lista
            st.markdown("<hr style='margin: 20px 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)

    else:
        st.info("Nenhum usuário encontrado com os filtros selecionados.") # Mensagem se nenhum usuário corresponder aos filtros


    # Botão para exportar a lista de usuários (apenas para admin)
    if st.session_state.username == "admin":
        if st.button("📤 Exportar Lista", key="users_export_button"):
            export_data = []
            for user, data in users.items():
                user_type = data.get("tipo", "Visualizador")
                user_sectors = data.get("setores", [])
                nome_completo = data.get("nome_completo", "")
                email = data.get("email", "")
                data_criacao = data.get("data_criacao", "N/A")
                if data_criacao != "N/A":
                    try: data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
                    except: pass
                # Formata a lista de setores para a exportação
                sectors_export = ", ".join(user_sectors) if user_sectors else "Nenhum"

                export_data.append({
                    "Login": user,
                    "Nome Completo": nome_completo,
                    "Email": email,
                    "Tipo": user_type,
                    "Setores Associados": sectors_export, # Coluna com os setores associados
                    "Data de Criação": data_criacao
                })
            # Cria DataFrame e gera link de download
            df_export = pd.DataFrame(export_data)
            download_link = get_download_link(df_export, "usuarios_sistema.xlsx")
            st.markdown(download_link, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def delete_user(username, user_performed):
    """Exclui um usuário do banco de dados."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # A exclusão na tabela usuarios deve ser suficiente,
            # pois a chave estrangeira em 'usuario_setores' tem ON DELETE CASCADE
            cur.execute("DELETE FROM usuarios WHERE username = %s;", (username,))
            conn.commit()
            log_user_action("Usuário excluído", username, user_performed) # Log
            # Recarrega a lista de usuários no estado da sessão após exclusão bem-sucedida
            # Note: users = load_users() dentro show_user_management será chamado no próximo rerun
            return True
        except psycopg2.Error as e:
            print(f"Erro ao excluir usuário do banco de dados: {e}")
            st.error(f"Erro ao excluir usuário: {e}") # Exibe erro no Streamlit
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False


def logout():
    """Realiza o logout do usuário."""
    # Limpa todo o estado da sessão
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun() # Reinicia a aplicação, mostrando a página de login


# --- Funções de Backup e Restauração (Mantidas) ---

# KEY_FILE = "secret.key" # Já definido globalmente no início

def generate_key(key_file):
    """Gera uma nova chave de criptografia se não existir."""
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        try:
            with open(key_file, "wb") as kf:
                kf.write(key)
            print(f"Chave de criptografia gerada em {key_file}")
        except Exception as e:
             print(f"Erro ao gerar ou salvar chave de criptografia: {e}")
             # st.error(f"Erro ao gerar ou salvar chave de criptografia: {e}") # Evita st.error aqui para não aparecer fora do contexto UI
             return None # Retorna None em caso de erro
        return key
    return None # Retorna None se a chave já existia


def load_key(key_file):
    """Carrega a chave de criptografia do arquivo."""
    try:
        with open(key_file, "rb") as kf:
            return kf.read()
    except FileNotFoundError:
        print(f"Arquivo de chave não encontrado: {key_file}. Gere a chave primeiro.")
        # st.error(f"Arquivo de chave não encontrado: {key_file}. Gere a chave primeiro.") # Evita st.error aqui
        return None
    except Exception as e:
         print(f"Erro ao carregar chave de criptografia: {e}")
         # st.error(f"Erro ao carregar chave de criptografia: {e}") # Evita st.error aqui
         return None


def initialize_cipher(key_file):
    """Inicializa o objeto Fernet para criptografia."""
    key = load_key(key_file)
    if key:
        return Fernet(key)
    return None # Retorna None se a chave não pôde ser carregada/gerada


def backup_data(cipher, tipo_backup="user"):
    """Cria um arquivo de backup criptografado com todos os dados do DB."""
    if not cipher:
        print("Objeto de criptografia não inicializado. Backup cancelado.")
        # st.error("Objeto de criptografia não inicializado. Backup cancelado.") # Evita st.error aqui
        return None

    # Carrega dados de TODAS as tabelas
    try:
        all_data = {
            "users": load_users(), # Agora inclui setores como lista
            "indicators": load_indicators(),
            "results": load_results(),
            "config": load_config(),
            "backup_log": load_backup_log(),
            "indicator_log": load_indicator_log(),
            "user_log": load_user_log()
        }
    except Exception as e:
         print(f"Erro ao carregar dados do DB para backup: {e}")
         # st.error(f"Erro ao carregar dados do DB para backup: {e}") # Evita st.error aqui
         return None


    try:
        # Serializa os dados para JSON (com indentação para legibilidade no arquivo, default=str para datas/objetos não JSON serializáveis)
        all_data_str = json.dumps(all_data, indent=4, default=str).encode('utf-8') # Codifica para bytes

        encrypted_data = cipher.encrypt(all_data_str) # Criptografa os bytes
    except Exception as e:
         print(f"Erro ao serializar ou criptografar dados para backup: {e}")
         # st.error(f"Erro ao serializar ou criptografar dados para backup: {e}") # Evita st.error aqui
         return None


    # Define o nome do arquivo de backup baseado no tipo (user/seguranca) e timestamp
    if tipo_backup == "user":
        BACKUP_FILE = os.path.join("backups", f"backup_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bkp")
    else: # tipo_backup == "seguranca"
        BACKUP_FILE = os.path.join("backups", f"backup_seguranca_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bkp")

    # Cria o diretório de backups se não existir
    if not os.path.exists("backups"):
        os.makedirs("backups")


    try:
        with open(BACKUP_FILE, "wb") as backup_file:
            backup_file.write(encrypted_data) # Escreve os dados criptografados no arquivo
        # Log da ação de backup (usa st.session_state.username, que só existe na sessão Streamlit)
        # Esta logagem pode falhar se o backup for agendado em um thread sem contexto de sessão.
        # Considerar passar o username como argumento para a função agendada ou usar um placeholder.
        user_performing_backup = getattr(st.session_state, 'username', 'Sistema Agendado') # Pega username se disponível, senão usa 'Sistema Agendado'
        log_backup_action("Backup criado", os.path.basename(BACKUP_FILE), user_performing_backup) # Registra no log
        return BACKUP_FILE # Retorna o caminho do arquivo criado
    except Exception as e:
        print(f"Erro ao salvar o arquivo de backup: {e}")
        # st.error(f"Erro ao salvar o arquivo de backup: {e}") # Evita st.error aqui
        return None # Retorna None em caso de error


def restore_data(backup_file_path, cipher):
    """Restaura os dados a partir de um arquivo de backup criptografado para o DB."""
    if not cipher:
        print("Objeto de criptografia não inicializado. Restauração cancelada.")
        # st.error("Objeto de criptografia não inicializado. Restauração cancelada.") # Evita st.error aqui
        return False

    if not os.path.exists(backup_file_path):
         print(f"Arquivo de backup não encontrado: {backup_file_path}")
         # st.error(f"Arquivo de backup não encontrado: {backup_file_path}") # Evita st.error aqui
         return False

    try:
        with open(backup_file_path, "rb") as file:
            encrypted_data = file.read() # Lê os dados criptografados do arquivo

        decrypted_data_str = cipher.decrypt(encrypted_data).decode('utf-8') # Descriptografa e decodifica para string
        restored_data = json.loads(decrypted_data_str) # Carrega os dados do JSON

    except Exception as e:
        print(f"Erro ao ler, descriptografar ou carregar dados do backup '{backup_file_path}': {e}")
        st.error(f"Erro ao processar o arquivo de backup: {e}. Verifique se o arquivo não está corrompido e se a chave de criptografia está correta.")
        return False


    conn = get_db_connection()
    if not conn:
        st.error("Não foi possível conectar ao banco de dados para restaurar os dados.")
        return False

    try:
        cur = conn.cursor()

        # Desabilita temporariamente as verificações de chave estrangeira para facilitar a limpeza e reinserção
        cur.execute("SET session_replication_role = 'replica';")

        # Limpa as tabelas existentes ANTES de inserir os dados restaurados
        # CUIDADO: Isso apaga TODOS os dados atuais!
        # Começa pelas tabelas dependentes
        cur.execute("DELETE FROM usuario_setores;")
        cur.execute("DELETE FROM resultados;")
        cur.execute("DELETE FROM indicadores;")
        cur.execute("DELETE FROM usuarios;")
        cur.execute("DELETE FROM configuracoes;")
        cur.execute("DELETE FROM log_backup;")
        cur.execute("DELETE FROM log_indicadores;")
        cur.execute("DELETE FROM log_usuarios;")


        # --- Inserir dados de usuários ---
        users_to_insert = restored_data.get("users", {})
        if users_to_insert:
            # Cria lista de tuplas para inserção na tabela usuarios
            user_records = [(u, d.get("password", ""), d.get("tipo", "Visualizador"), d.get("nome_completo", ""), d.get("email", "")) for u, d in users_to_insert.items()]
            sql_insert_users = "INSERT INTO usuarios (username, password_hash, tipo, nome_completo, email) VALUES (%s, %s, %s, %s, %s);"
            cur.executemany(sql_insert_users, user_records)

            # Cria lista de tuplas para inserção na tabela usuario_setores
            sector_records = []
            for username, data in users_to_insert.items():
                 sectors_list = data.get("setores", [])
                 for sector in sectors_list:
                      sector_records.append((username, sector))

            if sector_records:
                sql_insert_sectors = "INSERT INTO usuario_setores (username, setor) VALUES (%s, %s);"
                cur.executemany(sql_insert_sectors, sector_records)

        # --- Inserir dados de indicadores ---
        indicators_to_insert = restored_data.get("indicators", [])
        if indicators_to_insert:
            indicator_records = []
            for i in indicators_to_insert:
                 # Ajusta para lidar com valores None na data_criacao/atualizacao
                 data_criacao_dt = datetime.fromisoformat(i["data_criacao"]) if i.get("data_criacao") else None
                 data_atualizacao_dt = datetime.fromisoformat(i["data_atualizacao"]) if i.get("data_atualizacao") else None

                 indicator_records.append((
                     i.get("id"), i.get("nome"), i.get("objetivo"), i.get("formula"),
                     Json(i.get("variaveis", {})), i.get("unidade"), i.get("meta"),
                     i.get("comparacao"), i.get("tipo_grafico"), i.get("responsavel"),
                     data_criacao_dt, data_atualizacao_dt
                 ))

            if indicator_records: # Verifica se há registros para inserir
                 sql_insert_indicators = """
                    INSERT INTO indicadores (id, nome, objetivo, formula, variaveis, unidade, meta, comparacao, tipo_grafico, responsavel, data_criacao, data_atualizacao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            COALESCE(%s, CURRENT_TIMESTAMP), COALESCE(%s, CURRENT_TIMESTAMP));
                """
                 cur.executemany(sql_insert_indicators, indicator_records)


        # --- Inserir dados de resultados ---
        results_to_insert = restored_data.get("results", [])
        if results_to_insert:
            result_records = []
            for r in results_to_insert:
                 # Converte data_referencia de string para datetime
                 try: data_referencia_dt = datetime.fromisoformat(r.get("data_referencia"))
                 except (ValueError, TypeError): data_referencia_dt = None # Ignora se data inválida

                 if data_referencia_dt: # Só adiciona se a data for válida
                     # Ajusta para lidar com valores None nas datas de criação/atualização e usuário/status
                     data_criacao_dt = datetime.fromisoformat(r.get("data_criacao")) if r.get("data_criacao") else None
                     data_atualizacao_dt = datetime.fromisoformat(r.get("data_atualizacao")) if r.get("data_atualizacao") else None

                     result_records.append((
                         r.get("indicator_id"),
                         data_referencia_dt, # datetime object
                         r.get("resultado"),
                         Json(r.get("valores_variaveis", {})),
                         r.get("observacao"),
                         Json(r.get("analise_critica", {})),
                         data_criacao_dt, # datetime object ou None
                         data_atualizacao_dt, # datetime object ou None
                         r.get("usuario"),
                         r.get("status_analise")
                     ))

            if result_records: # Verifica se há registros para inserir
                 sql_insert_results = """
                    INSERT INTO resultados (indicator_id, data_referencia, resultado, valores_variaveis, observacao, analise_critica, data_criacao, data_atualizacao, usuario, status_analise)
                    VALUES (%s, %s, %s, %s, %s, %s,
                            COALESCE(%s, CURRENT_TIMESTAMP), COALESCE(%s, CURRENT_TIMESTAMP),
                            COALESCE(%s, 'Sistema Restaurado'), COALESCE(%s, 'N/A'));
                """
                 cur.executemany(sql_insert_results, result_records)


        # --- Inserir dados de configurações ---
        config_to_insert = restored_data.get("config", {})
        if config_to_insert:
             config_records = [(k, v) for k, v in config_to_insert.items()]
             if config_records:
                 sql_insert_config = "INSERT INTO configuracoes (key, value) VALUES (%s, %s);"
                 cur.executemany(sql_insert_config, config_records) # Usando INSERT simples, pois a tabela foi limpa


        # --- Inserir dados de logs ---
        # Decidimos limpar logs durante a restauração e apenas logar a restauração em si.
        # Se quiser restaurar logs antigos, insira-os aqui de forma semelhante às outras tabelas.
        # Exemplo (descomente e ajuste se necessário):
        # log_backup_to_insert = restored_data.get("backup_log", [])
        # if log_backup_to_insert:
        #      log_records = [(datetime.fromisoformat(e["timestamp"]), e["action"], e["file_name"], e["user"]) for e in log_backup_to_insert]
        #      sql_insert_log = "INSERT INTO log_backup (timestamp, action, file_name, user_performed) VALUES (%s, %s, %s, %s);"
        #      cur.executemany(sql_insert_log, log_records)
        # ... repetir para log_indicadores e log_usuarios ...


        # Habilita novamente as verificações de chave estrangeira
        cur.execute("SET session_replication_role = 'origin';")

        conn.commit() # Confirma todas as operações no DB

        # Log da ação de restauração (usando o usuário logado na sessão)
        user_performing_restore = getattr(st.session_state, 'username', 'Sistema Restaurado')
        log_backup_action("Backup restaurado", os.path.basename(backup_file_path), user_performing_restore)

        return True # Retorna True se a restauração foi bem-sucedida

    except Exception as e:
        print(f"Erro durante a inserção de dados restaurados no DB: {e}")
        st.error(f"Erro durante a inserção de dados restaurados no banco de dados: {e}. A restauração pode estar incompleta.")
        conn.rollback() # Reverte as operações em caso de error
        return False
    finally:
        if conn:
             # Garante que as verificações de chave estrangeira sejam reativadas mesmo em caso de erro
            try: cur.execute("SET session_replication_role = 'origin';")
            except: pass # Ignora se já estiver em 'origin' ou a conexão falhou
            cur.close()
            conn.close()


def agendar_backup(cipher):
    """Agenda o backup automático."""
    # Esta função roda em um thread separado.
    # A interação com Streamlit st.* não é segura aqui.
    # Impressões (print) vão para o console.

    config = load_config() # Carrega configurações do DB
    backup_hour = config.get("backup_hour", "00:00")

    schedule.clear() # Limpa agendamentos anteriores

    # Agenda o job de backup para rodar diariamente no horário configurado
    # Passa o cipher como argumento, pois o thread não tem acesso direto ao estado global Streamlit
    schedule.every().day.at(backup_hour).do(backup_job, cipher, tipo_backup="seguranca")

    # Loop infinito para rodar o agendador
    # Este loop rodará no thread separado.
    while True:
        schedule.run_pending() # Executa jobs pendentes
        time.sleep(60) # Espera 60 segundos antes de verificar novamente


def backup_job(cipher, tipo_backup):
    """Função executada pelo agendador de backup."""
    # Esta função roda no thread agendado.
    # Não use st.* aqui. Use print() para debug no console.
    print(f"Executando job de backup agendado ({tipo_backup})...")
    try:
        # Chama a função de backup
        # Note que log_backup_action dentro de backup_data tenta usar st.session_state.username.
        # Isso pode causar um erro em um thread sem contexto Streamlit.
        # A função log_backup_action foi modificada para usar um fallback ('Sistema Agendado').
        backup_file = backup_data(cipher, tipo_backup=tipo_backup)
        if backup_file:
            print(f"Backup automático criado: {backup_file}")
            # Atualiza a data do último backup nas configurações (carrega, atualiza, salva)
            config = load_config()
            config["last_backup_date"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            save_config(config) # Salva a configuração atualizada
            # Mantém apenas os últimos N backups
            keep_last_backups("backups", 5) # Mantém 5 backups automáticos
        else:
            print("Falha ao criar o backup automático.")
    except Exception as e:
        print(f"Erro durante a execução do job de backup: {e}")


def keep_last_backups(BACKUP_DIR, num_backups):
    """Mantém apenas os últimos 'num_backups' arquivos no diretório de backups."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR) # Cria o diretório se não existir

    # Lista arquivos de backup (filtrando por extensão .bkp)
    backups = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".bkp")]

    # Ordena os arquivos pela data de modificação (do mais recente para o mais antigo)
    # Isso garante que os backups mais recentes sejam mantidos
    backups.sort(key=os.path.getmtime, reverse=True)

    # Remove os arquivos mais antigos se houver mais do que o número especificado para manter
    if len(backups) > num_backups:
        for backup_to_remove in backups[num_backups:]:
            try:
                os.remove(backup_to_remove)
                print(f"Backup removido por política de retenção: {backup_to_remove}")
            except Exception as e:
                print(f"Erro ao remover backup antigo: {backup_to_remove} - {e}")


# --- Função Principal da Aplicação Streamlit ---

def main():
    global KEY_FILE # Declaração global para usar a variável

    # Configurações iniciais da página Streamlit
    configure_page()
    initialize_session_state() # Inicializa/verifica o estado da sessão
    configure_locale() # Configura o locale


    # --- Inicializa as tabelas do banco de dados ---
    # Roda a função que cria tabelas se não existirem
    create_tables_if_not_exists()

    # Carrega configurações da aplicação (pode ser útil para temas, etc.)
    app_config = load_config()

    # Define os ícones do menu
    MENU_ICONS = define_menu_icons()

    # --- Configuração de Criptografia para Backups ---
    # Garante que a chave exista e inicializa o objeto cipher
    generate_key(KEY_FILE)
    cipher = initialize_cipher(KEY_FILE)

    # --- Controle de Scroll ---
    # Rola para o topo se a flag should_scroll_to_top estiver True
    if st.session_state.get('should_scroll_to_top', False):
        scroll_to_here(0, key='top_of_page') # Rola para a posição 0 (topo)
        st.session_state.should_scroll_to_top = False # Reseta a flag

    # --- Lógica de Autenticação ---
    if not st.session_state.get('authenticated', False):
        # Se não estiver autenticado, mostra a página de login e para a execução
        show_login_page()
        return # Sai da função main se não autenticado

    # Se autenticado, carrega o tipo e setores do usuário logado no estado da sessão
    # Isso foi movido para show_login_page após o login bem-sucedido.
    # Apenas garantimos que existam no state, com fallbacks.
    user_type = st.session_state.get('user_type', 'Visualizador')
    user_sectors = st.session_state.get('user_sectors', []) # Pega a lista de setores
    username = st.session_state.get('username', 'Desconhecido')

    # Estilização CSS customizada para o Streamlit
    st.markdown("""
    <style>
        /* Oculta elementos padrão do Streamlit */
        #MainMenu, header, footer {display: none;}
        /* Estilo do container principal */
        .main { background-color: #f8f9fa; padding: 1rem; }
        /* Oculta a toolbar padrão do Streamlit */
        [data-testid="stToolbar"] { display: none !important; }
         /* Remove borda do container da view */
        [data-testid="stAppViewContainer"] { border: none !important; }
        /* Oculta footer e MainMenu novamente por segurança */
        footer { display: none !important; }
        #MainMenu { visibility: hidden !important; }
        header { display: none !important; } /* Já oculto acima, redundante mas seguro */

        /* Estilo para os cards de conteúdo */
        .dashboard-card { background-color: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        /* Estilo para títulos */
        h1, h2, h3 { color: #1E88E5; }
        /* Estilo para a sidebar */
        section[data-testid="stSidebar"] { background-color: #f8f9fa; }
        /* Estilo para os botões na sidebar */
        section[data-testid="stSidebar"] button { width: 100%; border-radius: 5px; text-align: left; margin-bottom: 5px; height: 40px; padding: 0 15px; font-size: 14px; }
        /* Estilo para o botão ativo na sidebar */
        .active-button button { background-color: #e3f2fd !important; border-left: 3px solid #1E88E5 !important; color: #1E88E5 !important; font-weight: 500 !important; }
        /* Ajusta padding no topo da sidebar */
        section[data-testid="stSidebar"] > div:first-child { padding-top: 0; }
        /* Estilo para o container do perfil do usuário na sidebar */
        .user-profile { background-color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #e0e0e0; }
        /* Estilo para o footer da sidebar (fixo na parte inferior) */
        .sidebar-footer { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #f8f9fa; border-top: 1px solid #e0e0e0; padding: 10px; font-size: 12px; color: #666; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 Portal de Indicadores") # Título principal da página

    # --- Sidebar ---
    # Exibe a logo na sidebar se o arquivo existir
    if os.path.exists("logo.png"):
        st.sidebar.markdown(f"<div style='text-align: center;'>{img_to_html('logo.png')}</div>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<h1 style='text-align: center; font-size: 40px;'>📊</h1>", unsafe_allow_html=True) # Fallback com emoji grande

    st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True) # Separador

    # Container do perfil do usuário na sidebar
    with st.sidebar.container():
        col1, col2 = st.columns([3, 1]) # Duas colunas para nome/tipo e botão logout
        with col1:
            # Exibe nome de usuário, tipo e setores (se aplicável)
            # Prepara a string de setores para exibição
            sectors_display = ", ".join(user_sectors) if user_sectors and user_type == "Operador" else "Todos" if user_type != "Operador" else "Nenhum setor"

            st.markdown(f"""
            <div style="background-color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #e0e0e0;">
                <p style="margin:0; font-weight:bold;">{username}</p>
                <p style="margin:0; font-size:12px; color:#666;">{user_type}</p>
                {'<p style="margin:0; font-size:12px; color:#666;">Setores: ' + sectors_display + '</p>' if user_type == "Operador" or sectors_display == "Todos" else ''} {/* FIX: Removido as chaves externas {} */}
            </div>
            """, unsafe_allow_html=True)
        with col2:
            # Botão de logout
            if st.button("🚪", help="Fazer logout"):
                logout() # Chama a função de logout

    # Define os itens do menu baseados no tipo de usuário
    if user_type == "Administrador":
        menu_items = ["Dashboard", "Criar Indicador", "Editar Indicador", "Preencher Indicador", "Visão Geral", "Configurações", "Gerenciar Usuários"]
    elif user_type == "Operador":
        # Operadores não podem criar/editar/gerenciar usuários/configurações
        menu_items = ["Dashboard", "Preencher Indicador", "Visão Geral"]
        # Se a página atual não for permitida para Operador, redireciona para Dashboard
        if st.session_state.get('page') not in menu_items:
             st.session_state.page = "Dashboard"
             st.rerun() # Reroda para ir para a página permitida
    else: # Visualizador
        # Visualizadores só podem ver Dashboard e Visão Geral
        menu_items = ["Dashboard", "Visão Geral"]
        # Se a página atual não for permitida para Visualizador, redireciona para Dashboard
        if st.session_state.get('page') not in menu_items:
             st.session_state.page = "Dashboard"
             st.rerun() # Reroda para ir para a página permitida


    # Controla a página atual no estado da sessão (inicia no Dashboard se não definida)
    if 'page' not in st.session_state:
        st.session_state.page = "Dashboard"

    # Cria os botões de navegação na sidebar
    for item in menu_items:
        icon = MENU_ICONS.get(item, "📋") # Pega o ícone definido, fallback para um padrão
        is_active = st.session_state.page == item # Verifica se é a página atual
        active_class = "active-button" if is_active else "" # Adiciona classe CSS se ativo

        # Cria o botão usando markdown para aplicar a classe CSS customizada
        st.sidebar.markdown(f'<div class="{active_class}">', unsafe_allow_html=True)
        if st.sidebar.button(f"{icon} {item}", key=f"menu_{item}"): # Chave única para o botão
            st.session_state.page = item # Atualiza a página no estado da sessão
            scroll_to_top() # Rola para o topo ao mudar de página
            st.rerun() # Reinicia a aplicação para renderizar a nova página
        st.sidebar.markdown('</div>', unsafe_allow_html=True)

    # Footer da sidebar
    st.sidebar.markdown("""
    <div class="sidebar-footer">
        <p style="margin:0;">Portal de Indicadores v1.4.0</p> {/* Versão atualizada */}
        <p style="margin:3px 0 0 0;">© 2025 Todos os direitos reservados</p>
        <p style="margin:0; font-size:10px;">Desenvolvido por FIA Softworks</p>
    </div>
    """, unsafe_allow_html=True)

    # --- Conteúdo Principal (Renderiza a página selecionada) ---
    # Cada função de página agora verifica as permissões internamente, mas a sidebar já restringe.
    if st.session_state.page == "Dashboard":
        show_dashboard(SETORES, TEMA_PADRAO)
    elif st.session_state.page == "Criar Indicador":
        # Verifica permissão adicional aqui, caso o usuário tente acessar via URL ou manipulação de estado
        if user_type == "Administrador":
            create_indicator(SETORES, TIPOS_GRAFICOS)
        else:
            st.error("Você não tem permissão para acessar esta página.") # Mensagem de error se sem permissão
            st.session_state.page = "Dashboard" # Redireciona
            st.rerun()
    elif st.session_state.page == "Editar Indicador":
        # Verifica permissão
        if user_type == "Administrador":
            edit_indicator(SETORES, TIPOS_GRAFICOS)
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.session_state.page = "Dashboard"
            st.rerun()
    elif st.session_state.page == "Preencher Indicador":
         # Verifica permissão (Admin ou Operador)
        if user_type in ["Administrador", "Operador"]:
            fill_indicator(SETORES, TEMA_PADRAO)
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.session_state.page = "Dashboard"
            st.rerun()
    elif st.session_state.page == "Visão Geral":
        # Visualizadores e Operadores podem acessar, Admin também
        show_overview()
    elif st.session_state.page == "Configurações":
        # Verifica permissão (apenas Admin)
        if user_type == "Administrador":
            show_settings()
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.session_state.page = "Dashboard"
            st.rerun()
    elif st.session_state.page == "Gerenciar Usuários":
         # Verifica permissão (apenas Admin)
        if user_type == "Administrador":
            show_user_management(SETORES)
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.session_state.page = "Dashboard"
            st.rerun()


    # --- Agendamento de Backup (Thread) ---
    # Inicia o thread de agendamento de backup se ele ainda não estiver rodando
    # Verifica se o thread já existe no estado da sessão e se está ativo
    if 'backup_thread' not in st.session_state or not st.session_state.backup_thread.is_alive():
        # Garante que o cipher está inicializado antes de passar para o thread
        if cipher is None:
             generate_key(KEY_FILE)
             cipher = initialize_cipher(KEY_FILE)

        # Inicia o thread, passando o cipher e configurando como daemon (encerra com a aplicação principal)
        if cipher: # Só inicia se o cipher foi inicializado com sucesso
             backup_thread = threading.Thread(target=agendar_backup, args=(cipher,))
             backup_thread.daemon = True # Garante que o thread não impeça o encerramento da aplicação
             backup_thread.start()
             st.session_state.backup_thread = backup_thread # Salva o thread no estado da sessão para verificações futuras
             print("Thread de backup agendado iniciado.") # Log no console
        else:
             print("Não foi possível inicializar o cipher. Agendamento de backup NÃO iniciado.") # Log no console


# Ponto de entrada da aplicação Streamlit
if __name__ == "__main__":
    main() # Chama a função principal para rodar a aplicação
